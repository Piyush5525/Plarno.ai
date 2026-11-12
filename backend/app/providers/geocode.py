"""Place resolution: any user-typed city/town/region -> verified coordinates + country.
Primary: Mapbox Geocoding (accurate for small towns; results kept only in a short in-memory cache, per its temporary-geocoding terms).
Fallback: OpenStreetMap Nominatim (free, 1 req/s policy, identifying User-Agent), cached 90 days."""
import re
import time

from .. import config
from ..data import stations as _stations
from . import base, photon

SOURCE = "OpenStreetMap Nominatim"
SOURCE_MB = "Mapbox Geocoding"
UA = {"User-Agent": "Plarno.ai/0.1 (travel planner prototype; contact via project owner)"}
PLACE_CATEGORIES = {"place", "boundary"}
PLACE_TYPES = {"city", "town", "village", "municipality", "administrative", "island", "county", "state", "region", "suburb", "hamlet", "district", "city_district", "quarter", "locality", "archipelago", "country"}
BROAD_TYPES = {"state", "region", "county", "country", "archipelago", "province", "state_district"}
_mb_cache: dict[str, tuple[float, dict | None]] = {}


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _mapbox(query: str) -> dict | None:
    key = _norm(query)
    hit = _mb_cache.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    try:
        base.throttle("mapbox-geocode", 0.05)
        d = base.http_json("GET", f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query.strip()}.json", retries=0, timeout=8,
                           params={"access_token": config.MAPBOX_TOKEN, "types": "place,locality,region,district,country", "limit": 5, "language": "en"})
    except Exception:  # noqa: BLE001
        return None
    feats = d.get("features", [])
    is_town = lambda f: bool({"place", "locality"} & set(f.get("place_type", [])))  # noqa: E731
    pick = feats[0] if feats else None
    if pick and not is_town(pick) and photon.fold(pick.get("text", "")) != photon.fold(query.split(",")[0]):
        # the top hit is a region whose name is not what was typed: look for a town instead
        pick = next((f for f in feats if is_town(f)), pick)
    # (a region whose name is exactly what was typed stays: "Goa" is the Indian state, not the UK village Goathland that merely starts the same)
    out = None
    if pick:
        cc = next((c.get("short_code", "") for c in pick.get("context", []) if c["id"].startswith("country")), "") or (pick["id"].startswith("country") and pick.get("properties", {}).get("short_code", "")) or ""
        parts = [p.strip() for p in pick["place_name"].split(",")]
        types = set(pick.get("place_type", []))
        out = {"broad": not ({"place", "locality"} & types), "name": pick["text"], "display": pick["place_name"], "lat": pick["center"][1], "lon": pick["center"][0],
               "country": parts[-1] if len(parts) > 1 else pick["text"], "country_code": cc.upper(), "kind": ",".join(sorted(types)),
               "provenance": base.prov(SOURCE_MB, "live", None, "Mapbox temporary geocoding (not stored long-term)", 0.9)}
    _mb_cache[key] = (time.time(), out)
    return out


def _matches(r: dict, query: str) -> bool:
    """Is Mapbox's answer really the place that was asked for? Every word of the typed place name must appear in what it found."""
    words = photon.fold(query.split(",")[0]).split()
    hay = photon.fold(f"{r.get('name', '')} {r.get('display', '')}")
    return bool(words) and all(w in hay for w in words)


