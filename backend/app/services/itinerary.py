"""Deterministic itinerary builder: geographic day clustering -> per-day route optimisation -> timed slots -> food near stops."""
from datetime import date as _date, timedelta as _td

from . import catalog, geo, hours as hrs

DAY_START_H = 9.0
PACE_MAX_MIN = {"relaxed": 300, "balanced": 420, "packed": 540}


def _fmt(h: float) -> str:
    return f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}"


def _pick_food(point, used_ids, prefs: dict, slot: str, restaurants: list[dict] | None = None):
    pool = restaurants if restaurants is not None else catalog.restaurants()
    if prefs.get("vegetarian"):
        pool = [r for r in pool if r.get("veg")] or pool  # unknown dietary data: fall back rather than return nothing
    if prefs.get("vegan"):
        pool = [r for r in pool if r.get("vegan")] or pool
    if slot == "lunch":
        pool = [r for r in pool if r.get("kind") != "fine_dining"] or pool
    pool = [r for r in pool if r["id"] not in used_ids] or pool
    if not pool:
        return None
    return min(pool, key=lambda r: geo.haversine_km(point, (r["lat"], r["lon"])) - (r.get("rating") or 3.5) * 0.15)


def _meal(r, meal, start, travellers, slot):
    price = r.get("price_for_two")
    return {"type": "meal", "meal": meal, "start": start, "name": r["name"], "id": r["id"], "lat": r["lat"], "lon": r["lon"], "slot": slot,
            "cost_inr": (price or 1400) / 2 * travellers, "rating": r.get("rating"), "thumbnail": r.get("thumbnail"), "website": r.get("website"),
            "note": ("" if r["id"].startswith("g-") else "DEMO venue · ") + f"{r.get('cuisine') or 'Restaurant'}" + (" (est. price)" if price else " (price not listed: ₹1,400 for two assumed)")}


