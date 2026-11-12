"""Place search: towns AND colleges/stations/airports, with Mapbox's fuzzy near-misses filtered out. Provider payloads are real response shapes, injected."""
import os

os.environ["PLARNO_OFFLINE"] = "1"
from app import config  # noqa: E402
from app.providers import base, geocode, photon, suggest  # noqa: E402


def _f(name, key, val, lon, lat, **p):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"name": name, "osm_key": key, "osm_value": val, **p}}


# Photon answer for "manipal" (trimmed from a live response)
PHOTON_MANIPAL = {"features": [
    _f("Manipal", "place", "town", 74.787, 13.352, state="Karnataka", country="India", countrycode="IN", district="Udupi taluku"),
    _f("Manipal University Jaipur", "amenity", "university", 75.567, 26.842, city="Dahmi Kalan", state="Rajasthan", country="India", countrycode="IN"),
    _f("Manipal Institute of Technology", "office", "educational_institution", 74.794, 13.347, city="Manipal", state="Karnataka", country="India", countrycode="IN"),
    _f("Manipal Hospitals", "amenity", "hospital", 77.6, 12.9, city="Bengaluru", state="Karnataka", country="India", countrycode="IN"),
    _f("Manipal Hospital", "amenity", "hospital", 73.8, 18.5, city="Pune", state="Maharashtra", country="India", countrycode="IN"),
    _f("Manipal Lake", "natural", "water", 74.78, 13.35, city="Manipal", state="Karnataka", country="India", countrycode="IN"),   # not a destination: ignored
    _f("Manipal Road", "highway", "residential", 74.78, 13.35, city="Manipal", state="Karnataka", country="India", countrycode="IN"),  # a street: ignored
]}
# What Mapbox's town-only index does with the same text: only look-alike villages, never Manipal itself
MAPBOX_MANIPAL = {"features": [{"id": f"locality.{i}", "text": t, "place_name": f"{t}, {c}", "place_type": ["locality"], "center": [88.0, 26.0], "context": []}
                               for i, (t, c) in enumerate((("Fanipal'", "Minsk region, Belarus"), ("Mahipal", "West Bengal, India"), ("Manupal", "Cotabato, Philippines"), ("Ranipal", "West Bengal, India")))]}
PHOTON_IIT = {"features": [_f("IIT Bombay Staff CHS Ltd", "landuse", "residential", 72.9, 19.1, city="Mumbai", country="India", countrycode="IN"),
                           _f("Indian Institute of Technology Bombay", "amenity", "university", 72.915, 19.133, city="Mumbai", state="Maharashtra", country="India", countrycode="IN")]}
MAPBOX_IIT = {"features": [{"id": "locality.1", "text": "Bombay Beach", "place_name": "Bombay Beach, California, United States", "place_type": ["locality"], "center": [-115.7, 33.3], "context": []},
                           {"id": "place.2", "text": "Bombay", "place_name": "Bombay, New York, United States", "place_type": ["place"], "center": [-74.5, 44.9], "context": []}]}


def _serve(monkeypatch, photon_payload, mapbox_payload):
    def fake(method, url, **kw):
        if "mapbox.com" in url:
            if isinstance(mapbox_payload, Exception):
                raise mapbox_payload
            return mapbox_payload
        if isinstance(photon_payload, Exception):
            raise photon_payload
        return photon_payload
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test")
    monkeypatch.setattr(base, "http_json", fake)
    suggest._cache.clear(); photon._cache.clear(); photon._spots_cache.clear(); geocode._mb_cache.clear(); base.reset_breakers()


def test_a_college_town_is_found_and_look_alike_villages_are_not(monkeypatch):
    _serve(monkeypatch, PHOTON_MANIPAL, MAPBOX_MANIPAL)
    r = suggest.suggest("manipal")
    labels = [s["label"] for s in r["suggestions"]]
    assert labels[0] == "Manipal, Udupi taluku, Karnataka, India" and r["suggestions"][0]["kind"] == ""          # the town first
    assert "Manipal Institute of Technology, Manipal, Karnataka, India" in labels                               # and the college, in that town
    assert labels.index("Manipal Institute of Technology, Manipal, Karnataka, India") < labels.index("Manipal University Jaipur, Dahmi Kalan, Rajasthan, India")
    assert not any(w in " ".join(labels) for w in ("Mahipal", "Fanipal", "Manupal", "Ranipal"))                  # the old results are gone
    assert not any("Hospital" in x or "Lake" in x or "Road" in x for x in labels)                                # hospitals, lakes and streets do not crowd the list
    assert {s["kind"] for s in r["suggestions"] if "Institute" in s["name"]} == {"college"}
    assert "Photon" in r["source"] and "Mapbox" not in r["source"]                                               # nothing usable came from Mapbox


