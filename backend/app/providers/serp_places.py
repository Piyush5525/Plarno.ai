"""Real places and hotels anywhere in the world via SerpApi (engines google_maps and google_hotels).
Every result carries Google-Maps coordinates, rating/review counts, hours text, photos and (for hotels) real nightly rates + booking links.
Quota safety: results cached 30 days (places) / 12 h (hotels); a shared daily cap protects the SerpApi free plan (250 searches/month)."""
from .. import config
from . import base

SOURCE_PLACES = "Google Maps via SerpApi"
SOURCE_HOTELS = "Google Hotels via SerpApi"
SEARCH = "https://serpapi.com/search.json"

VISIT_MIN = {"museum": 120, "park": 75, "religious": 60, "market": 90, "attraction": 90, "historical": 90, "restaurant": 75}
CATEGORY_WORDS = {
    "museum": ("museum", "gallery"), "park": ("park", "garden", "nature", "beach", "lake", "trail", "zoo", "botanical"),
    "religious": ("temple", "church", "cathedral", "mosque", "shrine", "monastery", "synagogue", "basilica", "gurdwara"),
    "market": ("market", "bazaar", "shopping", "mall", "souk"),
    "historical": ("historical", "monument", "castle", "fort", "palace", "landmark", "ruins", "memorial", "tomb", "heritage", "archaeological", "tower", "bridge"),
}
QUERIES = {"history": "historical landmarks and monuments in {c}", "museum": "best museums in {c}", "religious": "most famous religious landmarks and places of worship in {c}",
           "garden": "best parks and gardens in {c}", "shopping": "famous markets and shopping areas in {c}", "food": "famous food markets and street food in {c}"}
PRICE_LEVEL_INR = {"$": 500, "$$": 1400, "$$$": 3500, "$$$$": 7500}  # ESTIMATE per two people; Google exposes only a price level


def available() -> bool:
    return bool(config.SERP_KEY) and not config.OFFLINE


def _quota_ok() -> bool:
    return base.quota_ok("serpapi", config.SERP_DAILY_CAP)


def _category(types: list[str]) -> str:
    t = " ".join(types).lower()
    for cat, words in CATEGORY_WORDS.items():
        if any(w in t for w in words):
            return cat
    return "attraction"


def _norm_place(r: dict, kind: str) -> dict | None:
    g = r.get("gps_coordinates") or {}
    if g.get("latitude") is None or not r.get("title"):
        return None
    types = r.get("types") or ([r["type"]] if r.get("type") else [])
    cat = "restaurant" if kind == "restaurants" else _category(types + [r.get("description") or ""])
    out = {"id": "g-" + (r.get("place_id") or r.get("data_id") or r["title"]), "name": r["title"], "lat": g["latitude"], "lon": g["longitude"], "category": cat,
           "types": types, "tags": sorted({w for w in sum(CATEGORY_WORDS.values(), ()) if w in " ".join(types).lower()}) + ([cat] if cat != "attraction" else []),
           "address": r.get("address"), "area": (r.get("address") or "").split(",")[-2].strip() if (r.get("address") or "").count(",") >= 1 else None,
           "rating": r.get("rating"), "reviews": r.get("reviews"), "hours": r.get("open_state") or r.get("hours"), "phone": r.get("phone"),
           "website": r.get("website"), "thumbnail": r.get("thumbnail"), "operating_hours": r.get("operating_hours") if isinstance(r.get("operating_hours"), dict) else None, "description": r.get("description"),
           "fee_inr": None, "fee_note": "Ticket price not provided: check the official site", "visit_min": VISIT_MIN.get(cat, 90),
           "visit_min_note": "estimate by category", "accessibility": "see official site",
           "maps_url": f"https://www.google.com/maps/place/?q=place_id:{r['place_id']}" if r.get("place_id") else None}
    if kind == "restaurants":
        lvl = r.get("price")
        out.update({"cuisine": (types[0] if types else "Restaurant"), "price_level": lvl, "price_for_two": PRICE_LEVEL_INR.get(lvl) if lvl else None,
                    "price_note": "Estimate from Google price level" if lvl else "Price not provided", "veg": any("vegetarian" in x.lower() or "vegan" in x.lower() for x in types),
                    "vegan": any("vegan" in x.lower() for x in types), "kind": "restaurant"})
    return out


