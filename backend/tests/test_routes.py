"""Door-to-door routes: trains between REAL stations, honest bus/cab legs, links to book, and a budget that means what the user typed."""
import os

os.environ["PLARNO_OFFLINE"] = "1"
from app import config  # noqa: E402
from app.data import stations  # noqa: E402
from app.providers import geocode, photon  # noqa: E402
from app.services import routes  # noqa: E402

DAHMI = {"name": "Dahmi Kalan", "lat": 26.842, "lon": 75.567, "country_code": "IN"}      # Manipal University Jaipur: a campus in a village
MANDI = {"name": "Mandi", "lat": 31.708, "lon": 76.932, "country_code": "IN"}            # hill town with no broad-gauge station
MANIPAL = {"name": "Manipal", "lat": 13.3467, "lon": 74.7943, "country_code": "IN"}
BLR = {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946, "country_code": "IN"}


def _opt(res, *modes):
    return next(o for o in res["options"] if o["modes"] == list(modes))


def test_nearest_major_station():
    assert stations.nearest_station(26.842, 75.567)["code"] == "JP"
    assert stations.nearest_station(13.3467, 74.7943)["code"] == "UD"
    near_mandi = stations.nearest_station(31.708, 76.932, 250)
    assert near_mandi["code"] == "UHL" and 50 < near_mandi["km"] < 90
    assert stations.nearest_station(10.0, 60.0) is None                                   # the middle of the sea
    assert len({s["code"] for s in stations.STATIONS}) == len(stations.STATIONS)          # codes are unique


def test_train_runs_between_real_stations_not_invented_stops():
    res = routes.build_options(DAHMI, MANDI, "2026-12-12", 1, use_flights=False)
    train = _opt(res, "cab", "train", "bus")
    cab, rail, bus = train["legs"]
    assert (cab["from"], cab["to"]) == ("Dahmi Kalan", "Jaipur Junction (JP)") and 20 < cab["distance_km"] < 45        # a real 25-30 km ride, not a made-up 8 km
    assert (rail["from"], rail["to"]) == ("Jaipur Junction (JP)", "Una Himachal (UHL)") and rail["from_code"] == "JP"
    assert (bus["from"], bus["to"]) == ("Una", "Mandi") and bus["mode"] == "bus"                                         # 100+ km last stretch goes by bus, not a costly cab
    for o in res["options"]:
        for leg in o["legs"]:
            assert "stop" not in (leg["from"] + leg["to"]).lower(), leg                                                   # no "train stop" / "bus stop" placeholders
            assert len(leg["from_pt"]) == 2 and len(leg["to_pt"]) == 2 and leg["links"], leg                              # every leg can be mapped and checked
            assert isinstance(leg["fare_inr"], int) and leg["provenance"]["kind"] == "estimated"
    assert [f["label"] for f in rail["fare_options"]] == ["Sleeper", "AC 3-tier", "AC 2-tier"] and rail["fare_options"][0]["inr"] == rail["fare_inr"]
    assert rail["links"][0]["url"] == "https://erail.in/trains-between-stations/jaipur-junction-JP/una-himachal-UHL"
    assert "irctc.co.in" in rail["links"][1]["url"] and "redbus.in/bus-tickets/una-to-mandi" in bus["links"][0]["url"]
    assert "travelmode=driving" in cab["links"][0]["url"] and "origin=26.84200,75.56700" in cab["links"][0]["url"]
    assert train["via"] == ["Dahmi Kalan", "Jaipur Junction (JP)", "Una Himachal (UHL)", "Mandi"]
    assert any("no major station of its own" in n for n in train["notes"])
    assert not any(o["modes"] == ["train"] for o in res["options"])                                                       # never a bare "Train: village -> hill town"


def test_long_bus_leaves_from_the_city_bus_stand_and_short_bus_is_direct():
    far = _opt(routes.build_options(DAHMI, MANDI, "2026-12-12", 1, use_flights=False), "cab", "bus")
    assert far["legs"][0]["to"] == "Jaipur bus stand" and (far["legs"][1]["from"], far["legs"][1]["to"]) == ("Jaipur", "Mandi")
    kish, jaipur = {"name": "Kishangarh", "lat": 26.586, "lon": 74.854, "country_code": "IN"}, {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873, "country_code": "IN"}
    near = _opt(routes.build_options(kish, jaipur, "2026-12-12", 1, use_flights=False), "bus")
    assert (near["legs"][0]["from"], near["legs"][0]["to"]) == ("Kishangarh", "Jaipur")


def test_station_in_town_needs_only_a_short_cab_and_same_station_means_no_train():
    t = _opt(routes.build_options(MANIPAL, BLR, "2026-12-12", 2, use_flights=False), "cab", "train", "cab")
    assert t["legs"][1]["from"] == "Udupi (UD)" and t["legs"][1]["to"] == "KSR Bengaluru City (SBC)" and t["legs"][0]["distance_km"] < 15
    assert t["total_fare_inr"] == t["legs"][0]["fare_inr"] + t["legs"][0]["extra_charges_inr"] + 2 * t["legs"][1]["fare_inr"] + t["legs"][2]["fare_inr"] + t["legs"][2]["extra_charges_inr"]
    udupi = {"name": "Udupi", "lat": 13.34, "lon": 74.75, "country_code": "IN"}
    assert not any("train" in o["modes"] for o in routes.build_options(MANIPAL, udupi, "2026-12-12", 1, use_flights=False)["options"])


