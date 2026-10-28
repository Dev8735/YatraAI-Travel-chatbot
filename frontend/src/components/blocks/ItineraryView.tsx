"use client";

import { ArrowDown, ArrowUp, CalendarPlus, Car, Clock, Plus, RefreshCw, Trash2, Utensils } from "lucide-react";
import { useState } from "react";
import { formatDate, formatINR } from "@/lib/format";
import type { BudgetEstimate, ItineraryOperation, ItineraryPlan } from "@/lib/types";
import { MapEmbed } from "../MapEmbed";
import { Badge, Button, DataOriginBadge, Notice } from "../ui";

export function BudgetSummary({ estimate }: { estimate: BudgetEstimate }) {
  return (
    <div className="rounded-lg bg-surface-muted p-3 text-sm">
      <p>
        <span className="font-medium">Rough {estimate.tier} estimate:</span>{" "}
        {formatINR(estimate.total_min)} – {formatINR(estimate.total_max)}{" "}
        <span className="text-muted">
          ({formatINR(estimate.per_person_per_day_min)}–{formatINR(estimate.per_person_per_day_max)} per person/day ×{" "}
          {estimate.days} day(s) × {estimate.travellers} traveller(s){estimate.travellers_assumed ? ", assumed" : ""})
        </span>
      </p>
      {estimate.within_user_budget !== "unknown" && estimate.user_budget && (
        <p className="mt-1">
          Your budget ({estimate.user_budget.currency} {estimate.user_budget.amount.toLocaleString("en-IN")}):{" "}
          <Badge tone={{ yes: "success", partly: "warning", no: "danger", unknown: "neutral" }[estimate.within_user_budget] as "success"}>
            {{ yes: "covers this range", partly: "within the range", no: "below this range", unknown: "" }[estimate.within_user_budget]}
          </Badge>
        </p>
      )}
      <p className="mt-1 text-xs text-muted">
        {estimate.basis} Excludes {estimate.excludes.join(", ")}.{" "}
        {estimate.source_url && <a href={estimate.source_url} className="text-primary underline">How this is estimated</a>}
      </p>
    </div>
  );
}

export interface ItineraryEditor {
  apply: (ops: ItineraryOperation[]) => Promise<void>;
  busy: boolean;
}

