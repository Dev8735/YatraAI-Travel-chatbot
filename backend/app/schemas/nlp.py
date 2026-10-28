"""Typed NLP outputs."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Intent(StrEnum):
    WEBSITE_QA = "website_qa"
    DESTINATION_DISCOVERY = "destination_discovery"
    PLACE_SEARCH = "place_search"
    HOTEL_SEARCH = "hotel_search"
    ITINERARY_CREATE = "itinerary_create"
    ITINERARY_MODIFY = "itinerary_modify"
    DESTINATION_COMPARE = "destination_compare"
    BUDGET_ESTIMATE = "budget_estimate"
    ROUTE_LOOKUP = "route_lookup"
    TRANSPORT_INFO = "transport_info"
    FOLLOW_UP = "follow_up_clarification"
    GREETING_HELP = "greeting_help"
    UNKNOWN = "unknown"


class Money(BaseModel):
    amount: float = Field(gt=0, lt=1e10)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    qualifier: Literal["max", "approx", "min"] = "approx"
    per_person: bool = False


class DateRange(BaseModel):
    start: date | None = None
    end: date | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    text: str = ""

    @field_validator("end")
    @classmethod
    def _order(cls, v: date | None, info) -> date | None:  # noqa: ANN001
        start = info.data.get("start")
        if v and start and v < start:
            raise ValueError("end date before start date")
        return v


class Entities(BaseModel):
    destinations: list[str] = Field(default_factory=list)
    origin: str | None = None
    destination: str | None = None
    dates: DateRange | None = None
    duration_days: int | None = Field(default=None, ge=1, le=60)
    travellers: int | None = Field(default=None, ge=1, le=100)
    budget: Money | None = None
    budget_level: Literal["budget", "mid", "luxury"] | None = None
    interests: list[str] = Field(default_factory=list)
    accommodation: list[str] = Field(default_factory=list)
    transport_mode: str | None = None
    pace: Literal["relaxed", "balanced", "packed"] | None = None
    accessibility: list[str] = Field(default_factory=list)
    place_category: str | None = None
    refers_to_previous: bool = False  # "that place", "there", "wahan", "वहाँ", "ત્યાં"

    def merged_with(self, other: Entities) -> Entities:
        """Values in ``self`` win; gaps are filled from ``other`` (e.g. conversation context)."""
        data = other.model_dump()
        for key, value in self.model_dump().items():
            if value not in (None, [], False):
                data[key] = value
        return Entities.model_validate(data)


class NLUResult(BaseModel):
    text: str
    language: Literal["en", "hi", "gu", "hinglish"]
    intent: Intent
    # Rule-match strength in [0, 1]; used internally for routing, not shown as a percentage.
    intent_score: float = 0.0
    matched_rules: list[str] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    missing: list[str] = Field(default_factory=list)
    classifier: Literal["rules", "llm", "context"] = "rules"
