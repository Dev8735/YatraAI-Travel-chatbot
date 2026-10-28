"""Short localized UI strings for templated (non-LLM) replies. Hinglish falls back to its own or English."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "ask_destination": {
        "en": "Which destination do you have in mind?",
        "hinglish": "Aap kahan jaana chahte hain?",
        "hi": "आप कहाँ जाना चाहते हैं?",
        "gu": "તમે ક્યાં જવા માંગો છો?",
    },
    "ask_duration_days": {
        "en": "How many days is the trip?",
        "hinglish": "Trip kitne din ki hai?",
        "hi": "यात्रा कितने दिनों की है?",
        "gu": "પ્રવાસ કેટલા દિવસનો છે?",
    },
    "ask_origin": {
        "en": "Where will you be starting from?",
        "hinglish": "Aap kahan se start karenge?",
        "hi": "आप कहाँ से यात्रा शुरू करेंगे?",
        "gu": "તમે ક્યાંથી શરૂઆત કરશો?",
    },
    "ask_destinations": {
        "en": "Which two (or more) destinations should I compare?",
        "hinglish": "Kaunsi do (ya zyada) jagahon ko compare karun?",
        "hi": "मैं किन दो (या अधिक) जगहों की तुलना करूँ?",
        "gu": "હું કયા બે (કે વધુ) સ્થળોની તુલના કરું?",
    },
    "help": {
        "en": "Namaste! I'm YatraAI. I can answer questions from indexed travel websites (with sources), "
              "find places to visit, compare destinations, estimate rough budgets, and build day-by-day "
              "itineraries you can edit. Try: “Plan a 3-day trip to Jaipur for heritage and food”.",
        "hinglish": "Namaste! Main YatraAI hoon. Main indexed travel websites se sources ke saath jawab de sakta "
                    "hoon, ghumne ki jagah dhoondh sakta hoon, destinations compare kar sakta hoon, rough budget "
                    "bata sakta hoon aur din-ba-din itinerary bana sakta hoon. Try karein: “Jaipur ka 3 din ka plan "
                    "banao”.",
        "hi": "नमस्ते! मैं YatraAI हूँ। मैं अनुक्रमित ट्रैवल वेबसाइटों से स्रोतों के साथ जवाब दे सकता हूँ, घूमने की "
              "जगहें ढूँढ सकता हूँ, गंतव्यों की तुलना कर सकता हूँ, अनुमानित बजट बता सकता हूँ और दिन-प्रतिदिन की "
              "यात्रा योजना बना सकता हूँ। आज़माएँ: “जयपुर के लिए 3 दिन की योजना बनाओ”।",
        "gu": "નમસ્તે! હું YatraAI છું. હું અનુક્રમિત ટ્રાવેલ વેબસાઇટ્સમાંથી સ્રોતો સાથે જવાબ આપી શકું છું, ફરવાની "
              "જગ્યાઓ શોધી શકું છું, સ્થળોની તુલના કરી શકું છું, અંદાજિત બજેટ આપી શકું છું અને દિવસવાર પ્રવાસ "
              "યોજના બનાવી શકું છું. અજમાવો: “ઉદયપુર માટે 2 દિવસનો પ્લાન બનાવો”.",
    },
    "unknown": {
        "en": "I'm not sure how to help with that. I can answer travel questions from indexed sources, find "
              "places, compare destinations, estimate budgets and plan itineraries.",
        "hinglish": "Iss mein main madad nahi kar paaunga. Main travel sawaalon ke jawab, jagah dhoondhna, "
                    "destinations compare karna, budget aur itinerary mein madad kar sakta hoon.",
        "hi": "मैं इसमें मदद नहीं कर पाऊँगा। मैं यात्रा संबंधी सवालों के जवाब, जगहें ढूँढने, तुलना, बजट और यात्रा "
              "योजना में मदद कर सकता हूँ।",
        "gu": "હું આમાં મદદ કરી શકીશ નહીં. હું પ્રવાસના પ્રશ્નો, જગ્યાઓ શોધવા, તુલના, બજેટ અને પ્રવાસ યોજનામાં મદદ "
              "કરી શકું છું.",
    },
    "places_intro": {
        "en": "Here are some places in {dest}:",
        "hinglish": "{dest} mein yeh jagah dekh sakte hain:",
        "hi": "{dest} में कुछ जगहें:",
        "gu": "{dest} માં કેટલીક જગ્યાઓ:",
    },
    "itinerary_intro": {
        "en": "Here's a {days}-day plan for {dest}. Ask me to change it — for example “make it more relaxed”, "
              "“add one more day” or “remove {example}”.",
        "hinglish": "{dest} ke liye {days} din ka plan taiyaar hai. Badlav ke liye bolein — jaise “add one more "
                    "day” ya “remove {example}”.",
        "hi": "{dest} के लिए {days} दिन की योजना तैयार है। बदलाव के लिए कहें — जैसे “एक दिन और जोड़ो” या "
              "“{example} हटाओ”।",
        "gu": "{dest} માટે {days} દિવસની યોજના તૈયાર છે. ફેરફાર માટે કહો — જેમ કે “એક દિવસ વધુ ઉમેરો” અથવા "
              "“{example} કાઢી નાખો”.",
    },
    "itinerary_updated": {
        "en": "Updated your itinerary: {changes}",
        "hinglish": "Itinerary update ho gayi: {changes}",
        "hi": "आपकी यात्रा योजना अपडेट हो गई: {changes}",
        "gu": "તમારી પ્રવાસ યોજના અપડેટ થઈ: {changes}",
    },
    "no_itinerary": {
        "en": "There's no itinerary in this conversation yet. Tell me a destination and number of days and I'll "
              "build one.",
        "hinglish": "Is conversation mein abhi koi itinerary nahi hai. Destination aur din batayein, main plan bana "
                    "dunga.",
        "hi": "इस बातचीत में अभी कोई यात्रा योजना नहीं है। गंतव्य और दिनों की संख्या बताइए, मैं योजना बना दूँगा।",
        "gu": "આ વાતચીતમાં હજી કોઈ પ્રવાસ યોજના નથી. સ્થળ અને દિવસો જણાવો, હું યોજના બનાવી દઈશ.",
    },
}


def t(key: str, language: str, **kwargs: object) -> str:
    table = STRINGS[key]
    template = table.get(language) or table["en"]
    return template.format(**kwargs)
