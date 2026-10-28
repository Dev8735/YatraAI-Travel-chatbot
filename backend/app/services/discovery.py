"""Destination recommendations and comparisons with transparent criteria.

Ranking = (number of the user's interests matched by the destination's profile tags) and,
for short trips, a preference for destinations whose suggested stay fits the available days
and that are closer (straight-line) to the origin. No opaque scores are shown — only the
matched criteria themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.nlp.gazetteer import DESTINATIONS, Destination, get_destination, haversine_km

INTEREST_SYNONYMS = {
    "spiritual": {"spiritual", "temples", "ghats", "monasteries", "yoga"},
    "heritage": {"heritage", "forts", "palaces", "history", "ruins", "architecture", "museums", "culture"},
    "nature": {"nature", "lakes", "hills", "waterfalls", "gardens", "tea", "backwaters", "mountains"},
    "beaches": {"beaches", "diving"},
    "mountains": {"mountains", "snow", "hills", "trekking"},
    "adventure": {"adventure", "trekking", "rafting", "diving", "safari"},
    "wildlife": {"wildlife", "safari"},
    "food": {"food"},
    "shopping": {"shopping", "crafts"},
    "nightlife": {"nightlife"},
    "relaxation": {"relaxation", "beaches", "backwaters", "ayurveda", "lakes"},
    "museums": {"museums"},
    "photography": {"photography", "desert", "lakes", "forts"},
    "desert": {"desert"},
    "backwaters": {"backwaters"},
}


@dataclass
class Recommendation:
    destination: Destination
    matched_interests: list[str]
    reasons: list[str]
    straight_line_km: int | None = None
    fits_days: bool | None = None
    guide_url: str | None = None


@dataclass
class ComparisonRow:
    destination: Destination
    matched_interests: list[str]
    straight_line_km: int | None
    suggested_days: tuple[int, int]
    fits_days: bool | None
    guide_url: str | None
    notes: list[str] = field(default_factory=list)


def matched(dest: Destination, interests: list[str]) -> list[str]:
    tags = set(dest.tags)
    return [i for i in interests if tags & INTEREST_SYNONYMS.get(i, {i})]


def _distance(origin: Destination | None, dest: Destination) -> int | None:
    if origin is None or origin == dest:
        return None
    return round(haversine_km((origin.lat, origin.lng), (dest.lat, dest.lng)))


def recommend(*, interests: list[str], origin: str | None, days: int | None, exclude: list[str] | None = None,
              limit: int = 5, domestic_only: bool = True) -> tuple[list[Recommendation], list[str]]:
    origin_dest = get_destination(origin) if origin else None
    excluded = set(exclude or []) | ({origin_dest.name} if origin_dest else set())
    criteria = []
    if interests:
        criteria.append("how many of your interests (" + ", ".join(interests) + ") each destination is known for")
    if days:
        criteria.append(f"whether its usual suggested stay fits {days} day(s)")
    if origin_dest:
        criteria.append(f"straight-line distance from {origin_dest.name} (shorter is preferred for short trips)")
    if not criteria:
        criteria.append("a varied mix of popular destinations (tell me your interests to personalise this)")

    scored = []
    for d in DESTINATIONS:
        if d.name in excluded or d.kind == "state" or (domestic_only and d.country != "India"):
            continue
        m = matched(d, interests)
        if interests and not m:
            continue
        dist = _distance(origin_dest, d)
        fits = days >= d.suggested_days[0] if days else None
        # Lexicographic, explainable ordering: interest matches, fit, then proximity for short trips.
        proximity = -(dist or 0) if days and days <= 4 and dist is not None else 0
        scored.append(((len(m), fits is not False, proximity), d, m, dist, fits))
    scored.sort(key=lambda s: s[0], reverse=True)
    # Without interests, avoid near-duplicates by keeping a spread of landscapes.
    recs: list[Recommendation] = []
    seen_landscapes: set[str] = set()
    for _, d, m, dist, fits in scored:
        if not interests and d.landscape in seen_landscapes:
            continue
        seen_landscapes.add(d.landscape)
        reasons = []
        if m:
            reasons.append("Known for " + ", ".join(m))
        reasons.append(f"Landscape: {d.landscape}")
        if fits is not None:
            lo, hi = d.suggested_days
            reasons.append(f"Typical stay {lo}–{hi} days" + (" — fits your trip" if fits else
                                                              " — your trip may feel rushed"))
        if dist is not None:
            reasons.append(f"About {dist} km from {origin_dest.name} in a straight line (road distance is longer)")
        recs.append(Recommendation(d, m, reasons, dist, fits,
                                   f"/knowledge/demo/{d.guide_slug}" if d.guide_slug else None))
        if len(recs) >= limit:
            break
    return recs, criteria


def compare(names: list[str], *, interests: list[str], origin: str | None, days: int | None) -> list[ComparisonRow]:
    origin_dest = get_destination(origin) if origin else None
    rows = []
    for name in names:
        d = get_destination(name)
        if d is None:
            continue
        rows.append(ComparisonRow(
            destination=d, matched_interests=matched(d, interests), straight_line_km=_distance(origin_dest, d),
            suggested_days=d.suggested_days, fits_days=(days >= d.suggested_days[0]) if days else None,
            guide_url=f"/knowledge/demo/{d.guide_slug}" if d.guide_slug else None,
        ))
    return rows
