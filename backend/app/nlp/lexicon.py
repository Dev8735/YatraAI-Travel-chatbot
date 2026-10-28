"""Multilingual keyword lexicons (English, Hindi, Gujarati, romanized Hinglish).

Latin entries are matched on word boundaries; Devanagari/Gujarati entries are matched as
substrings because postpositions are often attached (e.g. "જયપુરમાં").
"""

from __future__ import annotations

INTERESTS: dict[str, list[str]] = {
    "heritage": ["heritage", "history", "historical", "fort", "forts", "palace", "palaces", "monument",
                 "monuments", "architecture", "itihas", "kila", "qila", "mahal",
                 "किला", "किले", "महल", "ऐतिहासिक", "विरासत", "इतिहास",
                 "કિલ્લો", "કિલ્લા", "મહેલ", "ઐતિહાસિક", "વારસો", "ઇતિહાસ"],
    "nature": ["nature", "scenic", "greenery", "waterfall", "waterfalls", "lake", "lakes", "valley",
               "prakriti", "hariyali", "प्रकृति", "झरना", "झील", "हरियाली", "કુદરત", "પ્રકૃતિ", "ધોધ", "તળાવ"],
    "food": ["food", "foodie", "cuisine", "street food", "local food", "eat", "eating", "khana", "khaana",
             "खाना", "व्यंजन", "स्ट्रीट फूड", "ખાવાનું", "ભોજન", "વાનગી", "ખાણીપીણી"],
    "beaches": ["beach", "beaches", "sea", "coast", "coastal", "samundar", "samudra",
                "समुद्र", "बीच", "तट", "દરિયો", "દરિયા", "બીચ", "દરિયાકિનારો"],
    "spiritual": ["temple", "temples", "mandir", "spiritual", "pilgrimage", "ghat", "ghats", "aarti",
                  "darshan", "teerth", "मंदिर", "धार्मिक", "तीर्थ", "घाट", "आरती", "दर्शन",
                  "મંદિર", "ધાર્મિક", "તીર્થ", "ઘાટ", "આરતી", "દર્શન"],
    "museums": ["museum", "museums", "gallery", "galleries", "art", "संग्रहालय", "म्यूजियम", "મ્યુઝિયમ", "સંગ્રહાલય"],
    "adventure": ["adventure", "trek", "trekking", "rafting", "paragliding", "hiking", "camping", "scuba",
                  "diving", "एडवेंचर", "ट्रेकिंग", "राफ्टिंग", "સાહસ", "ટ્રેકિંગ", "રાફ્ટિંગ"],
    "photography": ["photography", "photos", "photo", "instagram", "sunset", "sunrise", "फोटो", "फ़ोटो", "ફોટો"],
    "shopping": ["shopping", "market", "markets", "bazaar", "bazaars", "crafts", "handicrafts", "souvenir",
                 "souvenirs", "kharidari", "खरीदारी", "बाजार", "बाज़ार", "ખરીદી", "બજાર"],
    "nightlife": ["nightlife", "party", "parties", "pub", "pubs", "bars", "clubs", "club"],
    "wildlife": ["wildlife", "safari", "animals", "tiger", "tigers", "lion", "lions", "birds", "birding",
                 "वन्यजीव", "सफारी", "शेर", "वन्य", "વન્યજીવ", "સફારી", "સિંહ"],
    "relaxation": ["relaxing", "relaxation", "unwind", "chill", "spa", "ayurveda", "sukoon", "सुकून", "શાંતિ"],
    "mountains": ["mountain", "mountains", "snow", "himalaya", "himalayas", "hills", "hill station", "pahad",
                  "pahaad", "पहाड़", "पहाड़ों", "बर्फ", "हिल स्टेशन", "પહાડ", "પર્વત", "બરફ", "હિલ સ્ટેશન"],
    "desert": ["desert", "dunes", "sand dunes", "rann", "रेगिस्तान", "मरुस्थल", "રણ"],
    "backwaters": ["backwaters", "backwater", "houseboat", "houseboats"],
}

