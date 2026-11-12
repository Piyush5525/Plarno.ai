"""Worldwide trip data: catalog assembly from live providers, honest hotel ranking, and destination safety context.
Everything here is derived from provider data (Google Maps/Hotels via SerpApi, OpenStreetMap geocoding, AQICN/OpenWeather).
Factors for which a provider returned no data are EXCLUDED from scoring (weights renormalised) and reported as 'no data', never guessed."""
import math
from datetime import date, timedelta

from ..providers import serp_places
from ..services import geo, live

INTEREST_KEYS = {"history": ["historical", "monument", "castle", "fort", "palace", "landmark", "ruins", "heritage", "tower", "memorial", "tomb"],
                 "museum": ["museum", "gallery"], "religious": ["religious", "cathedral", "church", "temple", "mosque", "shrine", "basilica"],
                 "shopping": ["market", "shopping", "bazaar", "mall"], "garden": ["park", "garden", "nature", "beach", "lake", "botanical"]}
DEFAULT_WEIGHTS = {"attractions": 0.30, "hotel_quality": 0.25, "price": 0.25, "transit": 0.20}

EMERGENCY = {  # static reference list (well-known national numbers). Always verify locally before relying on it.
    "IN": {"All emergencies": "112", "Police": "100", "Ambulance": "102"}, "US": {"All emergencies": "911"}, "CA": {"All emergencies": "911"}, "MX": {"All emergencies": "911"},
    "GB": {"All emergencies": "999 (112 also works)"}, "IE": {"All emergencies": "112 or 999"}, "AU": {"All emergencies": "000"}, "NZ": {"All emergencies": "111"},
    "JP": {"Police": "110", "Fire/Ambulance": "119"}, "CN": {"Police": "110", "Ambulance": "120"}, "AE": {"Police": "999", "Ambulance": "998"}, "SG": {"Police": "999", "Ambulance": "995"},
    "TH": {"Police": "191", "Ambulance": "1669", "Tourist police": "1155"}, "ZA": {"Police": "10111", "Ambulance": "10177"}, "BR": {"Police": "190", "Ambulance": "192"},
    "TR": {"All emergencies": "112"}, "EG": {"Police": "122", "Ambulance": "123"}, "KR": {"Police": "112", "Fire/Ambulance": "119"},
    **{c: {"All emergencies": "112"} for c in ("FR", "DE", "IT", "ES", "PT", "NL", "BE", "AT", "CH", "CZ", "HU", "PL", "GR", "DK", "SE", "NO", "FI", "IS", "RO", "BG", "HR", "SK", "SI", "LT", "LV", "EE", "LU", "MT", "CY")}}


def dates_for(start: str, days: int) -> tuple[str, str]:
    s = date.fromisoformat(start)
    return s.isoformat(), (s + timedelta(days=max(1, days - 1))).isoformat()


def build_catalog(geo_info: dict, interests: list[str], check_in: str, check_out: str, adults: int, need_hotels: bool = True, want_places: int = 8) -> dict:
    """Fetch attractions (general + up to 2 interest-specific queries), restaurants and hotels. <=5 provider searches, all cached."""
    city, lat, lon = geo_info["name"], geo_info["lat"], geo_info["lon"]
    notes, seen, attractions = [], set(), []
    queries = [None] + [i for i in interests if i in serp_places.QUERIES and i != "food"][:2]
    prov = None
    for q in queries:
        r = serp_places.places("attractions", city, lat, lon, q)
        prov = prov or r["provenance"]
        if r.get("error"):
            notes.append(r["error"])
        for p in r["places"]:
            if p["id"] not in seen and geo.haversine_km((lat, lon), (p["lat"], p["lon"])) < 200:  # keep a wide net; narrowed below by radius
                seen.add(p["id"])
                attractions.append(p)
    rest = serp_places.places("restaurants", city, lat, lon)
    if rest.get("error"):
        notes.append(rest["error"])
    hot = serp_places.hotels(city, check_in, check_out, min(adults, 2)) if need_hotels else {"hotels": [], "provenance": {"source": "not requested", "kind": "none"}}
    if hot.get("error"):
        notes.append(hot["error"])
    # small towns have few listings nearby: widen the search radius step by step instead of returning almost nothing
    radius = 60
    for radius in (60, 120, 200):
        attr_near = [a for a in attractions if geo.haversine_km((lat, lon), (a["lat"], a["lon"])) < radius]
        if len(attr_near) >= want_places:
            break
    if radius > 60:
        notes.append(f"Few places were listed within 60 km of {city}, so the search area was widened to {radius} km.")
    near = lambda p: geo.haversine_km((lat, lon), (p["lat"], p["lon"])) < radius  # noqa: E731
    return {"geo": geo_info, "radius_km": radius, "attractions": [a for a in attractions if near(a)], "restaurants": [r for r in rest["places"] if near(r)], "hotels": [h for h in hot["hotels"] if near(h)],
            "provenance": {"attractions": prov, "restaurants": rest["provenance"], "hotels": hot["provenance"]}, "notes": notes}


