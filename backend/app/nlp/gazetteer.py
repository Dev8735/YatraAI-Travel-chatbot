"""Destination gazetteer with English, Hindi (Devanagari) and Gujarati aliases.

Coordinates are approximate city centres (2 d.p.), used only for entity resolution,
geographic grouping and *clearly labelled* straight-line distances — never presented
as road distance. Profile tags are a curated, coarse description for matching
interests; they are labelled in the UI as general guidance, not verified facts.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Destination:
    name: str
    state: str
    country: str
    lat: float
    lng: float
    aliases: tuple[str, ...] = ()
    kind: str = "city"  # city | region | state
    tags: tuple[str, ...] = ()
    landscape: str = ""
    suggested_days: tuple[int, int] = (2, 3)
    guide_slug: str | None = None
    extra: dict = field(default_factory=dict, compare=False, hash=False)


_D = Destination
DESTINATIONS: list[Destination] = [
    _D("Jaipur", "Rajasthan", "India", 26.91, 75.79, ("jaipur", "pink city", "जयपुर", "જયપુર"),
       tags=("heritage", "forts", "shopping", "food", "photography", "museums"), landscape="semi-arid city",
       suggested_days=(2, 3), guide_slug="jaipur"),
    _D("Udaipur", "Rajasthan", "India", 24.58, 73.71, ("udaipur", "city of lakes", "उदयपुर", "ઉદયપુર"),
       tags=("heritage", "lakes", "romantic", "photography", "food"), landscape="lakes and Aravalli hills",
       suggested_days=(2, 3), guide_slug="udaipur"),
    _D("Jodhpur", "Rajasthan", "India", 26.24, 73.02, ("jodhpur", "blue city", "जोधपुर", "જોધપુર"),
       tags=("heritage", "forts", "food", "photography"), landscape="desert-edge city"),
    _D("Jaisalmer", "Rajasthan", "India", 26.92, 70.91, ("jaisalmer", "golden city", "जैसलमेर", "જેસલમેર"),
       tags=("desert", "heritage", "forts", "adventure", "photography"), landscape="Thar desert"),
    _D("Pushkar", "Rajasthan", "India", 26.49, 74.55, ("pushkar", "पुष्कर", "પુષ્કર"),
       tags=("spiritual", "temples", "lakes"), landscape="lakeside town", suggested_days=(1, 2)),
    _D("Mount Abu", "Rajasthan", "India", 24.59, 72.71, ("mount abu", "माउंट आबू", "માઉન્ટ આબુ"),
       tags=("hills", "temples", "nature", "lakes"), landscape="hill station", suggested_days=(1, 2)),
    _D("Delhi", "Delhi", "India", 28.61, 77.21, ("delhi", "new delhi", "dilli", "दिल्ली", "દિલ્હી"),
       tags=("heritage", "food", "museums", "shopping", "history"), landscape="metropolis",
       suggested_days=(2, 3)),
    _D("Agra", "Uttar Pradesh", "India", 27.18, 78.01, ("agra", "आगरा", "આગ્રા"),
       tags=("heritage", "history", "photography"), landscape="riverside city", suggested_days=(1, 2)),
    _D("Varanasi", "Uttar Pradesh", "India", 25.32, 82.97,
       ("varanasi", "banaras", "benares", "kashi", "वाराणसी", "बनारस", "काशी", "વારાણસી", "બનારસ"),
       tags=("spiritual", "temples", "ghats", "food", "photography", "culture"), landscape="Ganga riverfront",
       suggested_days=(2, 3), guide_slug="varanasi"),
    _D("Rishikesh", "Uttarakhand", "India", 30.09, 78.27, ("rishikesh", "ऋषिकेश", "ઋષિકેશ"),
       tags=("spiritual", "adventure", "yoga", "nature", "rafting"), landscape="Himalayan foothills river town",
       suggested_days=(2, 3), guide_slug="rishikesh"),
    _D("Haridwar", "Uttarakhand", "India", 29.95, 78.16, ("haridwar", "हरिद्वार", "હરિદ્વાર"),
       tags=("spiritual", "temples", "ghats"), landscape="river town", suggested_days=(1, 2)),
    _D("Manali", "Himachal Pradesh", "India", 32.24, 77.19, ("manali", "मनाली", "મનાલી"),
       tags=("mountains", "adventure", "nature", "snow", "trekking"), landscape="Himalayan valley",
       suggested_days=(3, 5)),
    _D("Shimla", "Himachal Pradesh", "India", 31.10, 77.17, ("shimla", "simla", "शिमला", "શિમલા"),
       tags=("mountains", "heritage", "nature"), landscape="hill station", suggested_days=(2, 3)),
    _D("Leh", "Ladakh", "India", 34.15, 77.58, ("leh", "ladakh", "लेह", "लद्दाख", "લેહ", "લદ્દાખ"),
       tags=("mountains", "adventure", "monasteries", "photography"), landscape="high-altitude desert",
       suggested_days=(5, 7)),
    _D("Srinagar", "Jammu and Kashmir", "India", 34.08, 74.80, ("srinagar", "kashmir", "श्रीनगर", "कश्मीर", "શ્રીનગર", "કાશ્મીર"),
       tags=("lakes", "mountains", "nature", "gardens"), landscape="valley lakes", suggested_days=(3, 5)),
    _D("Amritsar", "Punjab", "India", 31.63, 74.87, ("amritsar", "अमृतसर", "અમૃતસર"),
       tags=("spiritual", "food", "history", "heritage"), landscape="plains city", suggested_days=(1, 2)),
    _D("Mumbai", "Maharashtra", "India", 19.08, 72.88, ("mumbai", "bombay", "मुंबई", "मुम्बई", "મુંબઈ"),
       tags=("food", "nightlife", "heritage", "shopping", "beaches"), landscape="coastal metropolis",
       suggested_days=(2, 3)),
    _D("Pune", "Maharashtra", "India", 18.52, 73.86, ("pune", "poona", "पुणे", "પુણે"),
       tags=("heritage", "food", "forts"), landscape="plateau city"),
    _D("Lonavala", "Maharashtra", "India", 18.75, 73.41, ("lonavala", "lonavla", "लोनावला", "લોનાવાલા"),
       tags=("hills", "nature", "monsoon"), landscape="Western Ghats hill station", suggested_days=(1, 2)),
    _D("Goa", "Goa", "India", 15.50, 73.83, ("goa", "panaji", "panjim", "गोवा", "ગોવા"), kind="state",
       tags=("beaches", "nightlife", "food", "heritage", "relaxation"), landscape="coastline",
       suggested_days=(3, 5), guide_slug="goa"),
    _D("Bengaluru", "Karnataka", "India", 12.97, 77.59, ("bengaluru", "bangalore", "बेंगलुरु", "बैंगलोर", "બેંગલુરુ"),
       tags=("food", "nightlife", "gardens"), landscape="plateau metropolis"),
    _D("Mysuru", "Karnataka", "India", 12.30, 76.64, ("mysuru", "mysore", "मैसूर", "મૈસુર"),
       tags=("heritage", "palaces", "culture"), landscape="plateau city", suggested_days=(1, 2)),
    _D("Coorg", "Karnataka", "India", 12.42, 75.74, ("coorg", "kodagu", "madikeri", "कूर्ग", "કુર્ગ"),
       tags=("nature", "coffee", "hills", "waterfalls"), landscape="Western Ghats hills"),
    _D("Hampi", "Karnataka", "India", 15.34, 76.46, ("hampi", "हम्पी", "હમ્પી"),
       tags=("heritage", "ruins", "history", "photography"), landscape="boulder landscape"),
    _D("Chennai", "Tamil Nadu", "India", 13.08, 80.27, ("chennai", "madras", "चेन्नई", "ચેન્નઈ"),
       tags=("food", "temples", "beaches", "culture"), landscape="coastal metropolis"),
    _D("Puducherry", "Puducherry", "India", 11.94, 79.81, ("puducherry", "pondicherry", "pondy", "पुडुचेरी", "પોંડિચેરી"),
       tags=("beaches", "heritage", "food", "relaxation"), landscape="coastal town"),
    _D("Ooty", "Tamil Nadu", "India", 11.41, 76.70, ("ooty", "udhagamandalam", "ऊटी", "ઊટી"),
       tags=("hills", "nature", "tea"), landscape="Nilgiri hill station"),
    _D("Kochi", "Kerala", "India", 9.93, 76.27, ("kochi", "cochin", "कोच्चि", "કોચી"),
       tags=("heritage", "food", "culture", "backwaters"), landscape="coastal port city",
       suggested_days=(2, 3), guide_slug="kerala"),
    _D("Munnar", "Kerala", "India", 10.09, 77.06, ("munnar", "मुन्नार", "મુન્નાર"),
       tags=("nature", "tea", "hills", "trekking"), landscape="tea-covered hills", suggested_days=(2, 3),
       guide_slug="kerala"),
    _D("Alleppey", "Kerala", "India", 9.49, 76.33, ("alleppey", "alappuzha", "अलेप्पी", "અલેપ્પી"),
       tags=("backwaters", "nature", "relaxation"), landscape="backwaters", suggested_days=(1, 2),
       guide_slug="kerala"),
    _D("Kerala", "Kerala", "India", 10.50, 76.30, ("kerala", "केरल", "કેરળ"), kind="state",
       tags=("backwaters", "nature", "beaches", "tea", "food", "ayurveda"), landscape="coast, backwaters and hills",
       suggested_days=(4, 7), guide_slug="kerala"),
    _D("Hyderabad", "Telangana", "India", 17.39, 78.49, ("hyderabad", "हैदराबाद", "હૈદરાબાદ"),
       tags=("food", "heritage", "history"), landscape="plateau metropolis"),
    _D("Kolkata", "West Bengal", "India", 22.57, 88.36, ("kolkata", "calcutta", "कोलकाता", "કોલકાતા"),
       tags=("food", "culture", "heritage", "museums"), landscape="riverside metropolis"),
    _D("Darjeeling", "West Bengal", "India", 27.04, 88.26, ("darjeeling", "दार्जिलिंग", "દાર્જિલિંગ"),
       tags=("mountains", "tea", "nature"), landscape="Himalayan hill station"),
    _D("Gangtok", "Sikkim", "India", 27.33, 88.61, ("gangtok", "sikkim", "गंगटोक", "ગંગટોક"),
       tags=("mountains", "monasteries", "nature"), landscape="Himalayan town"),
    _D("Ahmedabad", "Gujarat", "India", 23.02, 72.57, ("ahmedabad", "amdavad", "अहमदाबाद", "અમદાવાદ"),
       tags=("heritage", "food", "architecture", "museums", "shopping"), landscape="riverfront city",
       suggested_days=(1, 2), guide_slug="gujarat"),
    _D("Vadodara", "Gujarat", "India", 22.31, 73.18, ("vadodara", "baroda", "वडोदरा", "વડોદરા"),
       tags=("heritage", "palaces", "museums"), landscape="city", guide_slug="gujarat"),
    _D("Surat", "Gujarat", "India", 21.17, 72.83, ("surat", "सूरत", "સુરત"),
       tags=("food", "shopping"), landscape="city"),
    _D("Rajkot", "Gujarat", "India", 22.30, 70.80, ("rajkot", "राजकोट", "રાજકોટ"),
       tags=("food", "heritage"), landscape="city"),
    _D("Kutch", "Gujarat", "India", 23.25, 69.67,
       ("kutch", "kachchh", "rann of kutch", "bhuj", "कच्छ", "भुज", "કચ્છ", "ભુજ"), kind="region",
       tags=("desert", "crafts", "culture", "photography"), landscape="white salt desert",
       suggested_days=(2, 3), guide_slug="gujarat"),
    _D("Dwarka", "Gujarat", "India", 22.24, 68.97, ("dwarka", "द्वारका", "દ્વારકા"),
       tags=("spiritual", "temples", "beaches"), landscape="coastal temple town", guide_slug="gujarat"),
    _D("Somnath", "Gujarat", "India", 20.89, 70.40, ("somnath", "सोमनाथ", "સોમનાથ"),
       tags=("spiritual", "temples", "beaches"), landscape="coastal temple town", suggested_days=(1, 1),
       guide_slug="gujarat"),
    _D("Gir", "Gujarat", "India", 21.17, 70.60, ("gir", "sasan gir", "gir national park", "गिर नेशनल पार्क", "ગીર", "સાસણ"),
       tags=("wildlife", "nature", "safari"), landscape="dry deciduous forest", suggested_days=(1, 2),
       guide_slug="gujarat"),
    _D("Saputara", "Gujarat", "India", 20.58, 73.75, ("saputara", "सापुतारा", "સાપુતારા"),
       tags=("hills", "nature", "monsoon"), landscape="hill station", suggested_days=(1, 2)),
    _D("Statue of Unity", "Gujarat", "India", 21.84, 73.72,
       ("statue of unity", "kevadia", "ekta nagar", "स्टैच्यू ऑफ यूनिटी", "સ્ટેચ્યુ ઓફ યુનિટી", "કેવડિયા"),
       kind="region", tags=("landmark", "nature", "family"), landscape="Narmada valley", suggested_days=(1, 1),
       guide_slug="gujarat"),
    _D("Khajuraho", "Madhya Pradesh", "India", 24.85, 79.93, ("khajuraho", "खजुराहो", "ખજુરાહો"),
       tags=("heritage", "temples", "architecture"), landscape="small town"),
    _D("Port Blair", "Andaman and Nicobar Islands", "India", 11.62, 92.73,
       ("port blair", "andaman", "andamans", "अंडमान", "આંદામાન"), kind="region",
       tags=("beaches", "diving", "nature", "history"), landscape="tropical islands", suggested_days=(4, 6)),
    _D("Rajasthan", "Rajasthan", "India", 26.90, 73.80, ("rajasthan", "राजस्थान", "રાજસ્થાન"), kind="state",
       tags=("heritage", "forts", "desert", "culture"), landscape="desert and forts", suggested_days=(5, 8)),
    _D("Gujarat", "Gujarat", "India", 22.70, 71.60, ("gujarat", "गुजरात", "ગુજરાત"), kind="state",
       tags=("heritage", "wildlife", "desert", "food", "spiritual"), landscape="coast, desert and forests",
       suggested_days=(4, 7), guide_slug="gujarat"),
    _D("Himachal Pradesh", "Himachal Pradesh", "India", 31.90, 77.20, ("himachal", "हिमाचल", "હિમાચલ"),
       kind="state", tags=("mountains", "adventure", "nature"), landscape="Himalayas", suggested_days=(4, 7)),
    _D("Dubai", "Dubai", "United Arab Emirates", 25.20, 55.27, ("dubai", "दुबई", "દુબઈ"),
       tags=("shopping", "architecture", "desert", "nightlife"), landscape="desert metropolis",
       suggested_days=(3, 5)),
    _D("Singapore", "Singapore", "Singapore", 1.35, 103.82, ("singapore", "सिंगापुर", "સિંગાપોર"),
       tags=("food", "family", "gardens", "shopping"), landscape="city-state", suggested_days=(3, 4)),
    _D("Bangkok", "Bangkok", "Thailand", 13.76, 100.50, ("bangkok", "बैंकॉक", "બેંગકોક"),
       tags=("food", "temples", "nightlife", "shopping"), landscape="riverside metropolis",
       suggested_days=(3, 4)),
    _D("Bali", "Bali", "Indonesia", -8.34, 115.09, ("bali", "बाली", "બાલી"), kind="region",
       tags=("beaches", "temples", "nature", "relaxation"), landscape="tropical island", suggested_days=(4, 7)),
    _D("Kathmandu", "Bagmati", "Nepal", 27.72, 85.32, ("kathmandu", "काठमांडू", "કાઠમંડુ"),
       tags=("heritage", "temples", "mountains"), landscape="Himalayan valley city", suggested_days=(2, 4)),
    _D("Maldives", "Malé", "Maldives", 4.18, 73.51, ("maldives", "मालदीव", "માલદીવ"), kind="region",
       tags=("beaches", "diving", "relaxation", "romantic"), landscape="atolls", suggested_days=(3, 5)),
]

_BY_NAME = {d.name.lower(): d for d in DESTINATIONS}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


# Longest aliases first so "rann of kutch" wins over "kutch", "new delhi" over "delhi".
_ALIAS_INDEX: list[tuple[str, Destination]] = sorted(
    ((_norm(alias), d) for d in DESTINATIONS for alias in (d.name, *d.aliases)),
    key=lambda pair: len(pair[0]),
    reverse=True,
)
_LATIN_RE = re.compile(r"[a-z]")


@dataclass(frozen=True)
class GazetteerMatch:
    destination: Destination
    start: int
    end: int
    alias: str


def find_destinations(text: str) -> list[GazetteerMatch]:
    """Return non-overlapping destination mentions in order of appearance."""
    norm = _norm(text)
    taken: list[tuple[int, int]] = []
    matches: list[GazetteerMatch] = []
    for alias, dest in _ALIAS_INDEX:
        if len(alias) < 3 and _LATIN_RE.search(alias):
            continue
        if _LATIN_RE.search(alias):
            pattern = re.compile(rf"(?<![a-z]){re.escape(alias)}(?![a-z])")
        else:
            # Indic scripts: allow attached postpositions (e.g. "जयपुर में", "જયપુરમાં").
            pattern = re.compile(re.escape(alias))
        for m in pattern.finditer(norm):
            span = (m.start(), m.end())
            if any(not (span[1] <= s or span[0] >= e) for s, e in taken):
                continue
            # "gir" is ambiguous on its own, so require a travel-ish context word.
            if alias == "gir" and not re.search(r"\b(visit|trip|go|travel|to|in|at|national)\b", norm):
                continue
            taken.append(span)
            matches.append(GazetteerMatch(dest, m.start(), m.end(), alias))
    matches.sort(key=lambda g: g.start)
    return matches


def get_destination(name: str) -> Destination | None:
    if not name:
        return None
    hit = _BY_NAME.get(name.strip().lower())
    if hit:
        return hit
    found = find_destinations(name)
    return found[0].destination if found else None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))
