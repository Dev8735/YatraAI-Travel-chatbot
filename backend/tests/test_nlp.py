"""Intent classification and entity extraction across English, Hindi, Gujarati and Hinglish."""

from datetime import date

import pytest

from app.nlp.entities import extract_budget, extract_entities
from app.nlp.language import detect_language, normalize_digits
from app.nlp.pipeline import analyze
from app.schemas.nlp import Intent

TODAY = date(2026, 10, 28)


@pytest.mark.parametrize("text,lang", [
    ("What is the best time to visit Jaipur?", "en"),
    ("मुझे जयपुर घूमना है", "hi"),
    ("મારે ઉદયપુર જવું છે", "gu"),
    ("Jaipur mein ghumne ki jagah batao", "hinglish"),
    ("kitna kharcha hoga goa trip ka?", "hinglish"),
    ("Do you have a plan for Goa?", "en"),
])
def test_language_detection(text: str, lang: str) -> None:
    assert detect_language(text) == lang


def test_indic_digits_normalized() -> None:
    assert normalize_digits("३ दिन / ૩ દિવસ") == "3 दिन / 3 દિવસ"


@pytest.mark.parametrize("text,intent", [
    # English
    ("hello", Intent.GREETING_HELP),
    ("What can you do?", Intent.GREETING_HELP),
    ("What is the best time to visit Varanasi?", Intent.WEBSITE_QA),
    ("Plan a 3 day trip to Jaipur", Intent.ITINERARY_CREATE),
    ("Create an itinerary for Goa", Intent.ITINERARY_CREATE),
    ("Compare Goa and Kerala", Intent.DESTINATION_COMPARE),
    ("Goa vs Kerala for a family trip", Intent.DESTINATION_COMPARE),
    ("How much will a 4 day Goa trip cost?", Intent.BUDGET_ESTIMATE),
    ("Distance from Delhi to Agra", Intent.ROUTE_LOOKUP),
    ("trains from Mumbai to Goa", Intent.TRANSPORT_INFO),
    ("How to reach Rishikesh?", Intent.TRANSPORT_INFO),
    ("hotels in Udaipur", Intent.HOTEL_SEARCH),
    ("Things to do in Jaipur", Intent.PLACE_SEARCH),
    ("restaurants in Ahmedabad", Intent.PLACE_SEARCH),
    ("Where should I go for a weekend getaway?", Intent.DESTINATION_DISCOVERY),
    ("Suggest a destination for a honeymoon", Intent.DESTINATION_DISCOVERY),
    ("asdf qwerty", Intent.UNKNOWN),
    # Hindi
    ("नमस्ते", Intent.GREETING_HELP),
    ("मुझे उदयपुर में 2 दिन घूमने का प्लान बनाओ", Intent.ITINERARY_CREATE),
    ("दिल्ली से आगरा कितनी दूर है?", Intent.ROUTE_LOOKUP),
    ("जयपुर में होटल", Intent.HOTEL_SEARCH),
    ("गोवा और केरल की तुलना करो", Intent.DESTINATION_COMPARE),
    ("वाराणसी जाने का सही समय क्या है?", Intent.WEBSITE_QA),
    # Gujarati
    ("કેમ છો", Intent.GREETING_HELP),
    ("અમદાવાદથી ઉદયપુર કેટલું દૂર છે?", Intent.ROUTE_LOOKUP),
    ("ઉદયપુર માટે 2 દિવસનો પ્લાન બનાવો", Intent.ITINERARY_CREATE),
    ("જયપુરમાં ફરવા લાયક સ્થળો", Intent.PLACE_SEARCH),
    ("ગોવા 4 દિવસનો કેટલો ખર્ચ થશે?", Intent.BUDGET_ESTIMATE),
    # Hinglish
    ("Jaipur ghumne ki jagah batao", Intent.PLACE_SEARCH),
    ("Ahmedabad se Udaipur kitni door hai?", Intent.ROUTE_LOOKUP),
    ("Goa ka 3 din ka plan banao", Intent.ITINERARY_CREATE),
    ("kitna kharcha hoga 4 din ka Goa trip?", Intent.BUDGET_ESTIMATE),
    ("Goa ya Kerala, kaunsa better hai?", Intent.DESTINATION_COMPARE),
    ("weekend pe kahan jaye?", Intent.DESTINATION_DISCOVERY),
])
def test_intents(text: str, intent: Intent) -> None:
    assert analyze(text, today=TODAY).intent == intent


@pytest.mark.parametrize("text", ["make it cheaper", "add one more day", "remove the museum",
                                  "ek din aur add karo", "एक दिन और जोड़ो", "મ્યુઝિયમ કાઢી નાખો"])
def test_itinerary_edits(text: str) -> None:
    # Without an itinerary these are still edits; the chat handler then explains there is none yet.
    assert analyze(text, {"itinerary_id": "abc"}, today=TODAY).intent == Intent.ITINERARY_MODIFY


