"""Chat orchestration: NLU → intent handler → grounded/structured response → persistence.

Handlers return structured blocks (place cards, itineraries, routes, comparisons). Free text
is either templated (deterministic) or produced by the grounded RAG pipeline. The LLM never
produces place data, prices, routes or schedules.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ProviderError
from app.core.logging import get_logger
from app.db.models import Chunk, Document, Message, utcnow
from app.nlp.gazetteer import get_destination
from app.nlp.pipeline import analyze, llm_classify
from app.rag.answer import Citation, GroundedAnswer, generate_answer
from app.schemas.chat import (
    BudgetBlock,
    ChatResponse,
    CitationOut,
    ClarifyBlock,
    ComparisonBlock,
    ComparisonItem,
    ItineraryBlock,
    PlacesBlock,
    RecommendationItem,
    RecommendationsBlock,
    RouteBlock,
    TransportBlock,
)
from app.schemas.itinerary import (
    AddDay,
    AddStop,
    ItineraryPlan,
    ItineraryRequest,
    MoveStop,
    RegenerateDay,
    RemoveDay,
    RemoveStop,
    ReplaceStop,
    UpdatePreferences,
)
from app.schemas.nlp import Entities, Intent, NLUResult
from app.schemas.travel import RouteRequest
from app.services import conversation_service as conversations
from app.services import discovery, itinerary_service
from app.services import itinerary_engine as engine
from app.services.container import Container
from app.services.i18n import t

log = get_logger(__name__)
ROUTE_MODES = {"DRIVE": "DRIVE", "TWO_WHEELER": "TWO_WHEELER", "WALK": "WALK", "TRAIN": "TRANSIT",
               "BUS": "TRANSIT", "TRANSIT": "TRANSIT"}


@dataclass
class TurnResult:
    answer: str = ""
    blocks: list[Any] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    evidence: str | None = None
    mode: str = "template"
    suggestions: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    context_updates: dict[str, Any] = field(default_factory=dict)


def _citation_out(c: Citation) -> CitationOut:
    return CitationOut(id=c.id, url=c.url, title=c.title, heading=c.heading, snippet=c.snippet, is_demo=c.is_demo,
                       fetched_at=c.fetched_at, published_at=c.published_at)


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


class ChatService:
    def __init__(self, c: Container, session: AsyncSession, client_id: str) -> None:
        self.c = c
        self.session = session
        self.client_id = client_id
        self.conversation_id: str | None = None

    # ------------------------------------------------------------------ entry point
    async def handle(self, message: str, conversation_id: str | None,
                     source_ids: list[str] | None = None) -> AsyncIterator[tuple[str, Any]]:
        """Yields ("meta", dict), ("delta", str)... and finally ("final", ChatResponse)."""
        conv = await (conversations.get_owned(self.session, self.client_id, conversation_id) if conversation_id
                      else conversations.create(self.session, self.client_id))
        history = await conversations.recent_history(self.session, conv.id, self.c.settings.history_turns)
        if history and history[-1].role == "user":
            history.pop()
        context = dict(conv.context or {})
        self.conversation_id = conv.id

        nlu = analyze(message, context)
        if nlu.intent == Intent.UNKNOWN and self.c.llm.is_live:
            guessed = await llm_classify(message, self.c.llm)
            if guessed and guessed not in (Intent.FOLLOW_UP, Intent.UNKNOWN):
                nlu = nlu.model_copy(update={"intent": guessed, "classifier": "llm"})

        user_msg = Message(conversation_id=conv.id, role="user", content=message,
                           meta={"language": nlu.language, "intent": nlu.intent.value})
        self.session.add(user_msg)
        await self.session.flush()
        yield "meta", {"conversation_id": conv.id, "intent": nlu.intent.value, "language": nlu.language}

        result = TurnResult()
        streamed = False
        try:
            if nlu.missing:
                result = self._clarify(nlu)
            else:
                handler = {
                    Intent.GREETING_HELP: self._greeting,
                    Intent.ITINERARY_CREATE: self._itinerary_create,
                    Intent.ITINERARY_MODIFY: self._itinerary_modify,
                    Intent.PLACE_SEARCH: self._places,
                    Intent.HOTEL_SEARCH: self._places,
                    Intent.ROUTE_LOOKUP: self._route,
                    Intent.DESTINATION_DISCOVERY: self._discover,
                    Intent.BUDGET_ESTIMATE: self._budget,
                }.get(nlu.intent)
                if handler is not None:
                    result = await handler(nlu, context)
                else:
                    # website_qa, transport, compare, unknown → grounded answer (+ structured block)
                    pre = TurnResult()
                    if nlu.intent == Intent.TRANSPORT_INFO:
                        pre = await self._transport(nlu)
                    elif nlu.intent == Intent.DESTINATION_COMPARE:
                        pre = self._compare(nlu)
                    async for kind, payload in self._rag(nlu, context, history, source_ids):
                        if kind == "delta":
                            streamed = True
                            yield "delta", payload
                        else:
                            result = payload
                    result.blocks = pre.blocks + result.blocks
                    result.notices = pre.notices + result.notices
                    if nlu.intent == Intent.TRANSPORT_INFO and result.evidence == "none" and pre.notices:
                        # Nothing relevant indexed: lead with the honest provider limitation instead.
                        result.answer, pre.notices = pre.notices[0], pre.notices[1:]
                    if pre.answer:
                        sep = "\n\n" if result.answer else ""
                        if nlu.intent == Intent.UNKNOWN and result.evidence == "none":
                            result.answer = t("unknown", nlu.language)
                        else:
                            result.answer = pre.answer + sep + result.answer
                    elif nlu.intent == Intent.UNKNOWN and result.evidence == "none":
                        result.answer = t("unknown", nlu.language)
        except ProviderError as exc:
            result = TurnResult(answer=exc.message, notices=["A live data provider failed; nothing was invented "
                                                             "to fill the gap."])
        except AppError as exc:
            result = TurnResult(answer=exc.message)

        if not streamed and result.answer:
            yield "delta", result.answer

        # ---- persist assistant turn and structured context
        new_context = self._next_context(context, nlu, result)
        citations = [_citation_out(c) for c in result.citations]
        response_meta = {
            "language": nlu.language, "intent": nlu.intent.value, "classifier": nlu.classifier,
            "entities": nlu.entities.model_dump(mode="json", exclude_defaults=True),
            "citations": [c.model_dump() for c in citations], "evidence": result.evidence,
            "answer_mode": result.mode, "blocks": [b.model_dump(mode="json") for b in result.blocks],
            "suggestions": result.suggestions, "notices": result.notices,
        }
        assistant_msg = Message(conversation_id=conv.id, role="assistant", content=result.answer, meta=response_meta)
        self.session.add(assistant_msg)
        conv.context = new_context
        if conv.title == "New trip chat":
            conv.title = message.strip()[:60] + ("…" if len(message.strip()) > 60 else "")
        conv.updated_at = utcnow()
        await self.session.commit()

        yield "final", ChatResponse(
            conversation_id=conv.id, message_id=assistant_msg.id, user_message_id=user_msg.id, answer=result.answer,
            language=nlu.language, intent=nlu.intent.value, classifier=nlu.classifier,
            entities=response_meta["entities"], citations=citations, evidence=result.evidence,
            answer_mode=result.mode, blocks=result.blocks, suggestions=result.suggestions, notices=result.notices,
        )

    # ------------------------------------------------------------------ context
    def _next_context(self, context: dict[str, Any], nlu: NLUResult, result: TurnResult) -> dict[str, Any]:
        """Keep a bounded, structured memory — never raw retrieved text or secrets."""
        remembered = Entities.model_validate(context.get("entities") or {})
        merged = nlu.entities.merged_with(remembered) if nlu.intent != Intent.GREETING_HELP else remembered
        if nlu.entities.destination:
            merged.destination = nlu.entities.destination
        merged.refers_to_previous = False
        new = {**context, "entities": merged.model_dump(mode="json", exclude_defaults=True)}
        new["last_intent"] = nlu.intent.value
        new["pending"] = None
        new.update(result.context_updates)
        return new

    def _clarify(self, nlu: NLUResult) -> TurnResult:
        slot = nlu.missing[0]
        question = t(f"ask_{slot}", nlu.language)
        options: list[str] = []
        if slot in ("destination", "destinations"):
            options = ["Jaipur", "Udaipur", "Goa", "Varanasi", "Kerala"]
        elif slot == "duration_days":
            options = ["2 days", "3 days", "5 days", "1 week"]
        elif slot == "origin":
            options = ["Ahmedabad", "Mumbai", "Delhi", "Bengaluru"]
        return TurnResult(
            answer=question, blocks=[ClarifyBlock(question=question, missing=nlu.missing, options=options)],
            suggestions=options,
            context_updates={"pending": {"intent": nlu.intent.value,
                                         "entities": nlu.entities.model_dump(mode="json", exclude_defaults=True)}},
        )

    async def _greeting(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        return TurnResult(answer=t("help", nlu.language), suggestions=[
            "What is the best time to visit Varanasi?", "Plan a 3-day trip to Jaipur for heritage and food",
            "Compare Goa and Kerala for a relaxed trip", "Things to do in Udaipur"])

    # ------------------------------------------------------------------ RAG
    async def _rag(self, nlu: NLUResult, context: dict[str, Any], history: list, source_ids: list[str] | None
                   ) -> AsyncIterator[tuple[str, Any]]:
        query = nlu.text
        e = nlu.entities
        # Resolve short follow-ups ("what about food there?") against remembered destinations.
        for name in [e.destination, *e.destinations]:
            if name and name.lower() not in query.lower():
                query = f"{query} {name}"
        chunks = await self.c.retriever.retrieve(query, top_k=self.c.settings.retrieval_top_k, source_ids=source_ids)
        final: GroundedAnswer | None = None
        cross_lingual = nlu.language in ("hi", "gu") and self.c.embedder.name.startswith("st-")
        async for item in generate_answer(query, chunks, history, nlu.language, self.c.llm,
                                          max_tokens=self.c.settings.llm_max_tokens, cross_lingual=cross_lingual):
            if isinstance(item, GroundedAnswer):
                final = item
            else:
                yield "delta", item
        assert final is not None
        suggestions = []
        if e.destination:
            suggestions = [f"Plan a 2-day trip to {e.destination}", f"Things to do in {e.destination}"]
        yield "final", TurnResult(answer=final.text, citations=final.citations, evidence=final.evidence,
                                  mode=final.mode, notices=final.notices, suggestions=suggestions)

    # ------------------------------------------------------------------ places
    async def _places(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        e = nlu.entities
        dest = e.destination or ""
        category = "lodging" if nlu.intent == Intent.HOTEL_SEARCH else (e.place_category or "tourist_attraction")
        d = get_destination(dest)
        query = " ".join(e.interests) if e.interests else ""
        result = await self.c.places.search(query or dest, near=d.name if d else dest,
                                            lat=d.lat if d else None, lng=d.lng if d else None,
                                            category=category, limit=8)
        notices = [result.notice] if result.notice else []
        if nlu.intent == Intent.HOTEL_SEARCH and result.data_origin == "live":
            notices.append("Hotel results come from Google Places and do not include room prices or availability. "
                           "Check with the hotel or a booking site.")
        if result.places:
            lines = [t("places_intro", nlu.language, dest=d.name if d else dest)]
            for p in result.places[:6]:
                extra = f" — {p.rating:.1f}★ ({p.user_rating_count:,} reviews, Google)" \
                    if p.rating is not None and p.user_rating_count else ""
                lines.append(f"- **{p.name}**{extra}")
            label = "Live results from Google Places." if result.data_origin == "live" else \
                "These come from YatraAI's sample dataset (demo), not live search."
            lines.append(label)
            answer = "\n".join(lines)
        else:
            answer = result.notice or "No places found."
        return TurnResult(answer=answer, blocks=[PlacesBlock(result=result)], notices=notices,
                          suggestions=[f"Plan a 2-day trip to {d.name if d else dest}"] if result.places else [],
                          context_updates={"last_places": [{"id": p.id, "name": p.name} for p in result.places[:10]]})

    # ------------------------------------------------------------------ routes / transport
    async def _route(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        e = nlu.entities
        mode = ROUTE_MODES.get(e.transport_mode or "DRIVE", "DRIVE")
        route = await self.c.routes.compute(RouteRequest(origin=e.origin or "", destination=e.destination or "",
                                                         travel_mode=mode))
        if route.available:
            km = f"{route.distance_meters / 1000:.0f} km" if route.distance_meters else "unknown distance"
            answer = (f"From {route.origin} to {route.destination} ({mode.lower().replace('_', ' ')}): **{km}**, "
                      f"about **{_fmt_duration(route.duration_seconds)}** according to Google Routes "
                      f"(without live traffic).")
        else:
            answer = route.notice or "Route information is unavailable."
        return TurnResult(answer=answer, blocks=[RouteBlock(route=route)])

    async def _transport(self, nlu: NLUResult) -> TurnResult:
        e = nlu.entities
        info = await self.c.transport.lookup(mode=e.transport_mode, origin=e.origin, destination=e.destination)
        return TurnResult(blocks=[TransportBlock(info=info)], notices=[info.message])

    # ------------------------------------------------------------------ discovery / comparison / budget
    async def _discover(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        e = nlu.entities
        # A place named in a discovery request ("getaway from Ahmedabad", "near Mumbai") is the starting point.
        origin = e.origin or (e.destinations[0] if e.destinations else None)
        recs, criteria = discovery.recommend(interests=e.interests, origin=origin, days=e.duration_days)
        if not recs:
            return TurnResult(answer="I couldn't match those interests to destinations in my profile list. "
                                     "Try interests like heritage, nature, beaches, food or mountains.")
        items = [RecommendationItem(name=r.destination.name, state=r.destination.state,
                                    country=r.destination.country, matched_interests=r.matched_interests,
                                    reasons=r.reasons, guide_url=r.guide_url, straight_line_km=r.straight_line_km)
                 for r in recs]
        lines = ["Here are destinations that fit what you described:"]
        for it in items:
            lines.append(f"- **{it.name}** ({it.state}) — {it.reasons[0]}")
        lines.append("Ranked by: " + "; ".join(criteria) + ".")
        note = ("Profiles are YatraAI's general descriptions, not verified facts; check seasons, costs and access "
                "before deciding.")
        return TurnResult(answer="\n".join(lines),
                          blocks=[RecommendationsBlock(criteria=criteria, items=items, note=note)],
                          suggestions=[f"Plan a {e.duration_days or 3}-day trip to {items[0].name}",
                                       f"Compare {items[0].name} and {items[1].name}" if len(items) > 1 else
                                       f"Things to do in {items[0].name}"])

    def _compare(self, nlu: NLUResult) -> TurnResult:
        e = nlu.entities
        rows = discovery.compare(e.destinations[:4], interests=e.interests, origin=e.origin, days=e.duration_days)
        criteria = ["Landscape and what each place is known for (YatraAI profile tags)"]
        if e.interests:
            criteria.append("Which of your interests each destination matches")
        if e.duration_days:
            criteria.append(f"Whether the usual stay fits {e.duration_days} day(s)")
        if e.origin:
            criteria.append(f"Straight-line distance from {e.origin} (not road distance)")
        items = [ComparisonItem(name=r.destination.name, landscape=r.destination.landscape,
                                known_for=list(r.destination.tags), matched_interests=r.matched_interests,
                                suggested_days=f"{r.suggested_days[0]}–{r.suggested_days[1]} days",
                                fits_days=r.fits_days, straight_line_km=r.straight_line_km, guide_url=r.guide_url)
                 for r in rows]
        summary = ""
        if e.interests and items:
            parts = [f"{i.name} matches {len(i.matched_interests)} of your interests"
                     + (f" ({', '.join(i.matched_interests)})" if i.matched_interests else "") for i in items]
            summary = "; ".join(parts) + "."
        note = ("The table uses YatraAI's general destination profiles. Seasonal and practical details below are "
                "quoted from indexed sources where available.")
        return TurnResult(answer=summary, blocks=[ComparisonBlock(criteria=criteria, items=items, note=note)])

    async def _budget_citation(self) -> Citation | None:
        row = (await self.session.execute(
            select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
            .where(Document.url == engine.BUDGET_SOURCE_URL).order_by(Chunk.ordinal))).all()
        target = next(((c, d) for c, d in row if c.heading and "per-day" in c.heading.lower()), row[0] if row else None)
        if not target:
            return None
        c, d = target
        return Citation(id="S1", chunk_id=c.id, document_id=d.id, url=d.url, title=d.title, heading=c.heading,
                        snippet=c.text[:280], is_demo=d.is_demo, fetched_at=d.fetched_at.isoformat(),
                        published_at=d.published_at)

    async def _budget(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        e = nlu.entities
        request = None
        if context.get("itinerary_id") and not nlu.entities.destinations:
            try:
                row = await itinerary_service.get_owned(self.session, self.client_id, context["itinerary_id"])
                request = ItineraryRequest.model_validate(row.request)
                if e.budget_level:
                    request = request.model_copy(update={"budget_level": e.budget_level})
            except AppError:
                request = None
        if request is None:
            request = ItineraryRequest(destination=e.destination or "your destination", days=e.duration_days or 1,
                                       travellers=e.travellers, budget=e.budget, budget_level=e.budget_level)
        est = engine.estimate_budget(request, request.days)
        who = f"{est.travellers} traveller(s)" + (" (assumed — tell me how many)" if est.travellers_assumed else "")
        lines = [
            f"Rough **{est.tier}** estimate for {request.days} day(s) in {request.destination}, {who}: "
            f"**₹{est.total_min:,} – ₹{est.total_max:,}** "
            f"(₹{est.per_person_per_day_min:,}–₹{est.per_person_per_day_max:,} per person per day) [S1].",
            "This is a planning estimate based on YatraAI's assumptions, not live prices, and excludes "
            + ", ".join(est.excludes) + ".",
        ]
        if est.user_budget and est.within_user_budget != "unknown":
            verdict = {"yes": "Your budget covers the top of this range.",
                       "partly": "Your budget falls inside this range — it should work with careful choices.",
                       "no": "Your budget is below this range; consider the budget tier, fewer days or a "
                             "cheaper season."}[est.within_user_budget]
            lines.append(verdict)
        citation = await self._budget_citation()
        answer = "\n\n".join(lines)
        if citation is None:
            answer = answer.replace(" [S1]", "")
        return TurnResult(answer=answer, blocks=[BudgetBlock(estimate=est)],
                          citations=[citation] if citation else [], evidence="limited" if citation else None,
                          suggestions=["Make it cheaper"] if context.get("itinerary_id") else [])

    # ------------------------------------------------------------------ itineraries
    async def _itinerary_create(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        e = nlu.entities
        days = e.duration_days
        if not days and e.dates and e.dates.start and e.dates.end:
            days = (e.dates.end - e.dates.start).days + 1
        request = ItineraryRequest(
            destination=e.destination or "", origin=e.origin, start_date=e.dates.start if e.dates else None,
            days=min(days or 1, 14), travellers=e.travellers, budget=e.budget, budget_level=e.budget_level,
            interests=e.interests, pace=e.pace or "balanced", transport_mode=e.transport_mode,
            accommodation=e.accommodation, accessibility=e.accessibility,
        )
        row = await itinerary_service.create_itinerary(self.session, self.c.places, self.client_id, request,
                                                       self.conversation_id)
        plan = ItineraryPlan.model_validate(row.plan)
        first_stop = next((s.place.name for d in plan.days for s in d.stops), "a stop")
        notices = []
        if (days or 0) > 14:
            notices.append("Itineraries are limited to 14 days; I planned the first 14.")
        return TurnResult(
            answer=t("itinerary_intro", nlu.language, days=request.days, dest=plan.destination, example=first_stop),
            blocks=[ItineraryBlock(itinerary_id=row.id, title=row.title, version=row.version, plan=plan)],
            notices=notices,
            suggestions=["Make it more relaxed", "Add one more day", "Estimate the budget", f"Remove {first_stop}"],
            context_updates={"itinerary_id": row.id},
        )

    def _parse_edit(self, text: str, plan: ItineraryPlan, request: ItineraryRequest, e: Entities) -> list[Any]:
        low = text.lower()
        ops: list[Any] = []
        stops = [(d.day, s) for d in plan.days for s in d.stops]

        def tokens(value: str) -> set[str]:
            found = set(re.findall(r"[\w']+", value.lower()))
            return found | {w.rstrip("s") for w in found}

        def find_stops(fragment: str) -> list[str]:
            words = {w for w in tokens(fragment) if len(w) > 2} - {
                "the", "remove", "drop", "skip", "delete", "from", "day", "visit", "and", "with", "trip", "plan",
                "please", "can", "you", "itinerary"}
            if not words:
                return []
            # Most specific evidence wins: a name match, else the place category, else its tags.
            for field_of in (lambda s: s.place.name, lambda s: s.place.category or "",
                             lambda s: " ".join(s.place.tags)):
                overlap = {s.id: len(words & tokens(field_of(s))) for _, s in stops}
                best = max(overlap.values(), default=0)
                if best:
                    # "remove Amber Fort" should not also remove every other fort.
                    return [sid for sid, n in overlap.items() if n == best]
            return []

        def find_unplaced(fragment: str) -> str | None:
            frag = fragment.lower().strip(" .!?")
            for p in plan.unplaced:
                if p.name.lower() in frag or frag in p.name.lower():
                    return p.id
            return None

        if m := re.search(r"(?:remove|delete|drop) day (\d+)", low):
            ops.append(RemoveDay(op="remove_day", day=int(m.group(1))))
        elif re.search(r"add (one|1|a|an|another) (more )?(extra )?day|one more day|extra day|ek din aur|aur ek din|"
                       r"एक दिन और|और एक दिन|એક દિવસ વધુ|વધુ એક દિવસ", low):
            ops.append(AddDay(op="add_day"))
        elif m := re.search(r"(?:regenerate|redo|change|shuffle) day (\d+)", low):
            ops.append(RegenerateDay(op="regenerate_day", day=int(m.group(1))))
        elif m := re.search(r"move (.+?) to day (\d+)", low):
            ops += [MoveStop(op="move_stop", stop_id=sid, to_day=int(m.group(2))) for sid in find_stops(m.group(1))[:1]]
        elif m := re.search(r"(?:replace|swap) (.+?) (?:with|for) (.+)", low):
            sid = (find_stops(m.group(1)) or [None])[0]
            pid = find_unplaced(m.group(2))
            if sid and pid:
                ops.append(ReplaceStop(op="replace_stop", stop_id=sid, place_id=pid))
        elif re.search(r"\b(remove|drop|skip|delete|cut|exclude|hatao|hata do)\b|हटाओ|हटा दो|કાઢી નાખો|દૂર કરો", low):
            ops += [RemoveStop(op="remove_stop", stop_id=sid) for sid in find_stops(low)]
        elif re.search(r"cheaper|less expensive|reduce (the )?(cost|budget)|sasta|सस्ता|સસ્તું", low):
            lowered = engine.lower_budget_tier(request)
            ops.append(UpdatePreferences(op="update_preferences", budget_level=lowered.budget_level))
        elif e.pace and e.pace != request.pace or re.search(r"more relaxed|less rushed|slow (it )?down", low):
            ops.append(UpdatePreferences(op="update_preferences",
                                         pace="relaxed" if "relax" in low or "slow" in low else e.pace))
        elif m := re.search(r"\badd (.+)", low):
            pid = find_unplaced(m.group(1))
            if pid:
                lightest = min(plan.days, key=lambda d: len(d.stops)).day
                ops.append(AddStop(op="add_stop", day=lightest, place_id=pid))
            elif e.interests:
                ops.append(UpdatePreferences(op="update_preferences",
                                             interests=sorted(set(request.interests) | set(e.interests))))
        return ops

    async def _itinerary_modify(self, nlu: NLUResult, context: dict[str, Any]) -> TurnResult:
        itinerary_id = context.get("itinerary_id")
        if not itinerary_id:
            return TurnResult(answer=t("no_itinerary", nlu.language))
        row = await itinerary_service.get_owned(self.session, self.client_id, itinerary_id)
        plan = ItineraryPlan.model_validate(row.plan)
        request = ItineraryRequest.model_validate(row.request)
        ops = self._parse_edit(nlu.text, plan, request, nlu.entities)
        if not ops:
            names = ", ".join(s.place.name for d in plan.days for s in d.stops[:2])
            return TurnResult(answer="I couldn't tell which change you want. You can say things like “remove "
                                     f"{names.split(', ')[0] if names else 'a stop'}”, “add one more day”, "
                                     "“move X to day 2”, “make it more relaxed” or “make it cheaper”.",
                              blocks=[ItineraryBlock(itinerary_id=row.id, title=row.title, version=row.version,
                                                     plan=plan)])
        changes = await itinerary_service.apply_operations(self.session, self.c.places, row, ops)
        plan = ItineraryPlan.model_validate(row.plan)
        notices = []
        if any(isinstance(o, UpdatePreferences) and o.budget_level for o in ops):
            notices.append("“Cheaper” lowers the budget tier of the estimate. Attraction ticket prices are not "
                           "available in this data, so the stops themselves were not re-priced.")
        return TurnResult(
            answer=t("itinerary_updated", nlu.language, changes=" ".join(changes)),
            blocks=[ItineraryBlock(itinerary_id=row.id, title=row.title, version=row.version, plan=plan,
                                   changes=changes)],
            notices=notices, suggestions=["Estimate the budget", "Add one more day"],
            context_updates={"itinerary_id": row.id},
        )


async def run_chat(c: Container, session: AsyncSession, client_id: str, message: str, conversation_id: str | None,
                   source_ids: list[str] | None = None) -> AsyncIterator[tuple[str, Any]]:
    service = ChatService(c, session, client_id)
    async for event in service.handle(message, conversation_id, source_ids):
        yield event

