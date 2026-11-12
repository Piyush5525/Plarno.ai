"""Live trip guide: current conditions + forecast for the destination, recommendations drawn from the trip's own
catalogue, and smart tips. Design rule (same as the rest of the app): every number comes from a provider or from the
plan itself. The language model only *phrases* a short briefing from those facts; if it is unavailable the guide still
works from the deterministic tips."""
import hashlib
import math
from datetime import date, datetime, timedelta, timezone

from .. import config
from ..providers import base, gemini
from . import geo, live, safety, world

RAIN_POP = 0.55      # chance of rain from which a day counts as "likely wet"
HOT_C, COLD_C = 35, 5
OUTDOOR = ("park", "garden", "beach", "lake", "market", "fort", "monument", "viewpoint", "nature", "zoo", "bazaar", "ruins", "walk")
INDOOR = ("museum", "gallery", "mall", "aquarium", "cathedral", "church", "temple", "mosque", "palace", "theatre", "theater", "library")


def forecast(lat: float, lon: float) -> dict | None:
    """Daily forecast for the next ~5 days (OpenWeather 3-hourly feed grouped by LOCAL date) plus the place's UTC offset."""
    if not config.OPENWEATHER_KEY:
        return None
    d, kind = live._get(f"fc:{lat:.2f},{lon:.2f}", "https://api.openweathermap.org/data/2.5/forecast",
                        {"lat": lat, "lon": lon, "units": "metric", "appid": config.OPENWEATHER_KEY}, 1800)
    if not d or not d.get("list"):
        return None
    city = d.get("city") or {}
    off = int(city.get("timezone") or 0)
    tz = timezone(timedelta(seconds=off))
    days: dict[str, dict] = {}
    for x in d["list"]:
        t = datetime.fromtimestamp(x["dt"], tz)
        g = days.setdefault(t.date().isoformat(), {"date": t.date().isoformat(), "min_c": 99.0, "max_c": -99.0, "pop": 0.0, "slots": []})
        g["min_c"] = min(g["min_c"], x["main"]["temp_min"])
        g["max_c"] = max(g["max_c"], x["main"]["temp_max"])
        g["pop"] = max(g["pop"], float(x.get("pop") or 0))
        w = (x.get("weather") or [{}])[0]
        g["slots"].append((abs(t.hour - 13), w.get("main") or "", w.get("description") or "", t.hour, x["main"]["temp"]))
    out = []
    for g in list(days.values())[:6]:
        g["slots"].sort()
        _, main, desc, _, _ = g["slots"][0]  # the reading closest to early afternoon describes the day best
        out.append({"date": g["date"], "weekday": date.fromisoformat(g["date"]).strftime("%a"), "min_c": round(g["min_c"]), "max_c": round(g["max_c"]),
                    "pop": round(g["pop"], 2), "condition": main, "summary": desc})

    def hhmm(ts):
        return datetime.fromtimestamp(ts, tz).strftime("%H:%M") if ts else None
    return {"days": out, "utc_offset_min": off // 60, "sunrise": hhmm(city.get("sunrise")), "sunset": hhmm(city.get("sunset")),
            "provenance": {"source": "OpenWeather 5-day forecast", "kind": kind, "fetched_at": base.now_iso(), "confidence": 0.75,
                           "note": "Forecasts change; accuracy drops after 3 days."}}


def snapshot(lat: float, lon: float) -> dict:
    """Everything live about a point: weather now, air quality, forecast, local clock offset. Missing pieces are None, never guessed."""
    wx, aq, fc = live.weather(lat, lon), live.aqi(lat, lon), forecast(lat, lon)
    if aq:
        aq = {**aq, "band": safety.aqi_band(aq["value"])}
    return {"lat": lat, "lon": lon, "weather": wx, "aqi": aq, "forecast": fc,
            "utc_offset_min": fc["utc_offset_min"] if fc else None, "sunrise": fc["sunrise"] if fc else None, "sunset": fc["sunset"] if fc else None,
            "checked_at": base.now_iso()}


