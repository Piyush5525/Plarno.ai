"""Worldwide planning tests. Provider payloads are injected into the cache using the real SerpApi/Nominatim response shapes
(captured from live calls), so these run offline and deterministically."""
import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

os.environ["PLARNO_OFFLINE"] = "1"
from app import config, db  # noqa: E402
from app.providers import base  # noqa: E402

config.RATE_LIMIT_PER_MIN = 100000
from app.main import app  # noqa: E402

PARIS = {"lat": 48.8566, "lon": 2.3522}


def place(i, title, types, lat, lon, rating=4.6, reviews=50000, hours="Open · Closes 7 PM", oh=None):
    return {"operating_hours": oh, "title": title, "place_id": f"pid{i}", "gps_coordinates": {"latitude": lat, "longitude": lon}, "rating": rating, "reviews": reviews, "type": types[0], "types": types,
            "address": f"{i} Rue Test, 750{i:02d} Paris, France", "open_state": hours, "thumbnail": f"https://example.test/{i}.jpg", "website": "https://example.test", "description": "x"}


ALL_OPEN = {d: "10 AM–6 PM" for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
ATTR = [place(1, "Louvre Museum", ["Art museum", "Museum"], 48.8606, 2.3376, oh={**ALL_OPEN, "tuesday": "Closed"}), place(2, "Eiffel Tower", ["Tourist attraction", "Tower"], 48.8584, 2.2945),
        place(3, "Notre-Dame Cathedral", ["Tourist attraction", "Cathedral"], 48.8530, 2.3499), place(4, "Sainte-Chapelle", ["Chapel", "Historical landmark"], 48.8554, 2.3450),
        place(5, "Jardin du Luxembourg", ["Public park", "Garden"], 48.8462, 2.3372), place(6, "Musee d'Orsay", ["Art museum"], 48.8600, 2.3266),
        place(7, "Arc de Triomphe", ["Monument", "Historical landmark"], 48.8738, 2.2950), place(8, "Montmartre", ["Historical landmark", "Tourist attraction"], 48.8867, 2.3431),
        place(9, "Far Away Castle", ["Castle"], 45.0, 5.0)]  # ~400 km away: must be filtered out
REST = [place(20 + i, f"Bistro {i}", ["French restaurant"], 48.855 + i * 0.002, 2.34 + i * 0.002, 4.4, 900, None) | {"price": "$$"} for i in range(6)]


def hotel(i, name, nightly, lat, lon, rating=4.4):
    return {"type": "hotel", "name": name, "property_token": f"tok{i}", "gps_coordinates": {"latitude": lat, "longitude": lon}, "link": f"https://booking.test/{i}",
            "rate_per_night": {"extracted_lowest": nightly}, "total_rate": {"extracted_lowest": nightly * 4}, "overall_rating": rating, "reviews": 800 + i,
            "images": [{"thumbnail": f"https://example.test/h{i}.jpg"}], "amenities": ["Wi-Fi"],
            "nearby_places": [{"name": "Saint-Michel Metro Station", "transportations": [{"type": "Walking", "duration": "4 min"}]}]}


HOTELS = [hotel(1, "Hotel Lutetia Test", 24000, 48.851, 2.325, 4.7), hotel(2, "Budget Inn Paris", 6500, 48.870, 2.350, 4.0), hotel(3, "Quartier Latin Stay", 9800, 48.850, 2.345, 4.4),
          hotel(4, "Outskirts Hotel", 4000, 48.95, 2.45, 3.8)]


@pytest.fixture()
def client():
    db.reset(os.path.join(tempfile.mkdtemp(), "w.db"))
    base.reset_breakers()
    put = lambda k, v: db.run("INSERT INTO api_cache(key,value,fetched_at) VALUES(?,?,?)", (k, json.dumps(v), time.time()))  # noqa: E731
    put("nominatim:paris", [{"category": "boundary", "type": "administrative", "lat": "48.8566", "lon": "2.3522", "display_name": "Paris, France",
                             "address": {"city": "Paris", "country": "France", "country_code": "fr"}}])
    put("nominatim:atlantisland", [])
    put("serpplaces:top tourist attractions in paris:48.86,2.35", ATTR)
    put("serpplaces:historical landmarks and monuments in paris:48.86,2.35", ATTR)
    put("serpplaces:best restaurants in paris:48.86,2.35", REST)
    put("serphotels:paris:2026-12-05:2026-12-08:2:INR", HOTELS)
    yield TestClient(app)
    db.reset()


def auth(c):
    r = c.post("/api/auth/register", json={"email": f"w{time.time_ns()}@example.com", "password": "password123"})
    return {"Authorization": "Bearer " + r.json()["token"]}


MSG = "Plan a 4 day trip to Paris for two people, start 2026-12-05, budget ₹150000, historical places and museums, good food"


def test_plans_a_non_delhi_city_from_real_provider_shapes(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": MSG}).json()
    plan, ctx = r["plan"], r["context"]
    assert ctx["destination"] == "Paris" and ctx["dest_geo"]["country_code"] == "FR", r["reply"]
    assert plan["world"] is True and len(plan["itinerary"]["days"]) == 4
    names = [a["name"] for a in plan["catalog"]["attractions"]]
    assert "Far Away Castle" not in names  # results that drifted to another region are dropped
    assert plan["hotel"]["price_per_night"] <= 150000 * 0.6 / 3 and plan["hotel"]["provenance"]["kind"] in ("live", "cached")
    stops = [s for d in plan["itinerary"]["days"] for s in d["stops"] if s["type"] == "attraction"]
    assert stops and all(s["thumbnail"] and (s["hours_note"].split(":")[0] in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") or s["hours_note"].startswith("Google Maps now:")) for s in stops)  # real photos + hours carried through
    assert all(s["id"].startswith("g-") for s in stops)
    assert plan["budget"]["estimated_total_inr"] > 0 and plan["safety"]["city"] == "Paris" and plan["safety"]["emergency_contacts"]["All emergencies"] == "112"
    assert plan["bookable_items"] == [] and plan["booking_links"][0]["url"].startswith("https://booking.test/")  # external links, no fake confirmations
    assert "does not make reservations" in r["reply"]


def test_itinerary_follows_real_weekday_hours(client):
    h = auth(client)
    plan = client.post("/api/chat", headers=h, json={"message": MSG.replace("4 day", "4 day")}).json()["plan"]
    louvre_days = [d for d in plan["itinerary"]["days"] for s in d["stops"] if s["name"] == "Louvre Museum"]
    for d in plan["itinerary"]["days"]:
        for s in d["stops"]:
            if s["type"] == "attraction" and s["name"] in ("Louvre Museum", "Musee d'Orsay", "Sainte-Chapelle") and s["hours_note"].split(":")[0] in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
                if s["name"] == "Louvre Museum":
                    assert s["hours_flag"] != "closed" or d["date"] != "2026-12-08", "Louvre is closed on Tuesday and must not be scheduled then"
                    h_, m_ = map(int, s["start"].split(":"))
                    assert h_ + m_ / 60 >= 10 - 0.01  # waits for the 10 AM opening instead of arriving at a closed door
    assert louvre_days  # still included, just on an open day


def test_hours_parser_handles_real_formats():
    from app.services import hours
    assert hours.parse("9 AM–12 AM") == {"kind": "range", "open": 9, "close": 24, "text": "9 AM-12 AM"}
    assert hours.parse("7:50 AM–7 PM (Armistice Day might affect these hours)")["open"] == pytest.approx(7 + 50 / 60)
    assert hours.parse("Closed")["kind"] == "closed" and hours.parse("Open 24 hours")["kind"] == "24h"
    r = hours.parse("9 AM–12 PM, 2–6 PM")
    assert (r["open"], r["close"]) == (9, 18)
    assert hours.parse("garbage") is None and hours.parse(None) is None and hours.parse("") is None


def test_world_hotel_scoring_excludes_missing_factors_and_explains(client):
    h = auth(client)
    plan = client.post("/api/chat", headers=h, json={"message": MSG}).json()["plan"]
    top = plan["hotel_candidates"][0]
    kinds = {f["factor"]: f["data_kind"] for f in top["explanation"]["factors"]}
    assert set(kinds) == {"attractions", "hotel_quality", "price", "transit"}
    assert abs(sum(f["weight"] for f in top["explanation"]["factors"]) - 1) < 0.01
    assert "not available for this city" in top["explanation"]["disclaimer"]  # no invented noise/safety scores


def test_world_hotel_change_updates_everything(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": MSG}).json()
    old = r["plan"]
    r2 = client.post("/api/chat", headers=h, json={"message": "Change my hotel to Hotel Lutetia Test", "trip_id": r["trip_id"]}).json()
    new = r2["plan"]
    assert new["hotel"]["name"] == "Hotel Lutetia Test"
    assert new["budget"]["breakdown"]["hotels"] != old["budget"]["breakdown"]["hotels"]
    assert new["itinerary"]["days"][0]["route_geometry"][0] != old["itinerary"]["days"][0]["route_geometry"][0]
    assert new["booking_links"][0]["url"] == "https://booking.test/1"


def test_world_budget_pressure_picks_cheaper_hotel(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": MSG.replace("150000", "60000")}).json()
    assert r["plan"]["hotel"]["price_per_night"] <= 60000 * 0.6 / 3
    r2 = client.post("/api/chat", headers=h, json={"message": "Make it cheaper", "trip_id": r["trip_id"]}).json()
    assert r2["plan"]["hotel"]["price_per_night"] < r["plan"]["hotel"]["price_per_night"]


def test_world_tools_use_provider_data(client):
    h = auth(client)
    tid = client.post("/api/chat", headers=h, json={"message": MSG}).json()["trip_id"]
    r = client.post("/api/chat", headers=h, json={"message": "Find hotels under ₹10,000", "trip_id": tid}).json()
    assert "Budget Inn Paris" in r["reply"] and "Hotel Lutetia Test" not in r["reply"] and "Google Hotels" in r["reply"]
    r = client.post("/api/chat", headers=h, json={"message": "Show historical places nearby", "trip_id": tid}).json()
    assert "Google Maps data" in r["reply"] and "Sainte-Chapelle" in r["reply"] or "Louvre" in r["reply"]
    r = client.post("/api/chat", headers=h, json={"message": "Find good restaurants around my hotel", "trip_id": tid}).json()
    assert "Bistro" in r["reply"]


def test_unknown_place_is_handled_honestly(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Atlantisland for two people, budget ₹90000"}).json()
    assert "couldn't find a place called 'Atlantisland'" in r["reply"] and r["follow_ups"] == ["destination"] and "itinerary" not in r["plan"]


def test_bare_place_name_answers_the_destination_question(client):
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "I'd like to plan a trip for two people, 4 days, budget ₹150000, start 2026-12-05"}).json()
    assert r["follow_ups"] == ["destination"]
    r2 = client.post("/api/chat", headers=h, json={"message": "Paris", "trip_id": r["trip_id"]}).json()
    assert r2["context"]["destination"] == "Paris" and "itinerary" in r2["plan"]


def test_geocode_and_discover_endpoints_validate_input(client):
    assert client.get("/api/geocode", params={"q": "Paris"}).json()["country_code"] == "FR"
    assert client.get("/api/geocode", params={"q": "Atlantisland"}).status_code == 404
    assert client.get("/api/world/discover", params={"city": "Paris", "kind": "bogus"}).status_code == 422
    r = client.get("/api/world/discover", params={"city": "Paris", "kind": "attractions"}).json()
    assert r["geo"]["name"] == "Paris" and any(p["name"] == "Louvre Museum" for p in r["places"]) and r["places"][0]["thumbnail"]
    assert client.get("/api/world/discover", params={"city": "Paris", "kind": "hotels", "nights": 99}).status_code == 422


def test_saved_preferences_become_trip_defaults(client):
    h = auth(client)
    client.put("/api/me/preferences", headers=h, json={"vegetarian": True, "pace": "relaxed", "priority_preset": "budget", "bogus": 1})
    r = client.post("/api/chat", headers=h, json={"message": MSG}).json()
    assert r["context"]["vegetarian"] is True and r["context"]["pace"] == "relaxed" and r["context"]["priority_preset"] == "budget"
    per_day = [sum(1 for s in d["stops"] if s["type"] == "attraction") for d in r["plan"]["itinerary"]["days"]]
    assert sum(per_day) == 4  # relaxed pace = 1 sight/day x 4 days (a closed-day sight may shift days, but the total holds)
    assert r["plan"]["weights_used"]["price"] == 0.45  # budget preset raised the price weight
    # an explicit request still wins over a saved default
    r2 = client.post("/api/chat", headers=h, json={"message": MSG + " Action-packed schedule."}).json()
    assert r2["context"]["pace"] == "packed"


def test_region_destinations_ask_for_a_city(client):
    db.run("INSERT INTO api_cache(key,value,fetched_at) VALUES(?,?,?)", ("nominatim:madhya pradesh", json.dumps([{"category": "boundary", "type": "administrative", "lat": "23.5", "lon": "78.5",
           "display_name": "Madhya Pradesh, India", "address": {"state": "Madhya Pradesh", "country": "India", "country_code": "in"}}]), time.time()))
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Madhya Pradesh for two people, budget ₹60000"}).json()
    assert "covers a large area" in r["reply"] and "city or town" in r["reply"]
    assert r["follow_ups"] == ["destination"] and "itinerary" not in r["plan"]


def test_daily_cap_is_not_reported_as_an_outage(client, monkeypatch):
    from app.providers import serp_places
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "SERP_KEY", "k")
    monkeypatch.setattr(config, "SERP_DAILY_CAP", 0)
    r = serp_places.places("attractions", "Lisbon", 38.72, -9.14)
    assert "Daily search limit" in r["error"] and "not responding" not in r["error"]
    assert not base.breaker_open("serpplaces")  # our own cap must not mark the provider as down


def test_place_suggestions_live_shape_and_fallback(client, monkeypatch):
    from app.providers import suggest
    suggest._cache.clear()
    assert client.get("/api/geocode/suggest", params={"q": "k"}).json()["suggestions"] == []  # needs 2+ chars
    fb = client.get("/api/geocode/suggest", params={"q": "par"}).json()  # offline -> built-in list, labelled as such
    assert fb["suggestions"][0]["name"] == "Paris" and "built-in" in fb["source"]
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test")
    feats = {"features": [{"text": "Kishangarh", "place_name": "Kishangarh, Rajasthan, India", "place_type": ["place"], "center": [74.85, 26.58]},
                          {"text": "Kishangarh Division", "place_name": "Kishangarh Division, India", "place_type": ["region"], "center": [78.7, 23.5]}]}
    monkeypatch.setattr(base, "http_json", lambda *a, **k: feats)
    r = client.get("/api/geocode/suggest", params={"q": "kisha"}).json()
    assert r["suggestions"][0] == {"name": "Kishangarh", "context": "Rajasthan, India", "label": "Kishangarh, Rajasthan, India", "lon": 74.85, "lat": 26.58, "broad": False, "kind": ""}
    assert r["suggestions"][1]["broad"] is True  # states are flagged so the UI can warn
    monkeypatch.setattr(base, "http_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert client.get("/api/geocode/suggest", params={"q": "kishb"}).json()["source"].startswith("built-in")  # provider failure degrades gracefully


# ---------------- door-to-door routes, small towns, home base ----------------
def _put(k, v):
    db.run("INSERT INTO api_cache(key,value,fetched_at) VALUES(?,?,?)", (k, json.dumps(v), time.time()))


KISH = {"category": "place", "type": "town", "lat": "26.5866", "lon": "74.8541", "display_name": "Kishangarh, Ajmer, Rajasthan, India",
        "address": {"town": "Kishangarh", "state": "Rajasthan", "country": "India", "country_code": "in"}}
FLIGHT_JAI_CDG = {"best_flights": [{"flights": [{"airline": "Air France", "flight_number": "AF 1", "departure_airport": {"id": "JAI", "time": "2026-12-10 06:00"},
                                                 "arrival_airport": {"id": "CDG", "time": "2026-12-10 14:30"}, "duration": 600}], "total_duration": 600, "price": 42000}],
                  "other_flights": [{"flights": [{"airline": "Gulf Air", "flight_number": "GF 2", "departure_airport": {"id": "JAI", "time": "2026-12-10 09:00"},
                                                  "arrival_airport": {"id": "DXB", "time": "2026-12-10 11:30"}, "duration": 180}, {"airline": "Gulf Air", "flight_number": "GF 3",
                                                  "departure_airport": {"id": "DXB", "time": "2026-12-10 14:00"}, "arrival_airport": {"id": "CDG", "time": "2026-12-10 19:00"}, "duration": 450}],
                                     "total_duration": 780, "price": 31000, "layovers": [{"name": "Dubai"}]}], "link": "https://www.google.com/travel/flights?x"}


def test_small_town_origin_uses_nearest_airport_with_cab_legs(client):
    _put("nominatim:kishangarh", [KISH])
    _put("serpflights:JAI-CDG:2026-12-10:1", FLIGHT_JAI_CDG)
    _put("serphotels:paris:2026-12-10:2026-12-13:2:INR", HOTELS)
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Paris for two people from Kishangarh, start 2026-12-10, budget ₹250000, historical places and museums"}).json()
    p = r["plan"]
    ro = p["route_options"]
    assert ro["airports"]["origin"]["city"] == "Jaipur" and ro["airports"]["origin"]["km"] > 90
    assert len(ro["options"]) == 2 and all([l["mode"] for l in o["legs"]] == ["cab", "flight", "cab"] for o in ro["options"])
    assert any("Nearest airport to Kishangarh is Jaipur" in n for o in ro["options"] for n in o["notes"])
    cheap = ro["options"][ro["labels"]["cheapest"]]
    assert cheap["legs"][1]["fare_inr"] == 31000 and cheap["total_fare_inr"] > 31000 * 2  # 2 passengers + estimated cab transfers
    assert cheap["round_trip_inr"] == cheap["total_fare_inr"] * 2 and cheap["provenance"]["kind"] == "live"
    assert cheap["legs"][0]["provenance"]["kind"] == "estimated"  # transfers are labelled as estimates
    fitting = [o for o in ro["options"] if o["fits_budget"]]
    assert p["journey"]["total_fare_inr"] == (min(o["total_fare_inr"] for o in fitting) if fitting else cheap["total_fare_inr"])  # within budget, else the cheapest
    assert p["budget"]["breakdown"]["intercity_transport"] == p["journey"]["total_fare_inr"] * 2
    assert "Cab" in r["reply"]


def test_domestic_short_trip_offers_cab_bus_train_and_budget_tiers(client):
    from app.services import routes
    o = {"name": "Kishangarh", "lat": 26.5866, "lon": 74.8541, "country_code": "IN"}
    d = {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873, "country_code": "IN"}
    res = routes.build_options(o, d, "2026-12-10", 2, allowance_round_trip=3000)
    modes = {tuple(x["modes"]) for x in res["options"]}
    assert ("cab",) in modes and any("bus" in m for m in modes) and any("train" in m for m in modes)
    assert not any("flight" in m for m in modes)  # ~100 km: flights make no sense
    assert set(res["labels"]) == {"cheapest", "fastest", "most_comfortable", "best_value", "most_convenient"}
    assert all("fits_budget" in x for x in res["options"]) and any(not x["fits_budget"] for x in res["options"])
    assert all(x["provenance"]["kind"] == "estimated" for x in res["options"])  # no live bus/train data: never claimed live
    cab = next(x for x in res["options"] if x["modes"] == ["cab"])
    assert cab["total_fare_inr"] == round(max(300, cab["legs"][0]["distance_km"] * 14) * 1.1, -1) or abs(cab["total_fare_inr"] - cab["legs"][0]["distance_km"] * 14 * 1.1) < 60


def test_cab_is_priced_per_vehicle_not_per_person(client):
    from app.services import routes
    o = {"name": "A", "lat": 26.5, "lon": 74.8, "country_code": "IN"}
    d = {"name": "B", "lat": 26.9, "lon": 75.8, "country_code": "IN"}
    one = next(x for x in routes.build_options(o, d, "2026-12-10", 1)["options"] if x["modes"] == ["cab"])
    four = next(x for x in routes.build_options(o, d, "2026-12-10", 4)["options"] if x["modes"] == ["cab"])
    five = next(x for x in routes.build_options(o, d, "2026-12-10", 5)["options"] if x["modes"] == ["cab"])
    assert one["total_fare_inr"] == four["total_fare_inr"] and five["total_fare_inr"] == 2 * four["total_fare_inr"]


def test_home_base_trip_has_no_hotel_or_travel_and_still_plans_everything(client):
    _put("nominatim:kishangarh", [KISH])
    kp = [place(i, t, ty, 26.58 + i * 0.01, 74.85 + i * 0.01, 4.3, 800 + i * 50, None) for i, t, ty in
          [(1, "Phool Sagar Lake", ["Lake", "Tourist attraction"]), (2, "Marble Market", ["Market"]), (3, "Roopangarh Fort", ["Fort", "Historical landmark"]),
           (4, "Gondulav Lake", ["Lake"]), (5, "Mandir Shri Gopinath", ["Hindu temple"]), (6, "Local Garden", ["Public park"]), (7, "Old Haveli", ["Historical landmark"])]]
    _put("serpplaces:top tourist attractions in kishangarh:26.59,74.85", kp)
    _put("serpplaces:best restaurants in kishangarh:26.59,74.85", [place(30 + i, f"Dhaba {i}", ["Indian restaurant"], 26.59, 74.85 + i * 0.002, 4.2, 300) | {"price": "$"} for i in range(5)])
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "I live in Kishangarh. Plan a 3 day trip exploring places near me for two people, budget ₹15000, start 2026-12-10"}).json()
    p = r["plan"]
    assert r["context"]["stay_home"] is True and p["hotel"]["id"] == "home" and p["hotel"]["price_per_night"] == 0
    assert "route_options" not in p and p.get("journey") is None and "no long-distance travel" in (p.get("journey_note") or "")
    assert p["budget"]["breakdown"]["hotels"] == 0 and p["budget"]["breakdown"]["intercity_transport"] == 0 and p["budget"]["within_budget"]
    assert len(p["itinerary"]["days"]) == 3 and any(s["type"] == "attraction" for d in p["itinerary"]["days"] for s in d["stops"])
    assert any(s["type"] == "meal" and s["name"].startswith("Dhaba") for d in p["itinerary"]["days"] for s in d["stops"])
    assert p["booking_links"] == [] and "Home base" in r["reply"] or "home" in r["reply"].lower()


def test_trip_answers_fare_questions_from_the_real_options(client):
    from app.agents import tools
    for q in ["What are my ways to travel there?", "How much is the cab fare?", "What's the cheapest way to get there?", "How do I get there from home?", "fastest option please",
              "how much will it cost to travel"]:
        assert tools.classify(q) == {"intent": "transport_options"}, q
    for q in ["Make it cheaper", "Find hotels under ₹4,000", "Show historical places nearby"]:
        assert (tools.classify(q) or {}).get("intent") != "transport_options", q
    _put("nominatim:kishangarh", [KISH])
    _put("serpflights:JAI-CDG:2026-12-10:1", FLIGHT_JAI_CDG)
    _put("serphotels:paris:2026-12-10:2026-12-13:2:INR", HOTELS)
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Paris for two people from Kishangarh, start 2026-12-10, budget ₹250000, historical places"}).json()
    ro, tid = r["plan"]["route_options"], r["trip_id"]
    a = client.post("/api/chat", headers=h, json={"message": "What are my ways to travel there?", "trip_id": tid}).json()
    assert a["action"]["to"] == "/workspace?tab=travel"
    assert (chr(92) + 'n') not in a["reply"] and "\n- Cheapest" in a["reply"]  # real line breaks, never a literal backslash-n
    for key in ("cheapest", "fastest"):
        o = ro["options"][ro["labels"][key]]
        assert f"₹{o['total_fare_inr']:,}" in a["reply"] and o["summary"] in a["reply"]  # numbers come straight from the options
    assert "live" in a["reply"].lower() and "estimates" in a["reply"].lower()  # says which parts are live vs estimated
    fast = ro["options"][ro["labels"]["fastest"]]
    cheapest = ro["options"][ro["labels"]["cheapest"]]
    assert fast["total_fare_inr"] != cheapest["total_fare_inr"]  # the fixture offers a real choice
    b = client.post("/api/chat", headers=h, json={"message": "Switch to the fastest travel option", "trip_id": tid}).json()
    assert b["plan"]["journey"]["total_fare_inr"] == fast["total_fare_inr"] and b["plan"]["budget"]["breakdown"]["intercity_transport"] == fast["total_fare_inr"] * 2
    c = client.post("/api/chat", headers=h, json={"message": "Actually switch to the cheapest travel option", "trip_id": tid}).json()
    assert c["plan"]["journey"]["total_fare_inr"] == cheapest["total_fare_inr"] and c["plan"]["budget"]["breakdown"]["intercity_transport"] == cheapest["total_fare_inr"] * 2


def test_route_options_endpoint_and_choosing_an_option(client):
    _put("nominatim:kishangarh", [KISH])
    _put("serpflights:JAI-CDG:2027-01-10:1", FLIGHT_JAI_CDG)
    _put("serphotels:paris:2027-01-10:2027-01-13:2:INR", HOTELS)
    r = client.get("/api/routes/options", params={"origin": "Kishangarh", "destination": "Paris", "date": "2027-01-10", "travellers": 2, "budget": 400000})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["origin"]["name"] == "Kishangarh" and d["destination"]["name"] == "Paris" and len(d["options"]) == 2
    assert all("fits_budget" in o for o in d["options"]) and d["allowance_round_trip_inr"] == 180000
    assert client.get("/api/routes/options", params={"origin": "Kishangarh", "destination": "Atlantisland", "date": "2027-01-10"}).status_code == 404
    assert client.get("/api/routes/options", params={"origin": "Kishangarh", "destination": "Paris", "date": "2020-01-01"}).status_code == 422
    assert client.get("/api/routes/options", params={"origin": "Kishangarh", "destination": "Paris", "date": "nope"}).status_code == 422
    h = auth(client)
    pl = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Paris for two people from Kishangarh, start 2027-01-10, budget ₹400000, historical places"}).json()
    opts = pl["plan"]["route_options"]["options"]
    other = next(o for o in opts if o["total_fare_inr"] != pl["plan"]["journey"]["total_fare_inr"])
    ch = client.post(f"/api/trips/{pl['trip_id']}/journey", headers=h, json={"index": other["index"]}).json()
    assert ch["plan"]["journey"]["total_fare_inr"] == other["total_fare_inr"] and ch["plan"]["budget"]["breakdown"]["intercity_transport"] == other["total_fare_inr"] * 2
    assert client.post(f"/api/trips/{pl['trip_id']}/journey", headers=h, json={"index": 99}).status_code == 422
    assert client.post(f"/api/trips/{pl['trip_id']}/journey", json={"index": 0}).status_code == 401


def test_geocoder_prefers_the_actual_town_not_a_region(client, monkeypatch):
    from app.providers import geocode
    geocode._mb_cache.clear()
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test")
    resp = {"features": [{"text": "Kishangarh", "place_name": "Kishangarh, Rajasthan, India", "place_type": ["place"], "center": [74.854, 26.586], "id": "place.1",
                          "context": [{"id": "region.9", "short_code": "IN-RJ"}, {"id": "country.2", "short_code": "in"}]},
                         {"text": "Kishangarh", "place_name": "Kishangarh, Madhya Pradesh, India", "place_type": ["locality"], "center": [77.0, 24.0], "id": "locality.3", "context": []}]}
    monkeypatch.setattr(base, "http_json", lambda *a, **k: resp)
    g = geocode.resolve("Kishangarh, India")
    assert (g["name"], g["country_code"], g["broad"]) == ("Kishangarh", "IN", False) and abs(g["lat"] - 26.586) < 1e-6  # the Rajasthan town, never "Madhya Pradesh"
    geocode._mb_cache.clear()
    monkeypatch.setattr(base, "http_json", lambda *a, **k: {"features": [{"text": "Goa", "place_name": "Goa, India", "place_type": ["region"], "center": [74.05, 15.3], "id": "region.5",
                                                                           "context": [{"id": "country.2", "short_code": "in"}]}]})
    goa = geocode.resolve("Goa")
    assert goa["broad"] is True and goa["name"] == "Goa"  # a whole state is flagged so the planner asks for a town


def test_nominatim_fallback_keeps_the_place_name_not_the_state(client):
    from app.providers import geocode
    _put("nominatim:tinyvillage", [{"category": "place", "type": "village", "name": "Tinyvillage", "lat": "20.0", "lon": "70.0", "display_name": "Tinyvillage, Gujarat, India",
                                    "address": {"state": "Gujarat", "country": "India", "country_code": "in"}}])
    g = geocode.resolve("Tinyvillage")
    assert g["name"] == "Tinyvillage" and g["broad"] is False  # used to come back as the state's name


def test_cab_charge_question_gets_a_cab_specific_answer(client):
    _put("nominatim:kishangarh", [KISH])
    _put("serpflights:JAI-CDG:2026-12-10:1", FLIGHT_JAI_CDG)
    _put("serphotels:paris:2026-12-10:2026-12-13:2:INR", HOTELS)
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "Plan a 4 day trip to Paris for two people from Kishangarh, start 2026-12-10, budget ₹250000, historical places"}).json()
    a = client.post("/api/chat", headers=h, json={"message": "How much is the cab fare?", "trip_id": r["trip_id"]}).json()["reply"]
    g1 = r["plan"]["journey"]["legs"][0]
    assert a.startswith("Cab charges") and f"₹{g1['fare_inr'] + g1['extra_charges_inr']:,}" in a and "Kishangarh → Jaipur airport" in a
    assert "Getting around Paris" in a and "too far" in a  # no direct cab Kishangarh->Paris, and says so
    assert "Cheapest:" not in a  # not the generic options list


def test_every_planned_day_includes_lunch_and_dinner(client):
    h = auth(client)
    plan = client.post("/api/chat", headers=h, json={"message": MSG}).json()["plan"]
    for d in plan["itinerary"]["days"]:
        if any(s["type"] == "attraction" for s in d["stops"]):
            meals = {s["meal"] for s in d["stops"] if s["type"] == "meal"}
            assert {"lunch", "dinner"} <= meals, (d["day"], meals)
            assert [s["start"] for s in d["stops"]] == sorted(s["start"] for s in d["stops"])  # still chronological


def test_typed_place_beats_the_language_models_guess(client, monkeypatch):
    from app.providers import gemini
    monkeypatch.setattr(gemini, "available", lambda: True)
    monkeypatch.setattr(gemini, "extract_fields", lambda m: {"destination": "Ajmer", "origin": "Delhi", "days": 9, "adults": 2})  # model "corrects" the user's town
    _put("nominatim:kishangarh", [KISH])
    h = auth(client)
    r = client.post("/api/chat", headers=h, json={"message": "I live in Kishangarh, India. Plan a 3 day trip exploring places near me for 2 people, budget ₹10000"}).json()
    c = r["context"]
    assert c["destination"] != "Ajmer" and c["days"] == 3  # typed place and typed days win; the model only fills what the user did not say
    assert c["adults"] == 2 and c["stay_home"] is True
