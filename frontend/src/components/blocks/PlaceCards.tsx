import { Clock, ExternalLink, MapPin, Star } from "lucide-react";
import { safeHref, titleCase } from "@/lib/format";
import type { Place, PlaceSearchResult } from "@/lib/types";
import { Badge, DataOriginBadge, EmptyState, Notice } from "../ui";

export function PlaceCard({ place, action }: { place: Place; action?: React.ReactNode }) {
  const photo = place.photos[0];
  const maps = safeHref(place.maps_url);
  const site = safeHref(place.website);
  return (
    <li className="flex flex-col overflow-hidden rounded-xl border border-border bg-surface">
      {photo ? (
        <figure className="relative">
          {/* Provider photo served through our proxy; attribution shown as required by the provider. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo.url} alt={`Photo of ${place.name}`} className="h-36 w-full object-cover" loading="lazy" />
          {photo.attributions.length > 0 && (
            <figcaption className="absolute bottom-0 right-0 max-w-full truncate bg-black/60 px-1.5 py-0.5 text-[10px] text-white">
              Photo: {photo.attributions.map((a, i) => {
                const href = safeHref(a.uri);
                return href
                  ? <a key={i} href={href} target="_blank" rel="noopener noreferrer nofollow" className="underline">{a.name}</a>
                  : <span key={i}>{a.name}</span>;
              })}
            </figcaption>
          )}
        </figure>
      ) : null}
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-medium leading-snug">{place.name}</h4>
          {place.category && <Badge>{titleCase(place.category)}</Badge>}
        </div>
        {place.address && (
          <p className="flex items-start gap-1 text-xs text-muted">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{place.address}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {place.rating != null && place.user_rating_count ? (
            <span className="inline-flex items-center gap-1" title="Rating and review count from Google">
              <Star className="h-3.5 w-3.5 fill-accent text-accent" aria-hidden />
              {place.rating.toFixed(1)} <span className="text-muted">({place.user_rating_count.toLocaleString()} on Google)</span>
            </span>
          ) : null}
          {place.open_now != null && <Badge tone={place.open_now ? "success" : "danger"}>{place.open_now ? "Open now" : "Closed now"}</Badge>}
          {place.price_level && <Badge>{titleCase(place.price_level)}</Badge>}
          {place.typical_visit_minutes && place.data_origin === "demo" && (
            <span className="inline-flex items-center gap-1 text-muted" title="Planning assumption, not a verified duration">
              <Clock className="h-3.5 w-3.5" aria-hidden />~{place.typical_visit_minutes} min (assumed)
            </span>
          )}
        </div>
        {place.opening_hours.length > 0 && (
          <details className="text-xs text-muted">
            <summary className="cursor-pointer">Opening hours (from provider)</summary>
            <ul className="mt-1 space-y-0.5">{place.opening_hours.map((h) => <li key={h}>{h}</li>)}</ul>
          </details>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1 text-xs">
          <DataOriginBadge origin={place.data_origin} />
          {maps && <a className="inline-flex items-center gap-1 text-primary hover:underline" href={maps} target="_blank" rel="noopener noreferrer">Google Maps <ExternalLink className="h-3 w-3" aria-hidden /></a>}
          {site && <a className="inline-flex items-center gap-1 text-primary hover:underline" href={site} target="_blank" rel="noopener noreferrer nofollow">Website <ExternalLink className="h-3 w-3" aria-hidden /></a>}
          {action}
        </div>
      </div>
    </li>
  );
}

export function PlaceCards({ result }: { result: PlaceSearchResult }) {
  return (
    <div className="space-y-2">
      {result.notice && <Notice tone={result.data_origin === "demo" ? "warning" : "info"}>{result.notice}</Notice>}
      {result.places.length === 0 ? (
        <EmptyState icon={<MapPin className="h-6 w-6" />} title="No places to show">
          Try another destination or category.
        </EmptyState>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {result.places.map((p) => <PlaceCard key={p.id} place={p} />)}
        </ul>
      )}
      {result.data_origin === "live" && <p className="text-[11px] text-muted">Place data © Google</p>}
    </div>
  );
}