def test_new_plan_beats_edit_wording() -> None:
    r = analyze("Plan a 3 day trip to Goa and add one more day for beaches", {"itinerary_id": "abc"}, today=TODAY)
    assert r.intent == Intent.ITINERARY_CREATE


def test_entities_english_rich() -> None:
    e = extract_entities("Plan a 3 day trip from Mumbai to Jaipur for 2 people under ₹30,000 on 12 Dec, "
                         "we love heritage and food, relaxed pace, by train, with elderly parents", today=TODAY)
    assert e.origin == "Mumbai" and e.destination == "Jaipur"
    assert e.duration_days == 3 and e.travellers == 2
    assert e.budget and e.budget.amount == 30000 and e.budget.currency == "INR" and e.budget.qualifier == "max"
    assert e.dates and e.dates.start == date(2026, 12, 12)
    assert set(e.interests) >= {"heritage", "food"}
    assert e.pace == "relaxed" and e.transport_mode == "TRAIN" and "elderly" in e.accessibility


def test_entities_hindi() -> None:
    e = extract_entities("दिल्ली से आगरा 2 दिन की यात्रा, बजट 20 हज़ार रुपये, किले और खाना", today=TODAY)
    assert e.origin == "Delhi" and e.destination == "Agra"
    assert e.duration_days == 2
    assert e.budget and e.budget.amount == 20000
    assert "heritage" in e.interests and "food" in e.interests


def test_entities_gujarati_attached_postposition() -> None:
    e = extract_entities("અમદાવાદથી ઉદયપુર ૩ દિવસ, 4 લોકો", today=TODAY)
    assert e.origin == "Ahmedabad" and e.destination == "Udaipur"
    assert e.duration_days == 3 and e.travellers == 4


def test_entities_hinglish() -> None:
    e = extract_entities("Goa ka 4 din ka plan, 2 lakh budget, beach aur party, aaram se", today=TODAY)
    assert e.destination == "Goa" and e.duration_days == 4
    assert e.budget and e.budget.amount == 200000
    assert "beaches" in e.interests and "nightlife" in e.interests
    assert e.pace == "relaxed"


@pytest.mark.parametrize("text,days", [("a week in Kerala", 7), ("2 nights in Goa", 3), ("weekend getaway", 2),
                                       ("12-15 Dec in Rishikesh", 4), ("teen din", 3)])
def test_durations(text: str, days: int) -> None:
    assert extract_entities(text, today=TODAY).duration_days == days


def test_date_range_and_past_dates_roll_forward() -> None:
    e = extract_entities("trip on 5 Jan to 8 Jan", today=TODAY)
    assert e.dates and e.dates.start == date(2027, 1, 5) and e.dates.end == date(2027, 1, 8)
    assert e.duration_days == 4


@pytest.mark.parametrize("text,amount,currency", [
    ("budget 25k", 25000, "INR"), ("under Rs. 15,000", 15000, "INR"), ("$800 total", 800, "USD"),
    ("1.5 lakh rupees", 150000, "INR"), ("बजट 50 हज़ार", 50000, "INR"), ("AED 2000", 2000, "AED"),
])
def test_budget_parsing(text: str, amount: float, currency: str) -> None:
    m = extract_budget(text.lower())
    assert m is not None and m.amount == amount and m.currency == currency


@pytest.mark.parametrize("text", ["3 days in December 2026", "Plan 4 days for 2 people", "visit at 10 am"])
def test_numbers_that_are_not_budgets(text: str) -> None:
    assert extract_budget(text.lower()) is None


def test_no_assumptions_when_missing() -> None:
    r = analyze("plan a trip", today=TODAY)
    assert r.intent == Intent.ITINERARY_CREATE
    assert r.missing == ["destination", "duration_days"]
    assert r.entities.travellers is None and r.entities.budget is None


def test_follow_up_fills_pending_slot() -> None:
    pending = {"pending": {"intent": "itinerary_create", "entities": {"destination": "Goa", "destinations": ["Goa"]}}}
    r = analyze("4 days", pending, today=TODAY)
    assert r.intent == Intent.ITINERARY_CREATE and r.classifier == "context"
    assert r.entities.destination == "Goa" and r.entities.duration_days == 4 and not r.missing


def test_reference_resolution_uses_remembered_destination() -> None:
    ctx = {"entities": {"destination": "Varanasi", "destinations": ["Varanasi"]}}
    r = analyze("Can I take my phone inside the temple there?", ctx, today=TODAY)
    assert r.entities.destination == "Varanasi"
    # Without a back-reference, a new question does not inherit the old destination.
    r2 = analyze("What is the visa policy for Antarctica?", ctx, today=TODAY)
    assert r2.entities.destination is None


def test_ambiguous_words_not_taken_as_places() -> None:
    assert extract_entities("I may visit with my male friend", today=TODAY).destinations == []
