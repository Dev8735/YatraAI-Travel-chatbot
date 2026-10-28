"use client";

import clsx from "clsx";
import { Compass, Database, Map, MessageCircle, WifiOff } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useHealth } from "./health";
import { Badge } from "./ui";

const NAV = [
  { href: "/", label: "Chat", icon: MessageCircle },
  { href: "/plan", label: "Plan a trip", icon: Map },
  { href: "/explore", label: "Explore", icon: Compass },
  { href: "/knowledge", label: "Knowledge", icon: Database },
];

function StatusPill() {
  const { health, error } = useHealth();
  if (error) {
    return <Badge tone="danger" title={error}><WifiOff className="h-3 w-3" aria-hidden />Server offline</Badge>;
  }
  if (!health) return <Badge>Connecting…</Badge>;
  const c = health.components;
  const detail = `Language model: ${c.llm.live ? `${c.llm.provider} (${c.llm.model})` : "not configured (quoting sources)"}\n`
    + `Places: ${c.places.live ? c.places.provider : "sample data"}\nRoutes: ${c.routes.live ? c.routes.provider : "not configured"}\n`
    + `Embeddings: ${c.embeddings.name}`;
  return health.demo_mode
    ? <Badge tone="warning" title={detail}>Demo mode</Badge>
    : <Badge tone="success" title={detail}>Live providers</Badge>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const active = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
          <Link href="/" className="flex items-center gap-2" aria-label="YatraAI home">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary font-display text-lg font-semibold text-primary-foreground" aria-hidden>
              य
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">YatraAI</span>
          </Link>
          <nav aria-label="Main" className="hidden flex-1 md:block">
            <ul className="flex items-center gap-1">
              {NAV.map(({ href, label, icon: Icon }) => (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active(href) ? "page" : undefined}
                    className={clsx(
                      "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors",
                      active(href) ? "bg-primary/10 font-medium text-primary" : "text-muted hover:bg-surface-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4" aria-hidden />
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ml-auto"><StatusPill /></div>
        </div>
      </header>
      <main id="main" className="flex-1 pb-16 md:pb-0">{children}</main>
      <nav aria-label="Main (mobile)" className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface md:hidden">
        <ul className="grid grid-cols-4">
          {NAV.map(({ href, label, icon: Icon }) => (
            <li key={href}>
              <Link
                href={href}
                aria-current={active(href) ? "page" : undefined}
                className={clsx("flex flex-col items-center gap-0.5 py-2 text-[11px]", active(href) ? "text-primary" : "text-muted")}
              >
                <Icon className="h-5 w-5" aria-hidden />
                {label.split(" ")[0]}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