def test_college_abbreviations_find_the_full_name(monkeypatch):
    _serve(monkeypatch, PHOTON_IIT, MAPBOX_IIT)
    labels = [s["label"] for s in suggest.suggest("iit bombay")["suggestions"]]
    assert labels == ["Indian Institute of Technology Bombay, Mumbai, Maharashtra, India"]                      # not "Bombay Beach, California"
    assert photon.covers("Manipal Institute of Technology, Manipal", "mit manipal") and photon.covers("National Institute of Technology Trichy", "nit trichy")
    assert not photon.covers("Mahipal, West Bengal", "manipal")


def test_multi_word_query_with_no_phrase_match_retries_with_its_key_word(monkeypatch):
    calls = []

    def fake(method, url, **kw):
        if "mapbox.com" in url:
            return {"features": []}
        calls.append(kw["params"]["q"])
        return {"features": []} if kw["params"]["q"] == "mit manipal" else PHOTON_MANIPAL
    monkeypatch.setattr(config, "OFFLINE", False); monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test"); monkeypatch.setattr(base, "http_json", fake)
    suggest._cache.clear(); photon._cache.clear()
    labels = [s["label"] for s in suggest.suggest("mit manipal")["suggestions"]]
    assert calls == ["mit manipal", "manipal"] and labels == ["Manipal Institute of Technology, Manipal, Karnataka, India"]


def test_typos_still_get_suggestions_and_providers_can_fail(monkeypatch):
    _serve(monkeypatch, PHOTON_MANIPAL, {"features": []})
    assert suggest.suggest("manipall")["suggestions"]                                  # nothing matches exactly: closest guesses are shown
    _serve(monkeypatch, RuntimeError("down"), MAPBOX_MANIPAL)
    r = suggest.suggest("manipal")                                                      # Photon down: Mapbox's guesses are better than nothing
    assert r["source"] == "Mapbox" and r["suggestions"]
    _serve(monkeypatch, RuntimeError("down"), RuntimeError("down"))
    assert suggest.suggest("par")["source"].startswith("built-in")


def test_photon_ignores_foreign_and_incomplete_payloads(monkeypatch):
    assert photon.normalize({"text": "Kishangarh", "place_name": "x", "center": [1, 2]}) is None     # a Mapbox-shaped row
    assert photon.normalize({"properties": {"osm_key": "place", "osm_value": "town"}, "geometry": {"coordinates": [1, 2]}}) is None   # no name
    assert photon.normalize(_f("Somewhere", "shop", "bakery", 1, 2)) is None
    s = photon.normalize(_f("Goa", "place", "state", 74.0, 15.3, country="India", countrycode="IN"))
    assert s["broad"] is True and s["kind"] == "" and s["label"] == "Goa, India"
    assert photon.normalize(_f("Gaya Junction", "railway", "station", 85.0, 24.8, city="Gaya", state="Bihar", country="India", countrycode="IN"))["kind"] == "station"
    config.OFFLINE = True
    assert photon.search("anything") == []                                                           # offline mode never calls out


def test_resolve_finds_a_college_and_plans_around_the_town(monkeypatch):
    _serve(monkeypatch, PHOTON_MANIPAL, MAPBOX_MANIPAL)
    g = geocode.resolve("Manipal Institute of Technology, Manipal, Karnataka, India")
    assert g["kind"] == "college" and g["spot"] == "Manipal Institute of Technology"
    assert g["name"] == "Manipal" and g["country_code"] == "IN" and g["broad"] is False                # hotels/sights are searched in the town...
    assert abs(g["lat"] - 13.347) < 1e-6 and abs(g["lon"] - 74.794) < 1e-6                              # ...but distances start at the college itself
    t = geocode.resolve("Manipal")
    assert t["name"] == "Manipal" and t["spot"] is None and abs(t["lat"] - 13.352) < 1e-6              # not Mapbox's "Mahipal, West Bengal"
    _serve(monkeypatch, PHOTON_IIT, MAPBOX_IIT)
    iit = geocode.resolve("IIT Bombay, Mumbai, Maharashtra, India")
    assert iit["name"] == "Mumbai" and iit["spot"] == "Indian Institute of Technology Bombay" and abs(iit["lat"] - 19.133) < 1e-6


def test_resolve_falls_back_to_mapbox_guess_only_as_a_last_resort(monkeypatch):
    _serve(monkeypatch, {"features": []}, MAPBOX_MANIPAL)
    monkeypatch.setattr(base, "cached_fetch", lambda *a, **k: ([], "none", None))                       # Nominatim found nothing either
    g = geocode.resolve("Manipal")
    assert g and g["name"] == "Fanipal'"                                                                # an answer beats none; the planner still shows the place it chose