ACCOMMODATION: dict[str, list[str]] = {
    "hostel": ["hostel", "hostels", "dorm"],
    "budget_hotel": ["budget hotel", "cheap hotel", "sasta hotel", "सस्ता होटल", "સસ્તી હોટેલ"],
    "guesthouse": ["guesthouse", "guest house", "lodge"],
    "homestay": ["homestay", "home stay", "homestays"],
    "resort": ["resort", "resorts"],
    "luxury_hotel": ["luxury hotel", "5 star", "five star", "5-star", "luxury stay"],
    "heritage_hotel": ["heritage hotel", "haveli", "palace hotel"],
    "camp": ["camp", "camping", "tent", "tents", "glamping"],
    "dharamshala": ["dharamshala", "dharmshala", "धर्मशाला", "ધર્મશાળા"],
}

TRANSPORT: dict[str, list[str]] = {
    "DRIVE": ["car", "drive", "driving", "road trip", "roadtrip", "self-drive", "self drive", "cab", "taxi",
              "gaadi", "gadi", "गाड़ी", "कार", "टैक्सी", "કાર", "ગાડી", "ટેક્સી"],
    "TRAIN": ["train", "trains", "rail", "railway", "irctc", "ट्रेन", "रेल", "रेलगाड़ी", "ટ્રેન", "રેલ્વે"],
    "BUS": ["bus", "buses", "volvo", "बस", "બસ"],
    "FLIGHT": ["flight", "flights", "fly", "flying", "plane", "airport", "फ्लाइट", "हवाई जहाज", "विमान",
               "ફ્લાઇટ", "વિમાન"],
    "TWO_WHEELER": ["bike", "motorcycle", "motorbike", "scooter", "scooty", "बाइक", "બાઇક"],
    "WALK": ["walk", "walking", "on foot", "paidal", "पैदल", "ચાલતા"],
    "TRANSIT": ["metro", "public transport", "local train"],
}

PACE: dict[str, list[str]] = {
    "relaxed": ["relaxed", "relax", "slow", "slow-paced", "leisurely", "easy pace", "not rushed", "laid back",
                "laid-back", "aaram", "araam", "aram se", "आराम", "धीरे", "આરામ", "નિરાંતે"],
    "packed": ["packed", "fast-paced", "fast paced", "cover maximum", "as much as possible", "action packed",
               "busy", "hectic", "maximum places", "jyada se jyada", "zyada se zyada", "ज्यादा से ज्यादा",
               "ज़्यादा से ज़्यादा", "વધુમાં વધુ"],
    "balanced": ["balanced", "moderate", "medium pace"],
}

ACCESSIBILITY: dict[str, list[str]] = {
    "wheelchair": ["wheelchair", "व्हीलचेयर", "વ્હીલચેર"],
    "elderly": ["elderly", "senior citizen", "senior citizens", "old parents", "grandparents", "buzurg",
                "बुजुर्ग", "बुज़ुर्ग", "वृद्ध", "વૃદ્ધ", "વડીલ", "વડીલો"],
    "limited_walking": ["limited walking", "can't walk much", "cannot walk much", "knee problem", "less walking",
                        "mobility"],
    "young_children": ["kids", "children", "toddler", "toddlers", "baby", "infant", "bachche", "bacche",
                       "बच्चे", "बच्चों", "બાળકો", "બાળક"],
    "pregnancy": ["pregnant", "pregnancy"],
}

BUDGET_LEVEL: dict[str, list[str]] = {
    "budget": ["cheap", "cheaper", "budget", "low budget", "affordable", "economical", "backpacking", "sasta",
               "sasti", "kam kharch", "kam budget", "सस्ता", "सस्ती", "कम बजट", "कम खर्च", "સસ્તું", "સસ્તી",
               "ઓછા બજેટ", "ઓછો ખર્ચ"],
    "luxury": ["luxury", "luxurious", "premium", "lavish", "high end", "high-end", "5 star", "five star",
               "लक्ज़री", "लग्जरी", "આલીશાન", "લક્ઝરી"],
    "mid": ["mid-range", "mid range", "moderate budget", "comfortable"],
}