export function ItineraryView({ plan, editor, showMap = true }: { plan: ItineraryPlan; editor?: ItineraryEditor; showMap?: boolean }) {
  const [addTarget, setAddTarget] = useState<Record<string, number>>({});
  const dayCount = plan.days.length;
  const disabled = editor?.busy;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <DataOriginBadge origin={plan.data_origin} />
        <Badge>{dayCount} day{dayCount > 1 ? "s" : ""}</Badge>
        {editor && (
          <Button size="sm" variant="secondary" disabled={disabled} onClick={() => editor.apply([{ op: "add_day" }])}>
            <CalendarPlus className="h-4 w-4" aria-hidden /> Add a day
          </Button>
        )}
      </div>

      {plan.warnings.map((w) => <Notice key={w} tone="warning">{w}</Notice>)}

      <ol className="space-y-3">
        {plan.days.map((day) => (
          <li key={day.day} className="rounded-xl border border-border bg-surface">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
              <h4 className="font-medium">
                Day {day.day}{day.date ? <span className="font-normal text-muted"> · {formatDate(day.date)}</span> : null}
                <span className="block text-sm font-normal text-muted">{day.title}</span>
              </h4>
              {editor && (
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" disabled={disabled} aria-label={`Regenerate day ${day.day}`}
                          onClick={() => editor.apply([{ op: "regenerate_day", day: day.day }])}>
                    <RefreshCw className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">Regenerate</span>
                  </Button>
                  <Button size="sm" variant="ghost" disabled={disabled || dayCount <= 1} aria-label={`Remove day ${day.day}`}
                          title={dayCount <= 1 ? "An itinerary needs at least one day" : undefined}
                          onClick={() => editor.apply([{ op: "remove_day", day: day.day }])}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </Button>
                </div>
              )}
            </div>
            <ol className="divide-y divide-border">
              {day.stops.map((stop, idx) => {
                const lunch = day.breaks.find((b) => b.time <= stop.start_time && b.time >= (day.stops[idx - 1]?.end_time ?? "00:00"));
                return (
                  <li key={stop.id} className="px-3 py-2.5">
                    {lunch && (
                      <p className="mb-2 flex items-center gap-1.5 text-xs text-muted">
                        <Utensils className="h-3.5 w-3.5" aria-hidden /> {lunch.time} · {lunch.label} (~{lunch.duration_minutes} min)
                      </p>
                    )}
                    {stop.transfer_minutes_before ? (
                      <p className="mb-1 flex items-center gap-1.5 text-xs text-muted" title="Estimated from straight-line distance, not a routed travel time">
                        <Car className="h-3.5 w-3.5" aria-hidden /> ~{stop.transfer_minutes_before} min transfer (estimate)
                      </p>
                    ) : null}
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex w-14 shrink-0 flex-col text-xs tabular-nums text-muted">
                        <span className="font-medium text-foreground">{stop.start_time}</span>{stop.end_time}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{stop.place.name}</p>
                        <p className="text-sm text-muted">{stop.reason}</p>
                        <ul className="mt-1 space-y-0.5 text-xs text-muted">
                          <li className="flex items-center gap-1"><Clock className="h-3 w-3" aria-hidden /> {stop.duration_minutes} min planned</li>
                          {stop.notes.map((n) => <li key={n}>{n}</li>)}
                        </ul>
                      </div>
                      {editor && (
                        <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
                          <Button size="sm" variant="ghost" disabled={disabled || idx === 0} aria-label={`Move ${stop.place.name} earlier`}
                                  onClick={() => editor.apply([{ op: "move_stop", stop_id: stop.id, to_day: day.day, position: idx - 1 }])}>
                            <ArrowUp className="h-4 w-4" aria-hidden />
                          </Button>
                          <Button size="sm" variant="ghost" disabled={disabled || idx === day.stops.length - 1} aria-label={`Move ${stop.place.name} later`}
                                  onClick={() => editor.apply([{ op: "move_stop", stop_id: stop.id, to_day: day.day, position: idx + 1 }])}>
                            <ArrowDown className="h-4 w-4" aria-hidden />
                          </Button>
                          {dayCount > 1 && (
                            <select
                              aria-label={`Move ${stop.place.name} to another day`}
                              className="h-8 rounded-lg border border-border bg-surface px-1 text-xs"
                              disabled={disabled}
                              value=""
                              onChange={(e) => e.target.value && editor.apply([{ op: "move_stop", stop_id: stop.id, to_day: Number(e.target.value) }])}
                            >
                              <option value="">Move to…</option>
                              {plan.days.filter((d) => d.day !== day.day).map((d) => <option key={d.day} value={d.day}>Day {d.day}</option>)}
                            </select>
                          )}
                          <Button size="sm" variant="ghost" disabled={disabled} aria-label={`Remove ${stop.place.name}`}
                                  onClick={() => editor.apply([{ op: "remove_stop", stop_id: stop.id }])}>
                            <Trash2 className="h-4 w-4" aria-hidden />
                          </Button>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
              {day.stops.length === 0 && <li className="px-3 py-3 text-sm text-muted">No stops planned.</li>}
            </ol>
            {day.notes.length > 0 && (
              <div className="border-t border-border px-3 py-2 text-xs text-muted">{day.notes.join(" ")}</div>
            )}
          </li>
        ))}
      </ol>

      {editor && plan.unplaced.length > 0 && (
        <details className="rounded-xl border border-border bg-surface p-3">
          <summary className="cursor-pointer text-sm font-medium">More places you could add ({plan.unplaced.length})</summary>
          <ul className="mt-2 divide-y divide-border">
            {plan.unplaced.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>{p.name}{p.category ? <span className="text-muted"> · {p.category.replace(/_/g, " ")}</span> : null}</span>
                <span className="flex items-center gap-1">
                  <select
                    aria-label={`Day to add ${p.name} to`}
                    className="h-8 rounded-lg border border-border bg-surface px-1 text-xs"
                    value={addTarget[p.id] ?? 1}
                    onChange={(e) => setAddTarget({ ...addTarget, [p.id]: Number(e.target.value) })}
                  >
                    {plan.days.map((d) => <option key={d.day} value={d.day}>Day {d.day}</option>)}
                  </select>
                  <Button size="sm" variant="secondary" disabled={disabled}
                          onClick={() => editor.apply([{ op: "add_stop", day: addTarget[p.id] ?? 1, place_id: p.id }])}>
                    <Plus className="h-4 w-4" aria-hidden /> Add
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {plan.budget_estimate && <BudgetSummary estimate={plan.budget_estimate} />}

      <details className="text-xs text-muted">
        <summary className="cursor-pointer">Planning assumptions</summary>
        <ul className="mt-1 list-disc space-y-0.5 pl-5">{plan.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </details>

      {showMap && <MapEmbed mode="place" query={plan.destination} title={`Map of ${plan.destination}`} />}
    </div>
  );
}
