"""Itinerary persistence and edits (shared by the REST API and the chat flow)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.models import Itinerary
from app.nlp.gazetteer import get_destination
from app.providers.places.base import PlacesProvider
from app.schemas.itinerary import (
    AddDay,
    AddStop,
    ItineraryOperation,
    ItineraryOut,
    ItineraryPlan,
    ItineraryRequest,
    ItinerarySummary,
    MoveStop,
    RegenerateDay,
    RemoveDay,
    RemoveStop,
    Rename,
    ReplaceStop,
    UpdatePreferences,
)
from app.schemas.travel import Place
from app.services import itinerary_engine as engine


async def gather_candidates(places: PlacesProvider, request: ItineraryRequest) -> tuple[list[Place], str, str]:
    """Collect candidate places: general attractions plus one query per interest (live providers)."""
    dest = get_destination(request.destination)
    near = dest.name if dest else request.destination
    lat, lng = (dest.lat, dest.lng) if dest else (None, None)
    queries = [f"top tourist attractions in {near}"]
    if places.is_live:
        queries += [f"{interest} places in {near}" for interest in request.interests[:3]]
    found: dict[str, Place] = {}
    origin = "live" if places.is_live else "demo"
    for q in queries:
        result = await places.search(q, near=near, lat=lat, lng=lng, category="tourist_attraction", limit=20)
        for p in result.places:
            if p.destination is None:
                p = p.model_copy(update={"destination": near})
            found.setdefault(p.id, p)
    return list(found.values()), places.name, origin


def to_out(row: Itinerary) -> ItineraryOut:
    return ItineraryOut(id=row.id, title=row.title, conversation_id=row.conversation_id,
                        request=ItineraryRequest.model_validate(row.request),
                        plan=ItineraryPlan.model_validate(row.plan), version=row.version,
                        created_at=row.created_at, updated_at=row.updated_at)


def summary(row: Itinerary) -> ItinerarySummary:
    plan = row.plan or {}
    return ItinerarySummary(id=row.id, title=row.title, destination=plan.get("destination", ""),
                            days=len(plan.get("days", [])), version=row.version, updated_at=row.updated_at)


async def create_itinerary(session: AsyncSession, places: PlacesProvider, client_id: str, request: ItineraryRequest,
                           conversation_id: str | None = None) -> Itinerary:
    candidates, provider, origin = await gather_candidates(places, request)
    plan = engine.build_plan(request, candidates, provider=provider, data_origin=origin)
    dest = plan.destination
    title = f"{request.days}-day {dest} trip"
    row = Itinerary(client_id=client_id, conversation_id=conversation_id, title=title,
                    request=request.model_dump(mode="json"), plan=plan.model_dump(mode="json"), version=1)
    session.add(row)
    await session.commit()
    return row


async def get_owned(session: AsyncSession, client_id: str, itinerary_id: str) -> Itinerary:
    row = await session.get(Itinerary, itinerary_id)
    if row is None or row.client_id != client_id:
        raise NotFoundError("Itinerary not found.")
    return row


async def list_itineraries(session: AsyncSession, client_id: str, limit: int, offset: int) -> list[Itinerary]:
    rows = await session.execute(select(Itinerary).where(Itinerary.client_id == client_id)
                                 .order_by(Itinerary.updated_at.desc()).limit(limit).offset(offset))
    return list(rows.scalars())


async def apply_operations(session: AsyncSession, places: PlacesProvider, row: Itinerary,
                           operations: list[ItineraryOperation], expected_version: int | None = None) -> list[str]:
    """Apply edits atomically. Returns human-readable change descriptions."""
    if expected_version is not None and expected_version != row.version:
        raise ConflictError("This itinerary was changed elsewhere. Reload and try again.",
                            details={"current_version": row.version})
    request = ItineraryRequest.model_validate(row.request)
    plan = ItineraryPlan.model_validate(row.plan)
    title = row.title
    changes: list[str] = []
    try:
        for op in operations:
            if isinstance(op, RemoveStop):
                removed = engine.remove_stop(plan, request, op.stop_id)
                changes.append(f"Removed {removed.name}.")
            elif isinstance(op, AddStop):
                added = engine.add_stop(plan, request, op.day, op.place_id)
                changes.append(f"Added {added.name} to day {op.day}.")
            elif isinstance(op, MoveStop):
                engine.move_stop(plan, request, op.stop_id, op.to_day, op.position)
                changes.append(f"Moved a stop to day {op.to_day}.")
            elif isinstance(op, ReplaceStop):
                engine.replace_stop(plan, request, op.stop_id, op.place_id)
                changes.append("Replaced a stop.")
            elif isinstance(op, AddDay):
                engine.add_day(plan, request)
                request = request.model_copy(update={"days": len(plan.days)})
                changes.append(f"Added day {len(plan.days)}.")
            elif isinstance(op, RemoveDay):
                engine.remove_day(plan, request, op.day)
                request = request.model_copy(update={"days": len(plan.days)})
                changes.append(f"Removed day {op.day}.")
            elif isinstance(op, RegenerateDay):
                engine.regenerate_day(plan, request, op.day)
                changes.append(f"Regenerated day {op.day}.")
            elif isinstance(op, UpdatePreferences):
                updates = {k: v for k, v in op.model_dump(exclude={"op"}).items() if v is not None}
                request = request.model_copy(update=updates)
                if {"pace", "interests", "start_date"} & updates.keys():
                    candidates, provider, origin = await gather_candidates(places, request)
                    plan = engine.build_plan(request, candidates, provider=provider, data_origin=origin,
                                             excluded=set(plan.excluded_place_ids))
                    changes.append("Regenerated the plan with your updated preferences.")
                elif "budget_level" in updates:
                    changes.append(f"Switched the budget estimate to the '{updates['budget_level']}' tier.")
                else:
                    changes.append("Updated preferences.")
            elif isinstance(op, Rename):
                title = op.title
                changes.append("Renamed the itinerary.")
    except KeyError as exc:
        raise NotFoundError("A stop or place in this edit no longer exists in the itinerary.") from exc
    except IndexError as exc:
        raise AppError("That day does not exist in this itinerary.", code="invalid_day") from exc
    except ValueError as exc:
        raise AppError(str(exc), code="invalid_edit") from exc

    engine.refresh_budget(plan, request)
    row.title = title
    row.request = request.model_dump(mode="json")
    row.plan = plan.model_dump(mode="json")
    row.version += 1
    await session.commit()
    return changes
