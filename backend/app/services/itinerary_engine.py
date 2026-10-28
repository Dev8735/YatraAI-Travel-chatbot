"""Deterministic itinerary builder and editor.

Planning heuristics (all surfaced to the user as assumptions):
* stops per day by pace: relaxed 2–3, balanced 3–4, packed 4–5, bounded by a daily time window;
* places are ordered along a nearest-neighbour path and split into consecutive days, which
  keeps each day geographically compact and avoids backtracking;
* transfer times between stops are rough estimates from straight-line distance (~20 km/h
  city traffic + 10 min), never presented as routed travel times;
* a lunch break is inserted around 13:00;
* opening hours are only checked when the provider returned them.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime, timedelta

from app.nlp.gazetteer import get_destination, haversine_km
from app.schemas.itinerary import (
    Break,
    BudgetEstimate,
    Day,
    ItineraryPlan,
    ItineraryRequest,
    Stop,
)
from app.schemas.travel import Place

DAY_START = 9 * 60
DAY_END = {"relaxed": 18 * 60, "balanced": 19 * 60, "packed": 20 * 60}
MAX_STOPS = {"relaxed": 3, "balanced": 4, "packed": 5}
TARGET_STOPS = {"relaxed": 2, "balanced": 3, "packed": 4}
LUNCH_AT, LUNCH_MIN = 13 * 60, 60
DEFAULT_VISIT_MIN = 75
CITY_KMH, TRANSFER_BUFFER = 20.0, 10

TIERS: dict[str, tuple[int, int]] = {"budget": (1500, 3000), "mid": (3000, 7000), "luxury": (10000, 25000)}
TIER_ORDER = ["budget", "mid", "luxury"]
BUDGET_SOURCE_URL = "/knowledge/demo/budget-planning"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
INTEREST_LABEL = {"spiritual": "temples & spiritual sites", "beaches": "beaches", "museums": "museums"}


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _visit_minutes(place: Place, pace: str) -> int:
    base = place.typical_visit_minutes or DEFAULT_VISIT_MIN
    factor = {"relaxed": 1.15, "balanced": 1.0, "packed": 0.85}[pace]
    return int(round(base * factor / 15) * 15) or 15


def transfer_estimate(a: Place, b: Place) -> int | None:
    if None in (a.lat, a.lng, b.lat, b.lng):
        return None
    km = haversine_km((a.lat, a.lng), (b.lat, b.lng))  # type: ignore[arg-type]
    return int(math.ceil((km / CITY_KMH * 60 + TRANSFER_BUFFER) / 5) * 5)


def interest_matches(place: Place, interests: list[str]) -> list[str]:
    haystack = {t.lower() for t in place.tags} | {(place.category or "").lower()}
    haystack |= {t.lower() for t in place.types}
    aliases = {"spiritual": {"temple", "temples", "ghat", "ghats", "ashram", "spiritual", "church",
                             "hindu_temple", "place_of_worship"},
               "museums": {"museum", "museums", "art_gallery"},
               "heritage": {"heritage", "forts", "fort", "palace", "monument", "history", "historical_landmark",
                            "heritage_site", "architecture"},
               "nature": {"nature", "lake", "lakes", "waterfall", "garden", "national_park", "park"},
               "beaches": {"beach", "beaches"}, "shopping": {"market", "shopping", "shopping_mall"},
               "food": {"food", "market", "restaurant"}, "adventure": {"adventure", "rafting", "trekking"}}
    return [i for i in interests if haystack & (aliases.get(i, set()) | {i})]


def score_place(place: Place, interests: list[str]) -> float:
    score = 1.0 + 2.0 * len(interest_matches(place, interests))
    if place.rating is not None and place.user_rating_count:
        # Provider ratings nudge ordering only when there are enough reviews to mean something.
        weight = min(1.0, math.log10(max(place.user_rating_count, 1)) / 4)
        score += (place.rating - 4.0) * weight
    return score


def reason_for(place: Place, interests: list[str], destination: str) -> str:
    matched = interest_matches(place, interests)
    parts = []
    if matched:
        parts.append("Matches your interest in " + ", ".join(INTEREST_LABEL.get(m, m) for m in matched))
    elif interests:
        parts.append("Fills the day near your other stops")
    else:
        parts.append(f"A well-known sight in {destination}")
    if place.rating is not None and place.user_rating_count:
        parts.append(f"rated {place.rating:.1f} by {place.user_rating_count:,} Google reviewers")
    return "; ".join(parts) + "."


def order_by_proximity(places: list[Place]) -> list[Place]:
    """Nearest-neighbour path starting from the place farthest from the centroid."""
    located = [p for p in places if p.lat is not None and p.lng is not None]
    unlocated = [p for p in places if p not in located]
    if len(located) <= 2:
        return located + unlocated
    cy = sum(p.lat for p in located) / len(located)  # type: ignore[misc]
    cx = sum(p.lng for p in located) / len(located)  # type: ignore[misc]
    current = max(located, key=lambda p: haversine_km((cy, cx), (p.lat, p.lng)))  # type: ignore[arg-type]
    path, remaining = [current], [p for p in located if p is not current]
    while remaining:
        nxt = min(remaining, key=lambda p: haversine_km((current.lat, current.lng), (p.lat, p.lng)))  # type: ignore[arg-type]
        path.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return path + unlocated


def _hours_note(place: Place, day_date: date | None) -> tuple[list[str], bool]:
    if not place.opening_hours:
        return ["Opening hours not verified — check before visiting."], False
    if day_date is None:
        return ["Opening hours (provider): " + "; ".join(place.opening_hours[:2]) + "…"], True
    weekday = WEEKDAYS[day_date.weekday()]
    line = next((h for h in place.opening_hours if h.startswith(weekday)), None)
    if line is None:
        return ["Opening hours for this weekday not provided — check before visiting."], False
    if "closed" in line.lower():
        return [f"Provider lists this place as closed on {weekday}. Consider moving it."], True
    return [f"Provider hours — {line}"], True


def schedule_day(day_no: int, day_date: date | None, places: list[Place], request: ItineraryRequest,
                 destination: str, stop_ids: list[str | None] | None = None) -> Day:
    """Lay out stops in time. Existing stop ids are kept so clients can keep referring to them."""
    clock, stops, breaks, lunch_done = DAY_START, [], [], False
    prev: Place | None = None
    ids = stop_ids or [None] * len(places)
    for place, existing_id in zip(places, ids, strict=True):
        transfer = transfer_estimate(prev, place) if prev else None
        if transfer:
            clock += transfer
        if not lunch_done and clock >= LUNCH_AT - 30:
            breaks.append(Break(time=_fmt(clock), label="Lunch break", duration_minutes=LUNCH_MIN))
            clock += LUNCH_MIN
            lunch_done = True
        duration = _visit_minutes(place, request.pace)
        notes, verified = _hours_note(place, day_date)
        if place.data_origin == "demo":
            notes.append("Sample data: location approximate; visit time is a planning assumption.")
        stops.append(Stop(id=existing_id or uuid.uuid4().hex[:12], place=place, start_time=_fmt(clock),
                          end_time=_fmt(clock + duration), duration_minutes=duration,
                          transfer_minutes_before=transfer, transfer_is_estimate=True,
                          reason=reason_for(place, request.interests, destination), notes=notes,
                          hours_verified=verified))
        clock += duration
        prev = place
    if not lunch_done and stops:
        breaks.append(Break(time=_fmt(max(clock, LUNCH_AT)), label="Lunch break", duration_minutes=LUNCH_MIN))
    names = [s.place.name for s in stops[:2]]
    title = " & ".join(names) if names else "Free day"
    day_notes = []
    if not stops:
        day_notes.append("No further sights available in the current data — keep this day free, rest, "
                         "or plan a day trip.")
    elif clock > DAY_END[request.pace]:
        day_notes.append("This day runs late for your chosen pace; consider moving a stop.")
    return Day(day=day_no, date=day_date, title=title, stops=stops, breaks=breaks, notes=day_notes)


def _fits(places: list[Place], request: ItineraryRequest) -> bool:
    if len(places) > MAX_STOPS[request.pace]:
        return False
    minutes, prev = 0, None
    for p in places:
        minutes += _visit_minutes(p, request.pace) + ((transfer_estimate(prev, p) or 0) if prev else 0)
        prev = p
    return DAY_START + minutes + LUNCH_MIN <= DAY_END[request.pace]


def split_into_days(ordered: list[Place], request: ItineraryRequest) -> tuple[list[list[Place]], list[Place]]:
    days: list[list[Place]] = [[] for _ in range(request.days)]
    target = TARGET_STOPS[request.pace]
    idx = 0
    leftovers: list[Place] = []
    for place in ordered:
        while idx < request.days and (len(days[idx]) >= target or not _fits(days[idx] + [place], request)):
            if not days[idx] and not _fits([place], request):
                break  # a single very long visit still gets its own day
            idx += 1
        if idx >= request.days:
            leftovers.append(place)
            continue
        days[idx].append(place)
    return days, leftovers


def estimate_budget(request: ItineraryRequest, days: int) -> BudgetEstimate:
    travellers = request.travellers or 1
    tier = request.budget_level
    if tier is None and request.budget and request.budget.currency == "INR":
        per_head = request.budget.amount if request.budget.per_person else request.budget.amount / travellers
        per_day = per_head / max(days, 1)
        tier = "budget" if per_day < 3000 else "mid" if per_day < 9000 else "luxury"
    tier = tier or "mid"
    lo, hi = TIERS[tier]
    total_min, total_max = lo * days * travellers, hi * days * travellers
    within = "unknown"
    if request.budget and request.budget.currency == "INR":
        user_total = request.budget.amount * (travellers if request.budget.per_person else 1)
        within = "yes" if user_total >= total_max else "no" if user_total < total_min else "partly"
    return BudgetEstimate(
        tier=tier, per_person_per_day_min=lo, per_person_per_day_max=hi, days=days, travellers=travellers,
        travellers_assumed=request.travellers is None, total_min=total_min, total_max=total_max,
        user_budget=request.budget, within_user_budget=within,
        basis="YatraAI planning assumptions (per person per day), not live prices.",
        excludes=["intercity travel (flights/trains)", "shopping", "special activities and guided tours"],
        source_url=BUDGET_SOURCE_URL,
    )


def build_plan(request: ItineraryRequest, candidates: list[Place], *, provider: str, data_origin: str,
               excluded: set[str] | None = None) -> ItineraryPlan:
    excluded = excluded or set()
    dest = get_destination(request.destination)
    destination = dest.name if dest else request.destination
    pool = [p for p in candidates if p.id not in excluded]
    pool.sort(key=lambda p: score_place(p, request.interests), reverse=True)
    wanted = request.days * TARGET_STOPS[request.pace]
    chosen, spare = pool[:wanted], pool[wanted:]
    day_groups, leftovers = split_into_days(order_by_proximity(chosen), request)
    days = [schedule_day(i + 1, request.start_date + timedelta(days=i) if request.start_date else None,
                         group, request, destination) for i, group in enumerate(day_groups)]

    assumptions = [
        "Stops are grouped by approximate location to limit backtracking.",
        "Transfer times are rough estimates from straight-line distance (≈20 km/h + 10 min), not routed times.",
        f"Pace '{request.pace}': about {TARGET_STOPS[request.pace]} stops per day between 09:00 and "
        f"{_fmt(DAY_END[request.pace])}, with a lunch break.",
    ]
    warnings = ["Opening hours, ticket availability and closures have not all been verified. "
                "This plan is a suggestion, not a guarantee of feasibility."]
    if data_origin == "demo":
        warnings.insert(0, "Demo mode: stops come from YatraAI's sample landmark dataset, not live place data.")
    if not candidates:
        warnings.insert(0, f"No places were available for {destination} from the current provider.")
    if request.accessibility:
        warnings.append("Accessibility needs noted (" + ", ".join(request.accessibility) + "). Step-free access "
                        "and walking distances at each site are not verified — please confirm locally.")
    if request.transport_mode:
        assumptions.append(f"Preferred transport: {request.transport_mode.lower().replace('_', ' ')}.")
    if request.budget and request.budget.currency != "INR":
        warnings.append(f"Budget given in {request.budget.currency}; estimates below are in INR and no live "
                        "exchange rate is applied.")
    return ItineraryPlan(
        destination=destination, days=days, unplaced=leftovers + spare, excluded_place_ids=sorted(excluded),
        assumptions=assumptions, warnings=warnings, budget_estimate=estimate_budget(request, request.days),
        data_origin="live" if data_origin == "live" else "demo", provider=provider,
        generated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------- edits
def _reschedule(plan: ItineraryPlan, request: ItineraryRequest, day_index: int) -> None:
    day = plan.days[day_index]
    places = [s.place for s in day.stops]
    ids = [None if s.id == "tmp" else s.id for s in day.stops]
    plan.days[day_index] = schedule_day(day.day, day.date, places, request, plan.destination, ids)


def _find_stop(plan: ItineraryPlan, stop_id: str) -> tuple[int, int]:
    for di, day in enumerate(plan.days):
        for si, stop in enumerate(day.stops):
            if stop.id == stop_id:
                return di, si
    raise KeyError(stop_id)


def _take_place(plan: ItineraryPlan, place_id: str) -> Place:
    for i, p in enumerate(plan.unplaced):
        if p.id == place_id:
            return plan.unplaced.pop(i)
    raise KeyError(place_id)


def _renumber(plan: ItineraryPlan, request: ItineraryRequest) -> None:
    for i in range(len(plan.days)):
        plan.days[i].day = i + 1
        plan.days[i].date = request.start_date + timedelta(days=i) if request.start_date else None
        _reschedule(plan, request, i)


def remove_stop(plan: ItineraryPlan, request: ItineraryRequest, stop_id: str) -> Place:
    di, si = _find_stop(plan, stop_id)
    stop = plan.days[di].stops.pop(si)
    if stop.place.id not in plan.excluded_place_ids:
        plan.excluded_place_ids.append(stop.place.id)
    _reschedule(plan, request, di)
    return stop.place


def add_stop(plan: ItineraryPlan, request: ItineraryRequest, day: int, place_id: str) -> Place:
    if not 1 <= day <= len(plan.days):
        raise IndexError(day)
    place = _take_place(plan, place_id)
    plan.days[day - 1].stops.append(Stop(id="tmp", place=place, start_time="00:00", end_time="00:00",
                                         duration_minutes=0, reason=""))
    if place.id in plan.excluded_place_ids:
        plan.excluded_place_ids.remove(place.id)
    _reschedule(plan, request, day - 1)
    return place


def move_stop(plan: ItineraryPlan, request: ItineraryRequest, stop_id: str, to_day: int,
              position: int | None) -> None:
    if not 1 <= to_day <= len(plan.days):
        raise IndexError(to_day)
    di, si = _find_stop(plan, stop_id)
    stop = plan.days[di].stops.pop(si)
    target = plan.days[to_day - 1].stops
    target.insert(len(target) if position is None else min(position, len(target)), stop)
    _reschedule(plan, request, di)
    if to_day - 1 != di:
        _reschedule(plan, request, to_day - 1)


def replace_stop(plan: ItineraryPlan, request: ItineraryRequest, stop_id: str, place_id: str) -> None:
    di, si = _find_stop(plan, stop_id)
    new_place = _take_place(plan, place_id)
    old = plan.days[di].stops[si]
    plan.days[di].stops[si] = old.model_copy(update={"place": new_place})
    plan.unplaced.append(old.place)
    _reschedule(plan, request, di)


def add_day(plan: ItineraryPlan, request: ItineraryRequest) -> None:
    pool = [p for p in plan.unplaced if p.id not in plan.excluded_place_ids]
    pool.sort(key=lambda p: score_place(p, request.interests), reverse=True)
    picked = order_by_proximity(pool[:TARGET_STOPS[request.pace]])
    picked_ids = {p.id for p in picked}
    plan.unplaced = [p for p in plan.unplaced if p.id not in picked_ids]
    n = len(plan.days) + 1
    plan.days.append(schedule_day(n, request.start_date + timedelta(days=n - 1) if request.start_date else None,
                                  picked, request, plan.destination))


def remove_day(plan: ItineraryPlan, request: ItineraryRequest, day: int) -> None:
    if len(plan.days) <= 1:
        raise ValueError("An itinerary needs at least one day.")
    if not 1 <= day <= len(plan.days):
        raise IndexError(day)
    removed = plan.days.pop(day - 1)
    plan.unplaced = [s.place for s in removed.stops] + plan.unplaced
    _renumber(plan, request)


def regenerate_day(plan: ItineraryPlan, request: ItineraryRequest, day: int) -> None:
    if not 1 <= day <= len(plan.days):
        raise IndexError(day)
    current = [s.place for s in plan.days[day - 1].stops]
    pool = [p for p in current + plan.unplaced if p.id not in plan.excluded_place_ids]
    if not pool:
        return
    # Re-pick around the best-scoring available place, preferring ones close to it.
    pool.sort(key=lambda p: score_place(p, request.interests), reverse=True)
    anchor = pool[0]
    if anchor.lat is not None and anchor.lng is not None:
        pool.sort(key=lambda p: (haversine_km((anchor.lat, anchor.lng), (p.lat, p.lng))  # type: ignore[arg-type]
                                 if p.lat is not None and p.lng is not None else 1e9)
                  - score_place(p, request.interests))
    picked: list[Place] = []
    for p in pool:
        if len(picked) >= TARGET_STOPS[request.pace]:
            break
        if _fits(picked + [p], request):
            picked.append(p)
    picked = order_by_proximity(picked)
    picked_ids = {p.id for p in picked}
    plan.unplaced = [p for p in pool if p.id not in picked_ids]
    day_obj = plan.days[day - 1]
    plan.days[day - 1] = schedule_day(day, day_obj.date, picked, request, plan.destination)


def lower_budget_tier(request: ItineraryRequest) -> ItineraryRequest:
    current = request.budget_level or (estimate_budget(request, request.days).tier)
    idx = max(0, TIER_ORDER.index(current) - 1)
    return request.model_copy(update={"budget_level": TIER_ORDER[idx]})


def refresh_budget(plan: ItineraryPlan, request: ItineraryRequest) -> None:
    plan.budget_estimate = estimate_budget(request, len(plan.days))
