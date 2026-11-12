"""As-you-type place suggestions. Two live sources are queried in parallel and merged:
  * Photon (OpenStreetMap): towns plus colleges, universities, stations, airports, hospitals and landmarks, built for typeahead.
  * Mapbox Geocoding: accurate towns and cities worldwide (autocomplete is permitted there, unlike public Nominatim).
Mapbox results are held only in a short in-memory cache (its 'temporary geocoding' terms: do not store results long-term).
Mapbox fuzzy-matches aggressively ("manipal" -> Mahipal, Fanipal), so its results are kept only when they actually contain what was typed."""
import time
from concurrent.futures import ThreadPoolExecutor

from .. import config
from . import base, photon

_cache: dict[str, tuple[float, list, str]] = {}
FALLBACK = ["Paris", "Tokyo", "Bali", "New York", "Dubai", "Rome", "Bangkok", "Goa", "London", "Singapore", "Istanbul", "Delhi", "Mumbai", "Bengaluru", "Lisbon", "Cape Town",
            "Barcelona", "Sydney", "Amsterdam", "Kyoto", "Jaipur", "Madrid", "Berlin", "Vienna", "Prague", "Seoul", "Hong Kong", "Los Angeles", "San Francisco", "Phuket"]
PUBLIC = ("name", "context", "label", "lat", "lon", "broad", "kind")


def _mapbox(q: str, limit: int) -> list[dict] | None:
    """None = the call failed; [] = it worked and found nothing."""
    if not config.MAPBOX_TOKEN or config.OFFLINE:
        return None
    try:
        base.throttle("mapbox-suggest", 0.05)
        d = base.http_json("GET", f"https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json", retries=0, timeout=6,
                           params={"access_token": config.MAPBOX_TOKEN, "autocomplete": "true", "types": "place,locality,region,district", "limit": limit, "language": "en"})
    except Exception:  # noqa: BLE001
        return None
    out = []
    for f in d.get("features", []):
        try:
            types = f.get("place_type", [])
            parts = [p.strip() for p in f["place_name"].split(",")]
            out.append({"name": f["text"], "context": ", ".join(parts[1:]) if len(parts) > 1 else "", "label": f["place_name"], "lon": f["center"][0], "lat": f["center"][1],
                        "broad": "place" not in types and "locality" not in types, "kind": "", "_src": "Mapbox", "_group": "place", "_state": photon.fold(parts[1]) if len(parts) > 2 else ""})
        except (KeyError, IndexError, TypeError):
            continue
    return out


def _relevant(label: str, q: str) -> bool:
    """Every word typed appears in the label (a partial word such as 'kisha' counts, and so does an acronym such as 'iit')."""
    return photon.covers(label, q)


def merge(q: str, photon_rows: list[dict], mapbox_rows: list[dict] | None, limit: int) -> tuple[list[dict], list[str]]:
    """Towns first (Mapbox, then Photon), then specific spots (colleges, stations...). Unrelated Mapbox fuzzy matches are dropped unless nothing else was found."""
    mb = mapbox_rows or []
    pool = mb + photon_rows
    if any(_relevant(r["label"], q) for r in pool):
        # something really matches what was typed: show only such results (no Bombay Beach, California above IIT Bombay)
        mb, photon_rows = [r for r in mb if _relevant(r["label"], q)], [r for r in photon_rows if _relevant(r["label"], q)]
    elif photon_rows:
        mb = []  # typo tolerance: nothing matches exactly, so show the OpenStreetMap search's closest guesses, not Mapbox's looser ones
    keep = mb
    seen, places, spots = set(), [], []
    for r in keep + photon_rows:
        if r["kind"] == "hospital" and "hosp" not in q.lower() and "clinic" not in q.lower():
            continue  # hospitals are rarely what a traveller means, and a hospital chain's branches would crowd out colleges
        k = (photon.fold(r["name"]), r.get("_state", ""), r["kind"])
        if k in seen:
            continue
        seen.add(k)
        (places if r["_group"] == "place" else spots).append(r)
    top = photon.fold(places[0]["name"]) if places else ""
    # exact-word matches first; specific spots inside the best-matching town (MIT Manipal for "manipal") before namesakes elsewhere
    places.sort(key=lambda r: not _relevant(r["label"], q))
    spots.sort(key=lambda r: (not _relevant(r["label"], q), not (top and top in photon.fold(r["context"]))))
    ranked = places + spots
    # keep a good spread: do not let towns crowd out the colleges that were asked for (or the reverse)
    if len(ranked) > limit and spots and places:
        n_spots = min(len(spots), max(2, limit // 2))
        ranked = places[: limit - n_spots] + spots[:n_spots]
        ranked.sort(key=lambda r: 0 if r["_group"] == "place" else 1)
    ranked = ranked[:limit]
    return [{k: r[k] for k in PUBLIC} for r in ranked], list(dict.fromkeys(r["_src"] for r in ranked))


def suggest(q: str, limit: int = 8) -> dict:
    q = q.strip()
    if len(q) < 2:
        return {"suggestions": [], "source": "none"}
    key = f"{q.lower()}|{limit}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return {"suggestions": hit[1], "source": hit[2] + " (cached briefly)"}
    if not config.OFFLINE:
        with ThreadPoolExecutor(max_workers=2) as ex:  # both services at once: the slower one sets the latency, not the sum
            fp, fm = ex.submit(photon.search, q, limit), ex.submit(_mapbox, q, limit)
            p_rows, m_rows = fp.result(), fm.result()
        words = photon.fold(q).split()
        if not p_rows and len(words) > 1:  # "mit manipal": nothing for the whole phrase, so look up its most distinctive word
            p_rows = photon.search(max(words, key=len), limit)
        words = photon.fold(q).split()
        if not p_rows and len(words) > 1:  # "mit manipal": nothing for the whole phrase, so look up its most distinctive word
            p_rows = photon.search(max(words, key=len), limit)
        if p_rows or m_rows:
            out, srcs = merge(q, p_rows, m_rows, limit)
            if out:
                src = " + ".join(srcs)
                _cache[key] = (time.time(), out, src)
                return {"suggestions": out, "source": src}
    out = [{"name": c, "context": "", "label": c, "lat": None, "lon": None, "broad": False, "kind": ""} for c in FALLBACK if c.lower().startswith(q.lower()) or q.lower() in c.lower()][:limit]
    return {"suggestions": out, "source": "built-in list (live search unavailable)"}