def _anchor(ctx, plan) -> tuple[float, float]:
    h = (plan.get("itinerary") or {}).get("hotel") or plan.get("hotel") or {}
    if h.get("lat") is not None and h.get("lon") is not None:
        return float(h["lat"]), float(h["lon"])
    g = ctx.dest_geo or {}
    if g.get("lat") is not None:
        return float(g["lat"]), float(g["lon"])
    return 28.6139, 77.2090


def _text(p: dict) -> str:
    return " ".join([p.get("name") or "", p.get("category") or "", p.get("description") or ""] + list(p.get("types") or []) + list(p.get("tags") or [])).lower()


def _is_demo(p: dict) -> bool:
    """True for rows from the built-in demo dataset (not a real listing), so the UI can label them."""
    return ((p.get("provenance") or {}).get("kind") == "simulated")


def _fmt_reviews(n) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n and n >= 1000 else str(n or 0)


def recommendations(ctx, plan, pool: list[dict], restaurants: list[dict], limit: int = 6) -> dict:
    """Places worth adding, ranked from the trip's own catalogue. Each one says WHY in plain facts."""
    anchor = _anchor(ctx, plan)
    chosen = set(ctx.selected_attraction_ids or []) | {s.get("id") for d in (plan.get("itinerary") or {}).get("days", []) for s in d["stops"]}
    want = {i: world.INTEREST_KEYS[i] for i in ctx.interests if i in world.INTEREST_KEYS}
    places = []
    for a in pool:
        if a.get("id") in chosen or a.get("lat") is None:
            continue
        txt, reviews, rating = _text(a), a.get("reviews") or 0, a.get("rating")
        km = geo.haversine_km(anchor, (a["lat"], a["lon"]))
        hit = next((i for i, words in want.items() if any(w in txt for w in words) or i in (a.get("tags") or [])), None)
        score = (rating or 3.8) / 5 * 2 + min(math.log10(max(reviews, 1)), 5.5) / 5.5 * 2.5 + (1.5 if hit else 0) + max(0, 1.5 - km / 8)
        why = []
        if rating:
            why.append(f"{rating}★" + (f" from {_fmt_reviews(reviews)} reviews" if reviews else ""))
        if hit:
            why.append(f"matches your interest in {'nature' if hit == 'garden' else 'sacred sites' if hit == 'religious' else hit}")
        why.append(f"{km:.1f} km from {'home' if ctx.stay_home else 'your hotel'}")
        places.append((score, {**{k: a.get(k) for k in ("id", "name", "lat", "lon", "rating", "reviews", "thumbnail", "category", "visit_min", "hours", "address", "maps_url")},
                               "types": (a.get("types") or [])[:3], "distance_km": round(km, 1), "why": why, "match": hit, "score": round(score, 2), "demo": _is_demo(a)}))
    places.sort(key=lambda x: -x[0])

    used = {s.get("id") for d in (plan.get("itinerary") or {}).get("days", []) for s in d["stops"] if s.get("type") == "meal"}
    food = []
    for r in restaurants:
        if r.get("id") in used or r.get("lat") is None:
            continue
        if ctx.vegan and r.get("vegan") is False or ctx.vegetarian and r.get("veg") is False:
            continue
        km = geo.haversine_km(anchor, (r["lat"], r["lon"]))
        rating, reviews = r.get("rating"), r.get("reviews") or 0
        score = (rating or 3.8) / 5 * 3 + min(math.log10(max(reviews, 1)), 4.5) / 4.5 * 1.5 + max(0, 2 - km / 3)
        why = ([f"{rating}★" + (f" from {_fmt_reviews(reviews)} reviews" if reviews else "")] if rating else []) + [f"{km:.1f} km from {'home' if ctx.stay_home else 'your hotel'}"]
        if r.get("price_level"):
            why.append(f"price level {r['price_level']}")
        food.append((score, {**{k: r.get(k) for k in ("id", "name", "lat", "lon", "rating", "reviews", "thumbnail", "category", "hours", "address", "maps_url", "price_for_two", "price_level")},
                             "types": (r.get("types") or [])[:3] or ([r["cuisine"]] if r.get("cuisine") else []), "distance_km": round(km, 1), "why": why, "score": round(score, 2), "demo": _is_demo(r)}))
    food.sort(key=lambda x: -x[0])
    return {"places": [p for _, p in places[:limit]], "food": [f for _, f in food[:limit]]}