def build(attraction_ids: list[str], days: int, hotel: dict | None, travellers: int = 2, pace: str = "balanced",
          prefs: dict | None = None, start_date: str | None = None, pool: list[dict] | None = None, restaurants: list[dict] | None = None) -> dict:
    prefs = prefs or {}
    all_a = {a["id"]: a for a in (pool if pool is not None else catalog.attractions())}
    selected = [all_a[i] for i in attraction_ids if i in all_a]
    if days < 1:
        raise ValueError("days must be >= 1")
    base = (hotel["lat"], hotel["lon"]) if hotel else ((sum(a["lat"] for a in selected) / len(selected), sum(a["lon"] for a in selected) / len(selected)) if selected else (28.6139, 77.2090))
    pts = [(a["lat"], a["lon"]) for a in selected]
    groups = geo.cluster_days(pts, days) if selected else []
    day_date = (lambda i: _date.fromisoformat(start_date) + _td(days=i)) if start_date else None  # noqa: E731

    def open_info(idx, gi):
        return hrs.for_date(selected[idx].get("operating_hours"), day_date(gi)) if day_date else None

    if day_date and len(groups) > 1:  # move attractions that are closed on their assigned weekday to a day when they are open
        cap = max(len(g) for g in groups) + 1
        for gi, g in enumerate(groups):
            for idx in list(g):
                inf = open_info(idx, gi)
                if inf and inf["kind"] == "closed":
                    for gj, g2 in enumerate(groups):
                        i2 = open_info(idx, gj)
                        if gj != gi and len(g2) < cap and (i2 is None or i2["kind"] != "closed"):
                            g.remove(idx); g2.append(idx)
                            break
    day_plans, used_food = [], set()
    max_min = PACE_MAX_MIN.get(pace, 420)
    overflow = []
    for gi, g in enumerate(groups):
        gp = [pts[i] for i in g]
        order = [g[i] for i in geo.optimize_order(gp, base)]
        t, cur, stops, travel_total, dist_total, cost = DAY_START_H, base, [], 0.0, 0.0, 0.0
        active_min = 0
        for idx in order:
            a = selected[idx]
            leg = geo.route(cur, (a["lat"], a["lon"]), "drive")
            if active_min + leg["duration_min"] + a["visit_min"] > max_min and stops:
                overflow.append(a["name"])
                continue
            t += leg["duration_min"] / 60
            inf = open_info(idx, gi)
            flag, hours_text = None, None
            if inf:
                hours_text = inf["text"]
                if inf["kind"] == "closed":
                    flag = "closed"
                elif inf["kind"] == "range":
                    if t < inf["open"]:
                        t = inf["open"]  # wait for opening time instead of arriving at a locked door
                    if t + a["visit_min"] / 60 > inf["close"] + 0.01:
                        flag = "closes_early"
            slot = "morning" if t < 12 else ("afternoon" if t < 17 else "evening")
            if 13 <= t < 14.5 and not any(s["type"] == "meal" for s in stops):
                lunch = _pick_food(cur, used_food, prefs, "lunch", restaurants)
                if lunch:
                    used_food.add(lunch["id"])
                    stops.append(_meal(lunch, "lunch", _fmt(13.0), travellers, "afternoon"))
                t = max(t, 14.25)
            stops.append({"type": "attraction", "id": a["id"], "name": a["name"], "start": _fmt(t), "end": _fmt(t + a["visit_min"] / 60),
                          "slot": slot, "lat": a["lat"], "lon": a["lon"], "travel_min": leg["duration_min"], "travel_km": leg["distance_km"],
                          "mode": "cab", "fee_inr": a["fee_inr"], "fee_known": a["fee_inr"] is not None,
                          "hours_note": (f"{day_date(gi).strftime('%A')}: {hours_text}" if hours_text else ("Google Maps now: " + a["hours"]) if a.get("hours") else "Opening hours unverified - check official source before going"),
                          "hours_flag": flag,
                          "thumbnail": a.get("thumbnail"), "rating": a.get("rating"), "reviews": a.get("reviews"), "maps_url": a.get("maps_url"), "website": a.get("website"),
                          "cost_inr": (a["fee_inr"] or 0) * travellers})
            t += a["visit_min"] / 60
            travel_total += leg["duration_min"]
            dist_total += leg["distance_km"]
            active_min += leg["duration_min"] + a["visit_min"]
            cur = (a["lat"], a["lon"])
        if stops and not any(s.get("meal") == "lunch" for s in stops):  # every day gets a lunch near the morning's sights, scheduled around visits
            lunch_t = 13.0
            for s in stops:
                if s["type"] == "attraction":
                    sh, sm = map(int, s["start"].split(":"))
                    eh, em = map(int, s["end"].split(":"))
                    if sh + sm / 60 <= lunch_t < eh + em / 60:
                        lunch_t = eh + em / 60
            anchor = max((s for s in stops if s["type"] == "attraction" and int(s["start"].split(":")[0]) * 60 + int(s["start"].split(":")[1]) <= lunch_t * 60), key=lambda s: s["start"], default=None)
            point = (anchor["lat"], anchor["lon"]) if anchor else base
            lunch = _pick_food(point, used_food, prefs, "lunch", restaurants)
            if lunch and lunch_t < 15.5:
                used_food.add(lunch["id"])
                stops.append(_meal(lunch, "lunch", _fmt(lunch_t), travellers, "afternoon"))
                stops.sort(key=lambda s: s["start"])
        if stops:
            dinner = _pick_food(cur, used_food, prefs, "dinner", restaurants)
            if dinner:
                used_food.add(dinner["id"])
                stops.append(_meal(dinner, "dinner", _fmt(max(t + 0.25, 19.0)), travellers, "evening"))
            back = geo.route(cur, base, "drive")
            travel_total += back["duration_min"]
            dist_total += back["distance_km"]
        day_plans.append({"day": gi + 1, "title": f"Day {gi + 1}: " + " & ".join(s["name"] for s in stops if s["type"] == "attraction")[:60],
                          "stops": stops, "travel_min": round(travel_total), "distance_km": round(dist_total, 1),
                          "area_summary": sorted({all_a[s['id']].get('area') for s in stops if s['type'] == 'attraction' and all_a[s['id']].get('area')}),
                          "route_geometry": [[base[1], base[0]]] + [[s["lon"], s["lat"]] for s in stops if s["type"] == "attraction"] + [[base[1], base[0]]],
                          "cost_inr": round(sum(s["cost_inr"] for s in stops))})
    while len(day_plans) < days:  # spare days stay explicit so the user can fill them
        day_plans.append({"day": len(day_plans) + 1, "title": f"Day {len(day_plans) + 1}: Free day", "stops": [], "travel_min": 0,
                          "distance_km": 0, "area_summary": [], "route_geometry": [], "cost_inr": 0})
    return {"days": day_plans, "hotel": hotel and {"id": hotel["id"], "name": hotel["name"], "lat": hotel["lat"], "lon": hotel["lon"]},
            "dropped_for_pace": overflow, "pace": pace, "start_date": start_date,
            "provenance": "Travel times are straight-line estimates (x1.35); see the Map tab for road routes. Opening hours are the listed weekday hours where available; ticket prices are unverified."}
