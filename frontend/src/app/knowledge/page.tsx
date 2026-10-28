"use client";

import { BookOpen, Database, ExternalLink, Globe, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, EmptyState, inputClass, Notice, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, safeHref } from "@/lib/format";
import type { DemoDoc, SourceOut } from "@/lib/types";

const STATUS: Record<SourceOut["status"], { tone: "neutral" | "primary" | "success" | "warning" | "danger"; label: string }> = {
  pending: { tone: "neutral", label: "Pending" },
  running: { tone: "primary", label: "Indexing…" },
  ready: { tone: "success", label: "Ready" },
  partial: { tone: "warning", label: "Partially indexed" },
  failed: { tone: "danger", label: "Failed" },
};

function SourceRow({ s, onIngest, onDelete }: { s: SourceOut; onIngest: () => void; onDelete: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const job = s.latest_job;
  const running = s.status === "running" || job?.status === "queued" || job?.status === "running";
  const href = safeHref(s.url);
  return (
    <li className="space-y-2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-medium">
            <Globe className="h-4 w-4 shrink-0 text-primary" aria-hidden />
            <span className="truncate">{s.title || s.domain}</span>
          </p>
          {href && <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-xs text-muted hover:underline">{s.url}<ExternalLink className="h-3 w-3" aria-hidden /></a>}
        </div>
        <div className="flex items-center gap-1">
          <Badge tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Badge>
          <Button size="sm" variant="secondary" disabled={running} onClick={onIngest} aria-label={`Re-index ${s.domain}`}>
            <RefreshCw className={`h-4 w-4 ${running ? "animate-spin" : ""}`} aria-hidden />{s.status === "failed" ? "Retry" : "Re-index"}
          </Button>
          {confirm ? (
            <>
              <Button size="sm" variant="danger" onClick={onDelete}>Confirm delete</Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button>
            </>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirm(true)} aria-label={`Delete ${s.domain}`}><Trash2 className="h-4 w-4" aria-hidden /></Button>
          )}
        </div>
      </div>
      <p className="text-xs text-muted">
        {s.page_count} page(s) · {s.chunk_count} passages · limits {s.max_pages} pages, depth {s.max_depth}
        {s.last_ingested_at ? ` · last indexed ${formatDate(s.last_ingested_at)}` : ""}
      </p>
      {job && (
        <div className="rounded-lg bg-surface-muted p-2 text-xs">
          <p>
            Last job: <strong>{job.status}</strong> — fetched {job.pages_fetched}, indexed {job.pages_indexed}, unchanged {job.pages_unchanged},
            skipped {job.pages_skipped}, failed {job.pages_failed} (discovered {job.pages_discovered})
          </p>
          {running && <progress className="mt-1 h-1.5 w-full" max={Math.max(s.max_pages, 1)} value={job.pages_fetched} aria-label="Crawl progress" />}
          {job.message && <p className="mt-1 text-muted">{job.message}</p>}
          {job.errors.length > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer">Page issues ({job.errors.length})</summary>
              <ul className="mt-1 space-y-0.5">{job.errors.map((e, i) => <li key={i} className="break-all"><span className="text-muted">{e.url}</span> — {e.reason}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </li>
  );
}

export default function KnowledgePage() {
  const [sources, setSources] = useState<SourceOut[]>([]);
  const [docs, setDocs] = useState<DemoDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState(10);
  const [maxDepth, setMaxDepth] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api<SourceOut[]>("/api/knowledge/sources"), api<DemoDoc[]>("/api/knowledge/demo")]);
      setSources(s);
      setDocs(d);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  // Poll while any ingestion is in progress.
  const active = sources.some((s) => s.status === "running" || s.latest_job?.status === "running" || s.latest_job?.status === "queued");
  useEffect(() => {
    if (!active) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [active, load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await api("/api/knowledge/sources", { method: "POST", body: JSON.stringify({ url, max_pages: maxPages, max_depth: maxDepth }) });
      setUrl("");
      await load();
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const demo = sources.find((s) => s.is_demo);
  const web = sources.filter((s) => !s.is_demo);

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      <header>
        <h1 className="font-display text-2xl font-semibold">Knowledge sources</h1>
        <p className="text-sm text-muted">Index public websites so YatraAI can answer from them, with citations.</p>
      </header>

      <Card className="p-4">
        <h2 className="mb-2 font-medium">Add a website</h2>
        <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_7rem_7rem_auto]">
          <div>
            <label htmlFor="url" className="sr-only">Website URL</label>
            <input id="url" required className={inputClass} placeholder="https://example.gov.in/travel-guide" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div>
            <label htmlFor="pages" className="sr-only">Maximum pages</label>
            <select id="pages" className={inputClass} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))}>
              {[1, 5, 10, 25].map((n) => <option key={n} value={n}>{n} page{n > 1 ? "s" : ""}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="depth" className="sr-only">Link depth</label>
            <select id="depth" className={inputClass} value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))}>
              {[0, 1, 2].map((n) => <option key={n} value={n}>Depth {n}</option>)}
            </select>
          </div>
          <Button type="submit" disabled={submitting || !url.trim()}>{submitting ? "Adding…" : "Add & index"}</Button>
        </form>
        {formError && <div className="mt-2"><Notice tone="error">{formError}</Notice></div>}
        <p className="mt-2 text-xs text-muted">
          Only public pages on the same site are crawled, within the page and depth limits. robots.txt is respected, private/internal
          addresses are blocked, and pages behind logins or paywalls can’t be indexed. Retrieved text is treated as untrusted data.
        </p>
      </Card>

      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <Spinner label="Loading sources" /> : (
        <>
          <section aria-labelledby="web-sources">
            <h2 id="web-sources" className="mb-2 font-medium">Indexed websites</h2>
            {web.length === 0 ? (
              <EmptyState icon={<Database className="h-7 w-7" />} title="No websites indexed yet">
                Add a public travel site above. Until then, answers come from the demo guide below.
              </EmptyState>
            ) : (
              <Card as="div"><ul className="divide-y divide-border">
                {web.map((s) => (
                  <SourceRow key={s.id} s={s}
                    onIngest={async () => { try { await api(`/api/knowledge/sources/${s.id}/ingest`, { method: "POST" }); } catch (e) { setError((e as Error).message); } load(); }}
                    onDelete={async () => { await api(`/api/knowledge/sources/${s.id}`, { method: "DELETE" }); load(); }} />
                ))}
              </ul></Card>
            )}
          </section>

          {demo && (
            <section aria-labelledby="demo-source">
              <h2 id="demo-source" className="mb-2 flex items-center gap-2 font-medium">
                Demo travel guide <Badge tone="warning">Sample content</Badge>
              </h2>
              <Card className="p-4">
                <p className="mb-3 text-sm text-muted">
                  A small bundled guide so the app works without crawling. It is clearly marked as demo content in every citation.
                  {` ${demo.page_count} articles · ${demo.chunk_count} passages.`}
                </p>
                <ul className="grid gap-1.5 sm:grid-cols-2">
                  {docs.map((d) => (
                    <li key={d.slug}>
                      <Link href={d.url} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-muted">
                        <BookOpen className="h-4 w-4 text-primary" aria-hidden />{d.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          )}
        </>
      )}
    </div>
  );
}
