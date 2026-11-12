"""Everyday essentials near a point: pharmacies, hospitals, grocery shops, ATMs, police (Mapbox Search Box category search).
Real listings with address, phone (when the listing has one) and distance. Results are kept only briefly in memory."""
import time

from .. import config
from ..services import geo
from . import base

KINDS = {"pharmacy": ("pharmacy", "Pharmacies"), "hospital": ("hospital", "Hospitals & clinics"), "grocery": ("grocery", "Grocery shops"),
         "supermarket": ("supermarket", "Supermarkets"), "atm": ("atm", "ATMs"), "police": ("police_station", "Police")}
_cache: dict[str, tuple[float, list]] = {}


def search(kind: str, lat: float, lon: float, limit: int = 8) -> dict:
    cat, title = KINDS[kind]
    prov = {"source": "Mapbox place listings", "kind": "live", "fetched_at": base.now_iso(), "confidence": 0.75, "note": "Listings can be out of date: call ahead for opening hours."}
    if config.OFFLINE or not config.MAPBOX_TOKEN:
        return {"kind": kind, "title": title, "places": [], "provenance": {**prov, "kind": "no data"}, "error": "Nearby search is not available (no map key configured)."}
    key = f"{kind}:{lat:.3f},{lon:.3f}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 1800:
        return {"kind": kind, "title": title, "places": hit[1][:limit], "provenance": {**prov, "kind": "cached"}}
    try:
        base.throttle("mapbox-search", 0.05)
        d = base.http_json("GET", f"https://api.mapbox.com/search/searchbox/v1/category/{cat}", retries=0, timeout=8,
                           params={"access_token": config.MAPBOX_TOKEN, "proximity": f"{lon},{lat}", "limit": 12, "language": "en"})
    except Exception:  # noqa: BLE001
        return {"kind": kind, "title": title, "places": [], "provenance": {**prov, "kind": "no data"}, "error": "Could not load nearby places right now. Try again in a moment."}
    out, seen = [], set()
    for f in d.get("features", []) if isinstance(d, dict) else []:
        try:
            p, c = f["properties"], f["geometry"]["coordinates"]
            name, plat, plon = p["name"].strip(), float(c[1]), float(c[0])
            km = geo.haversine_km((lat, lon), (plat, plon))
            if not name or name.lower() in seen or km > 25:
                continue
            seen.add(name.lower())
            meta = p.get("metadata") or {}
            out.append({"id": p.get("mapbox_id") or f"{plat:.5f},{plon:.5f}", "name": name, "address": p.get("full_address") or p.get("place_formatted") or "", "lat": plat, "lon": plon,
                        "distance_km": round(km, 2), "phone": meta.get("phone") or None, "website": meta.get("website") or None,
                        "maps_url": f"https://www.google.com/maps/dir/?api=1&destination={plat:.6f},{plon:.6f}"})
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            continue
    out.sort(key=lambda x: x["distance_km"])
    if out:
        _cache[key] = (time.time(), out)
    return {"kind": kind, "title": title, "places": out[:limit], "provenance": prov}
