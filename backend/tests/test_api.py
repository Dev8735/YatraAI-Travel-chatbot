"""API-level tests: validation, errors, isolation, chat flows, ingestion end-to-end, itinerary CRUD."""

import asyncio
import json

import httpx
import pytest
import respx

from app.ingestion.fetcher import SafeFetcher
from tests.conftest import CLIENT_A, CLIENT_B, PUBLIC_IP, fake_resolver


async def chat(client: httpx.AsyncClient, message: str, conv: str | None = None, headers=CLIENT_A) -> dict:
    r = await client.post("/api/chat", json={"message": message, "conversation_id": conv}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_health_reports_demo_mode(client) -> None:  # noqa: ANN001
    r = await client.get("/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["demo_mode"] is True
    assert body["components"]["llm"]["live"] is False
    assert "X-Request-ID" in r.headers
    assert "key" not in json.dumps(body).lower().replace("api_key", "")  # nothing secret-shaped


async def test_validation_errors_have_consistent_shape(client) -> None:  # noqa: ANN001
    r = await client.post("/api/chat", json={"message": ""}, headers=CLIENT_A)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["request_id"] and err["details"]["errors"]
    r = await client.post("/api/chat", json={"message": "x" * 5000}, headers=CLIENT_A)
    assert r.status_code == 422


async def test_client_id_required(client) -> None:  # noqa: ANN001
    r = await client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "client_id_required"
    r = await client.get("/api/conversations", headers={"X-Client-Id": "bad id!"})
    assert r.status_code == 400


async def test_unknown_route_404_shape(client) -> None:  # noqa: ANN001
    r = await client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


async def test_grounded_answer_with_demo_citation(client) -> None:  # noqa: ANN001
    d = await chat(client, "What is the best time to visit Varanasi?")
    assert d["intent"] == "website_qa" and d["answer_mode"] == "extractive"
    assert d["citations"] and d["citations"][0]["url"] == "/knowledge/demo/varanasi"
    assert d["citations"][0]["is_demo"] is True
    assert "[S1]" in d["answer"] and "October to March" in d["answer"]
    assert d["evidence"] in ("strong", "limited")


async def test_unanswerable_question_is_declined(client) -> None:  # noqa: ANN001
    d = await chat(client, "What is the visa policy for Antarctica?")
    assert d["citations"] == [] and d["evidence"] == "none"
    assert "couldn't find" in d["answer"]


async def test_follow_up_reference_uses_conversation_context(client) -> None:  # noqa: ANN001
    first = await chat(client, "Tell me about Varanasi ghats")
    d = await chat(client, "Can I take my phone inside the temple there?", first["conversation_id"])
    assert d["citations"] and "phones" in d["answer"].lower()


async def test_clarifying_question_then_resume(client) -> None:  # noqa: ANN001
    d = await chat(client, "plan a trip")
    assert d["blocks"][0]["type"] == "clarify" and d["blocks"][0]["missing"][0] == "destination"
    d = await chat(client, "Udaipur", d["conversation_id"])
    assert d["blocks"][0]["type"] == "clarify" and d["blocks"][0]["missing"] == ["duration_days"]
    d = await chat(client, "2 days", d["conversation_id"])
    assert d["intent"] == "itinerary_create" and d["blocks"][0]["type"] == "itinerary"
    assert len(d["blocks"][0]["plan"]["days"]) == 2


async def test_itinerary_chat_edits(client) -> None:  # noqa: ANN001
    d = await chat(client, "Plan a 2 day trip to Jaipur for heritage")
    conv = d["conversation_id"]
    plan = d["blocks"][0]["plan"]
    names = [s["place"]["name"] for day in plan["days"] for s in day["stops"]]
    d = await chat(client, f"remove {names[0]}", conv)
    assert d["intent"] == "itinerary_modify"
    new_names = [s["place"]["name"] for day in d["blocks"][0]["plan"]["days"] for s in day["stops"]]
    assert names[0] not in new_names
    d = await chat(client, "add one more day", conv)
    assert len(d["blocks"][0]["plan"]["days"]) == 3
    d = await chat(client, "make it cheaper", conv)
    assert d["blocks"][0]["plan"]["budget_estimate"]["tier"] == "budget"
    d = await chat(client, "how much will it cost?", conv)
    assert d["intent"] == "budget_estimate" and d["citations"][0]["url"] == "/knowledge/demo/budget-planning"
    assert "estimate" in d["answer"].lower()


async def test_edit_without_itinerary_explains(client) -> None:  # noqa: ANN001
    d = await chat(client, "add one more day")
    assert "no itinerary" in d["answer"].lower()


async def test_places_routes_transport_in_demo_mode(client) -> None:  # noqa: ANN001
    d = await chat(client, "Things to do in Udaipur")
    places = d["blocks"][0]["result"]
    assert places["data_origin"] == "demo" and places["places"]
    d = await chat(client, "hotels in Udaipur")
    assert d["blocks"][0]["result"]["places"] == []
    d = await chat(client, "Distance from Ahmedabad to Udaipur")
    route = d["blocks"][0]["route"]
    assert route["available"] is False and route["distance_meters"] is None and route["straight_line_km"]
    d = await chat(client, "trains from Mumbai to Goa")
    assert any(b["type"] == "transport" for b in d["blocks"])
    assert "can't confirm" in d["answer"] or any("can't confirm" in n for n in d["notices"])


async def test_multilingual_chat(client) -> None:  # noqa: ANN001
    d = await chat(client, "मुझे उदयपुर में 2 दिन घूमने का प्लान बनाओ")
    assert d["language"] == "hi" and d["intent"] == "itinerary_create" and "योजना" in d["answer"]
    d = await chat(client, "નમસ્તે")
    assert d["language"] == "gu" and "YatraAI" in d["answer"]


async def test_conversation_isolation_and_crud(client) -> None:  # noqa: ANN001
    d = await chat(client, "Compare Goa and Kerala for beaches")
    conv = d["conversation_id"]
    r = await client.get(f"/api/conversations/{conv}", headers=CLIENT_A)
    body = r.json()
    assert r.status_code == 200 and [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["metadata"]["blocks"][0]["type"] == "comparison"
    # another client can neither read, rename, delete nor continue it
    assert (await client.get(f"/api/conversations/{conv}", headers=CLIENT_B)).status_code == 404
    assert (await client.delete(f"/api/conversations/{conv}", headers=CLIENT_B)).status_code == 404
    r = await client.post("/api/chat", json={"message": "hi", "conversation_id": conv}, headers=CLIENT_B)
    assert r.status_code == 404
    assert (await client.get("/api/conversations", headers=CLIENT_B)).json()["total"] == 0
    # owner can rename and delete
    r = await client.patch(f"/api/conversations/{conv}", json={"title": "Beach plans"}, headers=CLIENT_A)
    assert r.json()["title"] == "Beach plans"
    listing = (await client.get("/api/conversations", headers=CLIENT_A)).json()
    assert listing["total"] == 1 and listing["items"][0]["title"] == "Beach plans"
    assert (await client.delete(f"/api/conversations/{conv}", headers=CLIENT_A)).status_code == 204
    assert (await client.get(f"/api/conversations/{conv}", headers=CLIENT_A)).status_code == 404


async def test_streaming_endpoint_emits_meta_delta_final(client) -> None:  # noqa: ANN001
    async with client.stream("POST", "/api/chat/stream", json={"message": "Tell me about rafting in Rishikesh"},
                             headers=CLIENT_A) as r:
        assert r.status_code == 200
        raw = "".join([chunk async for chunk in r.aiter_text()])
    events = [line.split(":", 1)[1].strip() for line in raw.splitlines() if line.startswith("event:")]
    assert events[0] == "meta" and "delta" in events and events[-1] == "final"
    final = json.loads([ln for ln in raw.splitlines() if ln.startswith("data:")][-1][5:])
    assert final["citations"] and final["conversation_id"]


async def test_rate_limit_returns_429(client, settings) -> None:  # noqa: ANN001
    settings.rate_limit_chat_per_minute = 2
    from app.core import config

    config.get_settings.cache_clear()
    original = config.get_settings
    config.get_settings = lambda: settings  # type: ignore[assignment]
    try:
        import app.api.chat as chat_api

        chat_api.get_settings = config.get_settings  # the limiter reads settings lazily
        codes = [(await client.post("/api/chat", json={"message": "hi"}, headers=CLIENT_A)).status_code
                 for _ in range(3)]
        assert codes[-1] == 429
    finally:
        config.get_settings = original
        chat_api.get_settings = original


# ----------------------------------------------------------------- knowledge sources
@pytest.fixture
def container_overrides() -> dict:
    return {"fetcher_factory": lambda: SafeFetcher(user_agent="YatraAI-Test/1.0", resolver=fake_resolver)}


SITE = {
    "/": """<html><head><title>Testville Tourism</title></head><body><main><h1>Welcome to Testville</h1>
<p>Testville is a small mountain town famous for the Zorblax Waterfall, which is best visited in early spring
when snowmelt makes it roar. The town also hosts the Glimmer Lantern Festival every November along the river.</p>
<a href="/food">Food</a><a href="/private/x">Secret</a><a href="/dup">Dup</a></main></body></html>""",
    "/food": """<html><head><title>Food in Testville</title></head><body><main><h1>Eating in Testville</h1>
<p>The signature dish of Testville is the quorpel dumpling, served with smoked mountain honey at the old market.
Most food stalls at the old market open in the evening and close around midnight during festival season.</p>
</main></body></html>""",
}


def mock_site(router: respx.MockRouter) -> None:
    base = f"https://{PUBLIC_IP}"
    router.get(f"{base}/robots.txt").mock(return_value=httpx.Response(
        200, text="User-agent: *\nDisallow: /private\n", headers={"content-type": "text/plain"}))
    for path, html in SITE.items():
        router.get(f"{base}{path}").mock(return_value=httpx.Response(200, text=html,
                                                                     headers={"content-type": "text/html"}))
    router.get(f"{base}/dup").mock(return_value=httpx.Response(200, text=SITE["/food"],
                                                               headers={"content-type": "text/html"}))


async def wait_for_job(client: httpx.AsyncClient, job_id: str) -> dict:
    for _ in range(100):
        job = (await client.get(f"/api/knowledge/jobs/{job_id}")).json()
        if job["status"] not in ("queued", "running"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError("ingestion did not finish")


async def test_ingest_website_and_answer_with_its_citations(client) -> None:  # noqa: ANN001
    with respx.mock(assert_all_called=False) as router:
        mock_site(router)
        r = await client.post("/api/knowledge/sources", json={"url": "https://testville.example/", "max_pages": 5,
                                                              "max_depth": 1})
        assert r.status_code == 201, r.text
        source = r.json()
        job = await wait_for_job(client, source["latest_job"]["id"])
    assert job["status"] == "succeeded", job
    assert job["pages_indexed"] == 2 and job["pages_skipped"] >= 1  # /private disallowed, /dup duplicate
    assert any("robots" in e["reason"] for e in job["errors"])

    d = await chat(client, "What is the signature dish of Testville?")
    assert d["citations"] and d["citations"][0]["url"] == "https://testville.example/food"
    assert d["citations"][0]["is_demo"] is False and "quorpel" in d["answer"]

    # Re-ingesting unchanged content does not duplicate chunks
    with respx.mock(assert_all_called=False) as router:
        mock_site(router)
        job2 = (await client.post(f"/api/knowledge/sources/{source['id']}/ingest")).json()
        job2 = await wait_for_job(client, job2["id"])
    assert job2["pages_unchanged"] == 2 and job2["pages_indexed"] == 0
    detail = (await client.get(f"/api/knowledge/sources/{source['id']}")).json()
    assert detail["page_count"] == 2 and detail["status"] == "ready"
    chunks_before = detail["chunk_count"]

    # Deleting the source removes its content from retrieval
    assert (await client.delete(f"/api/knowledge/sources/{source['id']}")).status_code == 204
    d = await chat(client, "What is the signature dish of Testville?")
    assert not any(c["url"].startswith("https://testville.example") for c in d["citations"])
    assert chunks_before > 0


@pytest.mark.parametrize("url", ["http://localhost:80/", "http://169.254.169.254/latest", "http://evil.example/",
                                 "file:///etc/passwd", "http://10.0.0.1/", "https://user:pw@site.example/"])
async def test_unsafe_sources_rejected(client, url: str) -> None:  # noqa: ANN001
    r = await client.post("/api/knowledge/sources", json={"url": url})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsafe_url"


async def test_duplicate_source_conflict_and_demo_protection(client) -> None:  # noqa: ANN001
    with respx.mock(assert_all_called=False) as router:
        mock_site(router)
        r1 = await client.post("/api/knowledge/sources", json={"url": "https://testville.example/"})
        await wait_for_job(client, r1.json()["latest_job"]["id"])
        r2 = await client.post("/api/knowledge/sources", json={"url": "testville.example"})
    assert r2.status_code == 409 and r2.json()["error"]["details"]["source_id"] == r1.json()["id"]
    sources = (await client.get("/api/knowledge/sources")).json()
    demo = next(s for s in sources if s["is_demo"])
    assert demo["page_count"] == 10
    r = await client.post(f"/api/knowledge/sources/{demo['id']}/ingest")
    assert r.status_code == 409


async def test_failed_site_reports_errors(client) -> None:  # noqa: ANN001
    with respx.mock(assert_all_called=False) as router:
        router.get(f"https://{PUBLIC_IP}/robots.txt").mock(return_value=httpx.Response(404))
        router.get(f"https://{PUBLIC_IP}/").mock(return_value=httpx.Response(500))
        r = await client.post("/api/knowledge/sources", json={"url": "https://down.example/"})
        job = await wait_for_job(client, r.json()["latest_job"]["id"])
    assert job["status"] == "failed" and job["errors"][0]["reason"] == "The page returned HTTP 500."
    src = (await client.get(f"/api/knowledge/sources/{r.json()['id']}")).json()
    assert src["status"] == "failed"


async def test_demo_article_endpoints(client) -> None:  # noqa: ANN001
    docs = (await client.get("/api/knowledge/demo")).json()
    assert {d["slug"] for d in docs} >= {"jaipur", "varanasi", "train-travel"}
    art = (await client.get("/api/knowledge/demo/jaipur")).json()
    assert "Demo knowledge-base article" in art["body"]
    assert (await client.get("/api/knowledge/demo/nope")).status_code == 404


# ----------------------------------------------------------------- itineraries REST
async def test_itinerary_rest_crud_and_versioning(client) -> None:  # noqa: ANN001
    r = await client.post("/api/itineraries", json={"destination": "Varanasi", "days": 2, "interests": ["spiritual"],
                                                    "pace": "relaxed"}, headers=CLIENT_A)
    assert r.status_code == 201
    it = r.json()
    assert it["version"] == 1 and len(it["plan"]["days"]) == 2
    stop_id = it["plan"]["days"][0]["stops"][0]["id"]

    r = await client.patch(f"/api/itineraries/{it['id']}", headers=CLIENT_A, json={
        "expected_version": 1, "operations": [{"op": "remove_stop", "stop_id": stop_id}, {"op": "add_day"},
                                              {"op": "rename", "title": "Kashi trip"}]})
    assert r.status_code == 200, r.text
    it2 = r.json()
    assert it2["version"] == 2 and it2["title"] == "Kashi trip" and len(it2["plan"]["days"]) == 3

    stale = await client.patch(f"/api/itineraries/{it['id']}", headers=CLIENT_A,
                               json={"expected_version": 1, "operations": [{"op": "add_day"}]})
    assert stale.status_code == 409
    bad = await client.patch(f"/api/itineraries/{it['id']}", headers=CLIENT_A,
                             json={"operations": [{"op": "remove_day", "day": 9}]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_day"
    unknown_op = await client.patch(f"/api/itineraries/{it['id']}", headers=CLIENT_A,
                                    json={"operations": [{"op": "teleport"}]})
    assert unknown_op.status_code == 422

    assert (await client.get(f"/api/itineraries/{it['id']}", headers=CLIENT_B)).status_code == 404
    assert len((await client.get("/api/itineraries", headers=CLIENT_A)).json()) == 1
    assert (await client.delete(f"/api/itineraries/{it['id']}", headers=CLIENT_A)).status_code == 204
    assert (await client.get(f"/api/itineraries/{it['id']}", headers=CLIENT_A)).status_code == 404


async def test_places_and_routes_rest(client) -> None:  # noqa: ANN001
    r = await client.get("/api/places/search", params={"q": "temples", "near": "Varanasi", "category": "temple"})
    assert r.status_code == 200 and r.json()["places"][0]["data_origin"] == "demo"
    assert (await client.get("/api/places/search", params={"category": "nuclear"})).status_code == 422
    pid = r.json()["places"][0]["id"]
    assert (await client.get(f"/api/places/{pid}")).json()["id"] == pid
    assert (await client.get("/api/places/photo", params={"name": "places/x/photos/y"})).status_code == 404
    r = await client.post("/api/routes", json={"origin": "Delhi", "destination": "Agra"})
    assert r.json()["available"] is False and r.json()["straight_line_km"]
    assert (await client.post("/api/routes", json={"origin": "D", "destination": ""})).status_code == 422
