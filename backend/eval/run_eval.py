"""Offline evaluation of retrieval, citations, abstention, intent accuracy and latency.

Usage (from backend/):  python -m eval.run_eval [--embedding hashing|sentence_transformers] [--llm demo|configured]

Runs against an isolated temporary database and in-memory Qdrant seeded with the demo corpus,
so results are reproducible and never touch your local data. Writes eval/results/<timestamp>.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.db.migrate import upgrade_head_async
from app.db.session import init_engine, session_factory
from app.llm.base import DemoLLM
from app.nlp.pipeline import analyze
from app.rag.answer import GroundedAnswer, generate_answer
from app.rag.embeddings import build_embedder
from app.services.container import build_container
from app.services.knowledge_service import seed_demo_corpus

HERE = Path(__file__).parent


def slug_of(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


async def main(embedding: str, use_configured_llm: bool, top_k: int) -> dict:
    data = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="yatra-eval-"))
    settings = Settings(_env_file=None if not use_configured_llm else Settings.model_config["env_file"],
                        database_url=f"sqlite+aiosqlite:///{(tmp / 'eval.db').as_posix()}", qdrant_url=None,
                        qdrant_path=":memory:", embedding_backend=embedding, seed_demo_data=True,
                        **({} if use_configured_llm else {"llm_provider": "demo"}))
    await upgrade_head_async(settings.database_url)
    init_engine(settings.database_url)
    embedder = build_embedder(settings.embedding_backend, settings.embedding_model, settings.hashing_dim)
    c = build_container(settings, session_factory(), embedder=embedder,
                        llm=None if use_configured_llm else DemoLLM())
    await c.store.ensure_collection()
    await seed_demo_corpus(c)

    hits_at_1 = hits_at_k = 0
    rr: list[float] = []
    answerable = [q for q in data["qa"] if q["expected_doc"]]
    unanswerable = [q for q in data["qa"] if not q["expected_doc"]]
    cite_correct = cite_any = contains_ok = declined_ok = false_decline = 0
    retrieval_ms: list[float] = []
    answer_ms: list[float] = []
    per_question = []

    for item in data["qa"]:
        t0 = time.perf_counter()
        chunks = await c.retriever.retrieve(item["q"], top_k=top_k)
        retrieval_ms.append((time.perf_counter() - t0) * 1000)
        ranked_docs = list(dict.fromkeys(slug_of(ch.url) for ch in chunks))
        t1 = time.perf_counter()
        final: GroundedAnswer | None = None
        async for out in generate_answer(item["q"], chunks, [], "en", c.llm, max_tokens=800):
            if isinstance(out, GroundedAnswer):
                final = out
        answer_ms.append((time.perf_counter() - t1) * 1000)
        assert final is not None
        cited = [slug_of(ci.url) for ci in final.citations]
        row = {"q": item["q"], "expected": item["expected_doc"], "retrieved": ranked_docs[:3], "cited": cited,
               "evidence": final.evidence, "answer": final.text[:300]}
        if item["expected_doc"]:
            exp = item["expected_doc"]
            if ranked_docs[:1] == [exp]:
                hits_at_1 += 1
            if exp in ranked_docs:
                hits_at_k += 1
                rr.append(1 / (ranked_docs.index(exp) + 1))
            else:
                rr.append(0.0)
            if cited:
                cite_any += 1
                cite_correct += all(s == exp for s in cited)
            else:
                false_decline += 1
            contains_ok += item.get("must_contain", "").lower() in final.text.lower()
        else:
            declined_ok += final.evidence == "none" and not cited
        per_question.append(row)

    # Hindi/Gujarati questions over the English corpus, using the same query expansion as chat
    # (recognised destinations are appended by their canonical English name).
    xl_ok = 0
    for item in data.get("crosslingual", []):
        e = analyze(item["q"]).entities
        query = item["q"]
        for name in [e.destination, *e.destinations]:
            if name and name.lower() not in query.lower():
                query = f"{query} {name}"
        chunks = await c.retriever.retrieve(query, top_k=top_k)
        async for out in generate_answer(query, chunks, [], item["lang"], c.llm, max_tokens=800,
                                         cross_lingual=c.embedder.name.startswith("st-")):
            if isinstance(out, GroundedAnswer):
                xl_ok += bool(out.citations) and all(slug_of(ci.url) == item["expected_doc"] for ci in out.citations)

    intent_rows = [(r["text"], r["intent"], analyze(r["text"]).intent.value) for r in data["intents"]]
    intent_correct = sum(1 for _, exp, got in intent_rows if exp == got)

    result = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "embedder": c.embedder.name, "llm": f"{c.llm.name}:{c.llm.model}", "top_k": top_k,
        "retrieval": {"questions": len(answerable), "hit_at_1_pct": pct(hits_at_1, len(answerable)),
                      f"recall_at_{top_k}_pct": pct(hits_at_k, len(answerable)),
                      "mrr": round(statistics.mean(rr), 3) if rr else 0.0},
        "citations": {"answered_pct": pct(cite_any, len(answerable)),
                      "all_citations_correct_doc_pct_of_answered": pct(cite_correct, cite_any),
                      "answer_contains_expected_fact_pct": pct(contains_ok, len(answerable)),
                      "false_declines": false_decline},
        "abstention": {"unanswerable_questions": len(unanswerable),
                       "correctly_declined_pct": pct(declined_ok, len(unanswerable))},
        "crosslingual": {"questions": len(data.get("crosslingual", [])),
                         "answered_with_correct_citations_pct": pct(xl_ok, len(data.get("crosslingual", [])))},
        "intent": {"examples": len(intent_rows), "accuracy_pct": pct(intent_correct, len(intent_rows)),
                   "errors": [{"text": t, "expected": e, "got": g} for t, e, g in intent_rows if e != g]},
        "latency_ms": {"retrieval_p50": round(statistics.median(retrieval_ms), 1),
                       "retrieval_max": round(max(retrieval_ms), 1),
                       "answer_p50": round(statistics.median(answer_ms), 1),
                       "answer_max": round(max(answer_ms), 1)},
        "per_question": per_question,
    }
    await c.close()
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    (out_dir / f"{stamp}-{c.embedder.name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                                             encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding", default="hashing", choices=["hashing", "sentence_transformers"])
    parser.add_argument("--llm", default="demo", choices=["demo", "configured"],
                        help="'configured' uses LLM settings from .env (costs money for paid APIs)")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    res = asyncio.run(main(args.embedding, args.llm == "configured", args.top_k))
    summary = {k: v for k, v in res.items() if k != "per_question"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
