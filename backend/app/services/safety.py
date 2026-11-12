"""Safety & environmental intelligence. Everything is attributed; nothing is presented as verified/live unless a live provider is wired."""
from ..data import seed
from ..provenance import estimated, simulated
from . import catalog, geo, live


def aqi_band(aqi: float) -> str:
    for hi, label in [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very poor")]:
        if aqi <= hi:
            return label
    return "Severe"


def neighbourhood_report(nid: str) -> dict:
    nb = next((n for n in catalog.neighbourhoods() if n["id"] == nid), None)
    if not nb:
        raise KeyError(nid)
    la = live.aqi(nb["lat"], nb["lon"])
    aqi_entry = ({"value": la["value"], "band": aqi_band(la["value"]), "station": la["station"], "provenance": la["provenance"]} if la else
                 {"value": nb["aqi_est"], "band": aqi_band(nb["aqi_est"]), "provenance": nb["provenance"]["aqi_est"]})
    return {
        "neighbourhood": nb["name"],
        "environment": {
            "aqi": aqi_entry,
            "noise_db": {"value": nb["noise_db_est"], "provenance": nb["provenance"]["noise_db_est"]},
            "industrial_distance_km": {"value": nb["industrial_km"], "provenance": nb["provenance"]["industrial_km"]},
            "traffic_congestion_index": {"value": nb["traffic"], "provenance": estimated("demo heuristic", "Not live traffic.", 0.3)},
            "green_space_index": nb["green"],
        },
        "safety": {"index": nb["safety_idx"], "provenance": nb["provenance"]["safety_idx"],
                   "limitations": "Indicative demo score. Not verified crime or safety statistics; never a guarantee of safety."},
        "emergency_facilities": {"hospitals_nearby_count": nb["hospitals"], "police_stations_nearby_count": nb["police"],
                                 "provenance": simulated("demo counts", "Replace with OSM/Overpass lookup.")},
    }


def destination_safety(city: str = "Delhi", lat: float | None = None, lon: float | None = None) -> dict:
    adv = seed.SAFETY_ADVISORY.get(city)
    if not adv:
        return {"city": city, "advisory": None, "note": "No advisory data for this city in the prototype."}
    nearest = None
    if lat is not None and lon is not None:
        nearest = min(catalog.neighbourhoods(), key=lambda n: geo.haversine_km((lat, lon), (n["lat"], n["lon"])))
    return {"city": city, "advisory": {"text": adv["general"], "provenance": simulated("static text", "No live advisory feed connected."),
                                       "tips": adv["tips"]},
            "emergency_contacts": adv["emergency"],
            "nearest_neighbourhood_report": neighbourhood_report(nearest["id"]) if nearest else None,
            "weather": (live.weather(lat if lat is not None else 28.6139, lon if lon is not None else 77.2090) if city == "Delhi" else None)
            or {"available": False, "note": "No weather data available (provider offline or key missing)."},
            "disclaimer": "Plarno.ai cannot guarantee any route, hotel or neighbourhood is safe."}
