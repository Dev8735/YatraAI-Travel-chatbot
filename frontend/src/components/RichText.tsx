"use client";

import { Fragment, type ReactNode } from "react";
import type { Citation } from "@/lib/types";

/**
 * Minimal, safe renderer for assistant text: paragraphs, "- " bullets, **bold** and [S#]
 * citation markers. Everything is rendered as React text nodes — no HTML is ever injected,
 * so model output or retrieved content cannot execute markup or scripts.
 */
export function RichText({ text, citations = [], onCite }:
  { text: string; citations?: Citation[]; onCite?: (id: string) => void }) {
  const known = new Set(citations.map((c) => c.id));
  const blocks = text.split(/\n{2,}/).filter((b) => b.trim());
  return (
    <div className="space-y-2 leading-relaxed">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim());
        const isList = lines.length > 0 && lines.every((l) => /^\s*[-•]\s+/.test(l));
        const mixedList = !isList && lines.some((l) => /^\s*[-•]\s+/.test(l));
        if (isList || mixedList) {
          const lead = lines.filter((l) => !/^\s*[-•]\s+/.test(l));
          const items = lines.filter((l) => /^\s*[-•]\s+/.test(l));
          return (
            <Fragment key={bi}>
              {lead.map((l, i) => <p key={`l${i}`}>{inline(l, known, onCite)}</p>)}
              <ul className="list-disc space-y-1 pl-5">
                {items.map((l, i) => <li key={i}>{inline(l.replace(/^\s*[-•]\s+/, ""), known, onCite)}</li>)}
              </ul>
            </Fragment>
          );
        }
        return <p key={bi}>{lines.map((l, i) => <Fragment key={i}>{i > 0 && <br />}{inline(l, known, onCite)}</Fragment>)}</p>;
      })}
    </div>
  );
}

function inline(line: string, known: Set<string>, onCite?: (id: string) => void): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[S\d+\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index));
    const token = m[0];
    if (token.startsWith("**")) {
      out.push(<strong key={k++}>{token.slice(2, -2)}</strong>);
    } else {
      const id = token.slice(1, -1);
      if (known.has(id)) {
        out.push(
          <button
            key={k++}
            type="button"
            onClick={() => onCite?.(id)}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-primary/10 px-1 align-text-top text-[11px] font-semibold text-primary hover:bg-primary/20"
            aria-label={`Source ${id.slice(1)}`}
          >
            {id.slice(1)}
          </button>,
        );
      }
      // Unknown markers are dropped: we never show a citation we cannot back with a source.
    }
    last = m.index + token.length;
  }
  if (last < line.length) out.push(line.slice(last));
  return out;
}
