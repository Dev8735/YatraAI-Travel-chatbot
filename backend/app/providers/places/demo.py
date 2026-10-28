"""Demo places provider backed by a small, clearly labelled sample dataset.

It contains well-known landmarks only. It deliberately has no hotels, restaurants,
ratings, opening hours, prices or photos, because those would have to be invented.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.nlp.gazetteer import get_destination, haversine_km
from app.rag.keyword import content_terms
from app.schemas.travel import Place, PlaceSearchResult

DATA_FILE = Path(__file__).resolve().parents[2] / "demo" / "demo_places.json"
# Kerala is a state in the gazetteer; the demo data is organised by city.
REGION_MEMBERS = {"Kerala": ["Kochi", "Munnar", "Alleppey"]}
NO_LISTINGS = {"lodging", "restaurant", "cafe"}
DEMO_NOTICE = ("Sample data (demo mode) — not live results. Configure GOOGLE_MAPS_API_KEY for live places, "
               "ratings, opening hours and photos.")


@lru_cache
def load_demo_places() -> list[Place]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [
        Place(id=p["id"], name=p["name"], lat=p["lat"], lng=p["lng"], category=p["category"], tags=p["tags"],
              destination=p["destination"], typical_visit_minutes=p["typical_visit_minutes"],
              address=f"{p['destination']}, India (approximate location)", data_origin="demo",
              provider="demo_dataset", provider_attribution="YatraAI sample dataset")
        for p in data["places"]
    ]


class DemoPlacesProvider:
    name = "demo_dataset"
    is_live = False

    def _for_destination(self, near: str | None, lat: float | None, lng: float | None) -> list[Place]:
        places = load_demo_places()
        if near:
            dest = get_destination(near)
            if dest:
                members = REGION_MEMBERS.get(dest.name, [dest.name])
                matched = [p for p in places if p.destination in members]
                if matched:
                    return matched
                lat, lng = dest.lat, dest.lng
            else:
                return []
        if lat is not None and lng is not None:
            return [p for p in places if haversine_km((lat, lng), (p.lat or 0, p.lng or 0)) <= 60]
        return places

    async def search(self, query: str, *, near: str | None = None, lat: float | None = None,
                     lng: float | None = None, category: str | None = None, limit: int = 10) -> PlaceSearchResult:
        if category in NO_LISTINGS:
            kind = {"lodging": "hotel", "restaurant": "restaurant", "cafe": "cafe"}[category]
            return PlaceSearchResult(
                query=query, places=[], provider=self.name, data_origin="demo",
                notice=(f"Live {kind} search needs a places provider (set GOOGLE_MAPS_API_KEY). Demo mode does not "
                        f"include {kind} listings, because showing invented ones would be misleading."),
            )
        candidates = self._for_destination(near, lat, lng)
        terms = set(content_terms(query))
        if near:
            terms -= set(content_terms(near))
        category_aliases = {"museum": {"museum"}, "temple": {"temple", "ghat", "ashram"}, "beach": {"beach"},
                            "park": {"garden", "national_park", "lake"}, "shopping": {"market"}}

        def score(p: Place) -> float:
            s = 0.0
            if category and category in category_aliases and p.category in category_aliases[category]:
                s += 3
            haystack = set(content_terms(f"{p.name} {p.category} {' '.join(p.tags)}"))
            s += len(terms & haystack)
            return s

        ranked = sorted(candidates, key=score, reverse=True)
        if category and category in category_aliases:
            ranked = [p for p in ranked if p.category in category_aliases[category]] or ranked
        places = ranked[:limit]
        notice = DEMO_NOTICE if places else (
            f"The demo dataset has no places for “{near or query}”. Configure GOOGLE_MAPS_API_KEY for live search.")
        return PlaceSearchResult(query=query, places=places, provider=self.name, data_origin="demo", notice=notice)

    async def details(self, place_id: str) -> Place | None:
        return next((p for p in load_demo_places() if p.id == place_id), None)

    async def photo_uri(self, photo_name: str, max_width: int = 800) -> str | None:
        return None
