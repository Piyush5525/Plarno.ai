"""TRIP tool intents: each maps a natural-language request to a real application function and formats its result.
Every reply is built from service output (not generated), so numbers always match what the UI shows."""
import re

from ..providers import overpass
from ..services import catalog, geo, live, safety

CENTER = (28.6139, 77.2090)
TOOL_INTENTS = {"hotels_filter", "places_nearby", "restaurants_near", "route_best", "weather_aqi", "transport_options"}


def classify(text: str) -> dict | None:
    t = text.lower().replace(",", "")
    question = t.strip().endswith("?") or re.match(r"\s*(what|how|which|is|are|can|do|does|should|will|would|could)\b", t)
    if not question and re.search(r"\b(switch|change|use|choose|take|go with|pick|select|book)\b", t) and re.search(r"cheapest|fastest|comfortable|convenient|cab|taxi|train|bus|flight|travel option|route option", t):
        return None  # an instruction to change the travel choice, handled by the planner (not a question)
    m = re.search(r"hotels?.{0,25}?(?:under|below|within|less than|upto|up to|max(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(k)?", t)
    if m:
        return {"intent": "hotels_filter", "max": float(m.group(1)) * (1000 if m.group(2) else 1)}
    if re.search(r"restaurants?|places to eat|where to eat|food", t) and re.search(r"around|near|close to|nearby", t):
        return {"intent": "restaurants_near"}
    if re.search(r"(historical|history|attractions?|monuments?|museums?|places).{0,30}(nearby|near me|near|around)", t):
        return {"intent": "places_nearby"}
    if re.search(r"(ways?|options?|modes?|choices)\s+(of\s+|to\s+|for\s+)?(travel|transport|get|reach|go)|how (do|can|should|will) (i|we) (get|reach|travel|go)|cheapest (way|option|mode|flight|travel)|fastest (way|option|mode|travel)|most (comfortable|convenient) (way|option|mode|travel)|cab (charge|fare|cost|price)|taxi (charge|fare|cost)|(fare|cost|price) (of|for) (the )?(flight|cab|train|bus|travel|ticket)|how much.{0,30}(travel|get there|flight|cab|fare|train|bus)|(by|via) (cab|taxi|train|bus|flight)\b.{0,20}(cost|price|fare|how much)|within (my )?budget.{0,25}(travel|transport|get)", t):
        return {"intent": "transport_options"}
    if re.search(r"best route|optimi[sz]e.{0,15}route|route for (these|the|my)", t):
        return {"intent": "route_best"}
    if re.search(r"weather|pollution|\baqi\b|air quality|temperature", t):
        return {"intent": "weather_aqi"}
    return None


def _anchor(plan: dict, ctx=None) -> tuple[float, float]:
    h = plan.get("hotel")
    if h:
        return (h["lat"], h["lon"])
    if ctx is not None and ctx.dest_geo:
        return (ctx.dest_geo["lat"], ctx.dest_geo["lon"])
    return CENTER


def _dur(m: int) -> str:
    return f"{m // 60}h{m % 60:02d}"


def cab_reply(plan: dict, ctx) -> tuple[str, dict | None]:
    """Cab charges: transfers in the chosen journey, a direct cab option if sensible, and local cabs around the destination."""
    lines = ["Cab charges (all estimates: about ₹14/km, ₹300 minimum per cab, seats 4, plus ~8-10% tolls/parking; no live cab pricing is connected, so confirm with the driver or app):"]
    j, ro = plan.get("journey"), plan.get("route_options")
    for leg in (j or {}).get("legs", []):
        if leg["mode"] == "cab":
            lines.append(f"- {leg['from']} → {leg['to']}: ₹{leg['fare_inr'] + leg['extra_charges_inr']:,} for the cab, {leg['distance_km']} km, about {leg['duration_min']} min")
    direct = next((o for o in (ro or {}).get("options", []) if o["modes"] == ["cab"]), None)
    if direct:
        lines.append(f"- Direct cab {ctx.origin} → {ctx.destination}: ₹{direct['total_fare_inr']:,} one way (₹{direct['round_trip_inr']:,} round trip), about {_dur(direct['total_duration_min'])}")
    elif ro and ro.get("options"):
        lines.append(f"- A direct cab from {ctx.origin} to {ctx.destination} is not offered: it is too far for a sensible road trip.")
    it = plan.get("itinerary")
    if it:
        km = sum(d["distance_km"] for d in it["days"])
        lines.append(f"- Getting around {ctx.destination}: about {km:.0f} km over the trip ≈ ₹{km * 14:,.0f} by cab. " + "; ".join(f"Day {d['day']}: {d['distance_km']} km ≈ ₹{d['distance_km'] * 14:,.0f}" for d in it["days"][:6]))
    return ("\n".join(lines), {"to": "/workspace?tab=budget"})


