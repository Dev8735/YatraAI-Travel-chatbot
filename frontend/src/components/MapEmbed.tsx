import { MapPinOff } from "lucide-react";

// Google Maps Embed API key: a *browser* key that must be restricted by HTTP referrer in
// Google Cloud. It is intentionally public (NEXT_PUBLIC_*); never reuse the server key here.
const EMBED_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_EMBED_KEY;

export const mapsEnabled = Boolean(EMBED_KEY);

type MapProps =
  | { mode: "place"; query: string; title: string }
  | { mode: "directions"; origin: string; destination: string; waypoints?: string[]; travelMode?: string; title: string };

export function MapEmbed(props: MapProps) {
  if (!EMBED_KEY) {
    return (
      <p className="flex items-center gap-2 rounded-lg bg-surface-muted px-3 py-2 text-xs text-muted">
        <MapPinOff className="h-4 w-4" aria-hidden />
        Map unavailable: no map key configured (set NEXT_PUBLIC_GOOGLE_MAPS_EMBED_KEY).
      </p>
    );
  }
  const params = new URLSearchParams({ key: EMBED_KEY });
  let base: string;
  if (props.mode === "place") {
    base = "place";
    params.set("q", props.query);
  } else {
    base = "directions";
    params.set("origin", props.origin);
    params.set("destination", props.destination);
    if (props.waypoints?.length) params.set("waypoints", props.waypoints.join("|"));
    const mode = { DRIVE: "driving", WALK: "walking", BICYCLE: "bicycling", TRANSIT: "transit", TWO_WHEELER: "driving" }[props.travelMode ?? "DRIVE"];
    if (mode) params.set("mode", mode);
  }
  return (
    <iframe
      title={props.title}
      className="h-64 w-full rounded-lg border border-border"
      loading="lazy"
      referrerPolicy="strict-origin-when-cross-origin"
      src={`https://www.google.com/maps/embed/v1/${base}?${params.toString()}`}
      allowFullScreen
    />
  );
}
