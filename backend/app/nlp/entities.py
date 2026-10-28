"""Deterministic entity extraction: places, dates, durations, money, travellers, preferences.

Missing values are left as None — nothing is assumed.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.nlp.gazetteer import find_destinations
from app.nlp.language import normalize_digits
from app.nlp.lexicon import (
    ACCESSIBILITY,
    ACCOMMODATION,
    AMOUNT_MULTIPLIERS,
    BUDGET_LEVEL,
    CURRENCY_WORDS,
    INTERESTS,
    MONTHS,
    NUMBER_WORDS,
    PACE,
    PLACE_CATEGORIES,
    TRANSPORT,
)
from app.schemas.nlp import DateRange, Entities, Money

_LATIN = re.compile(r"[a-z]")


def _contains(text: str, phrase: str) -> bool:
    phrase = phrase.lower()
    if _LATIN.search(phrase) or phrase in {"$", "€", "£", "₹"}:
        if not phrase[0].isalnum():
            return phrase in text
        return re.search(rf"(?<![\w]){re.escape(phrase)}(?![\w])", text) is not None
    return phrase in text


def _match_lexicon(text: str, lexicon: dict[str, list[str]]) -> list[str]:
    return [key for key, words in lexicon.items() if any(_contains(text, w) for w in words)]


# ---------------------------------------------------------------- numbers / durations
_NUM = r"(\d+(?:\.\d+)?)"
_NUMWORD = "|".join(sorted((re.escape(k) for k in NUMBER_WORDS), key=len, reverse=True))
_DAY_UNITS = r"days?|din|dino|दिन|દિવસ|દિવસો"
_NIGHT_UNITS = r"nights?|raat|रात|रातें|રાત"


def _to_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def extract_duration(text: str) -> int | None:
    m = re.search(rf"(?:(\d+)|({_NUMWORD}))\s*-?\s*(?:{_DAY_UNITS})(?![a-z])", text)
    if m:
        n = _to_int(m.group(1) or m.group(2))
        if n and 1 <= n <= 60:
            return n
    m = re.search(rf"(?:(\d+)|({_NUMWORD}))\s*-?\s*(?:{_NIGHT_UNITS})(?![a-z])", text)
    if m:
        n = _to_int(m.group(1) or m.group(2))
        if n and 1 <= n <= 59:
            return n + 1  # N nights ≈ N+1 days
    m = re.search(rf"(?:(\d+)|({_NUMWORD}))\s*(?:weeks?(?![a-z])|hafte|hafta|हफ्ते|हफ़्ते|हफ्ता|અઠવાડિયા|અઠવાડિયું)", text)
    if m:
        n = _to_int(m.group(1) or m.group(2))
        if n and n <= 8:
            return n * 7
    if re.search(r"\b(a|one) week\b|\bweek-long\b|\bek hafte\b|एक हफ्ते|એક અઠવાડિયું", text):
        return 7
    if re.search(r"\bfortnight\b", text):
        return 14
    if re.search(r"\bweekend\b|वीकेंड|વીકેન્ડ", text):
        return 2
    return None


def extract_travellers(text: str) -> int | None:
    m = re.search(r"family of (\d+)", text)
    if m:
        return int(m.group(1))
    total = 0
    adults = re.search(r"(\d+)\s*(?:adults?|बड़े)", text)
    kids = re.search(r"(\d+)\s*(?:kids?|children|child|बच्चे|બાળકો)", text)
    if adults:
        total += int(adults.group(1))
    if kids:
        total += int(kids.group(1))
    if total:
        return total
    m = re.search(rf"(?:(\d+)|({_NUMWORD}))\s*(?:people|persons?|pax|travell?ers|friends|of us|members|"
                  r"log|logon|लोग|लोगों|व्यक्ति|લોકો|જણ|વ્યક્તિ)(?![a-z])", text)
    if m:
        n = _to_int(m.group(1) or m.group(2))
        if n and 1 <= n <= 100:
            return n
    if re.search(r"\b(couple|honeymoon|my (wife|husband|partner)|with (my )?(wife|husband|partner))\b", text):
        return 2
    if re.search(r"\b(solo|alone|by myself|akela|akele)\b|अकेले|એકલા", text):
        return 1
    return None


# ---------------------------------------------------------------- money
_CURRENCY_ALT = "|".join(
    sorted((re.escape(w) for words in CURRENCY_WORDS.values() for w in words), key=len, reverse=True)
)
_MULT_ALT = "|".join(sorted((re.escape(k) for k in AMOUNT_MULTIPLIERS), key=len, reverse=True))
_BUDGET_CUE = re.compile(r"budget|बजट|બજેટ|under|within|below|less than|max|maximum|upto|up to|around|about|"
                         r"approx|kharcha|खर्च|ખર્ચ|se kam|से कम|થી ઓછા|tak|तक|સુધી")


def _currency_for(token: str | None) -> str | None:
    if not token:
        return None
    token = token.lower().strip()
    for code, words in CURRENCY_WORDS.items():
        if token in (w.lower() for w in words):
            return code
    return None


def extract_budget(text: str) -> Money | None:
    pattern = re.compile(
        rf"(?P<pre>{_CURRENCY_ALT})?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>{_MULT_ALT})?(?![\w])\s*"
        rf"(?P<post>{_CURRENCY_ALT})?(?![a-z])"
    )
    for m in pattern.finditer(text):
        pre, num, mult, post = m.group("pre"), m.group("num"), m.group("mult"), m.group("post")
        context = text[max(0, m.start() - 30): m.end() + 25]
        if not (pre or post or mult) and not _BUDGET_CUE.search(context):
            continue
        # Skip things that are clearly durations/counts/dates.
        tail = text[m.end(): m.end() + 12]
        if not (pre or post) and re.match(r"\s*(days?|nights?|din|people|pax|km|hours?|am|pm|"
                                          r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|दिन|દિવસ)", tail):
            continue
        try:
            amount = float(num.replace(",", ""))
        except ValueError:
            continue
        if mult:
            amount *= AMOUNT_MULTIPLIERS[mult.lower()]
        if amount < 100 and not (pre or post) and not mult:
            continue
        # A bare year ("december 2026") is not a budget.
        if not (pre or post or mult) and re.fullmatch(r"(19|20)\d\d", num):
            continue
        currency = _currency_for(pre) or _currency_for(post) or "INR"
        before = text[max(0, m.start() - 25): m.start()]
        after = text[m.end(): m.end() + 15]
        qualifier = "approx"
        if re.search(r"under|within|below|less than|max|maximum|upto|up to|not more than", before) or \
           re.search(r"se kam|से कम|थी ओछा|થી ઓછા|tak|तक|સુધી", after):
            qualifier = "max"
        elif re.search(r"at least|minimum|more than", before):
            qualifier = "min"
        per_person = bool(re.search(r"per person|each|per head|pp\b|प्रति व्यक्ति|વ્યક્તિ દીઠ", after + before))
        if amount <= 0 or amount >= 1e10:
            continue
        return Money(amount=round(amount, 2), currency=currency, qualifier=qualifier, per_person=per_person)
    return None


# ---------------------------------------------------------------- dates
_MONTH_ALT = "|".join(sorted((re.escape(k) for k in MONTHS), key=len, reverse=True))
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _future(y_given: str | None, m: int, d: int, today: date) -> date | None:
    if y_given:
        y = int(y_given)
        if y < 100:
            y += 2000
        return _safe_date(y, m, d)
    candidate = _safe_date(today.year, m, d)
    if candidate and candidate < today:
        candidate = _safe_date(today.year + 1, m, d)
    return candidate


def extract_dates(text: str, today: date) -> DateRange | None:
    # ISO dates (one or two)
    iso = re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso:
        ds = [d for d in (_safe_date(int(y), int(m), int(dd)) for y, m, dd in iso) if d]
        if ds:
            return DateRange(start=ds[0], end=ds[1] if len(ds) > 1 and ds[1] >= ds[0] else None,
                             text=" to ".join(str(d) for d in ds[:2]))
    # dd/mm/yyyy (Indian day-first convention)
    dmy = re.findall(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b", text)
    if dmy:
        ds = [d for d in (_future(y, int(m), int(dd), today) for dd, m, y in dmy) if d]
        if ds:
            return DateRange(start=ds[0], end=ds[1] if len(ds) > 1 and ds[1] >= ds[0] else None, text="")
    # "12-15 dec", "12 to 15 december 2026"
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:-|–|to|se|से|થી)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+"
                  rf"({_MONTH_ALT})(?:\s+(\d{{4}}))?", text)
    if m:
        month = MONTHS[m.group(3)]
        start = _future(m.group(4), month, int(m.group(1)), today)
        end = _safe_date(start.year, month, int(m.group(2))) if start else None
        if start and end and end >= start:
            return DateRange(start=start, end=end, text=m.group(0))
    # "12 dec ... 15 dec" / "dec 12" forms
    found: list[date] = []
    for mm in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({_MONTH_ALT})(?:,?\s+(\d{{4}}))?", text):
        d = _future(mm.group(3), MONTHS[mm.group(2)], int(mm.group(1)), today)
        if d:
            found.append(d)
    for mm in re.finditer(rf"\b({_MONTH_ALT})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", text):
        d = _future(mm.group(3), MONTHS[mm.group(1)], int(mm.group(2)), today)
        if d:
            found.append(d)
    if found:
        found.sort()
        return DateRange(start=found[0], end=found[-1] if len(found) > 1 else None, text="")
    # Relative expressions
    if re.search(r"day after tomorrow", text):
        return DateRange(start=today + timedelta(days=2), text="day after tomorrow")
    if re.search(r"\btomorrow\b", text):
        return DateRange(start=today + timedelta(days=1), text="tomorrow")
    if re.search(r"\btoday\b|\baaj\b|आज|આજે", text):
        return DateRange(start=today, text="today")
    if re.search(r"(this|next|coming) weekend|is weekend|agle weekend|अगले वीकेंड|આવતા વીકેન્ડ", text):
        days_to_sat = (5 - today.weekday()) % 7
        start = today + timedelta(days=days_to_sat)
        if "next" in text or "agle" in text or "अगले" in text or "આવતા" in text:
            start = start if days_to_sat >= 2 else start + timedelta(days=7)
        return DateRange(start=start, end=start + timedelta(days=1), text="weekend")
    m = re.search(r"next (" + "|".join(_WEEKDAYS) + r")", text)
    if m:
        delta = (_WEEKDAYS.index(m.group(1)) - today.weekday()) % 7 or 7
        return DateRange(start=today + timedelta(days=delta), text=m.group(0))
    for m in re.finditer(rf"(?<![\w])({_MONTH_ALT})(?![\w])", text):
        word = m.group(1)
        # "may" is usually the modal verb; only accept it with a clear time cue.
        if word == "may" and not re.search(r"(in|during|this|next|of|early|late|mid)\s+$", text[:m.start()]):
            continue
        return DateRange(month=MONTHS[word], text=word)
    return None


# ---------------------------------------------------------------- origin / destination
_ORIGIN_BEFORE = re.compile(r"(?:from|starting from|starting at|leaving|departing)\s+$")
_ORIGIN_AFTER = re.compile(r"^\s*(?:se\b|से|થી|to\b(?=\s))")


def extract_places(text: str) -> tuple[list[str], str | None, str | None]:
    matches = find_destinations(text)
    names: list[str] = []
    for m in matches:
        if m.destination.name not in names:
            names.append(m.destination.name)
    origin = None
    for i, m in enumerate(matches):
        before = text[max(0, m.start - 25): m.start]
        after = text[m.end: m.end + 12]
        # "from X" / "X se Y" / "X से Y" / "Xથી Y" / "X to Y" mark X as the origin.
        followed_by_place = i + 1 < len(matches)
        if _ORIGIN_BEFORE.search(before) or (followed_by_place and _ORIGIN_AFTER.search(after)):
            origin = m.destination.name
            break
    others = [n for n in names if n != origin]
    destination = others[0] if others else None
    return names, origin, destination


_REFERENCE_RE = re.compile(
    r"\b(that place|this place|there|that city|same place|over there|it)\b|wahan|wahaan|vahan|वहाँ|वहां|"
    r"उधर|ત્યાં|એ જગ્યા"
)


def extract_entities(raw_text: str, *, today: date | None = None) -> Entities:
    today = today or date.today()
    text = normalize_digits(raw_text).lower()
    names, origin, destination = extract_places(text)
    dates = extract_dates(text, today)
    duration = extract_duration(text)
    if duration is None and dates and dates.start and dates.end:
        duration = (dates.end - dates.start).days + 1
    budget_levels = _match_lexicon(text, BUDGET_LEVEL)
    transport = _match_lexicon(text, TRANSPORT)
    pace = _match_lexicon(text, PACE)
    categories = _match_lexicon(text, PLACE_CATEGORIES)
    # Prefer the most specific category over the generic "tourist_attraction".
    category = next((c for c in categories if c != "tourist_attraction"), categories[0] if categories else None)
    return Entities(
        destinations=names,
        origin=origin,
        destination=destination,
        dates=dates,
        duration_days=duration if duration and 1 <= duration <= 60 else None,
        travellers=extract_travellers(text),
        budget=extract_budget(text),
        budget_level=budget_levels[0] if budget_levels else None,
        interests=_match_lexicon(text, INTERESTS),
        accommodation=_match_lexicon(text, ACCOMMODATION),
        transport_mode=transport[0] if transport else None,
        pace=pace[0] if pace else None,
        accessibility=_match_lexicon(text, ACCESSIBILITY),
        place_category=category,
        refers_to_previous=bool(_REFERENCE_RE.search(text)),
    )