def day_weather(plan: dict, fc: dict | None) -> dict:
    """Forecast row per itinerary day (only for days inside the forecast window)."""
    if not fc:
        return {}
    by = {d["date"]: d for d in fc["days"]}
    return {str(d["day"]): by[d["date"]] for d in (plan.get("itinerary") or {}).get("days", []) if d.get("date") in by}


def tips(ctx, plan, snap: dict, per_day: dict) -> list[dict]:
    """Deterministic, explainable advice. `ask` is a ready-made request for TRIP; `tab` opens a workspace section."""
    out: list[dict] = []
    it = plan.get("itinerary") or {}
    days = it.get("days", [])
    b = plan.get("budget") or {}

    def add(level, icon, title, text, ask=None, tab=None, label=None):
        out.append({"level": level, "icon": icon, "title": title, "text": text, "ask": ask, "tab": tab, "label": label})

    if b.get("within_budget") is False and b.get("remaining_inr") is not None:
        add("warn", "wallet", "Over budget", f"The plan is ₹{abs(b['remaining_inr']):,.0f} above your ₹{b.get('max_budget_inr', 0):,.0f} budget.", ask="Make it cheaper", label="Trim the cost")
    for d in days:
        w = per_day.get(str(d["day"]))
        if not w:
            continue
        names = [s["name"] for s in d["stops"] if s.get("type") == "attraction" and any(k in _text(s) for k in OUTDOOR) and not any(k in _text(s) for k in INDOOR)]
        if w["pop"] >= RAIN_POP:
            add("warn", "rain", f"Rain likely on day {d['day']}", f"{round(w['pop'] * 100)}% chance of rain on {w['weekday']} {w['date']}"
                + (f". Outdoor stops that day: {', '.join(names[:3])}." if names else ". Keep an umbrella handy."), tab="itinerary", label="Review that day")
        if w["max_c"] >= HOT_C:
            add("info", "heat", f"Hot afternoon on day {d['day']}", f"Up to {w['max_c']}°C. Do outdoor sights before 11:00 or after 16:00 and carry water.", tab="itinerary", label="See the schedule")
        if w["max_c"] <= COLD_C:
            add("info", "cold", f"Cold on day {d['day']}", f"High of only {w['max_c']}°C, low {w['min_c']}°C. Pack warm layers.")
    aq = snap.get("aqi")
    if aq and aq["value"] > 150:
        add("warn", "air", "Poor air quality right now", f"AQI {aq['value']} ({aq['band']}) at {aq.get('station') or 'the nearest station'}. Consider a mask outdoors and favour indoor sights.",
            tab="safety", label="Air quality details")
    for d in days:
        closed = [s["name"] for s in d["stops"] if s.get("hours_flag") == "closed"]
        if closed:
            add("warn", "clock", f"Closed on day {d['day']}", f"{', '.join(closed[:2])} {'is' if len(closed) == 1 else 'are'} listed as closed that day.",
                ask=f"Move {closed[0]} to a day when it is open", label="Fix it")
        early = [s["name"] for s in d["stops"] if s.get("hours_flag") == "closes_early"]
        if early:
            add("info", "clock", f"Tight timing on day {d['day']}", f"{early[0]} may close before your visit ends. Go earlier in the day.", tab="itinerary", label="Reorder stops")
        if d.get("travel_min", 0) >= 150:
            add("info", "route", f"Long travel on day {d['day']}", f"About {d['travel_min'] / 60:.1f} h on the road ({d.get('distance_km')} km). A relaxed pace or a closer hotel cuts this.",
                ask="Make the pace relaxed", label="Slow it down")
    if ctx.dates_assumed:
        add("info", "calendar", "Dates are assumed", "Hotel rates and the forecast depend on real dates. Tell TRIP when you are travelling.", ask=None, tab=None)
    if not ctx.origin and not ctx.stay_home:
        add("info", "plane", "Add where you start from", "Give your home town and TRIP compares flights, trains, buses and cabs door to door.", tab="travel", label="Travel options")
    h = plan.get("hotel") or {}
    if h.get("avg_km_to_attractions") and h["avg_km_to_attractions"] > 7 and h.get("id") != "home":
        add("info", "bed", "Your hotel is far from the sights", f"{h['name']} is {h['avg_km_to_attractions']} km on average from your stops.", tab="hotels", label="Compare hotels")
    if not out and days:
        add("good", "check", "This plan looks solid", "No weather, timing or budget problems found for the days we can see.")
    order = {"warn": 0, "info": 1, "good": 2}
    return sorted(out, key=lambda t: order[t["level"]])[:7]


