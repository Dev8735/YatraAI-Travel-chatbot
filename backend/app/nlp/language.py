"""Script- and marker-based language identification for en / hi / gu / Hinglish."""

from __future__ import annotations

import re
from typing import Literal

from app.nlp.lexicon import HINGLISH_MARKERS, STRONG_HINGLISH

Language = Literal["en", "hi", "gu", "hinglish"]

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_GUJARATI = re.compile(r"[઀-૿]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[a-z]+")

_DIGIT_TABLE = {**{0x0966 + i: str(i) for i in range(10)}, **{0x0AE6 + i: str(i) for i in range(10)}}


def normalize_digits(text: str) -> str:
    """Convert Devanagari (०-९) and Gujarati (૦-૯) digits to ASCII."""
    return text.translate(_DIGIT_TABLE)


def detect_language(text: str) -> Language:
    deva = len(_DEVANAGARI.findall(text))
    guj = len(_GUJARATI.findall(text))
    latin = len(_LATIN.findall(text))
    if guj and guj >= deva and guj >= latin * 0.3:
        return "gu"
    if deva and deva >= latin * 0.3:
        return "hi"
    words = _WORD.findall(text.lower())
    if not words:
        return "en"
    markers = sum(1 for w in words if w in HINGLISH_MARKERS)
    strong = sum(1 for w in words if w in STRONG_HINGLISH)
    if strong >= 1 and (markers >= 2 or len(words) <= 3):
        return "hinglish"
    if markers >= 3 and markers / len(words) >= 0.25:
        return "hinglish"
    return "en"
