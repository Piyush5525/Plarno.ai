"""Google Flights via SerpApi (engine=google_flights). Search-only: results carry a Google Flights link; booking happens on the
airline/OTA site. Protected by a persistent cache (6h) and a daily call guard because the SerpApi free plan is quota-limited.
Only user-initiated searches call this; it is never invoked on page render."""
from .. import config
from . import base

from ..data.airports import iata

SOURCE = "Google Flights via SerpApi"


def available() -> bool:
    return bool(config.SERP_FLIGHTS_KEY) and not config.OFFLINE


def search(origin: str, dest: str, date: str, adults: int = 1) -> dict:
    """Returns {itineraries:[...], provenance, error?}. Each itinerary: legs[], total_duration_min, price_inr (per adult as returned by Google), link."""
    o, d_ = iata(origin), iata(dest)
    if not o or not d_ or o == d_:
        return {"itineraries": [], "error": "No airport mapping for this city pair", "provenance": base.prov(SOURCE, "none")}
    key = f"serpflights:{o}-{d_}:{date}:{adults}"
    params = {"engine": "google_flights", "departure_id": o, "arrival_id": d_, "outbound_date": date, "type": "2",
              "currency": "INR", "hl": "en", "gl": "in", "adults": adults, "api_key": config.SERP_FLIGHTS_KEY}

    def fetch():
        if not base.quota_ok("serpapi", config.SERP_DAILY_CAP):
            raise base.QuotaGuard("daily flight-search guard reached")
        base.quota_use("serpapi")
        d = base.http_json("GET", "https://serpapi.com/search.json", retries=0, timeout=30, params=params)
        if d.get("error"):
            return {"error": str(d["error"])[:200], "best_flights": [], "other_flights": []}
        return {"best_flights": d.get("best_flights", []), "other_flights": d.get("other_flights", []),
                "link": d.get("search_metadata", {}).get("google_flights_url")}

    raw, kind, at = base.cached_fetch(key, 6 * 3600, fetch)
    if raw is None:
        msg = "Daily search limit reached ({} searches/day, set to protect the SerpApi plan). Cached cities still work; try again tomorrow or raise PLARNO_SERP_DAILY_CAP.".format(config.SERP_DAILY_CAP) if kind == "quota" else "The flight provider is not responding right now."
        return {"itineraries": [], "error": msg, "provenance": base.prov(SOURCE, "none")}
    if raw.get("error"):
        return {"itineraries": [], "error": raw["error"], "provenance": base.prov(SOURCE, kind, at)}
    out = []
    for it in (raw["best_flights"] + raw["other_flights"])[:6]:
        segs = it.get("flights") or []
        if not segs or it.get("price") is None:
            continue
        out.append({
            "legs": [{"airline": s.get("airline"), "flight_number": s.get("flight_number"),
                      "from": s.get("departure_airport", {}).get("id"), "to": s.get("arrival_airport", {}).get("id"),
                      "depart": (s.get("departure_airport", {}).get("time") or "").replace(" ", "T"),
                      "arrive": (s.get("arrival_airport", {}).get("time") or "").replace(" ", "T"), "duration_min": s.get("duration")} for s in segs],
            "total_duration_min": it.get("total_duration"), "price_inr": it["price"], "stops": max(0, len(segs) - 1),
            "layovers": [l.get("name") for l in it.get("layovers", [])] if it.get("layovers") else [],
        })
    return {"itineraries": out, "link": raw.get("link"), "provenance": base.prov(SOURCE, kind, at, "Fare as shown by Google Flights at fetch time; may change before booking.", 0.9)}
