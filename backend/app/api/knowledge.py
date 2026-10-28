from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.db.models import Document, IngestionJob, Source
from app.db.session import get_session
from app.services import knowledge_service as ks
from app.services.container import Container, get_container

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
ingest_limit = rate_limit("ingest", lambda: get_settings().rate_limit_ingest_per_hour, 3600)


class SourceCreate(BaseModel):
    url: str = Field(min_length=4, max_length=2048, examples=["https://www.incredibleindia.gov.in/"])
    max_pages: int = Field(default=10, ge=1, le=200)
    max_depth: int = Field(default=1, ge=0, le=5)
    start_ingestion: bool = True


class JobOut(BaseModel):
    id: str
    source_id: str
    status: str
    pages_discovered: int
    pages_fetched: int
    pages_indexed: int
    pages_unchanged: int
    pages_skipped: int
    pages_failed: int
    chunks_indexed: int
    errors: list[dict]
    message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SourceOut(BaseModel):
    id: str
    url: str
    domain: str
    title: str | None
    status: str
    is_demo: bool
    max_pages: int
    max_depth: int
    page_count: int
    chunk_count: int
    last_error: str | None
    last_ingested_at: datetime | None
    created_at: datetime
    latest_job: JobOut | None = None


class DocumentOut(BaseModel):
    id: str
    url: str
    title: str
    fetched_at: datetime
    published_at: str | None


class SourceDetail(SourceOut):
    documents: list[DocumentOut]


class DemoDoc(BaseModel):
    slug: str
    title: str
    url: str


class DemoDocContent(DemoDoc):
    body: str


def _job(j: IngestionJob) -> JobOut:
    return JobOut.model_validate(j, from_attributes=True)


async def _latest_job(session: AsyncSession, source_id: str) -> IngestionJob | None:
    return (await session.execute(select(IngestionJob).where(IngestionJob.source_id == source_id)
                                  .order_by(IngestionJob.created_at.desc()).limit(1))).scalar_one_or_none()


async def _source_out(session: AsyncSession, s: Source) -> SourceOut:
    out = SourceOut.model_validate(s, from_attributes=True)
    job = await _latest_job(session, s.id)
    out.latest_job = _job(job) if job else None
    return out


@router.post("/sources", response_model=SourceOut, status_code=201, dependencies=[Depends(ingest_limit)],
             summary="Register a public website and (by default) start crawling it")
async def create_source(body: SourceCreate, c: Container = Depends(get_container),
                        session: AsyncSession = Depends(get_session)) -> SourceOut:
    source = await ks.register_source(c, session, body.url, max_pages=body.max_pages, max_depth=body.max_depth)
    if body.start_ingestion:
        await ks.start_ingestion(c, session, source.id)
        await session.refresh(source)
    return await _source_out(session, source)


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[SourceOut]:
    rows = (await session.execute(select(Source).order_by(Source.is_demo.desc(), Source.created_at.desc()))).scalars()
    return [await _source_out(session, s) for s in rows]


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(source_id: str, session: AsyncSession = Depends(get_session)) -> SourceDetail:
    source = await session.get(Source, source_id)
    if source is None:
        raise NotFoundError("Source not found.")
    docs = (await session.execute(select(Document).where(Document.source_id == source_id)
                                  .order_by(Document.url).limit(500))).scalars()
    base = await _source_out(session, source)
    return SourceDetail(**base.model_dump(), documents=[DocumentOut.model_validate(d, from_attributes=True)
                                                       for d in docs])


@router.post("/sources/{source_id}/ingest", response_model=JobOut, status_code=202,
             dependencies=[Depends(ingest_limit)],
             summary="Start or retry ingestion (re-crawls; unchanged pages are skipped)")
async def ingest_source(source_id: str, c: Container = Depends(get_container),
                        session: AsyncSession = Depends(get_session)) -> JobOut:
    return _job(await ks.start_ingestion(c, session, source_id))


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobOut:
    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return _job(job)


@router.delete("/sources/{source_id}", status_code=204, response_class=Response,
               summary="Remove a source and all of its indexed content")
async def delete_source(source_id: str, c: Container = Depends(get_container),
                        session: AsyncSession = Depends(get_session)) -> Response:
    await ks.delete_source(c, session, source_id)
    return Response(status_code=204)


@router.get("/demo", response_model=list[DemoDoc], summary="List bundled demo articles")
async def demo_docs() -> list[DemoDoc]:
    return [DemoDoc(slug=d["slug"], title=d["title"], url=d["url"]) for d in ks.demo_documents()]


@router.get("/demo/{slug}", response_model=DemoDocContent)
async def demo_doc(slug: str) -> DemoDocContent:
    for d in ks.demo_documents():
        if d["slug"] == slug:
            return DemoDocContent(slug=d["slug"], title=d["title"], url=d["url"], body=d["body"])
    raise NotFoundError("Demo article not found.")


@router.get("/stats", summary="Counts of indexed sources, pages and chunks")
async def stats(session: AsyncSession = Depends(get_session)) -> dict:
    from app.db.models import Chunk

    return {
        "sources": (await session.execute(select(func.count(Source.id)))).scalar_one(),
        "documents": (await session.execute(select(func.count(Document.id)))).scalar_one(),
        "chunks": (await session.execute(select(func.count(Chunk.id)))).scalar_one(),
    }
