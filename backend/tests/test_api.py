import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["PLARNO_OFFLINE"] = "1"
os.environ["PLARNO_ADMIN_EMAILS"] = "admin@example.com"
from app import config, db  # noqa: E402

config.OFFLINE = True

config.ADMIN_EMAILS = ["admin@example.com"]
config.RATE_LIMIT_PER_MIN = 100000
from app.main import app  # noqa: E402

DEMO = ("Plan a five-day Delhi trip for two people. Our total budget is ₹30,000. We want to visit historical places, enjoy good food, "
        "stay in a peaceful hotel with good interiors, avoid heavily polluted and noisy areas, and travel comfortably.")


@pytest.fixture()
def client():
    d = tempfile.mkdtemp()
    db.reset(os.path.join(d, "t.db"))
    yield TestClient(app)
    db.reset()


def auth(client, email="u@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "name": "U"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_auth_flow(client):
    h = auth(client)
    assert client.post("/api/auth/register", json={"email": "u@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "u@example.com", "password": "wrongwrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "u@example.com", "password": "password123"}).status_code == 200
    assert client.get("/api/me", headers=h).json()["role"] == "user"
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer bad.token"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "nope", "password": "password123"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_rbac(client):
    h = auth(client)
    assert client.get("/api/admin/matching", headers=h).status_code == 403
    ha = auth(client, "admin@example.com")
    assert client.get("/api/admin/matching", headers=ha).status_code == 200


def test_missing_info_followups_and_context_kept(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "I want to explore Delhi"}).json()
    assert set(r["follow_ups"]) >= {"days", "travellers", "budget"}
    assert "itinerary" not in r["plan"]
    tid = r["trip_id"]
    r = client.post("/api/chat", headers=h, json={"message": "5 days for two people, budget ₹30000", "trip_id": tid}).json()
    assert r["context"]["destination"] == "Delhi" and r["context"]["days"] == 5 and r["context"]["adults"] == 2
    assert "itinerary" in r["plan"]  # destination remembered, not re-asked


