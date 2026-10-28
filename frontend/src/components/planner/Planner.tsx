"use client";

import { CalendarDays, Map, Trash2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BudgetTier, Itinerary, ItineraryOperation, ItinerarySummary, Pace } from "@/lib/types";
import { ItineraryView } from "../blocks/ItineraryView";
import { Button, Card, EmptyState, inputClass, Notice, Spinner } from "../ui";

const INTERESTS = ["heritage", "food", "nature", "spiritual", "museums", "shopping", "beaches", "adventure",
                   "photography", "wildlife", "nightlife", "relaxation"];
const ACCESSIBILITY = [
  { value: "elderly", label: "Travelling with elderly people" },
  { value: "young_children", label: "Young children" },
  { value: "limited_walking", label: "Limited walking" },
  { value: "wheelchair", label: "Wheelchair user" },
];

interface FormState {
  destination: string; days: number; start_date: string; travellers: string; pace: Pace;
  budget_level: "" | BudgetTier; budget_amount: string; interests: string[]; accessibility: string[]; transport_mode: string;
}

const EMPTY: FormState = { destination: "", days: 3, start_date: "", travellers: "", pace: "balanced", budget_level: "",
                           budget_amount: "", interests: [], accessibility: [], transport_mode: "" };

export function Planner() {
  const router = useRouter();
  const params = useSearchParams();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saved, setSaved] = useState<ItinerarySummary[]>([]);
  const [savedLoading, setSavedLoading] = useState(true);
  const [current, setCurrent] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSaved = useCallback(async () => {
    try { setSaved(await api<ItinerarySummary[]>("/api/itineraries?limit=50")); }
    catch (e) { setError((e as Error).message); }
    finally { setSavedLoading(false); }
  }, []);

  const open = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try { setCurrent(await api<Itinerary>(`/api/itineraries/${id}`)); }
    catch (e) { setError((e as Error).message); setCurrent(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSaved(); }, [loadSaved]);
  const idParam = params.get("id");
  useEffect(() => { if (idParam) open(idParam); }, [idParam, open]);

  const toggle = (key: "interests" | "accessibility", v: string) =>
    setForm((f) => ({ ...f, [key]: f[key].includes(v) ? f[key].filter((x) => x !== v) : [...f[key], v] }));

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body = {
        destination: form.destination.trim(), days: form.days, pace: form.pace, interests: form.interests,
        accessibility: form.accessibility, start_date: form.start_date || null,
        travellers: form.travellers ? Number(form.travellers) : null, budget_level: form.budget_level || null,
        transport_mode: form.transport_mode || null,
        budget: form.budget_amount ? { amount: Number(form.budget_amount), currency: "INR", qualifier: "max", per_person: false } : null,
      };
      const it = await api<Itinerary>("/api/itineraries", { method: "POST", body: JSON.stringify(body) });
      setCurrent(it);
      router.replace(`/plan?id=${it.id}`, { scroll: false });
      loadSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const apply = async (ops: ItineraryOperation[]) => {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      const it = await api<Itinerary>(`/api/itineraries/${current.id}`, {
        method: "PATCH", body: JSON.stringify({ operations: ops, expected_version: current.version }),
      });
      setCurrent(it);
      loadSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api(`/api/itineraries/${id}`, { method: "DELETE" });
    if (current?.id === id) { setCurrent(null); router.replace("/plan", { scroll: false }); }
    loadSaved();
  };

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[22rem_1fr]">
      <div className="space-y-4">
        <Card className="p-4">
          <h1 className="font-display text-xl font-semibold">Plan a trip</h1>
          <p className="mb-3 text-sm text-muted">Build a day-by-day plan, then edit it stop by stop.</p>
          <form onSubmit={create} className="space-y-3">
            <div>
              <label htmlFor="dest" className="mb-1 block text-sm font-medium">Destination</label>
              <input id="dest" required minLength={2} maxLength={100} className={inputClass} placeholder="e.g. Jaipur, Udaipur, Goa"
                     value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="days" className="mb-1 block text-sm font-medium">Days</label>
                <input id="days" type="number" min={1} max={14} required className={inputClass} value={form.days}
                       onChange={(e) => setForm({ ...form, days: Math.max(1, Math.min(14, Number(e.target.value) || 1)) })} />
              </div>
              <div>
                <label htmlFor="start" className="mb-1 block text-sm font-medium">Start date <span className="font-normal text-muted">(optional)</span></label>
                <input id="start" type="date" className={inputClass} value={form.start_date}
                       onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
              </div>
              <div>
                <label htmlFor="pax" className="mb-1 block text-sm font-medium">Travellers</label>
                <input id="pax" type="number" min={1} max={50} className={inputClass} placeholder="—" value={form.travellers}
                       onChange={(e) => setForm({ ...form, travellers: e.target.value })} />
              </div>
              <div>
                <label htmlFor="pace" className="mb-1 block text-sm font-medium">Pace</label>
                <select id="pace" className={inputClass} value={form.pace} onChange={(e) => setForm({ ...form, pace: e.target.value as Pace })}>
                  <option value="relaxed">Relaxed</option><option value="balanced">Balanced</option><option value="packed">Packed</option>
                </select>
              </div>
              <div>
                <label htmlFor="tier" className="mb-1 block text-sm font-medium">Budget style</label>
                <select id="tier" className={inputClass} value={form.budget_level}
                        onChange={(e) => setForm({ ...form, budget_level: e.target.value as FormState["budget_level"] })}>
                  <option value="">Not sure</option><option value="budget">Budget</option><option value="mid">Mid-range</option><option value="luxury">Luxury</option>
                </select>
              </div>
              <div>
                <label htmlFor="amount" className="mb-1 block text-sm font-medium">Max budget (₹)</label>
                <input id="amount" type="number" min={100} step={500} className={inputClass} placeholder="—" value={form.budget_amount}
                       onChange={(e) => setForm({ ...form, budget_amount: e.target.value })} />
              </div>
            </div>
            <div>
              <label htmlFor="transport" className="mb-1 block text-sm font-medium">Getting around</label>
              <select id="transport" className={inputClass} value={form.transport_mode} onChange={(e) => setForm({ ...form, transport_mode: e.target.value })}>
                <option value="">No preference</option><option value="DRIVE">Car / taxi</option><option value="TWO_WHEELER">Scooter / bike</option>
                <option value="TRANSIT">Public transport</option><option value="WALK">Walking</option>
              </select>
            </div>
            <fieldset>
              <legend className="mb-1 text-sm font-medium">Interests</legend>
              <div className="flex flex-wrap gap-1.5">
                {INTERESTS.map((i) => (
                  <label key={i} className={`cursor-pointer rounded-full border px-2.5 py-1 text-xs capitalize has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--focus)] ${form.interests.includes(i) ? "border-primary bg-primary/10 text-primary" : "border-border"}`}>
                    <input type="checkbox" className="sr-only" checked={form.interests.includes(i)} onChange={() => toggle("interests", i)} />
                    {i}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-1 text-sm font-medium">Accessibility & needs</legend>
              <div className="space-y-1">
                {ACCESSIBILITY.map((a) => (
                  <label key={a.value} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={form.accessibility.includes(a.value)} onChange={() => toggle("accessibility", a.value)} />
                    {a.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <Button type="submit" disabled={loading || form.destination.trim().length < 2} className="w-full">
              {loading ? "Building…" : "Build itinerary"}
            </Button>
          </form>
        </Card>

        <Card className="p-4">
          <h2 className="mb-2 font-medium">Saved itineraries</h2>
          {savedLoading ? <Spinner /> : saved.length === 0 ? <p className="text-sm text-muted">Nothing saved yet.</p> : (
            <ul className="divide-y divide-border">
              {saved.map((s) => (
                <li key={s.id} className="flex items-center gap-2 py-1.5">
                  <button type="button" onClick={() => router.replace(`/plan?id=${s.id}`, { scroll: false })}
                          className={`min-w-0 flex-1 truncate text-left text-sm ${current?.id === s.id ? "font-medium text-primary" : ""}`}>
                    {s.title} <span className="text-muted">· v{s.version}</span>
                  </button>
                  <Button size="sm" variant="ghost" aria-label={`Delete ${s.title}`} onClick={() => remove(s.id)}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="min-w-0 space-y-3">
        {error && <Notice tone="error">{error}</Notice>}
        {loading && !current ? <Spinner label="Building your plan" /> : current ? (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-2xl font-semibold">{current.title}</h2>
              <span className="text-xs text-muted">Version {current.version}{busy ? " · saving…" : ""}</span>
            </div>
            <ItineraryView plan={current.plan} editor={{ apply, busy }} />
          </>
        ) : (
          <EmptyState icon={<Map className="h-8 w-8" />} title="No itinerary open">
            Fill in the form to build one, open a saved plan, or ask the chat to “plan 2 days in Udaipur”.
            <span className="mt-2 flex items-center justify-center gap-1"><CalendarDays className="h-4 w-4" aria-hidden /> Plans are suggestions — hours and bookings are not guaranteed.</span>
          </EmptyState>
        )}
      </div>
    </div>
  );
}
