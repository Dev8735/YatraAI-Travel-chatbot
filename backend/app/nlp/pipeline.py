"""NLU pipeline: language → entities → intent → context resolution → missing-slot check."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.llm.base import ChatTurn, LLMError, LLMProvider
from app.nlp.entities import extract_entities
from app.nlp.intents import classify
from app.nlp.language import detect_language, normalize_digits
from app.schemas.nlp import Entities, Intent, NLUResult

log = get_logger(__name__)

REQUIRED_SLOTS: dict[Intent, list[str]] = {
    Intent.ITINERARY_CREATE: ["destination", "duration_days"],
    Intent.DESTINATION_COMPARE: ["destinations>=2"],
    Intent.ROUTE_LOOKUP: ["origin", "destination"],
    Intent.PLACE_SEARCH: ["destination"],
    Intent.HOTEL_SEARCH: ["destination"],
    Intent.BUDGET_ESTIMATE: ["destination", "duration_days"],
    Intent.TRANSPORT_INFO: [],
}


def _missing(intent: Intent, e: Entities) -> list[str]:
    missing = []
    for slot in REQUIRED_SLOTS.get(intent, []):
        if slot == "destinations>=2":
            if len(e.destinations) < 2:
                missing.append("destinations")
        elif getattr(e, slot) in (None, [], ""):
            missing.append(slot)
    return missing


def context_entities(context: dict[str, Any]) -> Entities:
    """Entities remembered from earlier turns (bounded, structured state — not raw text)."""
    try:
        return Entities.model_validate(context.get("entities") or {})
    except ValidationError:
        return Entities()


def analyze(text: str, context: dict[str, Any] | None = None, *, today: date | None = None) -> NLUResult:
    context = context or {}
    clean = normalize_digits(text).strip()
    language = detect_language(clean)
    entities = extract_entities(clean, today=today)
    pending = context.get("pending") or None
    has_itinerary = bool(context.get("itinerary_id"))
    intent, score, matched = classify(clean.lower(), entities, has_itinerary=has_itinerary,
                                      awaiting_slot=bool(pending))
    classifier = "rules"

    remembered = context_entities(context)
    if intent == Intent.FOLLOW_UP and pending:
        # Resume the intent we asked about, merging the newly supplied slot values.
        intent = Intent(pending["intent"])
        base = Entities.model_validate(pending.get("entities") or {})
        entities = entities.merged_with(base)
        if not entities.destination and entities.destinations:
            entities.destination = entities.destinations[0]
        classifier = "context"
    elif intent in (Intent.ITINERARY_MODIFY, Intent.BUDGET_ESTIMATE, Intent.PLACE_SEARCH, Intent.HOTEL_SEARCH,
                    Intent.TRANSPORT_INFO, Intent.ROUTE_LOOKUP, Intent.WEBSITE_QA, Intent.ITINERARY_CREATE):
        # Fill a missing destination from context. Questions and new plans only inherit it when the
        # user refers back ("there", "that place"); edits, budgets and searches are follow-ups by nature.
        inherits = entities.refers_to_previous or intent in (
            Intent.ITINERARY_MODIFY, Intent.BUDGET_ESTIMATE, Intent.PLACE_SEARCH, Intent.HOTEL_SEARCH)
        if not entities.destination and remembered.destination and inherits:
            entities.destination = remembered.destination
            if remembered.destination not in entities.destinations:
                entities.destinations = [*entities.destinations, remembered.destination]
        if intent == Intent.BUDGET_ESTIMATE and not entities.duration_days:
            entities.duration_days = remembered.duration_days
        if intent == Intent.BUDGET_ESTIMATE and not entities.travellers:
            entities.travellers = remembered.travellers
    elif intent == Intent.DESTINATION_COMPARE and len(entities.destinations) == 1 and remembered.destination \
            and remembered.destination not in entities.destinations:
        entities.destinations = [remembered.destination, *entities.destinations]

    if intent == Intent.ROUTE_LOOKUP and not entities.origin and len(entities.destinations) >= 2:
        entities.origin, entities.destination = entities.destinations[0], entities.destinations[1]

    missing = _missing(intent, entities)
    if intent == Intent.ITINERARY_CREATE and "duration_days" in missing and entities.dates and entities.dates.start:
        missing.remove("duration_days")
    return NLUResult(text=text, language=language, intent=intent, intent_score=score, matched_rules=matched,
                     entities=entities, missing=missing, classifier=classifier)


_LLM_CLASSIFIER_PROMPT = (
    "You classify a travel assistant user's message. Reply with JSON only, no prose: "
    '{"intent": one of [' + ", ".join(f'"{i.value}"' for i in Intent) + "]}. "
    "Pick website_qa for factual questions about places or travel information, unknown if unrelated to travel."
)


async def llm_classify(text: str, llm: LLMProvider) -> Intent | None:
    """Fallback for messages no rule matched. Output is validated against the Intent enum."""
    if not llm.is_live:
        return None
    try:
        raw = await llm.complete(_LLM_CLASSIFIER_PROMPT, [ChatTurn("user", text[:500])], max_tokens=200)
    except LLMError:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return Intent(json.loads(m.group(0)).get("intent"))
    except (ValueError, json.JSONDecodeError, AttributeError):
        log.info("llm classifier returned an invalid label")
        return None