def transport_reply(plan: dict, ctx, text: str = "") -> tuple[str, dict | None]:
    if re.search(r"\b(cab|taxi)\b", text.lower()) and re.search(r"charge|fare|cost|price|how much", text.lower()):
        return cab_reply(plan, ctx)
    ro = plan.get("route_options")
    if not ro or not ro.get("options"):
        j = plan.get("journey")
        if j:
            return (f"Your planned journey is {j['summary']}: ₹{j['total_fare_inr']:,} one way, about {_dur(j['total_duration_min'])}. These are demo/estimated figures.", {"to": "/workspace?tab=travel"})
        if ctx.stay_home:
            return ("This is a day-trips-from-home plan, so there's no long-distance travel. Local cab fares for each outing are shown in the itinerary (about ₹14/km, an estimate).", {"to": "/workspace?tab=itinerary"})
        return ("I don't have travel options yet. Tell me where you are travelling from (any city or town) and I'll compare flights, cabs, buses and trains door to door.", None)
    opts, lab = ro["options"], ro["labels"]
    cur = plan.get("journey")
    lines = [f"Ways to get from {ctx.origin} to {ctx.destination} (door to door, one way; round trip is double). Fares for flights are live; cab/bus/train are estimates:"]
    for k, nm in (("cheapest", "Cheapest"), ("fastest", "Fastest"), ("most_comfortable", "Most comfortable"), ("most_convenient", "Most convenient")):
        o = opts[lab[k]]
        lines.append(f"- {nm}: {o['summary']}: ₹{o['total_fare_inr']:,} (₹{o['round_trip_inr']:,} round trip), {_dur(o['total_duration_min'])}" + ("" if o.get("fits_budget", True) else f", ₹{o['over_by_inr']:,} over your travel allowance"))
    if cur:
        lines.append(f"Currently chosen: {cur['summary']} (₹{cur['round_trip_inr']:,} round trip).")
    if ro.get("allowance_round_trip_inr"):
        within = [o for o in opts if o.get("fits_budget")]
        lines.append(f"Your travel allowance is about ₹{ro['allowance_round_trip_inr']:,.0f} round trip (45% of the budget): {len(within)} option(s) fit." + (f" Stretch option: +₹{ro['stretch'][0]['extra_round_trip_inr']:,} for a better trip." if ro.get("stretch") else ""))
    for n in ro.get("notes", [])[:2] + [n for o in opts[:1] for n in o["notes"]]:
        lines.append("Note: " + n)
    return ("\n".join(lines), {"to": "/workspace?tab=travel"})