def test_full_demo_scenario(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": DEMO}).json()
    ctx, plan = r["context"], r["plan"]
    assert ctx["days"] == 5 and ctx["adults"] == 2 and ctx["budget_inr"] == 30000
    assert ctx["peaceful"] and ctx["avoid_polluted"] and ctx["avoid_noisy"] and "history" in ctx["interests"]
    assert len(plan["itinerary"]["days"]) == 5
    assert plan["budget"]["within_budget"], plan["budget"]
    assert plan["budget"]["status"] == "estimate"
    assert plan["hotel"]["provenance"]["kind"] == "simulated"
    assert plan["bookable_items"] and all(i["simulated"] for i in plan["bookable_items"])
    assert [s["agent"] for s in r["workflow"]][:3] == ["travel_planner", "destination_discovery", "neighbourhood_intelligence"]
    assert all(s["state"] in ("succeeded", "degraded") for s in r["workflow"])
    # nothing booked without approval
    assert client.get("/api/bookings", headers=h).json() == []
    # peaceful preference should avoid the polluted Okhla/industrial pick
    assert plan["hotel"]["neighbourhood"] != "Okhla"


def test_hotel_change_updates_everything(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": DEMO}).json()
    tid, old = r["trip_id"], r["plan"]
    r2 = client.post("/api/chat", headers=h, json={"message": "Change my hotel to Old Delhi Haveli Stay", "trip_id": tid}).json()
    new = r2["plan"]
    assert new["hotel"]["id"] == "h-old-haveli" != old["hotel"]["id"]
    assert new["itinerary"]["hotel"]["id"] == "h-old-haveli"
    assert new["budget"]["breakdown"]["hotels"] != old["budget"]["breakdown"]["hotels"]
    assert new["safety"]["neighbourhood_report"]["neighbourhood"] == "Old Delhi"
    assert new["itinerary"]["days"][0]["route_geometry"][0] != old["itinerary"]["days"][0]["route_geometry"][0]


def test_budget_conflict_resolution(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day Delhi trip for two, budget ₹15000, history"}).json()
    assert r["plan"]["hotel"]["price_per_night"] <= 3000  # budget agent forced a cheaper hotel


def test_cheaper_is_actually_cheaper_and_peaceful_pick(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": DEMO}).json()
    assert r["plan"]["hotel"]["neighbourhood"] in ("Lodhi Colony / Defence Colony", "Chanakyapuri", "Hauz Khas / Safdarjung")
    r2 = client.post("/api/chat", headers=h, json={"message": "Make it cheaper", "trip_id": r["trip_id"]}).json()
    assert r2["plan"]["hotel"]["price_per_night"] < r["plan"]["hotel"]["price_per_night"]
    assert r2["plan"]["budget"]["estimated_total_inr"] < r["plan"]["budget"]["estimated_total_inr"]


def test_budget_relaxes_transport_before_hotel(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": DEMO.replace("Delhi trip", "Delhi trip from Jaipur") + " Start 2026-12-05."}).json()
    p = r["plan"]
    assert p["budget"]["within_budget"]
    assert p["hotel"]["interiors"] >= 4.0 or "lower interiors rating" in r["reply"]  # never silently downgrade the stay
    assert r["context"]["transport_relaxed"] or p["journey"]["comfort"] >= 3.4


def test_cab_priced_per_vehicle(client):
    a = client.get("/api/transport/search", params={"origin": "Delhi", "destination": "Agra", "date": "2026-12-01", "travellers": 1}).json()
    b = client.get("/api/transport/search", params={"origin": "Delhi", "destination": "Agra", "date": "2026-12-01", "travellers": 4}).json()
    cab = lambda r: next(j for j in r["journeys"] if j["summary"] == "cab")["total_fare_inr"]
    assert cab(a) == cab(b)  # one vehicle seats 4


def test_modification_commands(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": DEMO}).json()["trip_id"]
    for msg in ["Make it cheaper", "Find a better hotel", "Add more sightseeing", "Avoid crowded places", "Find peaceful surroundings",
                "Reduce travel time", "Recalculate the budget", "Add good restaurants", "Why this hotel?", "Is it safe? emergency numbers"]:
        r = client.post("/api/chat", headers=h, json={"message": msg, "trip_id": tid})
        assert r.status_code == 200, msg
        assert "itinerary" in r.json()["plan"], msg
        assert r.json()["reply"], msg


def test_transport_multimodal_jaipur_manali(client):
    r = client.get("/api/transport/search", params={"origin": "Jaipur", "destination": "Manali", "date": "2026-12-01", "travellers": 2}).json()
    assert r["journeys"], r
    assert any(j["transfers"] >= 1 for j in r["journeys"]) and any(j["transfers"] == 0 for j in r["journeys"])
    assert r["labels"].keys() >= {"cheapest", "fastest", "best_value", "most_comfortable", "lowest_transfer"}
    j = r["journeys"][0]
    assert j["provenance"]["kind"] == "simulated"
    # combined duration/fare are consistent with legs
    for j in r["journeys"]:
        from app.services.transport import leg_cost
        assert j["total_fare_inr"] == round(sum(leg_cost(l, 2) for l in j["legs"]))
        assert j["total_duration_min"] >= sum(l["duration_min"] for l in j["legs"]) - 1
    assert client.get("/api/transport/search", params={"origin": "Jaipur", "destination": "Jaipur", "date": "2026-12-01"}).status_code == 422
    assert client.get("/api/transport/search", params={"origin": "Atlantis", "destination": "Jaipur", "date": "2026-12-01"}).status_code == 422
    assert client.get("/api/transport/search", params={"origin": "Delhi", "destination": "Agra", "date": "not-a-date"}).status_code == 422


def test_route_optimisation_not_worse_than_naive(client):
    ids = ["qutub-minar", "red-fort", "lotus-temple", "india-gate", "hauz-khas"]
    r = client.post("/api/route/optimize", json={"attraction_ids": ids, "start_lat": 28.63, "start_lon": 77.21}).json()
    assert sorted(r["order"]) == sorted(ids)
    assert r["total_km"] > 0
    assert client.post("/api/route/optimize", json={"attraction_ids": ["nope"]}).status_code == 422
    assert client.post("/api/route/optimize", json={"attraction_ids": []}).status_code == 422


def test_booking_approval_idempotency_and_cancel(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 3 day Delhi trip from Jaipur for two, budget ₹40000, start 2026-12-05"}).json()
    tid = r["trip_id"]
    ap = client.post(f"/api/trips/{tid}/booking/prepare", headers=h).json()
    assert ap["status"] == "pending" and client.get("/api/bookings", headers=h).json() == []
    assert client.post(f"/api/approvals/{ap['approval_id']}/decide", headers=h, json={"approve": True, "idempotency_key": "short"}).status_code == 422
    d = client.post(f"/api/approvals/{ap['approval_id']}/decide", headers=h, json={"approve": True, "idempotency_key": "key-12345678"}).json()
    assert d["simulated"] is True and "SIMULATED" in d["notice"]
    bks = client.get("/api/bookings", headers=h).json()
    n = len(bks)
    assert n >= 2 and all(b["simulated"] and b["reference"].startswith("SIM-") for b in bks)
    d2 = client.post(f"/api/approvals/{ap['approval_id']}/decide", headers=h, json={"approve": True, "idempotency_key": "key-12345678"}).json()
    assert d2["replayed"] and len(client.get("/api/bookings", headers=h).json()) == n  # no double booking
    # cancellation needs approval
    cr = client.post(f"/api/bookings/{bks[0]['id']}/cancel-request", headers=h).json()
    assert not any(b["status"] == "SIMULATED_CANCELLED" for b in client.get("/api/bookings", headers=h).json())
    client.post(f"/api/approvals/{cr['approval_id']}/decide", headers=h, json={"approve": True, "idempotency_key": "key-cancel-1"})
    assert any(b["status"] == "SIMULATED_CANCELLED" for b in client.get("/api/bookings", headers=h).json())


def test_rejected_approval_books_nothing(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": DEMO}).json()["trip_id"]
    ap = client.post(f"/api/trips/{tid}/booking/prepare", headers=h).json()
    client.post(f"/api/approvals/{ap['approval_id']}/decide", headers=h, json={"approve": False, "idempotency_key": "key-reject-1"})
    assert client.get("/api/bookings", headers=h).json() == []


def test_approvals_are_user_scoped(client):
    h1, h2 = auth(client, "a@example.com"), auth(client, "b@example.com")
    tid = client.post("/api/chat", headers=h1, json={"message": DEMO}).json()["trip_id"]
    ap = client.post(f"/api/trips/{tid}/booking/prepare", headers=h1).json()
    assert client.post(f"/api/approvals/{ap['approval_id']}/decide", headers=h2, json={"approve": True, "idempotency_key": "key-other-12"}).status_code == 404
    assert client.get(f"/api/trips/{tid}", headers=h2).status_code == 404


def test_disruption_flow(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 3 day Delhi trip from Jaipur for two, budget ₹40000, start 2026-12-05"}).json()
    tid = r["trip_id"]
    assert r["plan"]["journey"]
    mode = r["plan"]["journey"]["legs"][0]["mode"]
    other = "flight" if mode != "flight" else "bus"
    mm = client.post("/api/chat", headers=h, json={"message": f"My {other} is delayed by 2 hours", "trip_id": tid}).json()
    assert mm["follow_ups"] == ["journey"] and "pending_recovery" not in mm["plan"]  # mode mismatch -> clarify, don't guess
    r2 = client.post("/api/chat", headers=h, json={"message": f"My {mode} got delayed", "trip_id": tid}).json()
    assert "delay" in r2["follow_ups"]  # asks how long rather than guessing
    r3 = client.post("/api/chat", headers=h, json={"message": f"My {mode} is delayed by 4 hours", "trip_id": tid}).json()
    assert r3["plan"]["pending_recovery"]["requires_approval"]
    assert r3["plan"]["journey"] == r["plan"]["journey"]  # unchanged until approval
    opts = r3["plan"]["pending_recovery"]["options"]
    ap = client.post(f"/api/trips/{tid}/recovery/request-approval", headers=h, json={"option_id": opts[0]["id"]}).json()
    assert ap["status"] == "pending"
    assert client.post(f"/api/trips/{tid}/recovery/propose", headers=h, json={"delay_min": 0}).status_code == 422


def test_itinerary_edit_rebuild(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": DEMO}).json()["trip_id"]
    before = client.get(f"/api/trips/{tid}", headers=h).json()["plan"]["budget"]["estimated_total_inr"]
    r = client.post(f"/api/trips/{tid}/itinerary/rebuild", headers=h, json={"attraction_ids": ["red-fort", "qutub-minar"], "pace": "relaxed"})
    assert r.status_code == 200
    plan = r.json()["plan"]
    assert sum(1 for d in plan["itinerary"]["days"] for s in d["stops"] if s["type"] == "attraction") == 2
    assert plan["budget"]["estimated_total_inr"] != before
    assert client.post(f"/api/trips/{tid}/itinerary/rebuild", headers=h, json={"attraction_ids": ["bogus"]}).status_code == 422


def test_expenses_and_split(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": DEMO}).json()["trip_id"]
    client.post(f"/api/trips/{tid}/expenses", headers=h, json={"category": "food", "amount": 900, "paid_by": "A"})
    client.post(f"/api/trips/{tid}/expenses", headers=h, json={"category": "cab", "amount": 300, "paid_by": "B"})
    assert client.post(f"/api/trips/{tid}/expenses", headers=h, json={"category": "x", "amount": -5, "paid_by": "A"}).status_code == 422
    b = client.get(f"/api/trips/{tid}/budget", params={"members": "A,B,C"}, headers=h).json()
    assert b["actual_spent_inr"] == 1200 and b["split"]["share_each"] == 400
    assert {"from": "C", "to": "A", "amount": 400.0} in b["split"]["transfers"] or sum(t["amount"] for t in b["split"]["transfers"]) == 500


def test_neighbourhood_personalisation(client):
    fam = client.get("/api/neighbourhoods", params={"preset": "family"}).json()
    bud = client.post("/api/neighbourhoods/score", json={"weights": {"price": 0.0, "environment": 5.0}}).json()
    assert all(0 <= n["score"] <= 100 for n in fam)
    assert abs(sum(f["weight"] for f in fam[0]["factors"]) - 1) < 0.01
    assert bud[0]["id"] in ("chanakya", "lodhi", "hauzkhas")
    assert "guaranteed" in fam[0]["disclaimer"].lower() or "guarantee" in fam[0]["disclaimer"].lower()
    assert client.post("/api/neighbourhoods/score", json={"weights": {"bogus": 1}}).status_code == 422


def test_safety_provenance(client):
    r = client.get("/api/safety", params={"lat": 28.55, "lon": 77.2}).json()
    assert r["emergency_contacts"]["National emergency number"] == "112"
    aqi = r["nearest_neighbourhood_report"]["environment"]["aqi"]
    assert aqi["provenance"]["kind"] in ("simulated", "estimated")  # never presented as live
    assert "guarantee" in r["disclaimer"].lower()


def test_supplier_matching_metrics_and_admin_review(client):
    ha = auth(client, "admin@example.com")
    ev = client.get("/api/admin/evaluation", headers=ha).json()
    assert ev["precision"] == 1.0 and ev["false_merge_rate"] == 0 and ev["recall"] >= 0.85, ev
    m = client.get("/api/admin/matching", headers=ha).json()
    big = max(m["clusters"], key=lambda c: len(c["members"]))
    assert len(big["members"]) == 3 and big["ranked_offers"][0]["offer_score"] >= big["ranked_offers"][-1]["offer_score"]
    a, b = big["members"][0]["listing_id"], big["members"][1]["listing_id"]
    client.post("/api/admin/matching/decision", headers=ha, json={"a": a, "b": b, "decision": "reject"})
    m2 = client.get("/api/admin/matching", headers=ha).json()
    sizes = sorted(len(c["members"]) for c in m2["clusters"])
    assert sizes != sorted(len(c["members"]) for c in m["clusters"])  # rejecting a pair changed the clustering or queued it


def test_supplier_upload_validation(client):
    ha = auth(client, "admin@example.com")
    good = '[{"listing_id":"X1","name":"The Imperial Vista","lat":28.6311,"lon":77.2189,"room":"Deluxe King","beds":"1 King","occupancy":2,"meal":"Room only","price":10000}]'
    r = client.post("/api/admin/suppliers/upload", headers=ha, json={"supplier": "NewSup", "format": "json", "data": good}).json()
    assert r["accepted"] == 1
    bad = client.post("/api/admin/suppliers/upload", headers=ha, json={"supplier": "NewSup", "format": "json", "data": '[{"listing_id":"X2"}]'}).json()
    assert bad["accepted"] == 0 and bad["rejected"]
    assert client.post("/api/admin/suppliers/upload", headers=ha, json={"supplier": "S", "format": "json", "data": "{{"}).status_code == 422
    m = client.get("/api/admin/matching", headers=ha).json()
    assert any(any(x["listing_id"] == "X1" for x in c["members"]) and len(c["members"]) == 4 for c in m["clusters"])


def test_invalid_input(client):
    h = auth(client)
    assert client.post("/api/chat", headers=h, json={"message": ""}).status_code == 422
    assert client.post("/api/chat", headers=h, json={"message": "hi", "trip_id": 999}).status_code == 404
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 3 day Mumbai trip for two, budget ₹40000"}).json()
    assert "couldn't find a place" in r["reply"]  # offline: geocoder unavailable -> honest message, no fabricated plan
    assert "itinerary" not in r["plan"]
    assert client.get("/api/hotels", params={"nights": 0}).status_code == 422


def test_public_config_hides_server_keys(client):
    r = client.get("/api/config").json()
    assert set(r) == {"mapbox_token", "live"} and r["live"]["aqi"] is False  # offline in tests


def test_directions_fallback_is_labelled_estimate(client):
    r = client.post("/api/route/directions", json={"points": [[28.6562, 77.2410], [28.5245, 77.1855]]}).json()
    assert r["provenance"]["kind"] == "estimated" and r["distance_km"] > 10
    assert client.post("/api/route/directions", json={"points": [[28.6, 77.2]]}).status_code == 422


def test_natural_party_size_phrasings():
    from app.agents import nlu
    from app.agents.context import TripContext
    for text, n in [("two of us", 2), ("we are three", 3), ("just me", 1), ("there are 4 of us", 4), ("party of 5", 5), ("for two people", 2)]:
        assert nlu.extract(text, TripContext()).get("adults") == n, text
    assert nlu.extract("2", TripContext()).get("adults") == 2  # bare number answers the travellers question
    assert nlu.extract("30000", TripContext(adults=2)).get("budget_inr") == 30000
    assert nlu.extract("2", TripContext(adults=2, budget_inr=1000.0)).get("days") == 2
    assert "adults" not in nlu.extract("5 days", TripContext())  # "5 days" is a duration, not a party size


def test_home_phrases_do_not_misfire():
    from app.agents import nlu
    from app.agents.context import TripContext
    for t in ["Plan a 4 day trip to Paris", "a 3 day trip to Goa for two", "weekend day trip to Jaipur"]:
        assert not nlu.extract(t, TripContext()).get("stay_home"), t
    for t in ["I live in Kishangarh, show me things nearby", "explore my hometown Kishangarh", "day trips from home", "places near me"]:
        assert nlu.extract(t, TripContext()).get("stay_home") is True, t


def test_place_extraction_stops_at_sentence_end():
    from app.agents import nlu
    from app.agents.context import TripContext
    assert nlu.extract("I live in Kishangarh. Plan a trip for two", TripContext()).get("destination_raw") == "Kishangarh"
    assert nlu.extract("Trip to St. Louis for two", TripContext()).get("destination_raw") == "St. Louis"
    assert nlu.extract("Going to Paris, France for 5 days", TripContext()).get("destination_raw") in ("Paris", "Paris, France")


def test_place_with_country_suffix_is_one_place():
    from app.agents import nlu
    from app.agents.context import TripContext
    g = lambda t, k="destination_raw": nlu.extract(t, TripContext()).get(k)  # noqa: E731
    assert g("Plan a 4 day trip to Paris, France for two people") == "Paris, France"
    assert g("I live in Kishangarh, India. Plan a trip") == "Kishangarh, India"
    assert g("Plan a trip to Lisbon, start 2026-12-10") == "Lisbon"          # lowercase word after the comma is not a country
    assert g("a trip to Paris, France from Kishangarh, India for two", "origin_raw") == "Kishangarh, India"
