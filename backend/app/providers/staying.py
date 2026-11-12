"""StayingAPI hotel search adapter. IMPORTANT: the configured key is a SANDBOX key (prefix stay_test_) that returns fixed
fixture listings regardless of the query (e.g. a Croatian apartment for 'New Delhi'). Sandbox results are therefore NEVER
used as real inventory: they are returned flagged `sandbox=True` / kind 'simulated' and filtered out of recommendations.
With a `stay_live_` key the same adapter returns kind 'live' listings. Search costs credits (min 5), so results are cached 12h."""
from .. import config
from . import base

BASE = "https://api.stayingapi.com/v1"
SOURCE = "StayingAPI (Booking.com)"


def is_sandbox() -> bool:
    return config.STAYING_KEY.startswith("stay_test_")


def available() -> bool:
    return bool(config.STAYING_KEY) and not config.OFFLINE


def account() -> dict | None:
    if not available():
        return None
    try:
        d = base.http_json("GET", f"{BASE}/account", retries=0, timeout=10, headers={"Authorization": "Bearer " + config.STAYING_KEY})["data"]
        return {"plan": d["plan"]["name"], "env": d["key"]["env"], "credits": d["credits"]["available"], "rpm": d["rateLimit"]["requestsPerMinute"]}
    except Exception:  # noqa: BLE001
        return None


def search(location: str, check_in: str, check_out: str, adults: int = 2, limit: int = 10) -> dict:
    if not config.STAYING_KEY:
        return {"hotels": [], "sandbox": False, "provenance": base.prov(SOURCE, "none", note="No Staying API key configured")}
    key = f"staying:{location}:{check_in}:{check_out}:{adults}:{limit}"

    def fetch():
        base.throttle("staying", 2.1)  # free plan: 30 requests/minute
        return base.http_json("GET", f"{BASE}/search", retries=0, timeout=40, headers={"Authorization": "Bearer " + config.STAYING_KEY},
                              params={"location": location, "checkIn": check_in, "checkOut": check_out, "platforms": "booking",
                                      "adults": adults, "currency": "INR", "limit": limit, "sort": "rating_desc"})

    raw, kind, at = base.cached_fetch(key, 12 * 3600, fetch)
    sandbox = is_sandbox()
    if raw is None:
        return {"hotels": [], "sandbox": sandbox, "provenance": base.prov(SOURCE, "none", note="Provider unavailable")}
    hotels = []
    for h in raw.get("data", []):
        loc, price = h.get("location") or {}, h.get("price") or {}
        hotels.append({"id": h.get("id"), "name": h.get("name"), "type": h.get("propertyType"), "lat": loc.get("lat"), "lon": loc.get("lng"),
                       "city": loc.get("city"), "country": loc.get("country"), "stars": h.get("starRating"), "guest_rating": h.get("guestRating"),
                       "rating_scale": h.get("ratingScale"), "reviews": h.get("reviewCount"), "amenities": h.get("amenities", []),
                       "nightly_price": price.get("nightlyPrice"), "total_price": price.get("totalPrice"), "currency": price.get("currency"),
                       "booking_url": price.get("url") or h.get("url")})
    note = ("SANDBOX key: fixed fixture data unrelated to the query. Not real inventory and excluded from recommendations."
            if sandbox else "Rates as returned by the provider at fetch time; confirm on the booking site.")
    return {"hotels": hotels, "sandbox": sandbox, "provenance": base.prov(SOURCE, "simulated" if sandbox else kind, at, note, 0.1 if sandbox else 0.85)}
