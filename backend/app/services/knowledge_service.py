"""Knowledge sources: registration, crawling/ingestion jobs, indexing, deletion and demo seeding."""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnsafeURLError
from app.core.logging import get_logger
from app.db.models import Chunk, Document, IngestionJob, Source
from app.ingestion.extractor import extract, is_crawlable_link
from app.ingestion.fetcher import TEXT_TYPES, FetchError
from app.ingestion.robots import load_robots
from app.ingestion.url_safety import normalize_url, same_site, validate_public_url
from app.rag.chunking import chunk_text
from app.services.container import Container

log = get_logger(__name__)
DEMO_SOURCE_URL = "demo://yatra-travel-guide"
DEMO_DIR = Path(__file__).resolve().parents[1] / "demo" / "corpus"
MAX_ERRORS_STORED = 50
ACTIVE_JOB_STATES = ("queued", "running")


def content_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- indexing primitives
async def index_document(c: Container, session: AsyncSession, *, source: Source, url: str, title: str, text: str,
                         description: str | None = None, language: str | None = None,
                         published_at: str | None = None) -> tuple[str, int]:
    """Create/update one document. Returns (status, n_chunks) where status is 'indexed' or 'unchanged'."""
    digest = content_hash(text)
    doc = (await session.execute(
        select(Document).where(Document.source_id == source.id, Document.url == url))).scalar_one_or_none()
    if doc and doc.content_hash == digest:
        doc.fetched_at = datetime.now(UTC)
        return "unchanged", 0
    if doc is None:
        doc = Document(source_id=source.id, url=url, title=title[:500], content_hash=digest, is_demo=source.is_demo)
        session.add(doc)
        await session.flush()
    else:
        # Content changed: replace its chunks rather than accumulating duplicates.
        await c.store.delete_by("document_id", doc.id)
        await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        doc.content_hash = digest
        doc.title = title[:500]
    doc.description, doc.language, doc.published_at = description, language, published_at
    doc.fetched_at = datetime.now(UTC)

    pieces = chunk_text(text, size=c.settings.chunk_size, overlap=c.settings.chunk_overlap)
    if not pieces:
        return "indexed", 0
    ids = [str(uuid.uuid4()) for _ in pieces]
    vectors = await c.embedder.embed_documents(
        [f"{title}\n{p.heading or ''}\n{p.text}" for p in pieces])
    payloads = [{"chunk_id": i, "document_id": doc.id, "source_id": source.id, "url": url, "title": title,
                 "heading": p.heading, "is_demo": source.is_demo} for i, p in zip(ids, pieces, strict=True)]
    session.add_all([Chunk(id=i, document_id=doc.id, source_id=source.id, ordinal=p.ordinal, heading=p.heading,
                           text=p.text) for i, p in zip(ids, pieces, strict=True)])
    await c.store.upsert(ids, vectors, payloads)
    return "indexed", len(pieces)


async def refresh_source_counts(session: AsyncSession, source: Source) -> None:
    source.page_count = (await session.execute(
        select(func.count(Document.id)).where(Document.source_id == source.id))).scalar_one()
    source.chunk_count = (await session.execute(
        select(func.count(Chunk.id)).where(Chunk.source_id == source.id))).scalar_one()


# ---------------------------------------------------------------- sources
async def register_source(c: Container, session: AsyncSession, url: str, *, max_pages: int, max_depth: int) -> Source:
    normalized = normalize_url(url)
    # Validate resolution up-front so obviously unsafe URLs are rejected immediately.
    await validate_public_url(normalized, resolver=c.resolver, allow_private=c.settings.crawl_allow_private_networks)
    existing = (await session.execute(select(Source).where(Source.url == normalized))).scalar_one_or_none()
    if existing:
        raise ConflictError("This website is already registered.", details={"source_id": existing.id})
    source = Source(url=normalized, domain=urlsplit(normalized).hostname or "", status="pending",
                    max_pages=min(max_pages, c.settings.crawl_max_pages),
                    max_depth=min(max_depth, c.settings.crawl_max_depth))
    session.add(source)
    await session.commit()
    return source