def test_budget_means_what_was_typed():
    one = routes.build_options(DAHMI, MANDI, "2026-12-12", 1, 5000, use_flights=False, budget_basis="one_way", budget_share=None)
    train = _opt(one, "cab", "train", "bus")
    assert train["total_fare_inr"] < 5000 and train["fits_budget"] is True and train["over_by_inr"] == 0       # the reported case: Rs 5,000 budget, ~Rs 1,000 fare
    assert one["budget_inr"] == 5000 and one["budget_basis"] == "one_way" and one["budget_share"] is None and one["allowance_round_trip_inr"] is None
    cab = _opt(one, "cab")
    assert cab["fits_budget"] is False and cab["over_by_inr"] == cab["total_fare_inr"] - 5000
    tight = routes.build_options(DAHMI, MANDI, "2026-12-12", 1, train["total_fare_inr"] + 100, use_flights=False, budget_basis="one_way", budget_share=None)
    assert _opt(tight, "cab", "train", "bus")["fits_budget"] is True                                              # fits one way...
    rt = routes.build_options(DAHMI, MANDI, "2026-12-12", 1, train["total_fare_inr"] + 100, use_flights=False, budget_basis="round_trip", budget_share=None)
    t2 = _opt(rt, "cab", "train", "bus")
    assert t2["fits_budget"] is False and t2["over_by_inr"] == t2["round_trip_inr"] - (train["total_fare_inr"] + 100)   # ...but not there and back
    planner = routes.build_options(DAHMI, MANDI, "2026-12-12", 1, 9000, use_flights=False)                      # trip planner default: round trip, 45% share
    assert planner["budget_basis"] == "round_trip" and planner["budget_share"] == 0.45 and planner["allowance_round_trip_inr"] == 9000


def test_exact_coordinates_are_kept_and_named(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "MAPBOX_TOKEN", "")          # no network in tests
    monkeypatch.setattr(geocode, "resolve", lambda q: None)
    monkeypatch.setattr(photon, "reverse", lambda la, lo: {"name": "Dahmi Kalan", "display": "Dahmi Kalan, Rajasthan, India", "country": "India", "country_code": "IN"})
    g = geocode.at(26.842, 75.567, "Manipal University Jaipur, Dahmi Kalan, Rajasthan, India")
    assert (g["lat"], g["lon"], g["name"], g["country_code"], g["spot"]) == (26.842, 75.567, "Dahmi Kalan", "IN", "Manipal University Jaipur")
    me = geocode.at(26.9, 75.8, "My location")
    assert me["name"] == "Dahmi Kalan" and me["spot"] is None and me["broad"] is False
    assert geocode.at(999, 0, "x") is None
    monkeypatch.setattr(photon, "reverse", lambda la, lo: None)                                                   # lookup down: the label still names it, the point is kept
    g = geocode.at(26.842, 75.567, "Somewhere Nice, India")
    assert g["name"] == "Somewhere Nice" and g["lat"] == 26.842


def test_routes_endpoint_takes_coordinates_and_trip_type(monkeypatch):
    import tempfile
    from fastapi.testclient import TestClient
    from app import db
    from app.main import app
    db.reset(os.path.join(tempfile.mkdtemp(), "t.db"))
    config.RATE_LIMIT_PER_MIN = 100000
    monkeypatch.setattr(config, "OFFLINE", False); monkeypatch.setattr(config, "MAPBOX_TOKEN", "")
    names = {26.842: "Dahmi Kalan", 26.9124: "Jaipur"}
    monkeypatch.setattr(photon, "reverse", lambda la, lo: {"name": names[la], "display": names[la] + ", Rajasthan, India", "country": "India", "country_code": "IN"})
    c = TestClient(app)
    q = {"origin": "My location", "destination": "Jaipur, India", "date": "2027-01-10", "origin_lat": 26.842, "origin_lon": 75.567, "dest_lat": 26.9124, "dest_lon": 75.7873, "budget": 600}
    r = c.get("/api/routes/options", params=q)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["origin"]["name"] == "Dahmi Kalan" and d["origin"]["lat"] == 26.842 and d["trip"] == "one_way" and d["budget_inr"] == 600
    cab = next(o for o in d["options"] if o["modes"] == ["cab"])
    assert cab["fits_budget"] is (cab["total_fare_inr"] <= 600)
    rt = c.get("/api/routes/options", params={**q, "trip": "round_trip"}).json()
    assert rt["budget_basis"] == "round_trip" and next(o for o in rt["options"] if o["modes"] == ["cab"])["fits_budget"] is (cab["round_trip_inr"] <= 600)
    assert c.get("/api/routes/options", params={**q, "trip": "sideways"}).status_code == 422
    assert c.get("/api/routes/options", params={**q, "budget": -5}).status_code == 422
    rev = c.get("/api/geocode/reverse", params={"lat": 26.842, "lon": 75.567})
    assert rev.status_code == 200 and rev.json()["name"] == "Dahmi Kalan" and rev.json()["lat"] == 26.842
    db.reset()