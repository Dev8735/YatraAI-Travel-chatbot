"use client";

import { ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { formatDate, isExternal, safeHref } from "@/lib/format";
import type { Citation, Evidence } from "@/lib/types";
import { Badge } from "./ui";

export function EvidenceBadge({ evidence }: { evidence?: Evidence | null }) {
  if (!evidence) return null;
  const map = {
    strong: { tone: "success" as const, label: "Supported by 2+ sources", tip: "Two or more retrieved passages that passed the relevance check are cited." },
    limited: { tone: "warning" as const, label: "Supported by 1 source", tip: "Only one cited passage passed the relevance check." },
    none: { tone: "neutral" as const, label: "No supporting source", tip: "No indexed passage was relevant enough to cite." },
  }[evidence];
  return <Badge tone={map.tone} title={map.tip}>{map.label}</Badge>;
}

export function CitationList({ citations, highlighted }: { citations: Citation[]; highlighted?: string | null }) {
  if (!citations.length) return null;
  return (
    <ol className="space-y-2" aria-label="Sources">
      {citations.map((c) => {
        const href = safeHref(c.url);
        const date = c.published_at || formatDate(c.fetched_at);
        const body = (
          <>
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <span className="grid h-5 min-w-5 place-items-center rounded bg-primary/10 px-1 text-[11px] font-semibold text-primary">
                {c.id.slice(1)}
              </span>
              <span className="truncate">{c.title}{c.heading ? ` — ${c.heading}` : ""}</span>
              {href && isExternal(href) ? <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden /> : <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />}
            </span>
            <span className="mt-1 line-clamp-2 block text-xs text-muted">“{c.snippet}”</span>
            <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
              {c.is_demo && <Badge tone="warning">Demo content</Badge>}
              {href && <span className="truncate">{isExternal(href) ? new URL(href).hostname : "YatraAI demo guide"}</span>}
              {date && <span>· {c.published_at ? "dated" : "retrieved"} {date}</span>}
            </span>
          </>
        );
        const cls = `block rounded-lg border p-2.5 text-sm transition-colors hover:bg-surface-muted ${highlighted === c.id ? "border-primary ring-1 ring-primary" : "border-border"}`;
        return (
          <li key={c.id} id={`cite-${c.id}`}>
            {href ? (
              isExternal(href)
                ? <a href={href} target="_blank" rel="noopener noreferrer nofollow" className={cls}>{body}</a>
                : <Link href={href} className={cls}>{body}</Link>
            ) : <div className={cls}>{body}</div>}
          </li>
        );
      })}
    </ol>
  );
}