async def start_ingestion(c: Container, session: AsyncSession, source_id: str) -> IngestionJob:
    source = await session.get(Source, source_id)
    if source is None:
        raise NotFoundError("Source not found.")
    if source.is_demo:
        raise ConflictError("The demo knowledge base is bundled with the app and cannot be re-crawled.")
    active = (await session.execute(select(IngestionJob).where(
        IngestionJob.source_id == source_id, IngestionJob.status.in_(ACTIVE_JOB_STATES)))).scalar_one_or_none()
    if active:
        raise ConflictError("An ingestion job is already running for this source.", details={"job_id": active.id})
    job = IngestionJob(source_id=source_id, status="queued", errors=[])
    source.status = "running"
    session.add(job)
    await session.commit()
    c.spawn(run_ingestion_job(c, job.id))
    return job


async def delete_source(c: Container, session: AsyncSession, source_id: str) -> None:
    source = await session.get(Source, source_id)
    if source is None:
        raise NotFoundError("Source not found.")
    await c.store.delete_by("source_id", source_id)
    await session.delete(source)
    await session.commit()
    c.corpus_version.bump()


# ---------------------------------------------------------------- crawling
@dataclass
class _Progress:
    job_id: str

    async def update(self, c: Container, **fields: object) -> None:
        async with c.sessions() as s:
            await s.execute(update(IngestionJob).where(IngestionJob.id == self.job_id).values(**fields))
            await s.commit()


