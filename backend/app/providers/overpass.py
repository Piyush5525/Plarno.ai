"""OpenStreetMap places via the Overpass API (open data, ODbL). Real names/locations only: ratings, prices and
opening hours are returned ONLY when present in OSM tags, never invented. Cached for 7 days; ~1 request/2s politeness."""
from .. import config
from ..services import geo
from . import base

MIRRORS = [config.OVERPASS_URL, "https://overpass.kumi.systems/api/interpreter"]
SOURCE = "OpenStreetMap contributors via Overpass API (ODbL)"
QUERIES = {
    "attractions": '(nwr["tourism"~"^(attraction|museum|gallery|viewpoint)$"]{a};nwr["historic"~"^(monument|fort|castle|memorial|archaeological_site|ruins|tomb)$"]{a};nwr["leisure"~"^(park|garden)$"]["name"]{a};)',
    "restaurants": '(nwr["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]["name"]{a};)',
    "hotels": '(nwr["tourism"~"^(hotel|guest_house|hostel|motel|apartment)$"]["name"]{a};)',
    "hospitals": '(nwr["amenity"~"^(hospital|clinic)$"]["name"]{a};)',
    "police": '(nwr["amenity"="police"]{a};)',
    "transit": '(nwr["railway"="station"]["name"]{a};nwr["station"="subway"]["name"]{a};)',
}
RADIUS_M = {"attractions": 6000, "restaurants": 1500, "hotels": 5000, "hospitals": 3000, "police": 3000, "transit": 2500}
LIMIT = {"attractions": 60, "restaurants": 60, "hotels": 60, "hospitals": 15, "police": 15, "transit": 15}


def _normalize(el: dict, category: str) -> dict | None:
    t = el.get("tags", {})
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    if not t.get("name") or lat is None:
        return None
    return {
        "id": f"osm-{el['type'][0]}{el['id']}", "name": t["name"], "lat": lat, "lon": lon, "category": category,
        "subtype": t.get("tourism") or t.get("historic") or t.get("amenity") or t.get("leisure") or t.get("railway"),
        "cuisine": t.get("cuisine"), "opening_hours": t.get("opening_hours"), "website": t.get("website") or t.get("contact:website"),
        "phone": t.get("phone") or t.get("contact:phone"), "stars": t.get("stars"), "wheelchair": t.get("wheelchair"),
        "diet_vegetarian": t.get("diet:vegetarian"), "diet_vegan": t.get("diet:vegan"), "fee": t.get("fee"),
        "notability": int(bool(t.get("wikipedia") or t.get("wikidata"))), "address": t.get("addr:street"),
    }


def nearby(category: str, lat: float, lon: float, radius_m: int | None = None) -> dict:
    """Returns {places:[...], provenance:{...}}. places == [] with kind 'none' if Overpass unreachable and nothing cached."""
    r = radius_m or RADIUS_M[category]
    key = f"overpass:{category}:{lat:.3f},{lon:.3f}:{r}"
    q = QUERIES[category].format(a=f"(around:{r},{lat},{lon})")
    ql = f"[out:json][timeout:25];{q};out center tags {LIMIT[category] * 3};"

    def fetch():
        last = None
        for url in MIRRORS:
            base.throttle("overpass", 2.0)
            try:
                d = base.http_json("POST", url, retries=0, timeout=6, data={"data": ql}, headers={"User-Agent": "Plarno.ai/0.1 (travel planner prototype)"})
                return d.get("elements", [])
            except Exception as e:  # noqa: BLE001
                last = e
        raise last or RuntimeError("no overpass mirror")

    els, kind, at = base.cached_fetch(key, 7 * 86400, fetch)
    if els is None:
        return {"places": [], "provenance": base.prov(SOURCE, "none", note="Overpass unreachable and no cached copy")}
    places = [p for p in (_normalize(e, category) for e in els) if p]
    for p in places:
        p["distance_km"] = round(geo.haversine_km((lat, lon), (p["lat"], p["lon"])), 2)
    places.sort(key=lambda p: (-p["notability"], p["distance_km"]))
    return {"places": places[:LIMIT[category]], "provenance": base.prov(SOURCE, kind, at, "Ratings/prices are not in OSM and are not shown.", 0.7)}
