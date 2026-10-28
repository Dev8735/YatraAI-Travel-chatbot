import { Check, ExternalLink, Minus, Route as RouteIcon, TrainFront } from "lucide-react";
import Link from "next/link";
import { formatDuration, formatKm, safeHref, titleCase } from "@/lib/format";
import type { Block, ComparisonItem, RecommendationItem, RouteResult, TransportInfo } from "@/lib/types";
import { MapEmbed } from "../MapEmbed";
import { Badge, Notice } from "../ui";
import { BudgetSummary } from "./ItineraryView";

export function RouteSummary({ route }: { route: RouteResult }) {
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <RouteIcon className="h-4 w-4 text-primary" aria-hidden />
        <span className="font-medium">{route.origin} → {route.stops.length ? `${route.stops.join(" → ")} → ` : ""}{route.destination}</span>
        <Badge>{titleCase(route.travel_mode.toLowerCase())}</Badge>
        <Badge tone={route.available ? "success" : "neutral"}>{route.available ? `Source: ${route.provider === "google_routes" ? "Google Routes" : route.provider}` : "No routing provider"}</Badge>
      </div>
      {route.available ? (
        <>
          <dl className="grid grid-cols-2 gap-2 text-sm sm:max-w-sm">
            <div><dt className="text-xs text-muted">Road distance</dt><dd className="font-medium">{formatKm(route.distance_meters)}</dd></div>
            <div><dt className="text-xs text-muted">Est. duration (no live traffic)</dt><dd className="font-medium">{formatDuration(route.duration_seconds)}</dd></div>
          </dl>
          {route.legs.length > 1 && (
            <ol className="text-xs text-muted">
              {route.legs.map((l, i) => <li key={i}>{l.start} → {l.end}: {formatKm(l.distance_meters)}, {formatDuration(l.duration_seconds)}</li>)}
            </ol>
          )}
          {route.summary && <p className="text-xs text-muted">Via {route.summary}</p>}
          {route.warnings.map((w) => <Notice key={w} tone="warning">{w}</Notice>)}
          <MapEmbed mode="directions" origin={route.origin} destination={route.destination} waypoints={route.stops}
                    travelMode={route.travel_mode} title={`Route from ${route.origin} to ${route.destination}`} />
        </>
      ) : (
        <Notice tone="warning">
          {route.notice}
          {route.straight_line_km != null && (
            <span className="mt-1 block font-medium">Straight-line (not road) distance: ~{route.straight_line_km} km</span>
          )}
        </Notice>
      )}
    </div>
  );
}

export function TransportCard({ info }: { info: TransportInfo }) {
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
      <p className="flex items-center gap-2 font-medium">
        <TrainFront className="h-4 w-4 text-primary" aria-hidden />
        {info.origin && info.destination ? `${info.origin} → ${info.destination}` : "Transport information"}
        <Badge>{info.available ? "Live schedule source" : "No schedule source connected"}</Badge>
      </p>
      <ul className="space-y-1 text-sm">
        {info.official_links.map((l) => {
          const href = safeHref(l.url);
          return href ? (
            <li key={l.url}>
              <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                {l.label} <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            </li>
          ) : null;
        })}
      </ul>
    </div>
  );
}

function Fits({ value }: { value?: boolean | null }) {
  if (value == null) return <span className="text-muted">—</span>;
  return value
    ? <span className="inline-flex items-center gap-1 text-success"><Check className="h-4 w-4" aria-hidden />Fits</span>
    : <span className="inline-flex items-center gap-1 text-warning"><Minus className="h-4 w-4" aria-hidden />May feel rushed</span>;
}

export function ComparisonTable({ criteria, items, note }: { criteria: string[]; items: ComparisonItem[]; note: string }) {
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full min-w-[520px] text-left text-sm">
          <caption className="sr-only">Destination comparison</caption>
          <thead className="bg-surface-muted text-xs text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Criterion</th>
              {items.map((i) => <th key={i.name} scope="col" className="px-3 py-2 font-medium text-foreground">{i.name}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Landscape</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.landscape}</td>)}</tr>
            <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Known for</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.known_for.join(", ")}</td>)}</tr>
            <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Your interests matched</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.matched_interests.length ? i.matched_interests.join(", ") : <span className="text-muted">—</span>}</td>)}</tr>
            <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Usual stay</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.suggested_days} {i.fits_days != null && <Fits value={i.fits_days} />}</td>)}</tr>
            {items.some((i) => i.straight_line_km != null) && (
              <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Straight-line distance</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.straight_line_km != null ? `~${i.straight_line_km} km` : "—"}</td>)}</tr>
            )}
            <tr><th scope="row" className="px-3 py-2 font-normal text-muted">Guide</th>{items.map((i) => <td key={i.name} className="px-3 py-2">{i.guide_url ? <Link href={i.guide_url} className="text-primary underline">Read</Link> : <span className="text-muted">—</span>}</td>)}</tr>
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">Compared on: {criteria.join("; ")}. {note}</p>
    </div>
  );
}

export function RecommendationList({ criteria, items, note }: { criteria: string[]; items: RecommendationItem[]; note: string }) {
  return (
    <div className="space-y-2">
      <ol className="grid gap-2 sm:grid-cols-2">
        {items.map((r, i) => (
          <li key={r.name} className="rounded-xl border border-border bg-surface p-3">
            <p className="font-medium"><span className="text-muted">{i + 1}.</span> {r.name} <span className="text-sm font-normal text-muted">· {r.state}</span></p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-muted">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
            {r.guide_url && <Link href={r.guide_url} className="mt-1 inline-block text-sm text-primary underline">Read the guide</Link>}
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted">Ranked by: {criteria.join("; ")}. {note}</p>
    </div>
  );
}

export function ClarifyChips({ options, onPick, disabled }: { options: string[]; onPick: (v: string) => void; disabled?: boolean }) {
  if (!options.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Quick answers">
      {options.map((o) => (
        <button key={o} type="button" disabled={disabled} onClick={() => onPick(o)}
                className="rounded-full border border-border bg-surface px-3 py-1 text-sm hover:border-primary hover:text-primary disabled:opacity-50">
          {o}
        </button>
      ))}
    </div>
  );
}

export function BlockView({ block, onPick, disabled, itineraryAction }:
  { block: Block; onPick: (v: string) => void; disabled?: boolean; itineraryAction?: (id: string) => React.ReactNode }) {
  switch (block.type) {
    case "route": return <RouteSummary route={block.route} />;
    case "transport": return <TransportCard info={block.info} />;
    case "comparison": return <ComparisonTable criteria={block.criteria} items={block.items} note={block.note} />;
    case "recommendations": return <RecommendationList criteria={block.criteria} items={block.items} note={block.note} />;
    case "budget": return <BudgetSummary estimate={block.estimate} />;
    case "clarify": return <ClarifyChips options={block.options} onPick={onPick} disabled={disabled} />;
    default: return itineraryAction && block.type === "itinerary" ? <>{itineraryAction(block.itinerary_id)}</> : null;
  }
}