async def run_ingestion_job(c: Container, job_id: str) -> None:
    progress = _Progress(job_id)
    async with c.sessions() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return
        source = await session.get(Source, job.source_id)
        if source is None:
            return
        start_url, source_id = source.url, source.id
        max_pages, max_depth = source.max_pages, source.max_depth
    await progress.update(c, status="running", started_at=datetime.now(UTC))

    counters = {"pages_discovered": 1, "pages_fetched": 0, "pages_indexed": 0, "pages_unchanged": 0,
                "pages_skipped": 0, "pages_failed": 0, "chunks_indexed": 0}
    errors: list[dict[str, str]] = []
    seen_urls: set[str] = {start_url}
    seen_canonical: set[str] = set()
    seen_hashes: set[str] = set()
    root_host = urlsplit(start_url).hostname or ""
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    truncated = False
    fatal: str | None = None

    def record_error(url: str, reason: str) -> None:
        counters["pages_failed"] += 1
        if len(errors) < MAX_ERRORS_STORED:
            errors.append({"url": url, "reason": reason})

    fetcher = c.fetcher_factory()
    try:
        robots = await load_robots(fetcher, start_url)
        if robots.disallow_all:
            fatal = "The site's robots.txt (or its unavailability) does not allow crawling."
        delay = max(c.settings.crawl_delay_seconds, min(robots.crawl_delay() or 0.0, 5.0))
        while queue and not fatal:
            if counters["pages_fetched"] >= max_pages:
                truncated = True
                break
            url, depth = queue.popleft()
            if not robots.allowed(url):
                counters["pages_skipped"] += 1
                if len(errors) < MAX_ERRORS_STORED:
                    errors.append({"url": url, "reason": "Disallowed by robots.txt — skipped."})
                continue
            try:
                result = await fetcher.fetch(url)
            except FetchError as exc:
                record_error(url, str(exc))
                continue
            counters["pages_fetched"] += 1
            if not same_site(result.url, root_host):
                counters["pages_skipped"] += 1
                continue

            if result.content_type.startswith(TEXT_TYPES):
                page_title, text, canonical, links = url.rsplit("/", 1)[-1] or url, result.text, result.url, []
                meta = {"description": None, "language": None, "published_at": None}
                noindex = nofollow = False
            else:
                page = extract(result.text, result.url)
                page_title, text, links = page.title, page.text, page.links
                canonical = page.canonical_url if page.canonical_url and same_site(page.canonical_url, root_host) \
                    else result.url
                meta = {"description": page.description, "language": page.language,
                        "published_at": page.published_at}
                noindex, nofollow = page.noindex, page.nofollow

            if not nofollow and depth < max_depth:
                for link in links:
                    if link not in seen_urls and same_site(link, root_host) and is_crawlable_link(link):
                        seen_urls.add(link)
                        queue.append((link, depth + 1))
                counters["pages_discovered"] = len(seen_urls)

            digest = content_hash(text)
            if noindex:
                counters["pages_skipped"] += 1
            elif len(text) < 200:
                counters["pages_skipped"] += 1
                if len(errors) < MAX_ERRORS_STORED:
                    errors.append({"url": url, "reason": "Too little readable text — skipped."})
            elif canonical in seen_canonical or digest in seen_hashes:
                counters["pages_skipped"] += 1  # duplicate of a page already indexed in this run
            else:
                seen_canonical.add(canonical)
                seen_hashes.add(digest)
                try:
                    async with c.sessions() as session:
                        source = await session.get(Source, source_id)
                        if source is None:
                            fatal = "The source was deleted during ingestion."
                            break
                        status, n = await index_document(c, session, source=source, url=canonical,
                                                         title=page_title, text=text, **meta)
                        await session.commit()
                    c.corpus_version.bump()
                    if status == "unchanged":
                        counters["pages_unchanged"] += 1
                    else:
                        counters["pages_indexed"] += 1
                        counters["chunks_indexed"] += n
                except Exception:  # embedding / vector store failure for this page
                    log.exception("indexing failed for a page")
                    record_error(url, "The page was fetched but could not be indexed.")
            await progress.update(c, **counters, errors=list(errors))
            if queue and delay:
                await asyncio.sleep(delay)
    except asyncio.CancelledError:
        fatal = "Ingestion was cancelled (server shutting down). Retry to resume."
        raise
    except UnsafeURLError as exc:
        fatal = exc.message
    except Exception:
        log.exception("ingestion job crashed")
        fatal = "Ingestion stopped because of an unexpected error. You can retry."
    finally:
        await fetcher.aclose()
        ok_pages = counters["pages_indexed"] + counters["pages_unchanged"]
        if fatal:
            status = "failed" if ok_pages == 0 else "partial"
        elif ok_pages == 0:
            status = "failed"
            fatal = "No indexable pages were found."
        elif counters["pages_failed"]:
            status = "partial"
        else:
            status = "succeeded"
        message = fatal or (f"Indexed {counters['pages_indexed']} new/changed page(s), "
                            f"{counters['pages_unchanged']} unchanged.")
        if truncated:
            message += f" Stopped at the page limit ({max_pages})."
        try:
            async with c.sessions() as session:
                source = await session.get(Source, source_id)
                if source is not None:
                    # Pages that disappeared from a complete, error-free crawl are removed from the index.
                    if status == "succeeded" and not truncated:
                        stale = (await session.execute(select(Document).where(
                            Document.source_id == source_id, Document.url.not_in(seen_canonical)))).scalars().all()
                        for doc in stale:
                            await c.store.delete_by("document_id", doc.id)
                            await session.delete(doc)
                    await session.flush()
                    await refresh_source_counts(session, source)
                    source.status = {"succeeded": "ready", "partial": "partial", "failed": "failed"}[status] \
                        if source.page_count or status == "failed" else "failed"
                    source.last_error = fatal
                    source.last_ingested_at = datetime.now(UTC)
                    if not source.title and seen_canonical:
                        first = (await session.execute(select(Document.title).where(
                            Document.source_id == source_id).limit(1))).scalar_one_or_none()
                        source.title = first
                await session.execute(update(IngestionJob).where(IngestionJob.id == job_id).values(
                    status=status, message=message, finished_at=datetime.now(UTC), errors=list(errors),
                    **counters))
                await session.commit()
            c.corpus_version.bump()
        except Exception:
            log.exception("failed to finalize ingestion job")


