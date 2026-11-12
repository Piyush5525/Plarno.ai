"""Photon (OpenStreetMap-based geocoder built for as-you-type search). Unlike a town-only index it also knows colleges, universities,
stations, airports, hospitals and landmarks, so "manipal institute of technology" or "iit bombay" can be found.
Public demo server: fair-use only, so results are cached briefly in memory and calls are throttled. Self-host and set PHOTON_URL for heavy use.
Data © OpenStreetMap contributors (ODbL)."""
import re
import time
import unicodedata

from .. import config
from . import base

SOURCE = "Photon (OpenStreetMap)"
SOURCE_SHORT = "Photon/OpenStreetMap"
UA = {"User-Agent": "Plarno.ai/0.1 (travel planner prototype)"}
_cache: dict[str, tuple[float, list]] = {}

PLACE_VALUES = {"city", "town", "village", "hamlet", "suburb", "locality", "district", "borough", "quarter", "neighbourhood", "municipality", "island", "isolated_dwelling"}
BROAD_VALUES = {"county", "state", "region", "province", "country", "state_district", "archipelago"}
EDU = {"university", "college", "school", "research_institute"}
KIND_BY_VALUE = {"university": "college", "college": "college", "school": "school", "research_institute": "college", "educational_institution": "college", "hospital": "hospital",
                 "station": "station", "halt": "station", "bus_station": "station", "aerodrome": "airport", "ferry_terminal": "port"}


def fold(s: str) -> str:
    """Lower-case, accent-free, single-spaced text for tolerant comparisons."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def key_words(text: str) -> list[str]:
    """The words that must appear in a match. Short words (abbreviations such as 'iit', 'mit', 'of') are optional, because a college is
    often typed as an abbreviation while its official name spells it out."""
    toks = fold(text).split()
    return [w for w in toks if len(w) > 3] or toks


_STOP = {"of", "the", "and", "for", "de", "in", "at"}


def covers(label: str, text: str) -> bool:
    """Does `label` match everything typed in `text`? Each typed word may appear inside a word of the label, or be an acronym of its words
    ('iit' -> Indian Institute of Technology, 'mit' -> Manipal Institute of Technology)."""
    hay = fold(label)
    initials = "".join(w[0] for w in hay.split() if w not in _STOP)
    return all(w in hay or w in initials for w in fold(text).split())


def _classify(p: dict) -> tuple[str | None, str, bool]:
    """(group, kind, broad). group 'place' = a town/region you can plan a trip to; 'poi' = a specific spot; None = ignore (roads, land-use, shops...)."""
    key, val, typ = p.get("osm_key"), p.get("osm_value"), p.get("type")
    if key == "place":
        if val in PLACE_VALUES:
            return "place", "", False
        if val in BROAD_VALUES:
            return "place", "", True
    if key == "boundary" and val == "administrative":
        return "place", "", typ in ("state", "country", "county")
    if key == "amenity" and val in EDU | {"hospital", "bus_station", "ferry_terminal"}:
        return "poi", KIND_BY_VALUE[val], False
    if key == "office" and val == "educational_institution":
        return "poi", "college", False
    if key == "railway" and val in ("station", "halt"):
        return "poi", "station", False
    if key == "aeroway" and val == "aerodrome":
        return "poi", "airport", False
    if key in ("tourism", "historic") and p.get("name"):
        return "poi", "landmark", False
    return None, "", False


def normalize(feature: dict) -> dict | None:
    """One Photon GeoJSON feature -> a suggestion, or None when it is not something worth offering. Tolerates foreign shapes."""
    try:
        p, c = feature["properties"], feature["geometry"]["coordinates"]
        name = (p.get("name") or "").strip()
        lon, lat = float(c[0]), float(c[1])
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return None
    if not name:
        return None
    group, kind, broad = _classify(p)
    if not group:
        return None
    area = next((p.get(k) for k in ("city", "locality", "district", "county") if p.get(k) and fold(p[k]) != fold(name)), None)
    ctx = [x for x in dict.fromkeys(x for x in (area, p.get("state"), p.get("country")) if x) if fold(x) != fold(name)]
    # a state/country/county is "broad" for planning: the UI warns and asks for a specific town
    return {"name": name, "context": ", ".join(ctx), "label": ", ".join([name, *ctx]), "lat": lat, "lon": lon, "broad": broad, "kind": kind,
            "_src": SOURCE_SHORT, "_group": group, "_state": fold(p.get("state") or ""), "_area": area or "", "_cc": (p.get("countrycode") or "").upper(), "_country": p.get("country") or ""}


def search(q: str, limit: int = 8) -> list[dict]:
    """Suggestions for a typed query (empty list on any failure: callers fall back to other sources)."""
    key = fold(q)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    if config.OFFLINE or not key:
        return []
    try:
        base.throttle("photon", 0.1)
        d = base.http_json("GET", config.PHOTON_URL, retries=0, timeout=5, headers=UA, params={"q": q.strip(), "limit": max(limit * 2, 10), "lang": "en"})
    except Exception:  # noqa: BLE001
        return []
    seen, out = set(), []
    for f in d.get("features", []) if isinstance(d, dict) else []:
        s = normalize(f)
        if not s:
            continue
        k = (fold(s["name"]), s["_state"], s["kind"])
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    if out:
        _cache[key] = (time.time(), out)
    return out


def resolve(query: str) -> dict | None:
    """Best match for a typed or picked place (town or specific spot) in the shape the planner expects.
    For a specific spot (a college, a station) the coordinates are the spot's own, but the planning name is the town around it,
    so attractions and hotels are searched in the right area."""
    want = key_words(query.split(",")[0])
    if not want:
        return None
    rows = search(query, 8)
    if "," in query:  # a long "name, town, state, country" string can confuse the search: also try just the name
        rows = rows + [r for r in search(query.split(",")[0], 8) if r not in rows]
    for s in rows:
        hay = fold(s["name"] + " " + s["context"])
        if not all(w in hay for w in want):
            continue
        poi = s["_group"] == "poi"
        town = s["_area"] if poi and s["_area"] else s["name"]
        display = s["label"]
        return {"broad": s["broad"], "name": town, "display": display, "lat": s["lat"], "lon": s["lon"], "country": s["_country"] or None, "country_code": s["_cc"],
                "kind": s["kind"] or "place", "spot": s["name"] if poi else None,
                "provenance": base.prov(SOURCE, "live", None, "OpenStreetMap data via Photon (ODbL)", 0.8)}
    return None
