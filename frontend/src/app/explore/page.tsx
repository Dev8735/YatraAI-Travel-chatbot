"use client";

import { Route, Search } from "lucide-react";
import { useState } from "react";
import { RouteSummary } from "@/components/blocks/InfoBlocks";
import { PlaceCards } from "@/components/blocks/PlaceCards";
import { Button, Card, inputClass, Notice, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { PlaceSearchResult, RouteResult, TravelMode } from "@/lib/types";

const CATEGORIES = [
  ["tourist_attraction", "Attractions"], ["museum", "Museums"], ["temple", "Temples"], ["beach", "Beaches"],
  ["park", "Parks & gardens"], ["shopping", "Markets"], ["restaurant", "Restaurants"], ["cafe", "Cafés"], ["lodging", "Hotels"],
] as const;

export default function ExplorePage() {
  const [near, setNear] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("tourist_attraction");
  const [places, setPlaces] = useState<PlaceSearchResult | null>(null);
  const [placesState, setPlacesState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });

  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [stops, setStops] = useState("");
  const [mode, setMode] = useState<TravelMode>("DRIVE");
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeState, setRouteState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });

  const searchPlaces = async (e: React.FormEvent) => {
    e.preventDefault();
    setPlacesState({ loading: true, error: null });
    try {
      const params = new URLSearchParams({ q, near, category, limit: "12" });
      setPlaces(await api<PlaceSearchResult>(`/api/places/search?${params}`));
      setPlacesState({ loading: false, error: null });
    } catch (err) {
      setPlacesState({ loading: false, error: (err as Error).message });
    }
  };

  const computeRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    setRouteState({ loading: true, error: null });
    try {
      const body = { origin, destination, travel_mode: mode, stops: stops.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 8) };
      setRoute(await api<RouteResult>("/api/routes", { method: "POST", body: JSON.stringify(body) }));
      setRouteState({ loading: false, error: null });
    } catch (err) {
      setRouteState({ loading: false, error: (err as Error).message });
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <header>
        <h1 className="font-display text-2xl font-semibold">Explore</h1>
        <p className="text-sm text-muted">Search places and check routes. Results are labelled as live or sample data.</p>
      </header>

      <Card className="space-y-4 p-4">
        <h2 className="flex items-center gap-2 font-medium"><Search className="h-4 w-4 text-primary" aria-hidden /> Find places</h2>
        <form onSubmit={searchPlaces} className="grid gap-2 sm:grid-cols-[1fr_1fr_12rem_auto]">
          <div>
            <label htmlFor="near" className="sr-only">Destination</label>
            <input id="near" required className={inputClass} placeholder="Destination (e.g. Udaipur)" value={near} onChange={(e) => setNear(e.target.value)} />
          </div>
          <div>
            <label htmlFor="q" className="sr-only">Keywords</label>
            <input id="q" className={inputClass} placeholder="Keywords (optional)" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div>
            <label htmlFor="cat" className="sr-only">Category</label>
            <select id="cat" className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <Button type="submit" disabled={placesState.loading || !near.trim()}>Search</Button>
        </form>
        {placesState.loading && <Spinner label="Searching places" />}
        {placesState.error && <Notice tone="error">{placesState.error}</Notice>}
        {places && !placesState.loading && <PlaceCards result={places} />}
      </Card>

      <Card className="space-y-4 p-4">
        <h2 className="flex items-center gap-2 font-medium"><Route className="h-4 w-4 text-primary" aria-hidden /> Route & road distance</h2>
        <form onSubmit={computeRoute} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_10rem_auto]">
          <div>
            <label htmlFor="origin" className="sr-only">From</label>
            <input id="origin" required minLength={2} className={inputClass} placeholder="From (e.g. Ahmedabad)" value={origin} onChange={(e) => setOrigin(e.target.value)} />
          </div>
          <div>
            <label htmlFor="destination" className="sr-only">To</label>
            <input id="destination" required minLength={2} className={inputClass} placeholder="To (e.g. Udaipur)" value={destination} onChange={(e) => setDestination(e.target.value)} />
          </div>
          <div>
            <label htmlFor="stops" className="sr-only">Stops</label>
            <input id="stops" className={inputClass} placeholder="Stops, comma-separated (optional)" value={stops} onChange={(e) => setStops(e.target.value)} />
          </div>
          <div>
            <label htmlFor="mode" className="sr-only">Travel mode</label>
            <select id="mode" className={inputClass} value={mode} onChange={(e) => setMode(e.target.value as TravelMode)}>
              <option value="DRIVE">Drive</option><option value="TWO_WHEELER">Two-wheeler</option><option value="TRANSIT">Transit</option>
              <option value="WALK">Walk</option><option value="BICYCLE">Bicycle</option>
            </select>
          </div>
          <Button type="submit" disabled={routeState.loading || origin.trim().length < 2 || destination.trim().length < 2}>Get route</Button>
        </form>
        {routeState.loading && <Spinner label="Calculating route" />}
        {routeState.error && <Notice tone="error">{routeState.error}</Notice>}
        {route && !routeState.loading && <RouteSummary route={route} />}
      </Card>
    </div>
  );
}