async def fail_interrupted_jobs(c: Container) -> None:
    """Jobs left queued/running by a previous process cannot resume; mark them retryable."""
    async with c.sessions() as session:
        await session.execute(update(IngestionJob).where(IngestionJob.status.in_(ACTIVE_JOB_STATES)).values(
            status="failed", message="Interrupted by a server restart. Retry to resume.",
            finished_at=datetime.now(UTC)))
        await session.execute(update(Source).where(Source.status == "running").values(
            status="failed", last_error="Interrupted by a server restart. Retry to resume."))
        await session.commit()


# ---------------------------------------------------------------- demo corpus
def parse_demo_doc(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---"):
        _, header, body = raw.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body.strip()


def demo_documents() -> list[dict[str, str]]:
    docs = []
    for path in sorted(DEMO_DIR.glob("*.md")):
        meta, body = parse_demo_doc(path)
        slug = meta.get("slug") or path.stem
        docs.append({"slug": slug, "title": meta.get("title", slug), "body": body,
                     "url": f"/knowledge/demo/{slug}"})
    return docs


async def seed_demo_corpus(c: Container) -> int:
    """Idempotently (re)index the bundled demo articles. Returns number of pages (re)indexed."""
    async with c.sessions() as session:
        source = (await session.execute(select(Source).where(Source.url == DEMO_SOURCE_URL))).scalar_one_or_none()
        if source is None:
            source = Source(url=DEMO_SOURCE_URL, domain="demo", title="YatraAI demo travel guide (sample content)",
                            status="ready", is_demo=True, max_pages=0, max_depth=0)
            session.add(source)
            await session.flush()
        indexed = 0
        urls = []
        for d in demo_documents():
            # The blockquote disclaimer is shown on the article page; the document itself is flagged
            # is_demo, so the disclaimer is not indexed as retrievable "content".
            text = re.sub(r"^>.*$", "", d["body"], flags=re.MULTILINE).strip()
            status, _ = await index_document(c, session, source=source, url=d["url"], title=d["title"], text=text,
                                             language="en", published_at="2026-10")
            urls.append(d["url"])
            indexed += status == "indexed"
        stale = (await session.execute(select(Document).where(Document.source_id == source.id,
                                                              Document.url.not_in(urls)))).scalars().all()
        for doc in stale:
            await c.store.delete_by("document_id", doc.id)
            await session.delete(doc)
        await session.flush()
        await refresh_source_counts(session, source)
        source.status = "ready"
        source.last_ingested_at = datetime.now(UTC)
        await session.commit()
    c.corpus_version.bump()
    return indexed


async def reindex_vectors_if_missing(c: Container) -> int:
    """If the vector collection is empty but chunks exist (new embedder, wiped Qdrant), rebuild vectors from DB."""
    await c.store.ensure_collection()
    if await c.store.count() > 0:
        return 0
    async with c.sessions() as session:
        rows = (await session.execute(
            select(Chunk, Document.url, Document.title, Source.is_demo)
            .join(Document, Chunk.document_id == Document.id).join(Source, Document.source_id == Source.id)
        )).all()
    for start in range(0, len(rows), 64):
        batch = rows[start:start + 64]
        vectors = await c.embedder.embed_documents(
            [f"{title}\n{ch.heading or ''}\n{ch.text}" for ch, _url, title, _demo in batch])
        await c.store.upsert(
            [ch.id for ch, *_ in batch], vectors,
            [{"chunk_id": ch.id, "document_id": ch.document_id, "source_id": ch.source_id, "url": url,
              "title": title, "heading": ch.heading, "is_demo": bool(demo)} for ch, url, title, demo in batch])
    if rows:
        log.info("re-embedded %d chunks into %s", len(rows), c.store.collection)
    return len(rows)
