"""Chat and conversation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.itinerary import BudgetEstimate, ItineraryPlan
from app.schemas.travel import PlaceSearchResult, RouteResult, TransportInfo


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=32)
    source_ids: list[str] | None = Field(default=None, max_length=20)


class CitationOut(BaseModel):
    id: str
    url: str
    title: str
    heading: str | None = None
    snippet: str
    is_demo: bool
    fetched_at: str | None = None
    published_at: str | None = None


class PlacesBlock(BaseModel):
    type: Literal["places"] = "places"
    result: PlaceSearchResult


class ItineraryBlock(BaseModel):
    type: Literal["itinerary"] = "itinerary"
    itinerary_id: str
    title: str
    version: int
    plan: ItineraryPlan
    changes: list[str] = Field(default_factory=list)


class RouteBlock(BaseModel):
    type: Literal["route"] = "route"
    route: RouteResult


class RecommendationItem(BaseModel):
    name: str
    state: str
    country: str
    matched_interests: list[str]
    reasons: list[str]
    guide_url: str | None = None
    straight_line_km: int | None = None


class RecommendationsBlock(BaseModel):
    type: Literal["recommendations"] = "recommendations"
    criteria: list[str]
    items: list[RecommendationItem]
    note: str


class ComparisonItem(BaseModel):
    name: str
    landscape: str
    known_for: list[str]
    matched_interests: list[str]
    suggested_days: str
    fits_days: bool | None = None
    straight_line_km: int | None = None
    guide_url: str | None = None


class ComparisonBlock(BaseModel):
    type: Literal["comparison"] = "comparison"
    criteria: list[str]
    items: list[ComparisonItem]
    note: str


class BudgetBlock(BaseModel):
    type: Literal["budget"] = "budget"
    estimate: BudgetEstimate


class TransportBlock(BaseModel):
    type: Literal["transport"] = "transport"
    info: TransportInfo


class ClarifyBlock(BaseModel):
    type: Literal["clarify"] = "clarify"
    question: str
    missing: list[str]
    options: list[str] = Field(default_factory=list)


Block = Annotated[
    PlacesBlock | ItineraryBlock | RouteBlock | RecommendationsBlock | ComparisonBlock | BudgetBlock
    | TransportBlock | ClarifyBlock,
    Field(discriminator="type"),
]


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    user_message_id: str
    answer: str
    language: str
    intent: str
    classifier: str
    entities: dict[str, Any]
    citations: list[CitationOut] = Field(default_factory=list)
    evidence: Literal["strong", "limited", "none"] | None = None
    answer_mode: Literal["llm", "extractive", "template", "none"] = "template"
    blocks: list[Block] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]
    context: dict[str, Any] = Field(default_factory=dict)


class Page(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int