PACK_WORDS = ("pack", "wear", "clothes", "clothing", "bring", "umbrella", "luggage", "suitcase")
MODEST = ("temple", "mosque", "church", "cathedral", "shrine", "basilica", "gurudwara", "masjid", "religious")


def is_packing_question(message: str) -> bool:
    t = message.lower()
    return any(w in t for w in PACK_WORDS) and "?" in t or t.strip().startswith(("what should i pack", "what to pack", "what should i wear", "what to wear"))


def packing(ctx, plan) -> str:
    """Packing advice worked out from the forecast, air quality and the stops in the plan (no language model involved)."""
    lat, lon = _anchor(ctx, plan)
    snap = snapshot(lat, lon)
    per = day_weather(plan, snap.get("forecast"))
    fc = (snap.get("forecast") or {}).get("days") or []
    rows = list(per.values()) or fc[:5]
    out = []
    if not rows:
        wx = snap.get("weather")
        out.append(f"I could not get a forecast for {ctx.destination} right now" + (f" (it is {round(wx['temp_c'])}°C and {wx['summary']} at the moment)" if wx else "") + ", so this is a general list.")
        lo = hi = round(wx["temp_c"]) if wx else None
        wet = []
    else:
        lo, hi = min(r["min_c"] for r in rows), max(r["max_c"] for r in rows)
        wet = [r for r in rows if r["pop"] >= RAIN_POP]
        scope = "your trip days" if per and len(per) == len((plan.get("itinerary") or {}).get("days", [])) else "the trip days inside the 5-day forecast" if per else "the next few days"
        out.append(f"**Packing for {ctx.destination}:** {lo}°C to {hi}°C over {scope} (OpenWeather forecast).")
        if not per:
            out.append("Your dates are beyond the forecast window, so this is the current outlook. Ask me again a few days before you leave.")
    if lo is not None:
        if lo <= 3:
            out.append("- A proper winter coat, gloves and a hat: it gets close to freezing.")
        elif lo <= 12:
            out.append("- Warm layers and a jacket for mornings and evenings.")
        if hi >= 30:
            out.append("- Light, breathable clothes, sunscreen, a hat and a refillable water bottle.")
        elif hi >= 22 and lo > 12:
            out.append("- Light clothes, plus one extra layer for the evening.")
    if wet:
        out.append("- An umbrella or rain jacket: rain is likely on " + ", ".join(f"{r['weekday']} {r['date'][8:]}/{r['date'][5:7]} ({round(r['pop'] * 100)}%)" for r in wet[:4]) + ".")
    aq = snap.get("aqi")
    if aq and aq["value"] > 150:
        out.append(f"- A well-fitting mask (N95 or similar): the air quality index is {aq['value']} ({aq['band']}) right now.")
    days = (plan.get("itinerary") or {}).get("days", [])
    km = max((d.get("distance_km") or 0 for d in days), default=0)
    out.append("- Comfortable walking shoes" + (f": your longest day covers about {km:.0f} km between stops." if km else "."))
    holy = [s["name"] for d in days for s in d["stops"] if s.get("type") == "attraction" and any(w in _text(s) for w in MODEST)]
    if holy:
        out.append(f"- Something that covers shoulders and knees for {holy[0]}" + (f" and {len(holy) - 1} other sacred site{'s' if len(holy) > 2 else ''}" if len(holy) > 1 else "") + ".")
    out.append("- Copies of your ID and bookings, a power bank, and a plug adapter if you are travelling abroad.")
    return "\n".join(out)