def select_attractions(attractions: list[dict], interests: list[str], count: int, avoid_crowded: bool = False) -> list[dict]:
    want = [w for i in interests if i in INTEREST_KEYS for w in INTEREST_KEYS[i]]
    scored = []
    for a in attractions:
        txt = " ".join(a["types"] + [a.get("description") or ""]).lower()
        matches = min(sum(1 for w in want if w in txt), 2)  # capped: matching many keywords must not beat being a genuine headline sight
        reviews = a.get("reviews") or 0
        s = matches * 1.5 + (a.get("rating") or 3.5) / 5 * 1.5 + min(math.log10(max(reviews, 1)), 5.5) / 5.5 * 3.5
        if reviews < 1500:
            s -= 1.5  # statues, plaques and minor spots with few visitors rarely make a good itinerary slot
        if any(t in txt for t in ("statue", "monument aux", "plaque", "fountain")) and reviews < 20000:
            s -= 1.0
        if avoid_crowded and reviews > 60000:
            s -= 2
        scored.append((s, a))
    scored.sort(key=lambda x: -x[0])
    return [a for _, a in scored[:count]]


def rank_hotels(hotels: list[dict], attractions: list[dict], nights: int, budget_per_night: float | None, travellers: int, weights: dict | None = None) -> list[dict]:
    if not hotels:
        return []
    rooms = max(1, -(-travellers // 2))
    pts = [(a["lat"], a["lon"]) for a in attractions] or [(h["lat"], h["lon"]) for h in hotels]
    cen = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    w = {**DEFAULT_WEIGHTS, **{k: v for k, v in (weights or {}).items() if k in DEFAULT_WEIGHTS}}
    out = []
    for h in hotels:
        km = sum(geo.haversine_km((h["lat"], h["lon"]), p) for p in pts) / len(pts)
        night = h["nightly"] * rooms
        f = {"attractions": (max(0, 1 - km / 12), f"avg {km:.1f} km to your selected attractions", "estimated"),
             "hotel_quality": ((h["rating"] / 5) * 0.8 + min(math.log10(max(h.get("reviews") or 1, 1)), 4) / 4 * 0.2 if h.get("rating") else None, f"guest rating {h.get('rating')} from {h.get('reviews')} reviews" if h.get("rating") else "no rating", "live"),
             "price": ((1.0 if not budget_per_night else max(0, min(1, 1.6 - night / budget_per_night))), f"₹{night:,.0f}/night vs cap " + (f"₹{budget_per_night:,.0f}" if budget_per_night else "none"), "live"),
             "transit": (min(1, len(h["transit_nearby"]) / 2) if h.get("transit_nearby") else None, ("near " + ", ".join(h["transit_nearby"])) if h.get("transit_nearby") else "no station listed nearby", "live")}
        avail = {k: v for k, v in f.items() if v[0] is not None and w.get(k, 0) > 0}
        tw = sum(w[k] for k in avail) or 1
        score = sum(avail[k][0] * w[k] for k in avail) / tw * 100
        over = bool(budget_per_night and night > budget_per_night)
        out.append({**h, "id": h["id"], "price_per_night": night, "rooms": rooms, "total_price": night * nights, "over_budget": over,
                    "score": round(max(0, score - (15 if over else 0)), 1), "avg_km_to_attractions": round(km, 1), "neighbourhood": (h["nearby"][0] if h["nearby"] else "city"),
                    "interiors": None, "base_price": h["nightly"], "provenance": {"source": "Google Hotels via SerpApi", "kind": "live", "fetched_at": "", "note": "rate for searched dates"},
                    "explanation": {"neighbourhood": h["name"], "score": round(score, 1), "avg_km_to_attractions": round(km, 1),
                                    "factors": [{"factor": k, "subscore": round(v[0], 2) if v[0] is not None else 0, "weight": round(w[k] / tw, 3) if k in avail else 0,
                                                 "detail": v[1], "data_kind": v[2] if v[0] is not None else "no data"} for k, v in f.items()],
                                    "disclaimer": "Scores use only provider data. Noise, safety and industrial-proximity data are not available for this city, so they are not scored."}})
    return sorted(out, key=lambda r: -r["score"])


def safety_context(geo_info: dict) -> dict:
    cc = geo_info.get("country_code") or ""
    la, wx = live.aqi(geo_info["lat"], geo_info["lon"]), live.weather(geo_info["lat"], geo_info["lon"])
    from . import safety as _s
    return {"city": geo_info["name"], "country": geo_info.get("country"),
            "advisory": {"text": "Check your government's official travel advisory for this destination before you travel. Plarno.ai has no live advisory feed connected.",
                         "tips": ["Keep digital and paper copies of your passport and bookings.", "Use licensed taxis or ride-hailing apps.", "Check entry/visa and health requirements early.",
                                  "Share your itinerary with someone you trust."], "provenance": {"source": "static guidance", "kind": "simulated", "fetched_at": "", "note": "No live advisory feed"}},
            "emergency_contacts": EMERGENCY.get(cc, {"Emergency numbers": "Differ by country: look up the local number before you travel (112 works in many countries)"}),
            "emergency_note": "Static reference of well-known national numbers; verify locally." if cc in EMERGENCY else "No stored numbers for this country.",
            "neighbourhood_report": {"neighbourhood": geo_info["name"], "environment": {
                "aqi": ({"value": la["value"], "band": _s.aqi_band(la["value"]), "station": la["station"], "provenance": la["provenance"]} if la else None)},
                "safety": None},
            "weather": wx or {"available": False, "note": "Weather unavailable (provider offline or no coverage)."},
            "disclaimer": "Plarno.ai cannot guarantee any place, route or hotel is safe."}
