"""Rule-based intent classification with weighted multilingual patterns.

Each rule adds weight to an intent; entity cues and conversation context adjust the
scores. The highest-scoring intent wins. Results are deterministic and unit-tested;
an optional LLM classifier (nlp/pipeline.py) is consulted only when no rule fires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.nlp import Entities, Intent


@dataclass(frozen=True)
class Rule:
    intent: Intent
    pattern: re.Pattern[str]
    weight: float
    name: str


def _r(intent: Intent, name: str, weight: float, pattern: str) -> Rule:
    return Rule(intent, re.compile(pattern, re.IGNORECASE), weight, name)


I = Intent
RULES: list[Rule] = [
    # Greeting / help
    _r(I.GREETING_HELP, "greeting", 2.0,
       r"^\s*(hi+|hello+|hey+|namaste|namaskar|namaskaar|kem cho|good (morning|afternoon|evening)|"
       # No \b after the group: it fails after Devanagari/Gujarati vowel signs; the $ anchor suffices.
       r"नमस्ते|नमस्कार|હેલો|નમસ્તે|કેમ છો)[\s!.,?]*(there|yatra(ai)?|ji|जी)?[\s!.,?]*$"),
    _r(I.GREETING_HELP, "help", 2.0,
       r"^\s*(help|madad|मदद|મદદ)\s*[!?.]*$|what can you do|how (can|do) (you|i use)|"
       r"tum kya kar sakte|आप क्या कर सकते|તમે શું કરી શકો"),

    # Itinerary modification (needs an existing itinerary; boosted by context)
    _r(I.ITINERARY_MODIFY, "make_it", 2.2,
       r"\bmake (it|this|the (trip|plan|itinerary))\s+(cheaper|more relaxed|relaxed|slower|faster|packed|"
       r"shorter|longer|budget|luxur\w*)"),
    _r(I.ITINERARY_MODIFY, "add_day", 2.2,
       r"\badd (one|1|a|an|another|two|2) (more )?(extra )?days?\b|\bone more day\b|\bextra day\b|"
       r"\bek din (aur|aur add)\b|\baur ek din\b|एक दिन और|और एक दिन|એક દિવસ વધુ|વધુ એક દિવસ"),
    _r(I.ITINERARY_MODIFY, "remove", 2.0,
       r"\b(remove|drop|skip|delete|cut|exclude)\b.{0,40}\b(day|museum|temple|fort|stop|visit|place|"
       r"palace|beach|market|ghat|lake)\b|\bremove (the )?\w+|\bhatao\b|\bhata do\b|हटाओ|हटा दो|"
       r"કાઢી નાખો|દૂર કરો"),
    _r(I.ITINERARY_MODIFY, "replace", 2.0, r"\b(replace|swap|instead of|change)\b.{0,40}\b(with|to|for)\b"),
    _r(I.ITINERARY_MODIFY, "move", 1.8, r"\bmove\b.{0,40}\bday\s*\d"),
    _r(I.ITINERARY_MODIFY, "cheaper", 1.4,
       r"\b(cheaper|less expensive|reduce (the )?(cost|budget))\b|\bsasta karo\b|सस्ता करो|સસ્તું કરો"),
    _r(I.ITINERARY_MODIFY, "pace_change", 1.2, r"\b(more relaxed|less rushed|slow (it )?down|more packed)\b"),

    # Itinerary creation
    _r(I.ITINERARY_CREATE, "itinerary_word", 2.5,
       r"\bitinerar(y|ies)\b|day[- ]by[- ]day|day[- ]wise|यात्रा योजना|ઇટિનરરી|આયોજન"),
    _r(I.ITINERARY_CREATE, "plan_trip", 2.2,
       r"\bplan\b.{0,30}\b(trip|vacation|holiday|tour|visit|getaway|days?|weekend)\b|"
       r"\b(trip|tour) plan\b|\bplan (banao|bana do|karo)\b|\bplan for \d+\b|"
       r"प्लान बना|योजना बना|प्लान कर|પ્લાન બનાવ|આયોજન કર|ટ્રિપ પ્લાન"),
    _r(I.ITINERARY_CREATE, "n_day_trip", 1.6,
       r"\b\d+\s*-?\s*(day|days|night|nights|din)\s+(trip|tour|vacation|holiday|itinerary|getaway|plan)\b"),
    # Indic "N days" alone is a weaker signal: it also appears in cost and season questions.
    _r(I.ITINERARY_CREATE, "n_days_indic", 1.0, r"\d+\s*(दिन|દિવસ)"),
    _r(I.ITINERARY_CREATE, "schedule", 1.0, r"\bschedule for (my|our|a) trip\b"),

    # Comparison
    _r(I.DESTINATION_COMPARE, "compare", 2.5, r"\bcompare|comparison|\bvs\.?\b|\bversus\b|तुलना|તુલના|સરખામણી"),
    _r(I.DESTINATION_COMPARE, "which_better", 2.0,
       r"\b(which|what) is better\b|\bwhich (one )?(is|would be) better\b|\bbetter\b.{0,30}\bor\b|"
       r"\b(should i|shall we) (go to|choose|pick) .{2,30} or\b|"
       r"\bkaun ?sa (better|accha|acha)\b|\bkonsa (better|accha|acha)\b|कौन सा बेहतर|कौनसा अच्छा|"
       r"કયું સારું|કયું વધુ સારું"),
    _r(I.DESTINATION_COMPARE, "difference", 1.6, r"\bdifference between\b|\bpros and cons\b"),

    # Budget
    _r(I.BUDGET_ESTIMATE, "how_much_cost", 2.4,
       r"\bhow much (will|would|does|do|should|is)\b.{0,40}\b(cost|spend|budget|need|expensive)\b|"
       r"\b(estimate|estimated)\b.{0,20}\b(cost|budget|expense)|\bbudget (estimate|breakdown)\b|"
       r"\bkitna (kharcha|kharch|paisa|budget)\b|\bkharcha kitna\b|कितना खर्च|खर्च कितना|"
       r"कितने पैसे|કેટલો ખર્ચ|ખર્ચ કેટલો|કેટલા પૈસા"),
    _r(I.BUDGET_ESTIMATE, "cost_of_trip", 1.6, r"\b(cost|expense|expenses) of (a |the )?(trip|travel|tour|visit)\b"),
    _r(I.BUDGET_ESTIMATE, "is_it_expensive", 1.2, r"\bis .{2,25} expensive\b|\baffordable\b.{0,20}\?"),

    # Route / distance
    _r(I.ROUTE_LOOKUP, "distance", 2.4,
       r"\bdistance\b|\bhow far\b|\bkm (from|to|between)\b|\bkitni door\b|\bkitna door\b|कितनी दूर|"
       r"कितना दूर|दूरी|કેટલું દૂર|અંતર"),
    _r(I.ROUTE_LOOKUP, "route", 2.0,
       r"\broute\b|\bdirections?\b|\bdrive (time|from|to)\b|\bdriving (time|distance|route)\b|"
       r"\bhow long (does it take|to drive|is the drive)\b|\broad trip from\b|रास्ता|રસ્તો|રૂટ"),

    # Transport / trains
    _r(I.TRANSPORT_INFO, "train", 2.2,
       r"\btrains?\b|\brailway\b|\birctc\b|\bpnr\b|\btatkal\b|\btimetable\b|\bseat availability\b|"
       r"ट्रेन|रेल|ટ્રેન|રેલ્વે"),
    _r(I.TRANSPORT_INFO, "how_to_reach", 2.0,
       r"\bhow (to|do i|can i|should i) (reach|get to|travel to|go to)\b|\bkaise (pahunche|pahuche|jaye|jaaye|"
       r"jayein|jaun|pahunchu)\b|कैसे पहुंच|कैसे पहुँच|कैसे जाएं|કેવી રીતે પહોંચ|કેવી રીતે જવ"),
    _r(I.TRANSPORT_INFO, "flight_bus", 1.6,
       r"\b(flights?|buses|bus) (to|from|between)\b|\b(airport|bus stand|railway station)\b"),

    # Hotels
    _r(I.HOTEL_SEARCH, "hotel", 2.2,
       r"\bhotels?\b|\bwhere (to|should i|can i|should we) stay\b|\baccommodation\b|\bhostels?\b|"
       r"\bhomestays?\b|\bresorts?\b|\bplace to stay\b|\brehne ki jagah\b|\bstay (in|at|near)\b|"
       r"होटल|ठहरने|रुकने की जगह|રહેવા|હોટેલ|હોટલ"),

    # Places / attractions
    _r(I.PLACE_SEARCH, "attractions", 2.0,
       r"\b(places|things|spots) to (visit|see|do|eat)\b|\battractions?\b|\bsightseeing\b|\bmust[- ]see\b|"
       r"\bwhat to (see|do)\b|\btourist (places|spots)\b|\bghumne (ki|ke) jagah\b|\bghoomne\b|"
       r"घूमने की जगह|घूमने लायक|देखने लायक|दर्शनीय|ફરવા લાયક|જોવાલાયક|ફરવાની જગ્યા"),
    _r(I.PLACE_SEARCH, "eat_find", 1.8,
       r"\b(restaurants?|cafes?|cafés?|dhabas?|eateries|street food stalls?)\b|\bwhere to eat\b|"
       r"\bkhane ki jagah\b|खाने की जगह|रेस्टोरेंट|રેસ્ટોરન્ટ|જમવા"),
    _r(I.PLACE_SEARCH, "things_in_place", 2.4,
       r"\b(best |top |famous |popular )?(places|things|spots|sights|attractions|museums?|temples?|beaches|parks?|"
       r"markets?|forts?|palaces?|ghats?|lakes?)( to (visit|see|do))? (in|at|near|around)\s+\w"),
    _r(I.PLACE_SEARCH, "find_near", 1.4, r"\b(find|show|list|suggest)\b.{0,30}\b(museums?|temples?|beaches|parks?|"
                                          r"markets?|forts?|palaces?)\b"),

    # Destination discovery
    _r(I.DESTINATION_DISCOVERY, "where_to_go", 2.2,
       r"\bwhere (should|can|could) (i|we) (go|travel|visit)\b|\bwhere to (go|travel)\b|"
       r"\b(suggest|recommend)\b.{0,30}\b(destination|place|places|trip|getaway|somewhere)\b|"
       r"\bweekend getaway\b|\b(holiday|trip|vacation) ideas\b|\bbest (places?|destinations?) (for|to)\b|"
       r"\bkahan (jaye|jaayein|jaun|jayen|ghume|ghumne)\b|कहाँ जाएं|कहां जाएं|कहाँ घूम|ક્યાં જવું|ક્યાં ફરવા"),
    _r(I.DESTINATION_DISCOVERY, "destination_for", 1.4,
       r"\b(honeymoon|family trip|solo trip|friends trip|getaway|vacation|holiday) (destination|spot|place)s?\b"),

    # Website / knowledge-base Q&A
    _r(I.WEBSITE_QA, "source_ref", 2.5,
       r"\b(according to|from|on|in) (the |your |this )?(website|site|source|sources|guide|page|knowledge base|"
       r"docs?)\b|\bindexed\b"),
    _r(I.WEBSITE_QA, "question_word", 0.8,
       r"^\s*(what|when|where|why|how|which|who|is|are|does|do|can|should|tell me|explain|kya|kab|kyun|"
       r"kaun|क्या|कब|क्यों|कौन|कैसे|શું|ક્યારે|કેમ|કોણ|કેવી)\b|\?\s*$"),
    _r(I.WEBSITE_QA, "info_topic", 1.0,
       r"\b(best time|season|weather|monsoon|visa|permit|entry fee|ticket|opening hours|timings|dress code|"
       r"festival|tips?|safety|history of|famous for|known for)\b|मौसम|सही समय|ઋતુ|સમય"),
]


def classify(text: str, entities: Entities, *, has_itinerary: bool = False,
             awaiting_slot: bool = False) -> tuple[Intent, float, list[str]]:
    scores: dict[Intent, float] = {}
    matched: list[str] = []
    for rule in RULES:
        if rule.pattern.search(text):
            scores[rule.intent] = scores.get(rule.intent, 0.0) + rule.weight
            matched.append(f"{rule.intent.value}:{rule.name}")

    n_places = len(entities.destinations)
    # Entity cues
    if n_places >= 2 and I.DESTINATION_COMPARE in scores:
        scores[I.DESTINATION_COMPARE] += 1.0
    if entities.origin and entities.destination:
        for intent in (I.ROUTE_LOOKUP, I.TRANSPORT_INFO):
            if intent in scores:
                scores[intent] += 0.8
    if entities.duration_days and n_places and I.ITINERARY_CREATE in scores:
        scores[I.ITINERARY_CREATE] += 0.8
    if entities.budget and I.BUDGET_ESTIMATE in scores:
        scores[I.BUDGET_ESTIMATE] += 0.4

    # Context: edits make sense only when an itinerary exists.
    if I.ITINERARY_MODIFY in scores:
        if has_itinerary:
            scores[I.ITINERARY_MODIFY] += 1.5
        else:
            scores[I.ITINERARY_MODIFY] -= 1.5
    # A new plan request with explicit destination+duration beats an edit.
    if I.ITINERARY_CREATE in scores and I.ITINERARY_MODIFY in scores and n_places and entities.duration_days:
        scores[I.ITINERARY_MODIFY] -= 1.0
    # Greeting only wins when nothing substantive was asked.
    if I.GREETING_HELP in scores and any(k not in (I.GREETING_HELP, I.WEBSITE_QA) for k in scores):
        scores[I.GREETING_HELP] -= 1.5

    # Short replies that only supply slot values answer our previous clarifying question.
    substantive = {k: v for k, v in scores.items() if k not in (I.WEBSITE_QA, I.GREETING_HELP) and v > 0}
    if awaiting_slot and not substantive and len(text.split()) <= 12:
        filled = any([entities.destinations, entities.duration_days, entities.dates, entities.budget,
                      entities.travellers, entities.interests, entities.pace, entities.transport_mode])
        if filled or re.fullmatch(r"\s*(yes|yeah|ok|okay|sure|haan|ha|हाँ|હા|no|nahi|ના)\s*[.!]*\s*", text, re.I):
            return I.FOLLOW_UP, 1.0, matched + ["context:awaiting_slot"]

    positive = {k: v for k, v in scores.items() if v > 0}
    if not positive:
        if n_places and (entities.interests or entities.duration_days):
            return I.ITINERARY_CREATE if entities.duration_days else I.DESTINATION_DISCOVERY, 0.4, matched
        if n_places == 1 and len(text.split()) <= 4:
            # A bare destination name: show things to do there.
            return I.PLACE_SEARCH, 0.4, matched + ["bare_destination"]
        return I.UNKNOWN, 0.0, matched
    best = max(positive.items(), key=lambda kv: kv[1])
    score = min(1.0, best[1] / 4.0)
    return best[0], round(score, 2), matched