def test_a_region_typed_exactly_beats_a_lookalike_village(monkeypatch):
    goa = {"features": [{"text": "Goathland", "place_name": "Goathland, North Yorkshire, England, United Kingdom", "place_type": ["locality"], "center": [-0.7, 54.4], "id": "locality.1", "context": []},
                        {"text": "Goa", "place_name": "Goa, India", "place_type": ["region"], "center": [74.05, 15.3], "id": "region.1", "context": [{"id": "country.1", "short_code": "in"}]}]}
    _serve(monkeypatch, {"features": []}, goa)
    g = geocode.resolve("Goa")
    assert g["name"] == "Goathland"                      # Mapbox listed the village first and it is a *town*, so it is kept unless the region comes first
    goa["features"].reverse()
    geocode._mb_cache.clear()
    g = geocode.resolve("Goa")
    assert (g["name"], g["country_code"], g["broad"]) == ("Goa", "IN", True)                          # the Indian state: the planner asks for a town in it
    nyc = {"features": [{"text": "New York City", "place_name": "New York City, New York, United States", "place_type": ["place"], "center": [-74.0, 40.7], "id": "place.1", "context": []},
                        {"text": "New York", "place_name": "New York, United States", "place_type": ["region"], "center": [-75.4, 42.7], "id": "region.1", "context": []}]}
    _serve(monkeypatch, {"features": []}, nyc)
    assert geocode.resolve("New York City")["name"] == "New York City"


def test_college_towns_get_a_sensible_nearest_airport():
    from app.data import airports
    near = airports.nearest_airport(13.3467, 74.7943)            # Manipal Institute of Technology
    assert (near["city"], near["iata"]) == ("Mangaluru", "IXE") and near["km"] < 60                   # used to be Goa, 234 km away
    assert airports.iata("Mangalore") == "IXE" and airports.iata("Vizag") == "VTZ" and airports.iata("Trichy") == "TRZ"   # everyday spellings work
    assert airports.nearest_airport(26.586, 74.854)["iata"] == "JAI"                                  # unchanged for Kishangarh

SEARCHBOX = {"features": [
    {"geometry": {"coordinates": [75.565, 26.844]}, "properties": {"name": "Manipal University Jaipur", "feature_type": "poi", "poi_category": ["education", "university"], "place_formatted": "Jaipur, 303007, India",
                                                                   "context": {"place": {"name": "Jaipur"}, "region": {"name": "Rajasthan"}, "country": {"name": "India", "country_code": "IN"}}}},
    {"geometry": {"coordinates": [75.565, 26.842]}, "properties": {"name": "Manipal University Library", "poi_category": ["education", "library", "university building"], "place_formatted": "Jaipur, India", "context": {"place": {"name": "Jaipur"}}}},
    {"geometry": {"coordinates": [75.563, 26.843]}, "properties": {"name": "Nothing Before Coffee - Manipal University, Jaipur", "poi_category": ["café", "coffee"], "place_formatted": "Jaipur, India", "context": {}}},
    {"geometry": {"coordinates": [75.57, 26.837]}, "properties": {"name": "Stay Well Hostel near Manipal University Jaipur", "poi_category": ["education", "university"], "place_formatted": "Jaipur, India", "context": {}}}]}


def test_college_search_still_works_when_the_openstreetmap_server_is_down(monkeypatch):
    calls = []

    def fake(method, url, **kw):
        calls.append(url)
        if "searchbox" in url:
            return SEARCHBOX
        if "mapbox.com" in url:
            return {"features": []}
        raise RuntimeError("photon timed out")
    monkeypatch.setattr(config, "OFFLINE", False); monkeypatch.setattr(config, "MAPBOX_TOKEN", "pk.test"); monkeypatch.setattr(base, "http_json", fake)
    suggest._cache.clear(); photon._cache.clear(); photon._spots_cache.clear(); geocode._mb_cache.clear(); base.reset_breakers()
    r = suggest.suggest("manipal university jaipur")
    assert [(s["name"], s["kind"]) for s in r["suggestions"]] == [("Manipal University Jaipur", "college")]      # the campus only: no library, cafe or hostel
    assert r["suggestions"][0]["label"] == "Manipal University Jaipur, Jaipur, Rajasthan, India" and r["source"] == "Mapbox Search"
    n = sum("photon" in u for u in calls)
    suggest.suggest("manipal univ")
    assert sum("photon" in u for u in calls) == n          # after one failure the dead server is skipped (no timeout per keystroke)
    g = geocode.resolve("Manipal University Jaipur")
    assert g["spot"] == "Manipal University Jaipur" and g["name"] == "Jaipur" and g["country_code"] == "IN" and abs(g["lat"] - 26.844) < 1e-6
    base.reset_breakers()