def places(kind: str, city: str, lat: float, lon: float, interest: str | None = None) -> dict:
    """kind: attractions | restaurants. Returns {places:[...], provenance, error?}."""
    if kind == "restaurants":
        q = f"best restaurants in {city}"
    elif interest in QUERIES:
        q = QUERIES[interest].format(c=city)
    else:
        q = f"top tourist attractions in {city}"
    key = f"serpplaces:{q.lower()}:{lat:.2f},{lon:.2f}"
    params = {"engine": "google_maps", "type": "search", "q": q, "ll": f"@{lat:.5f},{lon:.5f},12z", "hl": "en", "api_key": config.SERP_KEY}

    def fetch():
        if not _quota_ok():
            raise base.QuotaGuard("daily SerpApi guard reached")
        base.quota_use("serpapi")
        d = base.http_json("GET", SEARCH, retries=0, timeout=40, params=params)
        if d.get("error") and "hasn't returned any results" not in str(d["error"]):
            raise RuntimeError(str(d["error"])[:120])
        return d.get("local_results", [])

    raw, kindc, at = base.cached_fetch(key, 30 * 86400, fetch)
    if raw is None:
        msg = "Daily search limit reached ({} searches/day, set to protect the SerpApi plan). Cached cities still work; try again tomorrow or raise PLARNO_SERP_DAILY_CAP.".format(config.SERP_DAILY_CAP) if kindc == "quota" else "The places provider is not responding right now. Please try again in a minute."
        return {"places": [], "provenance": base.prov(SOURCE_PLACES, "none", note="provider unavailable"), "error": msg}
    out = [p for p in (_norm_place(r, kind) for r in raw) if p]
    out.sort(key=lambda p: -((p.get("rating") or 0) * (min(p.get("reviews") or 0, 50000) ** 0.5)))
    return {"places": out, "provenance": base.prov(SOURCE_PLACES, kindc, at, "Coordinates, ratings and hours as listed on Google Maps at fetch time.", 0.9)}


def hotels(city: str, check_in: str, check_out: str, adults: int = 2, currency: str = "INR") -> dict:
    key = f"serphotels:{city.lower()}:{check_in}:{check_out}:{adults}:{currency}"
    params = {"engine": "google_hotels", "q": f"hotels in {city}", "check_in_date": check_in, "check_out_date": check_out, "adults": adults,
              "currency": currency, "hl": "en", "api_key": config.SERP_KEY}

    def fetch():
        if not _quota_ok():
            raise base.QuotaGuard("daily SerpApi guard reached")
        base.quota_use("serpapi")
        d = base.http_json("GET", SEARCH, retries=0, timeout=45, params=params)
        if d.get("error"):
            raise RuntimeError(str(d["error"])[:120])
        return d.get("properties", [])

    raw, kindc, at = base.cached_fetch(key, 12 * 3600, fetch)
    if raw is None:
        msg = "Daily search limit reached ({} searches/day, set to protect the SerpApi plan). Cached cities still work; try again tomorrow or raise PLARNO_SERP_DAILY_CAP.".format(config.SERP_DAILY_CAP) if kindc == "quota" else "The hotel provider is not responding right now. Please try again in a minute."
        return {"hotels": [], "provenance": base.prov(SOURCE_HOTELS, "none", note="provider unavailable"), "error": msg}
    out = []
    for h in raw:
        g, rate = h.get("gps_coordinates") or {}, (h.get("rate_per_night") or {}).get("extracted_lowest")
        if g.get("latitude") is None or rate is None:
            continue
        transit = [n for n in h.get("nearby_places", []) if any(t.get("type") in ("Walking", "Public transport", "Taxi") and _minutes(t.get("duration")) <= 12 for t in n.get("transportations", []))
                   and any(w in n.get("name", "").lower() for w in ("station", "metro", "subway", "gare", "bahn", "stop", "airport", "tube", "rail"))]
        out.append({"id": "h-" + (h.get("property_token") or h["name"])[:24], "name": h["name"], "lat": g["latitude"], "lon": g["longitude"], "type": h.get("type", "hotel"),
                    "stars": _stars(h.get("hotel_class")), "rating": h.get("overall_rating"), "reviews": h.get("reviews"), "location_rating": h.get("location_rating"),
                    "nightly": rate, "total": (h.get("total_rate") or {}).get("extracted_lowest"), "currency": currency, "amenities": h.get("amenities", [])[:8],
                    "images": [i.get("thumbnail") for i in h.get("images", [])[:3] if i.get("thumbnail")], "booking_url": h.get("link"),
                    "check_in_time": h.get("check_in_time"), "check_out_time": h.get("check_out_time"), "transit_nearby": [n["name"] for n in transit][:3],
                    "nearby": [n.get("name") for n in h.get("nearby_places", [])[:4]]})
    return {"hotels": out, "provenance": base.prov(SOURCE_HOTELS, kindc, at, "Nightly rate as shown at fetch time for the searched dates; confirm on the booking site.", 0.9)}


def _minutes(s: str | None) -> int:
    try:
        return int("".join(c for c in (s or "") if c.isdigit()) or 99)
    except ValueError:
        return 99


def _stars(c) -> int | None:
    try:
        return int(str(c)[0]) if c else None
    except ValueError:
        return None
