"""Live guide: forecast grouping, tips, recommendations, packing advice and the API. All offline: provider payloads are injected."""
import os
import tempfile
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ["PLARNO_OFFLINE"] = "1"
from app import config, db  # noqa: E402

config.OFFLINE = True
config.RATE_LIMIT_PER_MIN = 100000
from app.agents.context import TripContext  # noqa: E402
from app.main import app  # noqa: E402
from app.services import guide, live  # noqa: E402

DEMO = "Plan a five-day Delhi trip for two people. Our total budget is ₹30,000. We want to visit historical places and enjoy good food."


@pytest.fixture()
def client():
    d = tempfile.mkdtemp()
    db.reset(os.path.join(d, "t.db"))
    yield TestClient(app)
    db.reset()


def auth(client, email="g@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "name": "G"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def _feed(start: date, temps, pops, offset=19800):
    """OpenWeather /forecast shape: 3-hourly rows; here one midday and one night row per day."""
    rows = []
    for i, (t, p) in enumerate(zip(temps, pops)):
        for hour, delta in ((13, 0), (2, -6)):
            local = datetime(start.year, start.month, start.day, hour, tzinfo=timezone(timedelta(seconds=offset))) + timedelta(days=i)
            rows.append({"dt": int(local.timestamp()), "main": {"temp": t + delta, "temp_min": t + delta - 1, "temp_max": t + delta + 1},
                         "weather": [{"main": "Rain" if p > 0.5 else "Clear", "description": "light rain" if p > 0.5 else "clear sky"}], "pop": p})
    rows.sort(key=lambda r: r["dt"])
    return {"list": rows, "city": {"timezone": offset, "sunrise": int(datetime(start.year, start.month, start.day, 1, 0, tzinfo=timezone.utc).timestamp()),
                                   "sunset": int(datetime(start.year, start.month, start.day, 12, 0, tzinfo=timezone.utc).timestamp())}}


def _patch(monkeypatch, start, temps, pops, aqi=None):
    monkeypatch.setattr(config, "OPENWEATHER_KEY", "k")
    monkeypatch.setattr(live, "_get", lambda key, url, params, ttl: (_feed(start, temps, pops), "live") if key.startswith("fc:") else (None, "offline"))
    monkeypatch.setattr(live, "weather", lambda la, lo: {"available": True, "temp_c": temps[0], "feels_like_c": temps[0], "humidity": 40, "summary": "clear sky", "wind_ms": 2,
                                                        "provenance": {"kind": "live", "source": "t"}})
    monkeypatch.setattr(live, "aqi", lambda la, lo: {"value": aqi, "station": "S", "provenance": {"kind": "live", "source": "t"}} if aqi else None)


def test_forecast_groups_by_local_day(monkeypatch):
    start = date(2026, 12, 1)
    _patch(monkeypatch, start, [20, 22, 9], [0.0, 0.8, 0.1])
    fc = guide.forecast(28.6, 77.2)
    assert [d["date"] for d in fc["days"]] == ["2026-12-01", "2026-12-02", "2026-12-03"]
    assert fc["days"][1]["pop"] == 0.8 and fc["days"][1]["condition"] == "Rain"
    assert fc["days"][0]["max_c"] == 21 and fc["days"][0]["min_c"] == 13   # midday +1, night (-6) -1
    assert fc["utc_offset_min"] == 330 and fc["sunrise"] == "06:30"


def test_no_key_means_no_forecast_not_a_guess(monkeypatch):
    monkeypatch.setattr(config, "OPENWEATHER_KEY", "")
    assert guide.forecast(0, 0) is None
    snap = guide.snapshot(0, 0)
    assert snap["forecast"] is None and snap["utc_offset_min"] is None


def _plan(start: date):
    stop = lambda i, name, flag=None: {"type": "attraction", "id": f"a{i}", "name": name, "lat": 28.6 + i / 100, "lon": 77.2, "types": ["Park"], "hours_flag": flag, "start": "10:00"}  # noqa: E731
    return {"itinerary": {"hotel": {"lat": 28.6, "lon": 77.2, "name": "H"}, "days": [
        {"day": 1, "date": start.isoformat(), "stops": [stop(1, "City Park")], "travel_min": 40, "distance_km": 9},
        {"day": 2, "date": (start + timedelta(days=1)).isoformat(), "stops": [stop(2, "Old Garden", "closed")], "travel_min": 200, "distance_km": 60}]},
        "budget": {"within_budget": False, "remaining_inr": -5000, "max_budget_inr": 30000, "estimated_total_inr": 35000},
        "hotel": {"id": "h1", "name": "H", "avg_km_to_attractions": 9.5}}


def test_tips_cover_rain_budget_hours_air_and_distance(monkeypatch):
    start = date(2026, 12, 1)
    _patch(monkeypatch, start, [20, 36], [0.0, 0.9], aqi=210)
    ctx = TripContext(destination="Testville", days=2, adults=2, budget_inr=30000, selected_attraction_ids=["a1", "a2"], dates_assumed=True)
    plan = _plan(start)
    snap = guide.snapshot(28.6, 77.2)
    per = guide.day_weather(plan, snap["forecast"])
    assert set(per) == {"1", "2"}
    tips = guide.tips(ctx, plan, snap, per)
    titles = " | ".join(t["title"] for t in tips)
    for want in ("Over budget", "Rain likely on day 2", "Hot afternoon on day 2", "Poor air quality", "Closed on day 2"):
        assert want in titles, titles
    assert tips[0]["level"] == "warn"                                   # problems first
    assert next(t for t in tips if t["title"] == "Over budget")["ask"] == "Make it cheaper"
    assert "Old Garden" in next(t for t in tips if t["title"].startswith("Rain"))["text"]  # names the outdoor stop that day


def test_clean_plan_says_so(monkeypatch):
    start = date(2026, 12, 1)
    _patch(monkeypatch, start, [22, 23], [0.0, 0.1])
    ctx = TripContext(destination="Testville", origin="Home", start_date=start.isoformat(), days=1, adults=1, budget_inr=30000)
    plan = _plan(start)
    plan["itinerary"]["days"] = plan["itinerary"]["days"][:1]
    plan["budget"], plan["hotel"] = {"within_budget": True, "remaining_inr": 100}, {"id": "h1", "name": "H", "avg_km_to_attractions": 2}
    snap = guide.snapshot(28.6, 77.2)
    tips = guide.tips(ctx, plan, snap, guide.day_weather(plan, snap["forecast"]))
    assert [t["level"] for t in tips] == ["good"]


def test_recommendations_skip_chosen_and_explain_why():
    ctx = TripContext(destination="X", interests=["museum"], selected_attraction_ids=["in"])
    plan = {"itinerary": {"hotel": {"lat": 10.0, "lon": 10.0, "name": "H"}, "days": [{"day": 1, "stops": [{"type": "meal", "id": "r-used"}]}]}}
    pool = [{"id": "in", "name": "Already chosen", "lat": 10.0, "lon": 10.0, "rating": 5, "reviews": 99999, "types": []},
            {"id": "far", "name": "Far Fort", "lat": 10.5, "lon": 10.0, "rating": 4.9, "reviews": 50000, "types": ["Fort"]},
            {"id": "near", "name": "Near Museum", "lat": 10.01, "lon": 10.0, "rating": 4.6, "reviews": 20000, "types": ["Museum"]},
            {"id": "nogeo", "name": "No location", "lat": None, "lon": None, "types": []}]
    food = [{"id": "r-used", "name": "Used", "lat": 10.0, "lon": 10.0, "rating": 5}, {"id": "r1", "name": "Bistro", "lat": 10.0, "lon": 10.001, "rating": 4.5, "reviews": 800, "veg": True},
            {"id": "r2", "name": "Steakhouse", "lat": 10.0, "lon": 10.001, "rating": 4.9, "reviews": 800, "veg": False}]
    r = guide.recommendations(ctx, plan, pool, food)
    assert [p["id"] for p in r["places"]] == ["near", "far"]            # interest match + distance beat raw popularity; chosen/no-geo excluded
    assert r["places"][0]["match"] == "museum" and any("km from your hotel" in w for w in r["places"][0]["why"])
    assert [f["id"] for f in r["food"]] == ["r2", "r1"]
    ctx.vegetarian = True
    assert [f["id"] for f in guide.recommendations(ctx, plan, pool, food)["food"]] == ["r1"]


def test_packing_uses_forecast_and_plan(monkeypatch):
    start = date(2026, 12, 1)
    _patch(monkeypatch, start, [4, 6], [0.0, 0.7], aqi=180)
    ctx = TripContext(destination="Testville", days=2, adults=2)
    plan = _plan(start)
    plan["itinerary"]["days"][0]["stops"].append({"type": "attraction", "id": "t", "name": "Grand Temple", "types": ["Hindu temple"], "lat": 28.6, "lon": 77.2})
    text = guide.packing(ctx, plan)
    assert "Packing for Testville" in text and "your trip days" in text
    for want in ("jacket", "rain is likely", "mask", "Grand Temple", "walking shoes"):
        assert want in text, text
    assert guide.is_packing_question("What should I pack?") and guide.is_packing_question("what to wear in the evening")
    assert not guide.is_packing_question("Make it cheaper") and not guide.is_packing_question("Bring the cost down")


def test_guide_api(client, monkeypatch):
    h = auth(client)
    empty = client.post("/api/chat", headers=h, json={"message": "I want to explore Delhi"}).json()
    assert client.get(f"/api/trips/{empty['trip_id']}/guide", headers=h).status_code == 409     # no plan yet
    tid = client.post("/api/chat", headers=h, json={"message": DEMO}).json()["trip_id"]
    assert client.get(f"/api/trips/{tid}/guide").status_code == 401
    assert client.get(f"/api/trips/{tid}/guide", headers=auth(client, "other@example.com")).status_code == 404
    g = client.get(f"/api/trips/{tid}/guide", headers=h)
    assert g.status_code == 200, g.text
    g = g.json()
    assert g["briefing"] is None                                         # offline: no language model, and nothing invented in its place
    assert g["live"]["weather"] is None and g["live"]["forecast"] is None and g["day_weather"] == {}
    assert g["tips"] and all(t["level"] in ("warn", "info", "good") for t in g["tips"])
    recs = g["recommendations"]["places"]
    assert recs and all(p["demo"] for p in recs)                         # Delhi demo rows are flagged for the UI
    plan = client.get(f"/api/trips/{tid}", headers=h).json()
    chosen = set(plan["context"]["selected_attraction_ids"])
    assert not chosen & {p["id"] for p in recs}
    # a recommendation can be added through the normal rebuild endpoint
    r = client.post(f"/api/trips/{tid}/itinerary/rebuild", headers=h, json={"attraction_ids": plan["context"]["selected_attraction_ids"] + [recs[0]["id"]]})
    assert r.status_code == 200, r.text
    again = client.get(f"/api/trips/{tid}/guide", headers=h).json()
    assert recs[0]["id"] not in {p["id"] for p in again["recommendations"]["places"]}
    reply = client.post("/api/chat", headers=h, json={"message": "What should I pack?", "trip_id": tid}).json()["reply"]
    assert "walking shoes" in reply


def test_live_endpoint_validates_and_never_leaks(client):
    assert client.get("/api/live?lat=999&lon=0").status_code == 422
    r = client.get("/api/live?lat=48.85&lon=2.35")
    assert r.status_code == 200 and r.json()["weather"] is None and r.json()["aqi"] is None
    assert "appid" not in r.text and "token" not in r.text
