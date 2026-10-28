"""Provider adapters with mocked HTTP: defensive mapping, key handling, honest fallbacks."""

import httpx
import pytest
import respx

from app.core.errors import ProviderError
from app.providers.places.demo import DemoPlacesProvider
from app.providers.places.google import GooglePlacesProvider, map_place
from app.providers.routes.providers import ROUTES_URL, GoogleRoutesProvider, NoRoutesProvider
from app.providers.transport.providers import NoTransportProvider
from app.schemas.travel import RouteRequest

RAW_PLACE = {
    "id": "ChIJabc123def456",
    "displayName": {"text": "Hawa Mahal"},
    "formattedAddress": "Badi Choupad, Jaipur",
    "location": {"latitude": 26.92, "longitude": 75.82},
    "rating": 4.5, "userRatingCount": 120345,
    "types": ["tourist_attraction", "point_of_interest"], "primaryType": "tourist_attraction",
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"]},
    "photos": [{"name": "places/ChIJabc123def456/photos/AbC_d-1", "widthPx": 800, "heightPx": 600,
                "authorAttributions": [{"displayName": "A. Photographer", "uri": "https://maps.google.com/u/1"}]},
               {"name": "../../etc/passwd"}],
    "priceLevel": "PRICE_LEVEL_MODERATE",
}


def test_map_place_full_and_safe_photo_proxy() -> None:
    p = map_place(RAW_PLACE, "Jaipur")
    assert p and p.name == "Hawa Mahal" and p.rating == 4.5 and p.user_rating_count == 120345
    assert p.data_origin == "live" and p.provider == "google_places"
    assert len(p.photos) == 1  # the malformed photo name is dropped
    assert p.photos[0].url.startswith("/api/places/photo?name=places/")
    assert "key=" not in p.photos[0].url
    assert p.photos[0].attributions[0].name == "A. Photographer"
    assert p.price_level == "moderate"


@pytest.mark.parametrize("raw", [{}, {"id": "x"}, {"displayName": {"text": "No id"}},
                                 {"id": "bad id with spaces!", "displayName": {"text": "x"}}])
def test_map_place_rejects_incomplete(raw: dict) -> None:
    assert map_place(raw) is None


def test_map_place_missing_optional_fields() -> None:
    p = map_place({"id": "ChIJminimal0001", "displayName": {"text": "Somewhere"}, "rating": "n/a"})
    assert p and p.rating is None and p.photos == [] and p.opening_hours == [] and p.lat is None


@respx.mock
async def test_google_places_search_sends_key_in_header_and_maps() -> None:
    route = respx.post("https://places.googleapis.com/v1/places:searchText").mock(
        return_value=httpx.Response(200, json={"places": [RAW_PLACE, {"bad": True}]}))
    provider = GooglePlacesProvider("test-key-123")
    result = await provider.search("forts", near="Jaipur", lat=26.9, lng=75.8, category="tourist_attraction")
    req = route.calls.last.request
    assert req.headers["x-goog-api-key"] == "test-key-123" and "places.displayName" in req.headers["x-goog-fieldmask"]
    assert "test-key-123" not in str(req.url)
    assert result.data_origin == "live" and [p.name for p in result.places] == ["Hawa Mahal"]
    await provider.aclose()


@respx.mock
async def test_google_places_errors_are_user_safe() -> None:
    respx.post("https://places.googleapis.com/v1/places:searchText").mock(return_value=httpx.Response(429))
    provider = GooglePlacesProvider("k")
    with pytest.raises(ProviderError, match="rate limited"):
        await provider.search("x")
    respx.post("https://places.googleapis.com/v1/places:searchText").mock(
        return_value=httpx.Response(403, json={"error": {"message": "API key invalid: k"}}))
    with pytest.raises(ProviderError) as exc:
        await provider.search("x")
    assert "API key" not in exc.value.message
    await provider.aclose()


@respx.mock
async def test_photo_uri_validates_name() -> None:
    respx.get(url__regex=r"https://places\.googleapis\.com/v1/places/.+/media.*").mock(
        return_value=httpx.Response(200, json={"photoUri": "https://lh3.googleusercontent.com/p/abc"}))
    provider = GooglePlacesProvider("k")
    assert await provider.photo_uri("places/ChIJabc/photos/xyz") == "https://lh3.googleusercontent.com/p/abc"
    assert await provider.photo_uri("../secrets") is None
    await provider.aclose()


async def test_demo_places_are_labelled_and_never_list_hotels() -> None:
    demo = DemoPlacesProvider()
    result = await demo.search("forts", near="Jaipur")
    assert result.data_origin == "demo" and result.places and "not live" in (result.notice or "")
    assert all(p.rating is None and not p.photos and not p.opening_hours for p in result.places)
    hotels = await demo.search("hotels", near="Jaipur", category="lodging")
    assert hotels.places == [] and "invented" in (hotels.notice or "")
    assert (await demo.search("x", near="Atlantis")).places == []


async def test_demo_region_expands_to_member_cities() -> None:
    result = await DemoPlacesProvider().search("", near="Kerala", limit=20)
    assert {p.destination for p in result.places} >= {"Kochi", "Munnar"}


@respx.mock
async def test_google_routes_parses_provider_values() -> None:
    route = respx.post(ROUTES_URL).mock(return_value=httpx.Response(200, json={"routes": [{
        "distanceMeters": 233000, "duration": "14400s", "description": "NH48",
        "polyline": {"encodedPolyline": "abc"},
        "legs": [{"distanceMeters": 100000, "duration": "6000s"}, {"distanceMeters": 133000, "duration": "8400s"}],
    }]}))
    provider = GoogleRoutesProvider("k")
    result = await provider.compute(RouteRequest(origin="Ahmedabad", destination="Udaipur", stops=["Himmatnagar"]))
    body = route.calls.last.request.content.decode()
    assert '"intermediates":[{"address":"Himmatnagar"}]' in body.replace(" ", "")
    assert result.available and result.distance_meters == 233000 and result.duration_seconds == 14400
    assert [leg.end for leg in result.legs] == ["Himmatnagar", "Udaipur"]
    assert result.straight_line_km is None
    await provider.aclose()


@respx.mock
async def test_google_routes_no_route() -> None:
    respx.post(ROUTES_URL).mock(return_value=httpx.Response(200, json={}))
    provider = GoogleRoutesProvider("k")
    result = await provider.compute(RouteRequest(origin="Delhi", destination="Bali"))
    assert not result.available and result.distance_meters is None
    await provider.aclose()


async def test_no_routes_provider_never_reports_road_distance() -> None:
    result = await NoRoutesProvider().compute(RouteRequest(origin="Ahmedabad", destination="Udaipur"))
    assert not result.available and result.distance_meters is None and result.duration_seconds is None
    assert result.straight_line_km and 150 < result.straight_line_km < 300
    assert "straight-line" in result.notice and "not use this for planning" in result.notice
    unknown = await NoRoutesProvider().compute(RouteRequest(origin="Foo town", destination="Bar city"))
    assert unknown.straight_line_km is None


async def test_no_transport_provider_links_official_sources() -> None:
    info = await NoTransportProvider().lookup(mode="TRAIN", origin="Mumbai", destination="Goa")
    assert not info.available and "can't confirm" in info.message
    assert any("irctc.co.in" in link.url for link in info.official_links)
