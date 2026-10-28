import clsx from "clsx";
import { AlertTriangle, Info, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variant = "primary", size = "md", className, children, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  return (
    <button
      {...props}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-2.5 text-sm" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary-hover",
        variant === "secondary" && "border border-border bg-surface text-foreground hover:bg-surface-muted",
        variant === "ghost" && "text-muted hover:bg-surface-muted hover:text-foreground",
        variant === "danger" && "border border-border bg-surface text-danger hover:bg-danger-soft",
        className,
      )}
    >
      {children}
    </button>
  );
}

type Tone = "neutral" | "primary" | "accent" | "success" | "warning" | "danger";

export function Badge({ tone = "neutral", children, className, title }:
  { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tone === "neutral" && "bg-surface-muted text-muted",
        tone === "primary" && "bg-primary/10 text-primary",
        tone === "accent" && "bg-accent-soft text-accent",
        tone === "success" && "bg-success-soft text-success",
        tone === "warning" && "bg-warning-soft text-warning",
        tone === "danger" && "bg-danger-soft text-danger",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Card({ children, className, as: Tag = "section" }:
  { children: ReactNode; className?: string; as?: "section" | "article" | "div" | "li" }) {
  return <Tag className={clsx("rounded-xl border border-border bg-surface", className)}>{children}</Tag>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warning" | "error"; children: ReactNode }) {
  const Icon = tone === "info" ? Info : AlertTriangle;
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={clsx(
        "flex gap-2 rounded-lg px-3 py-2 text-sm",
        tone === "info" && "bg-surface-muted text-muted",
        tone === "warning" && "bg-warning-soft text-warning",
        tone === "error" && "bg-danger-soft text-danger",
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border px-6 py-10 text-center">
      <div className="text-muted" aria-hidden>{icon}</div>
      <p className="font-medium">{title}</p>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function DataOriginBadge({ origin }: { origin: "live" | "demo" }) {
  return origin === "live"
    ? <Badge tone="success" title="Returned by a configured live provider">Live data</Badge>
    : <Badge tone="warning" title="From YatraAI's sample dataset — not live">Sample data</Badge>;
}

export const inputClass =
  "h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted " +
  "focus-visible:outline-2 focus-visible:outline-offset-0";