def resolve(query: str) -> dict | None:
    """Returns {name, display, lat, lon, country, country_code, kind, broad, provenance} or None if nothing place-like was found."""
    q = _norm(query)
    if not q or len(q) > 80 or re.search(r"[\d@/\\]", q):
        return None
    mb = None
    if config.MAPBOX_TOKEN and not config.OFFLINE:
        mb = _mapbox(query)
        if mb and _matches(mb, query):
            return mb
    if not config.OFFLINE:
        # Mapbox only knows towns, and fuzzy-matches a college or a small place to a different town ("manipal" -> Mahipal), so ask the
        # OpenStreetMap-based search, which knows colleges, stations and small places, before trusting a poor match
        ph = photon.resolve(query)
        if ph:
            return ph

    def fetch():
        base.throttle("nominatim", 1.1)
        d = base.http_json("GET", "https://nominatim.openstreetmap.org/search", retries=1, timeout=12, headers=UA,
                           params={"q": query.strip(), "format": "jsonv2", "limit": 3, "addressdetails": 1, "accept-language": "en"})
        return d if isinstance(d, list) else []

    rows, kind, at = base.cached_fetch(f"nominatim:{q}", 90 * 86400, fetch)
    if not rows:
        return mb  # last resort: Mapbox's closest guess (None when Mapbox found nothing either)
    pick = next((r for r in rows if r.get("category") in PLACE_CATEGORIES and r.get("type") in PLACE_TYPES), None)
    if not pick:
        return mb
    a = pick.get("address", {})
    name = pick.get("name") or a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or a.get("hamlet") or a.get("state") or query.title()
    named_like_state = bool(a.get("state")) and name == a.get("state") and not (a.get("city") or a.get("town") or a.get("village") or a.get("municipality"))
    return {"broad": pick.get("type") in BROAD_TYPES or named_like_state, "name": name, "display": pick.get("display_name"), "lat": float(pick["lat"]), "lon": float(pick["lon"]),
            "country": a.get("country"), "country_code": (a.get("country_code") or "").upper(), "kind": pick.get("type"),
            "provenance": base.prov(SOURCE, kind, at, "ODbL", 0.85)}


def _mapbox_reverse(lat: float, lon: float) -> dict | None:
    if not config.MAPBOX_TOKEN:
        return None
    try:
        base.throttle("mapbox-geocode", 0.05)
        d = base.http_json("GET", f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json", retries=0, timeout=6,
                           params={"access_token": config.MAPBOX_TOKEN, "types": "place,locality", "language": "en", "limit": 1})
        f = d["features"][0]
    except Exception:  # noqa: BLE001
        return None
    place = next((c["text"] for c in f.get("context", []) if c["id"].startswith("place")), None)
    name = f["text"] if "place" in f.get("place_type", []) or not place else place   # a locality inside a city is named by the city
    cc = next((c.get("short_code", "") for c in f.get("context", []) if c["id"].startswith("country")), "")
    return {"name": name, "display": f["place_name"], "country": f["place_name"].split(",")[-1].strip(), "country_code": cc.upper()}


def at(lat: float, lon: float, label: str | None = None) -> dict | None:
    """A place given by exact coordinates (picked from the suggestions, or the visitor's own location). The coordinates are kept as they are;
    the name and country come from a reverse lookup, or from the label when that is unavailable."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    r = None if config.OFFLINE else (photon.reverse(lat, lon) or _mapbox_reverse(lat, lon))
    parts = [p.strip() for p in (label or "").split(",") if p.strip()]
    if not r:
        g = resolve(label) if label else None  # offline or lookup failed: fall back to the text, keeping the exact point
        if g and _stations._km((lat, lon), (g["lat"], g["lon"])) > 150:
            g = None  # the text search found some other place far from this point: do not borrow its name or country
        if not g and not parts:
            return None
        r = {"name": (g or {}).get("name") or parts[0], "display": (g or {}).get("display") or label, "country": (g or {}).get("country"), "country_code": (g or {}).get("country_code", "")}
    spot = parts[0] if parts and photon.fold(parts[0]) != photon.fold(r["name"]) and not parts[0].lower().startswith("my location") else None
    return {"broad": False, "name": r["name"], "display": label or r["display"], "lat": lat, "lon": lon, "country": r.get("country"), "country_code": r.get("country_code", ""),
            "kind": "point", "spot": spot, "provenance": base.prov(photon.SOURCE, "live", None, "Exact coordinates; name from an OpenStreetMap reverse lookup", 0.85)}
