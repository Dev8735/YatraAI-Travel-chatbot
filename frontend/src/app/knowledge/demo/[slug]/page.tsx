"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { RichText } from "@/components/RichText";
import { Badge, Notice, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { DemoDoc } from "@/lib/types";

/** Renders a bundled demo article (the target of demo citations). Markdown is shown as safe text. */
export default function DemoArticle({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [doc, setDoc] = useState<DemoDoc | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<DemoDoc>(`/api/knowledge/demo/${encodeURIComponent(slug)}`).then(setDoc).catch((e: Error) => setError(e.message));
  }, [slug]);

  const sections = (doc?.body ?? "").split(/\n(?=#\s)/);
  return (
    <article className="mx-auto max-w-3xl space-y-4 px-4 py-6">
      <Link href="/knowledge" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Knowledge sources
      </Link>
      {error && <Notice tone="error">{error}</Notice>}
      {!doc && !error && <Spinner />}
      {doc && (
        <>
          <header className="space-y-2">
            <Badge tone="warning">Demo knowledge-base article</Badge>
            <h1 className="font-display text-3xl font-semibold">{doc.title}</h1>
          </header>
          {sections.map((sec, i) => {
            const lines = sec.split("\n");
            const heading = lines[0].startsWith("# ") ? lines[0].slice(2) : null;
            const body = (heading ? lines.slice(1) : lines).join("\n").replace(/^>\s?/gm, "").trim();
            return (
              <section key={i} className="space-y-2">
                {heading && <h2 className="font-display text-xl font-semibold">{heading}</h2>}
                <div className={i === 0 && !heading ? "rounded-lg bg-warning-soft p-3 text-sm text-warning" : ""}>
                  <RichText text={body} />
                </div>
              </section>
            );
          })}
        </>
      )}
    </article>
  );
}
