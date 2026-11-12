"""Live data providers (AQICN air quality, OpenWeather, Mapbox Directions). Each call is cached (TTL), time-limited and
returns None on failure so callers can fall back to labelled simulated data. Provenance kind is 'live' (or 'cached' on a cache hit)."""
import time

import httpx

from .. import config
from ..provenance import now_iso

_cache: dict[str, tuple[float, dict]] = {}


def _get(key: str, url: str, params: dict, ttl: int) -> tuple[dict | None, str]:
    if config.OFFLINE:
        return None, "offline"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1], "cached"
    try:
        r = httpx.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None, "error"
    _cache[key] = (time.time(), data)
    return data, "live"


def aqi(lat: float, lon: float) -> dict | None:
    if not config.AQICN_KEY:
        return None
    d, kind = _get(f"aqi:{lat:.2f},{lon:.2f}", f"https://api.waqi.info/feed/geo:{lat};{lon}/", {"token": config.AQICN_KEY}, 1800)
    if not d or d.get("status") != "ok" or not isinstance(d["data"].get("aqi"), (int, float)):
        return None
    x = d["data"]
    return {"value": x["aqi"], "station": x.get("city", {}).get("name"), "provenance": {
        "source": "AQICN / WAQI (nearest monitoring station)", "kind": kind, "fetched_at": now_iso(), "confidence": 0.8,
        "note": "Reading from the nearest station, which may be several km from the exact location."}}


def weather(lat: float, lon: float) -> dict | None:
    if not config.OPENWEATHER_KEY:
        return None
    d, kind = _get(f"wx:{lat:.2f},{lon:.2f}", "https://api.openweathermap.org/data/2.5/weather",
                   {"lat": lat, "lon": lon, "units": "metric", "appid": config.OPENWEATHER_KEY}, 900)
    if not d or "main" not in d:
        return None
    return {"available": True, "temp_c": d["main"]["temp"], "feels_like_c": d["main"]["feels_like"], "humidity": d["main"]["humidity"],
            "summary": d["weather"][0]["description"], "wind_ms": d.get("wind", {}).get("speed"),
            "provenance": {"source": "OpenWeather current conditions", "kind": kind, "fetched_at": now_iso(), "confidence": 0.9, "note": None}}


def directions(coords: list[tuple[float, float]], profile: str = "driving") -> dict | None:
    """coords are (lat, lon). Returns distance/duration/geometry for the whole multi-stop route (<=25 points)."""
    if not config.MAPBOX_TOKEN or len(coords) < 2 or len(coords) > 25:
        return None
    path = ";".join(f"{lo},{la}" for la, lo in coords)
    d, kind = _get(f"dir:{profile}:{path}", f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{path}",
                   {"access_token": config.MAPBOX_TOKEN, "geometries": "geojson", "overview": "full"}, 3600)
    if not d or d.get("code") != "Ok":
        return None
    r = d["routes"][0]
    return {"distance_km": round(r["distance"] / 1000, 2), "duration_min": round(r["duration"] / 60, 1), "geometry": r["geometry"]["coordinates"],
            "provenance": {"source": "Mapbox Directions (road network, no live traffic)", "kind": kind, "fetched_at": now_iso(), "confidence": 0.85,
                           "note": "Road routing; does not include live traffic."}}