def briefing(ctx, plan, snap: dict, per_day: dict, tip_list: list[dict], recs: dict) -> dict | None:
    """Short AI summary phrased by the language model from the facts above. Cached per distinct fact set."""
    if not gemini.available():
        return None
    wx, aq = snap.get("weather"), snap.get("aqi")
    b = plan.get("budget") or {}
    facts = [f"Destination: {ctx.destination}. Days: {ctx.days}. Travellers: {ctx.travellers}. Interests: {', '.join(ctx.interests) or 'general sightseeing'}. Pace: {ctx.pace}."]
    if wx and wx.get("available"):
        facts.append(f"Weather now: {round(wx['temp_c'])}C, {wx['summary']}, feels like {round(wx['feels_like_c'])}C, humidity {wx.get('humidity')}%.")
    if aq:
        facts.append(f"Air quality index now: {aq['value']} ({aq['band']}).")
    for k, w in per_day.items():
        facts.append(f"Forecast day {k} ({w['date']}): {w['min_c']} to {w['max_c']}C, {w['summary']}, rain chance {round(w['pop'] * 100)}%.")
    for d in (plan.get("itinerary") or {}).get("days", [])[:7]:
        facts.append(f"Day {d['day']}: " + ", ".join(s["name"] for s in d["stops"] if s.get("type") == "attraction")[:220])
    if b.get("estimated_total_inr"):
        facts.append(f"Estimated total INR {round(b['estimated_total_inr'])}" + (f", budget INR {round(b['max_budget_inr'])}" if b.get("max_budget_inr") else "") + ".")
    facts += [f"Issue: {t['title']}: {t['text']}" for t in tip_list if t["level"] == "warn"]
    if recs["places"]:
        facts.append("Not in the plan yet but well rated nearby: " + ", ".join(p["name"] for p in recs["places"][:3]) + ".")
    blob = "\n".join(facts)
    key = "gemini:brief:" + hashlib.sha1(blob.encode()).hexdigest()
    system = ("You are TRIP, the travel assistant of Plarno.ai. Write a friendly briefing for this trip in 3 short sentences, plain text, no markdown, no lists. "
              "Say what to look forward to, the one thing to watch out for, and one concrete suggestion. Use ONLY the FACTS for any number, temperature, price or place name. "
              "Never promise safety or availability.")
    try:
        data, kind, at = base.cached_fetch(key, 6 * 3600, lambda: {"t": gemini._call(system, "FACTS:\n" + blob, False)})
    except Exception:  # noqa: BLE001
        return None
    text = (data or {}).get("t") if isinstance(data, dict) else None
    if not text:
        return None
    return {"text": " ".join(text.split())[:700], "provenance": {"source": f"Gemini ({gemini.MODEL}) summarising the live data on this page", "kind": "estimated", "fetched_at": at or "",
                                                               "confidence": 0.6, "note": "AI-written summary. Numbers come from the providers shown on this page."}}


def build(ctx, plan, pool: list[dict], restaurants: list[dict], with_ai: bool = True) -> dict:
    lat, lon = _anchor(ctx, plan)
    snap = snapshot(lat, lon)
    per_day = day_weather(plan, snap.get("forecast"))
    recs = recommendations(ctx, plan, pool, restaurants)
    tip_list = tips(ctx, plan, snap, per_day)
    return {"live": snap, "day_weather": per_day, "tips": tip_list, "recommendations": recs,
            "briefing": briefing(ctx, plan, snap, per_day, tip_list, recs) if with_ai else None,
            "place": {"name": ctx.destination, "country": (ctx.dest_geo or {}).get("country")}}