PLACE_CATEGORIES: dict[str, list[str]] = {
    "restaurant": ["restaurant", "restaurants", "food places", "where to eat", "places to eat", "dhaba",
                   "dhabas", "eateries", "रेस्टोरेंट", "खाने की जगह", "ढाबा", "રેસ્ટોરન્ટ", "જમવા"],
    "cafe": ["cafe", "cafes", "café", "coffee shop", "coffee shops", "कैफे", "કાફે"],
    "lodging": ["hotel", "hotels", "stay", "stays", "accommodation", "where to stay", "hostel", "hostels",
                "homestay", "resort", "resorts", "rehne", "rukne", "होटल", "ठहरने", "रुकने", "રહેવા",
                "હોટેલ", "હોટલ", "રોકાવા"],
    "museum": ["museum", "museums", "संग्रहालय", "મ્યુઝિયમ"],
    "temple": ["temple", "temples", "mandir", "मंदिर", "મંદિર"],
    "beach": ["beach", "beaches", "बीच", "બીચ"],
    "park": ["park", "parks", "garden", "gardens", "उद्यान", "બગીચો"],
    "shopping": ["market", "markets", "shopping", "bazaar", "बाजार", "બજાર"],
    "tourist_attraction": ["attraction", "attractions", "things to do", "places to visit", "place to visit",
                           "places to see", "what to see", "sightseeing", "must see", "must-see", "spots",
                           "tourist places", "ghumne", "ghoomne", "घूमने", "देखने लायक", "दर्शनीय",
                           "ફરવા", "જોવાલાયક", "જોવા લાયક"],
}

CURRENCY_WORDS: dict[str, list[str]] = {
    "INR": ["₹", "rs", "rs.", "inr", "rupees", "rupee", "rupaye", "rupay", "रुपये", "रुपए", "रु", "રૂપિયા", "રૂ"],
    "USD": ["$", "usd", "dollars", "dollar", "डॉलर", "ડોલર"],
    "EUR": ["€", "eur", "euro", "euros"],
    "GBP": ["£", "gbp", "pounds"],
    "AED": ["aed", "dirham", "dirhams"],
}

# Multipliers for amounts like "20k", "2 lakh", "50 हज़ार".
AMOUNT_MULTIPLIERS: dict[str, int] = {
    "k": 1_000, "thousand": 1_000, "hazar": 1_000, "hazaar": 1_000, "हजार": 1_000, "हज़ार": 1_000,
    "હજાર": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000, "लाख": 100_000,
    "લાખ": 100_000, "crore": 10_000_000, "cr": 10_000_000, "करोड़": 10_000_000, "કરોડ": 10_000_000,
}

NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "a": 1, "an": 1, "couple of": 2, "few": 3,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10,
    "એક": 1, "બે": 2, "ત્રણ": 3, "ચાર": 4, "પાંચ": 5, "છ": 6, "સાત": 7, "આઠ": 8, "નવ": 9, "દસ": 10,
}

MONTHS: dict[str, int] = {
    **{m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                   "september", "october", "november", "december"], start=1)},
    **{m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                   "nov", "dec"], start=1)},
    "sept": 9,
    **{m: i for i, m in enumerate(["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
                                   "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"], start=1)},
    "फ़रवरी": 2, "सितम्बर": 9, "अक्तूबर": 10, "नवम्बर": 11, "दिसम्बर": 12,
    **{m: i for i, m in enumerate(["જાન્યુઆરી", "ફેબ્રુઆરી", "માર્ચ", "એપ્રિલ", "મે", "જૂન", "જુલાઈ",
                                   "ઓગસ્ટ", "સપ્ટેમ્બર", "ઓક્ટોબર", "નવેમ્બર", "ડિસેમ્બર"], start=1)},
    "ઑગસ્ટ": 8, "ઑક્ટોબર": 10,
}

HINGLISH_MARKERS = {
    "hai", "hain", "kya", "kaise", "kaisa", "kaun", "kaunsa", "kahan", "kahaan", "kab", "kitna", "kitni",
    "mujhe", "humein", "hume", "hum", "chahiye", "karna", "karo", "karke", "jana", "jaana", "ghumna",
    "ghumne", "batao", "bataiye", "accha", "achha", "acha", "sasta", "mein", "liye", "wala", "wali",
    "aur", "se", "tak", "din", "raat", "yaar", "bhai", "chalo", "dekho", "konsa", "jagah", "hoga", "hogi",
    "rehna", "rukna", "kharcha", "paisa", "lagbhag", "banao", "bana", "ke", "ki", "ka",
}
STRONG_HINGLISH = {"kya", "kaise", "kahan", "kahaan", "mujhe", "chahiye", "batao", "bataiye", "ghumne",
                   "ghumna", "kitna", "kitni", "hai", "hain", "banao", "jagah", "kharcha", "kaunsa", "konsa"}
