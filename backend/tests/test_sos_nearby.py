"""Emergency alert (Telegram) and nearby essentials. No network: the HTTP layer is replaced and every outgoing call is recorded."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["PLARNO_OFFLINE"] = "1"
from app import config, db, main  # noqa: E402
from app.providers import base, geocode, nearby  # noqa: E402

TOKEN = "123456:TEST-TOKEN-never-shown"


@pytest.fixture()
def client(monkeypatch):
    db.reset(os.path.join(tempfile.mkdtemp(), "t.db"))
    config.RATE_LIMIT_PER_MIN = 100000
    main._sos.clear()
    monkeypatch.setattr(geocode, "at", lambda la, lo, label=None: {"name": "Jaipur", "display": "Ganpati Nagar, Jaipur, Rajasthan, India", "country_code": "IN"})
    yield TestClient(main.app)
    db.reset()


def auth(c, email="sos@example.com", name="Asha Rao"):
    return {"Authorization": "Bearer " + c.post("/api/auth/register", json={"email": email, "password": "password123", "name": name}).json()["token"]}


def telegram(monkeypatch, fail=None):
    calls = []

    def fake(method, url, **kw):
        m = url.rsplit("/", 1)[-1]
        calls.append((m, kw.get("json") or {}))
        if fail and m == fail:
            return {"ok": False, "description": "Bad Request: chat not found"}
        return {"ok": True, "result": {"message_id": 77}}
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "4242")
    monkeypatch.setattr(base, "http_json", fake)
    return calls


def test_sos_needs_sign_in_and_says_when_not_set_up(client, monkeypatch):
    assert client.post("/api/sos", json={"lat": 26.9, "lon": 75.8}).status_code == 401
    h = auth(client)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    assert client.get("/api/sos/status", headers=h).json()["configured"] is False
    r = client.post("/api/sos", headers=h, json={"lat": 26.9, "lon": 75.8})
    assert r.status_code == 503 and "emergency number" in r.json()["detail"]


def test_alert_carries_name_contact_and_location_then_live_updates(client, monkeypatch):
    h = auth(client)
    assert client.put("/api/me/preferences", headers=h, json={"emergency_name": "Ravi (brother)", "emergency_phone": "+91 98765 43210", "pace": "balanced"}).status_code == 200
    calls = telegram(monkeypatch)
    st = client.get("/api/sos/status", headers=h).json()
    assert st["configured"] and st["contact"] == {"name": "Ravi (brother)", "phone": "+91 98765 43210"} and st["active"] is False
    r = client.post("/api/sos", headers=h, json={"lat": 26.91234, "lon": 75.78765, "accuracy_m": 18})
    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True and r.json()["place"].startswith("Ganpati Nagar") and "26.912340,75.787650" in r.json()["maps_url"]
    (m1, text), (m2, loc) = calls
    assert m1 == "sendMessage" and text["chat_id"] == "4242" and "parse_mode" not in text            # plain text: a name cannot inject formatting
    body = text["text"]
    for want in ("EMERGENCY ALERT", "Asha Rao", "sos@example.com", "Ravi (brother) +91 98765 43210", "Ganpati Nagar, Jaipur", "26.91234, 75.78765", "about 18 m", "google.com/maps?q=26.912340,75.787650"):
        assert want in body, (want, body)
    assert "TEST" not in body
    assert m2 == "sendLocation" and loc["latitude"] == 26.91234 and loc["live_period"] == 900
    assert TOKEN not in r.text
    assert client.get("/api/sos/status", headers=h).json()["active"] is True
    assert client.post("/api/sos", headers=h, json={"lat": 26.9, "lon": 75.8}).status_code == 429     # a double tap does not spam the contact
    main._sos[next(iter(main._sos))]["last"] -= 60
    up = client.post("/api/sos/update", headers=h, json={"lat": 26.92, "lon": 75.79})
    assert up.status_code == 200 and up.json()["updated"] is True
    assert calls[-1] == ("editMessageLiveLocation", {"chat_id": "4242", "message_id": 77, "latitude": 26.92, "longitude": 75.79})
    assert client.post("/api/sos/update", headers=h, json={"lat": 26.93, "lon": 75.79}).json()["updated"] is False   # throttled
    assert client.post("/api/sos/stop", headers=h, json={}).json()["stopped"] is True
    assert [c[0] for c in calls[-2:]] == ["stopMessageLiveLocation", "sendMessage"] and "marked themselves safe" in calls[-1][1]["text"]
    assert client.post("/api/sos/update", headers=h, json={"lat": 1, "lon": 1}).status_code == 409


def test_test_alert_is_labelled_and_failures_are_reported_without_the_token(client, monkeypatch):
    h = auth(client)
    calls = telegram(monkeypatch)
    assert client.post("/api/sos", headers=h, json={"lat": 1.0, "lon": 2.0, "test": True}).status_code == 200
    assert calls[0][1]["text"].startswith("TEST ALERT (no action needed)") and "Emergency contact on file: none saved" in calls[0][1]["text"]
    main._sos.clear()
    telegram(monkeypatch, fail="sendMessage")
    r = client.post("/api/sos", headers=h, json={"lat": 1.0, "lon": 2.0})
    assert r.status_code == 502 and "chat not found" in r.json()["detail"] and TOKEN not in r.text
    monkeypatch.setattr(base, "http_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("https://api.telegram.org/bot" + TOKEN + "/x timed out")))
    r = client.post("/api/sos", headers=h, json={"lat": 1.0, "lon": 2.0})
    assert r.status_code == 502 and TOKEN not in r.text                                                # the token is in the URL: it must never leak through an error


def test_emergency_phone_is_validated(client):
    h = auth(client)
    assert client.put("/api/me/preferences", headers=h, json={"emergency_phone": "call me maybe"}).status_code == 422
    assert client.put("/api/me/preferences", headers=h, json={"emergency_phone": " +44 20 7946 0958 ", "emergency_name": "  Sam  "}).json()["preferences"] == {"emergency_phone": "+44 20 7946 0958", "emergency_name": "Sam"}


PHARM = {"features": [
    {"geometry": {"coordinates": [75.5700, 26.8400]}, "properties": {"name": "Far Chemist", "full_address": "Ajmer Rd, Jaipur", "mapbox_id": "b", "metadata": {}}},
    {"geometry": {"coordinates": [75.5672, 26.8421]}, "properties": {"name": "Best Care Pharmacy", "full_address": "Shop 39, Dahmi Kalan, Jaipur 303007", "mapbox_id": "a", "metadata": {"phone": "+919772256724"}}},
    {"geometry": {"coordinates": [75.5672, 26.8421]}, "properties": {"name": "Best Care Pharmacy", "mapbox_id": "dup"}},
    {"geometry": {"coordinates": [77.0, 28.0]}, "properties": {"name": "Another City Pharmacy", "mapbox_id": "c"}},
    {"properties": {"name": "broken row"}}]}


def test_nearby_lists_real_places_closest_first(client, monkeypatch):
    assert client.get("/api/nearby", params={"lat": 26.842, "lon": 75.567, "kind": "casino"}).status_code == 422
    off = client.get("/api/nearby", params={"lat": 26.842, "lon": 75.567}).json()
    assert off["places"] == [] and off["error"]                                                       # offline: says so, invents nothing
    seen = {}
    monkeypatch.setattr(config, "OFFLINE", False); monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test"); nearby._cache.clear()
    monkeypatch.setattr(base, "http_json", lambda method, url, **kw: seen.update(url=url, params=kw["params"]) or PHARM)
    r = client.get("/api/nearby", params={"lat": 26.842, "lon": 75.567, "kind": "pharmacy"}).json()
    assert seen["url"].endswith("/category/pharmacy") and seen["params"]["proximity"] == "75.567,26.842"
    assert [p["name"] for p in r["places"]] == ["Best Care Pharmacy", "Far Chemist"]                  # nearest first; duplicate, far-away and broken rows dropped
    best = r["places"][0]
    assert best["phone"] == "+919772256724" and best["distance_km"] < 0.1 and "destination=26.842100,75.567200" in best["maps_url"]
    assert r["places"][1]["phone"] is None and r["provenance"]["kind"] == "live"
    assert "pk.test" not in str(r)
    police = client.get("/api/nearby", params={"lat": 26.842, "lon": 75.567, "kind": "police"}).json()
    assert seen["url"].endswith("/category/police_station") and police["title"] == "Police"