def facts_text(plan: dict, ctx) -> str:
    """Compact, data-only summary of the trip for grounded Q&A (the model may only use these facts)."""
    f = [f"Destination: {ctx.destination}; {ctx.days} days from {ctx.start_date}; {ctx.travellers} traveller(s); budget ₹{ctx.budget_inr or 0:,.0f}; home-base trip: {ctx.stay_home}."]
    b = plan.get("budget")
    if b:
        f.append(f"Estimated total ₹{b['estimated_total_inr']:,}; breakdown {b['breakdown']}; within budget: {b.get('within_budget')}.")
    h = plan.get("hotel")
    if h and h.get("id") != "home":
        f.append(f"Hotel: {h['name']} ₹{h['price_per_night']:,.0f}/night, rating {h.get('rating')}.")
    ro = plan.get("route_options")
    if ro:
        for o in ro["options"][:6]:
            f.append(f"Travel option: {o['summary']}; one way ₹{o['total_fare_inr']:,}; {_dur(o['total_duration_min'])}; comfort {o['comfort']}/5; badges {o.get('badges', [])}; fits budget {o.get('fits_budget')}.")
    it = plan.get("itinerary")
    if it:
        for d in it["days"][:8]:
            f.append(f"Day {d['day']}: " + ", ".join(f"{s['start']} {s['name']}" for s in d["stops"]) + f" (travel {d['travel_min']} min, {d['distance_km']} km, est ₹{d['cost_inr']:,}).")
    s = plan.get("safety") or {}
    if s.get("weather", {}).get("available"):
        w = s["weather"]
        f.append(f"Weather now: {w['temp_c']}C, {w['summary']}.")
    aqi = (((s.get("neighbourhood_report") or {}).get("environment") or {}).get("aqi"))
    if aqi:
        f.append(f"AQI {aqi['value']} ({aqi['band']}).")
    return "\n".join(f)


