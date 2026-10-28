"""Itinerary engine: creation, grouping, scheduling, edits and budget estimates."""

from datetime import date

import pytest

from app.providers.places.demo import load_demo_places
from app.schemas.itinerary import ItineraryRequest
from app.schemas.nlp import Money
from app.schemas.travel import Place
from app.services import itinerary_engine as engine


def jaipur(**kw) -> tuple[ItineraryRequest, list[Place]]:
    req = ItineraryRequest(destination="Jaipur", days=kw.pop("days", 2), interests=kw.pop("interests", ["heritage"]),
                           **kw)
    return req, [p for p in load_demo_places() if p.destination == "Jaipur"]


def all_place_ids(plan) -> list[str]:  # noqa: ANN001
    return [s.place.id for d in plan.days for s in d.stops]


def test_build_plan_structure_and_no_duplicates() -> None:
    req, places = jaipur(days=2, start_date=date(2026, 12, 1))
    plan = engine.build_plan(req, places, provider="demo_dataset", data_origin="demo")
    assert len(plan.days) == 2
    ids = all_place_ids(plan)
    assert len(ids) == len(set(ids)) and 4 <= len(ids) <= 8
    assert plan.days[1].date == date(2026, 12, 2)
    assert plan.data_origin == "demo" and any("Demo mode" in w for w in plan.warnings)
    assert any("not a guarantee" in w for w in plan.warnings)
    for day in plan.days:
        times = [s.start_time for s in day.stops]
        assert times == sorted(times) and times[0] == "09:00"
        assert any(b.label == "Lunch break" for b in day.breaks)
        for s in day.stops:
            assert s.reason and not s.hours_verified  # demo data has no verified hours
            assert any("not verified" in n for n in s.notes)


def test_interest_matching_prioritises_relevant_places() -> None:
    req, places = jaipur(days=1, interests=["shopping"], pace="relaxed")
    plan = engine.build_plan(req, places, provider="demo", data_origin="demo")
    first = plan.days[0].stops
    assert any("Johari Bazaar" == s.place.name for s in first)
    assert "shopping" in next(s for s in first if s.place.name == "Johari Bazaar").reason


def test_pace_changes_stop_count() -> None:
    relaxed = engine.build_plan(jaipur(days=1, pace="relaxed")[0], jaipur()[1], provider="d", data_origin="demo")
    packed = engine.build_plan(jaipur(days=1, pace="packed")[0], jaipur()[1], provider="d", data_origin="demo")
    assert len(relaxed.days[0].stops) < len(packed.days[0].stops)


def test_days_are_geographically_compact() -> None:
    req, places = jaipur(days=2, interests=[])
    plan = engine.build_plan(req, places, provider="d", data_origin="demo")
    # Amber Fort (north) and Albert Hall (south) should not be paired if they're on different ends.
    for day in plan.days:
        located = [s for s in day.stops if s.transfer_minutes_before is not None]
        assert all(s.transfer_minutes_before < 90 for s in located)


def test_closed_day_from_provider_hours_is_flagged() -> None:
    place = load_demo_places()[0].model_copy(update={
        "opening_hours": ["Monday: Closed", "Tuesday: 9:00 AM – 5:00 PM"], "data_origin": "live"})
    req = ItineraryRequest(destination="Jaipur", days=1, start_date=date(2026, 11, 2))  # a Monday
    plan = engine.build_plan(req, [place], provider="google_places", data_origin="live")
    stop = plan.days[0].stops[0]
    assert stop.hours_verified and any("closed on Monday" in n for n in stop.notes)


def test_edit_operations() -> None:
    req, places = jaipur(days=2)
    plan = engine.build_plan(req, places, provider="d", data_origin="demo")
    first = plan.days[0].stops[0]

    removed = engine.remove_stop(plan, req, first.id)
    assert removed.id not in all_place_ids(plan) and removed.id in plan.excluded_place_ids

    engine.add_day(plan, req)
    assert len(plan.days) == 3 and plan.days[2].day == 3
    assert removed.id not in all_place_ids(plan)  # excluded places are not re-added automatically

    target = plan.days[1].stops[0]
    engine.move_stop(plan, req, target.id, to_day=1, position=0)
    assert plan.days[0].stops[0].place.id == target.place.id

    engine.remove_day(plan, req, 2)
    assert [d.day for d in plan.days] == [1, 2]

    if plan.unplaced:
        spare = plan.unplaced[0]
        engine.add_stop(plan, req, 1, spare.id)
        assert spare.id in all_place_ids(plan)

    with pytest.raises(KeyError):
        engine.remove_stop(plan, req, "missing")
    with pytest.raises(IndexError):
        engine.move_stop(plan, req, plan.days[0].stops[0].id, to_day=9, position=None)


def test_cannot_remove_last_day() -> None:
    req, places = jaipur(days=1)
    plan = engine.build_plan(req, places, provider="d", data_origin="demo")
    with pytest.raises(ValueError):
        engine.remove_day(plan, req, 1)


def test_stop_ids_survive_rescheduling() -> None:
    req, places = jaipur(days=1, pace="packed")
    plan = engine.build_plan(req, places, provider="d", data_origin="demo")
    a, b = plan.days[0].stops[0].id, plan.days[0].stops[1].id
    engine.remove_stop(plan, req, a)
    engine.remove_stop(plan, req, b)  # still resolvable after the first edit re-timed the day
    assert a not in [s.id for s in plan.days[0].stops] and b not in [s.id for s in plan.days[0].stops]


def test_regenerate_day_keeps_other_days() -> None:
    req, places = jaipur(days=2)
    plan = engine.build_plan(req, places, provider="d", data_origin="demo")
    day2_before = [s.place.id for s in plan.days[1].stops]
    engine.regenerate_day(plan, req, 1)
    assert [s.place.id for s in plan.days[1].stops] == day2_before
    ids = all_place_ids(plan)
    assert len(ids) == len(set(ids))


def test_budget_estimate_is_labelled_and_compares_user_budget() -> None:
    req = ItineraryRequest(destination="Goa", days=3, travellers=2,
                           budget=Money(amount=15000, currency="INR", qualifier="max"))
    est = engine.estimate_budget(req, 3)
    assert est.tier == "budget"  # ₹15k / 2 people / 3 days = ₹2.5k pp/day → budget tier
    assert (est.total_min, est.total_max) == (1500 * 6, 3000 * 6)
    assert est.within_user_budget == "partly"  # ₹15k falls inside ₹9k–₹18k
    assert "not live prices" in est.basis and est.source_url == engine.BUDGET_SOURCE_URL
    assert not est.travellers_assumed


def test_lower_budget_tier() -> None:
    req = ItineraryRequest(destination="Goa", days=3, budget_level="luxury")
    assert engine.lower_budget_tier(req).budget_level == "mid"
    assert engine.lower_budget_tier(req.model_copy(update={"budget_level": "budget"})).budget_level == "budget"


def test_no_candidates_produces_free_days_with_warning() -> None:
    req = ItineraryRequest(destination="Nowhere", days=2)
    plan = engine.build_plan(req, [], provider="demo", data_origin="demo")
    assert all(not d.stops and d.title == "Free day" for d in plan.days)
    assert any("No places were available" in w for w in plan.warnings)
