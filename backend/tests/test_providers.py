"""Provider-layer regression tests. No network: payloads are injected into the persistent cache or http is monkeypatched."""
import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

os.environ["PLARNO_OFFLINE"] = "1"
from app import config, db  # noqa: E402
from app.agents import tools  # noqa: E402
from app.providers import base, flights, gemini, overpass, staying  # noqa: E402

config.RATE_LIMIT_PER_MIN = 100000
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    db.reset(os.path.join(tempfile.mkdtemp(), "p.db"))
    base.reset_breakers()
    yield TestClient(app)
    config.OFFLINE = True
    db.reset()


def put_cache(key, value):
    db.run("INSERT INTO api_cache(key,value,fetched_at) VALUES(?,?,?)", (key, json.dumps(value), time.time()))


def auth(c):
    r = c.post("/api/auth/register", json={"email": f"p{time.time_ns()}@example.com", "password": "password123"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_gemini_validation_drops_bad_values():
    out = gemini.validate({"destination": "Atlantis", "origin": "Jaipur", "days": 400, "adults": "two", "budget_inr": 5, "pace": "turbo",
                           "interests": ["history", "skydiving"], "vegan": "yes", "peaceful": True, "transport_pref": "cheapest", "bogus": 1})
    assert out == {"origin": "Jaipur", "destination": "Atlantis", "interests": ["history"], "peaceful": True, "transport_pref": "cheapest"}  # place names are validated later by geocoding


def test_gemini_rejects_non_place_strings():
    assert gemini.validate({"destination": "x", "origin": "12345 Main St/Apt 4"}) == {}


def test_gemini_disabled_offline_returns_nothing(client):
    assert gemini.extract_fields("plan a trip to Delhi for 5 days") == {} and gemini.answer("hi", "facts") is None


def test_tool_intent_classification():
    assert tools.classify("Find hotels under ₹4,000") == {"intent": "hotels_filter", "max": 4000.0}
    assert tools.classify("hotels below 3.5k")["max"] == 3500.0
    assert tools.classify("Find good restaurants around my hotel")["intent"] == "restaurants_near"
    assert tools.classify("Show historical places nearby")["intent"] == "places_nearby"
    assert tools.classify("Show the best route for these five attractions")["intent"] == "route_best"
    assert tools.classify("Explain today's weather and pollution")["intent"] == "weather_aqi"
    assert tools.classify("hello there") is None


def test_full_planning_request_not_hijacked_by_tools(client):
    h = auth(client)
    msg = ("Plan a five-day Delhi trip for two people with a total budget of ₹30,000. I want historical attractions, good food near the "
           "attractions, a hotel with beautiful interiors, peaceful surroundings and good transport connectivity.")
    r = client.post("/api/chat", headers=h, json={"message": msg}).json()
    assert "itinerary" in r["plan"]


def test_trip_tools_use_real_services(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day Delhi trip for two, budget ₹30000, history"}).json()["trip_id"]
    r = client.post("/api/chat", headers=h, json={"message": "Find hotels under ₹4,000", "trip_id": tid}).json()
    assert "at or under" in r["reply"] and r["action"]["to"] == "/workspace?tab=hotels"
    prices = [int(x.replace(",", "")) for x in __import__("re").findall(r"₹([\d,]+)/night", r["reply"].split("\n", 1)[1])]
    assert prices and all(p <= 4000 for p in prices)
    r = client.post("/api/chat", headers=h, json={"message": "Show the best route for these five attractions", "trip_id": tid}).json()
    assert "Best visiting order" in r["reply"] and "Day 1" in r["reply"]
    r = client.post("/api/chat", headers=h, json={"message": "Find good restaurants around my hotel", "trip_id": tid}).json()
    assert "unavailable" in r["reply"] and "fictional" in r["reply"]  # offline: honest fallback to labelled demo data
    r = client.post("/api/chat", headers=h, json={"message": "Explain today's weather and pollution", "trip_id": tid}).json()
    assert "unavailable" in r["reply"]  # no live provider offline: says so instead of inventing numbers


def test_overpass_normalisation_never_invents_fields(client):
    els = [{"type": "node", "id": 1, "lat": 28.61, "lon": 77.21, "tags": {"name": "Cafe X", "amenity": "cafe", "cuisine": "coffee_shop"}},
           {"type": "way", "id": 2, "center": {"lat": 28.62, "lon": 77.22}, "tags": {"name": "Fort Y", "historic": "fort", "wikidata": "Q1", "opening_hours": "Mo-Su 09:00-17:00"}},
           {"type": "node", "id": 3, "lat": 28.6, "lon": 77.2, "tags": {"amenity": "cafe"}}]  # no name: dropped
    put_cache("overpass:restaurants:28.614,77.209:1200", els)
    res = overpass.nearby("restaurants", 28.6139, 77.2090, 1200)
    assert [p["name"] for p in res["places"]] == ["Fort Y", "Cafe X"]  # notable first
    cafe = next(p for p in res["places"] if p["name"] == "Cafe X")
    assert cafe["opening_hours"] is None and cafe["stars"] is None and cafe["diet_vegetarian"] is None  # absent in OSM => None
    assert "rating" not in cafe and "price_for_two" not in cafe
    assert res["provenance"]["kind"] == "cached" and "OpenStreetMap" in res["provenance"]["source"]


def test_overpass_down_returns_empty_not_fake(client):
    res = overpass.nearby("hospitals", 1.0, 2.0)  # offline, nothing cached
    assert res["places"] == [] and res["provenance"]["kind"] == "none"
    assert client.get("/api/places/nearby", params={"category": "nope"}).status_code == 422
    assert client.get("/api/places/nearby", params={"category": "hospitals", "radius_m": 5}).status_code == 422


def test_staying_sandbox_results_are_quarantined(client, monkeypatch):
    monkeypatch.setattr(config, "STAYING_KEY", "stay_test_abc")
    fixture = {"data": [{"id": "x", "name": "Apartments Abramovic 2", "location": {"lat": 43.7, "lng": 15.9, "city": "Sibenik", "country": "HR"},
                         "price": {"nightlyPrice": 303, "currency": "EUR", "url": "https://example.test"}}]}
    put_cache("staying:New Delhi, India:2026-12-05:2026-12-09:2:10", fixture)
    r = client.get("/api/hotels/provider").json()
    assert r["sandbox"] is True and r["provenance"]["kind"] == "simulated" and "SANDBOX" in r["provenance"]["note"]
    # sandbox hotels never appear in recommendations
    assert all("Abramovic" not in h["name"] for h in client.get("/api/hotels").json())


def test_live_flights_normalised_and_labelled(client, monkeypatch):
    monkeypatch.setattr(config, "SERP_FLIGHTS_KEY", "k")
    monkeypatch.setattr(config, "OFFLINE", False)
    raw = {"best_flights": [{"flights": [{"airline": "IndiGo", "flight_number": "6E 349", "departure_airport": {"id": "BOM", "time": "2026-12-05 15:15"},
                                           "arrival_airport": {"id": "DEL", "time": "2026-12-05 17:25"}, "duration": 130}], "total_duration": 130, "price": 13168}],
           "other_flights": [], "link": "https://www.google.com/travel/flights?x"}
    put_cache("serpflights:BOM-DEL:2026-12-05:1", raw)
    r = client.get("/api/transport/search", params={"origin": "Mumbai", "destination": "Delhi", "date": "2026-12-05", "travellers": 2, "live_flights": True}).json()
    live = [j for j in r["journeys"] if j["provenance"]["kind"] in ("live", "cached") and j["summary"] == "flight"]
    assert len(live) == 1 and live[0]["total_fare_inr"] == 13168 * 2  # per-person fare x travellers
    assert live[0]["legs"][0]["booking_link"].startswith("https://www.google.com") and "Live flight fares" in r["live_note"]
    assert not any(j["summary"] == "flight" and j["provenance"]["kind"] == "simulated" for j in r["journeys"])  # simulated direct flights replaced


def test_provider_failure_falls_back_with_clear_message(client, monkeypatch):
    """Scenario 4: provider outage is detected, explained, simulated alternatives remain, breaker prevents hammering."""
    monkeypatch.setattr(config, "SERP_FLIGHTS_KEY", "k")
    monkeypatch.setattr(config, "OFFLINE", False)
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("provider down")
    monkeypatch.setattr(base, "http_json", boom)
    p = {"origin": "Mumbai", "destination": "Delhi", "date": "2026-12-06", "travellers": 1, "live_flights": True}
    r = client.get("/api/transport/search", params=p).json()
    assert "unavailable" in r["live_note"].lower() and r["journeys"]
    assert all(j["provenance"]["kind"] == "simulated" for j in r["journeys"])
    client.get("/api/transport/search", params=p)
    assert calls["n"] == 1  # circuit breaker: second search did not call the dead provider again


def test_flight_daily_guard(client, monkeypatch):
    monkeypatch.setattr(config, "FLIGHT_SEARCHES_PER_DAY", 0)
    assert base.quota_ok("serpapi", 0) is False


def test_provider_health_never_leaks_keys(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_KEY", "SECRET-GEMINI-VALUE")
    monkeypatch.setattr(config, "STAYING_KEY", "stay_test_SECRETSTAY")
    text = client.get("/api/providers/health").text + client.get("/api/config").text
    assert "SECRET-GEMINI-VALUE" not in text and "SECRETSTAY" not in text
    rows = {r["provider"]: r for r in client.get("/api/providers/health").json()}
    assert rows["StayingAPI"]["status"] == "sandbox" and rows["Qrail"]["status"] in ("not integrated", "no key")
    base.last_outcome["overpass"] = {"ok": False, "at": "t", "error": "ReadTimeout"}
    rows = {r["provider"]: r for r in client.get("/api/providers/health").json()}
    assert rows["OpenStreetMap Overpass"]["status"] == "degraded" and "ReadTimeout" in rows["OpenStreetMap Overpass"]["note"]  # health reports reality, not just configuration
    base.last_outcome.clear()