def run(intent: dict, plan: dict, ctx) -> tuple[str, dict | None]:
    kind = intent["intent"]
    if kind == "transport_options":
        return transport_reply(plan, ctx, intent.get("text", ""))
    nights, travellers = ctx.nights, max(ctx.travellers, 2)
    cat = plan.get("catalog") if ctx.is_world else None
    if cat and kind in ("hotels_filter", "places_nearby", "restaurants_near"):
        lat, lon = _anchor(plan, ctx)
        if kind == "hotels_filter":
            from ..services import world
            ranked = world.rank_hotels(cat["hotels"], plan.get("attractions") or cat["attractions"], nights, None, travellers)
            ok = [h for h in ranked if h["price_per_night"] <= intent["max"]]
            if not ok:
                low = min(ranked, key=lambda h: h["price_per_night"]) if ranked else None
                return (f"No hotel found at or under ₹{intent['max']:,.0f}/night in {ctx.destination} for your dates." + (f" The cheapest is {low['name']} at ₹{low['price_per_night']:,.0f}." if low else ""), {"to": "/workspace?tab=hotels"})
            return (f"{len(ok)} hotel(s) at or under ₹{intent['max']:,.0f}/night in {ctx.destination} (Google Hotels rates for your dates):\n" + "\n".join(
                f"- {h['name']}: ₹{h['price_per_night']:,.0f}/night, rating {h.get('rating') or 'n/a'}, {h['avg_km_to_attractions']} km from your sights" for h in ok[:5]), {"to": "/workspace?tab=hotels"})
        src = cat["attractions"] if kind == "places_nearby" else cat["restaurants"]
        near = sorted(src, key=lambda p: geo.haversine_km((lat, lon), (p["lat"], p["lon"])))[:6]
        label = "Places" if kind == "places_nearby" else "Restaurants"
        return (f"{label} near {'your hotel' if plan.get('hotel') else ctx.destination} (Google Maps data):\n" + "\n".join(
            f"- {p['name']} ({geo.haversine_km((lat, lon), (p['lat'], p['lon'])):.1f} km" + (f", ★{p['rating']}" if p.get("rating") else "") + (f", {p['hours']}" if p.get("hours") else "") + ")" for p in near),
            {"to": "/workspace?tab=map"})
    if kind == "hotels_filter":
        cap = intent["max"]
        ranked = catalog.rank_hotels(nights, None, None, plan.get("attractions") or catalog.attractions(), travellers)
        ok = [h for h in ranked if h["price_per_night"] <= cap]
        if not ok:
            cheapest = min(ranked, key=lambda h: h["price_per_night"])
            return (f"No hotel in the demo dataset is at or under ₹{cap:,.0f}/night for {travellers} travellers. The cheapest is {cheapest['name']} at ₹{cheapest['price_per_night']:,.0f}.", {"to": "/workspace?tab=hotels"})
        lines = [f"- {h['name']} ({h['neighbourhood']}): ₹{h['price_per_night']:,.0f}/night, score {h['score']}" for h in ok[:5]]
        return (f"{len(ok)} hotel(s) at or under ₹{cap:,.0f}/night (simulated rates, not live availability):\n" + "\n".join(lines), {"to": "/workspace?tab=hotels"})
    if kind == "places_nearby":
        lat, lon = _anchor(plan)
        res = overpass.nearby("attractions", lat, lon, 4000)
        if res["places"]:
            lines = [f"- {p['name']} ({p['distance_km']} km)" for p in res["places"][:6]]
            return (f"Places near {'your hotel' if plan.get('hotel') else 'central Delhi'} from OpenStreetMap ({res['provenance']['kind']}):\n" + "\n".join(lines), {"to": "/discover"})
        near = sorted(catalog.attractions(), key=lambda a: geo.haversine_km((lat, lon), (a["lat"], a["lon"])))[:6]
        lines = [f"- {a['name']} ({geo.haversine_km((lat, lon), (a['lat'], a['lon'])):.1f} km)" for a in near]
        return ("OpenStreetMap lookup is unavailable right now, so these come from the curated demo list:\n" + "\n".join(lines), {"to": "/discover"})
    if kind == "restaurants_near":
        lat, lon = _anchor(plan)
        res = overpass.nearby("restaurants", lat, lon, 1200)
        if res["places"]:
            lines = [f"- {p['name']}{' · ' + p['cuisine'] if p['cuisine'] else ''} ({p['distance_km']} km)" for p in res["places"][:6]]
            return (f"Restaurants within ~1.2 km of {'your hotel' if plan.get('hotel') else 'central Delhi'} (OpenStreetMap, {res['provenance']['kind']}; ratings and prices are not available from OSM):\n" + "\n".join(lines), {"to": "/discover?tab=food"})
        pool = sorted(catalog.restaurants(), key=lambda r: geo.haversine_km((lat, lon), (r["lat"], r["lon"])))[:5]
        lines = [f"- {r['name']} ({r['cuisine']}, ~₹{r['price_for_two']} for two, est.)" for r in pool]
        return ("OpenStreetMap lookup is unavailable right now. Demo-dataset venues (fictional names, estimated prices):\n" + "\n".join(lines), {"to": "/discover?tab=food"})
    if kind == "route_best":
        if not plan.get("itinerary"):
            return ("Plan a trip first, then I can order your attractions. Or name the places you want to route.", None)
        parts = []
        for d in plan["itinerary"]["days"]:
            stops = [s["name"] for s in d["stops"] if s["type"] == "attraction"]
            if stops:
                parts.append(f"Day {d['day']}: hotel → " + " → ".join(stops) + f" → hotel ({d['distance_km']} km, ~{round(d['travel_min'])} min, estimated)")
        saved = plan.get("route_stats")
        return ("Best visiting order, grouped by area to avoid backtracking:\n" + "\n".join(parts), {"to": "/workspace?tab=map"})
    if kind == "weather_aqi":
        lat, lon = _anchor(plan, ctx)
        w, a = live.weather(lat, lon), live.aqi(lat, lon)
        out = []
        if w:
            out.append(f"Weather: {round(w['temp_c'])}°C (feels {round(w['feels_like_c'])}°C), {w['summary']}, humidity {w['humidity']}% ({w['provenance']['kind']}, OpenWeather).")
        if a:
            out.append(f"Air quality: AQI {a['value']} ({safety.aqi_band(a['value'])}) at the nearest station ({a['station']}), {a['provenance']['kind']}.")
            if a["value"] > 150:
                out.append("Air quality is poor for sensitive groups: consider a mask, shorter outdoor stretches and indoor sights in the afternoon. This is general guidance, not medical advice.")
        if not out:
            return ("Live weather and AQI are unavailable right now (provider offline or key missing).", None)
        return ("\n".join(out), {"to": "/workspace?tab=safety"})
    return ("", None)
