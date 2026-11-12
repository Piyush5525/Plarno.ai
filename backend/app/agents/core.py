"""Agent framework + the specialist agents. Agents are small, independent classes with a typed contract:
    run(ctx: TripContext, plan: dict) -> dict   (reads/writes the shared `plan` blackboard)
Calculations (routing, scoring, pricing) are deterministic services; language/personalisation lives in llm.py."""
import time
import uuid
from datetime import date, datetime, timedelta

from .. import db
from ..providers import geocode
from ..services import booking, budget, catalog, geo, itinerary, recovery, routes, safety, transport, world
from .context import TripContext


class Agent:
    name = "agent"
    critical = True
    max_retries = 2

    def run(self, ctx: TripContext, plan: dict) -> str:  # returns one-line summary
        raise NotImplementedError

    def execute(self, ctx: TripContext, plan: dict, workflow_id: str) -> dict:
        t0, attempts, err, state, summary = time.time(), 0, None, "running", ""
        while attempts <= self.max_retries:
            attempts += 1
            try:
                summary = self.run(ctx, plan)
                state, err = "succeeded", None
                break
            except ValueError as e:  # validation errors are deterministic: no retry
                state, err = "failed", str(e)
                break
            except Exception as e:  # noqa: BLE001 - transient: retry
                state, err = "failed", f"{type(e).__name__}: {e}"
        dur = int((time.time() - t0) * 1000)
        db.run("INSERT INTO agent_logs(workflow_id,agent,state,attempts,duration_ms,summary,error) VALUES(?,?,?,?,?,?,?)",
               (workflow_id, self.name, state, attempts, dur, summary, err))
        return {"agent": self.name, "state": state if state == "succeeded" or self.critical else "degraded",
                "attempts": attempts, "duration_ms": dur, "summary": summary, "error": err}


class TravelPlannerAgent(Agent):
    name = "travel_planner"

    def run(self, ctx, plan):
        missing = ctx.missing_required()
        if missing:
            raise ValueError("missing: " + ", ".join(missing))
        if ctx.is_world:
            if not ctx.dest_geo or ctx.dest_geo.get("query") != ctx.destination:
                g = geocode.resolve(ctx.destination)
                if not g:
                    bad, ctx.destination, ctx.dest_geo = ctx.destination, None, None
                    raise ValueError(f"I couldn't find a place called '{bad}'. Could you give the city name (and country if it's ambiguous)?")
                if g.get("broad"):
                    bad, ctx.destination, ctx.dest_geo = ctx.destination, None, None
                    raise ValueError(f"{g['name']} covers a large area{' in ' + g['country'] if g.get('country') and g['country'] != g['name'] else ''}. Which city or town would you like to base the trip in? (For example the main city or a resort town.)")
                g["query"] = ctx.destination
                ctx.dest_geo = g
                ctx.destination = g["name"]
                ctx.dest_geo["query"] = ctx.destination
        else:
            ctx.destination, ctx.dest_geo = "Delhi", None
        if not ctx.start_date:
            ctx.start_date = (date.today() + timedelta(days=14)).isoformat()
            ctx.dates_assumed = True
        datetime.fromisoformat(ctx.start_date)
        plan["dates"] = [ctx.start_date, (date.fromisoformat(ctx.start_date) + timedelta(days=ctx.days - 1)).isoformat()]
        plan["travellers"] = ctx.travellers
        return f"{ctx.travellers} traveller(s), {ctx.days} days from {ctx.start_date}" + (" (date assumed)" if ctx.dates_assumed else "")


class DestinationDiscoveryAgent(Agent):
    name = "destination_discovery"

    def run(self, ctx, plan):
        per_day = {"relaxed": 1, "balanced": 2, "packed": 3}[ctx.pace]
        n = per_day * (ctx.days or 1) + ctx.extra_attractions
        if ctx.is_world:
            ci, co = world.dates_for(ctx.start_date, ctx.days)
            cat = world.build_catalog(ctx.dest_geo, ctx.interests, ci, co, max(ctx.adults or 2, 1), need_hotels=not ctx.stay_home, want_places=max(6, (ctx.days or 1) * 2))
            plan["catalog"], plan["world"] = cat, True
            if not cat["attractions"]:
                raise ValueError("I couldn't retrieve places for " + ctx.destination + " right now (" + "; ".join(cat["notes"][:1] or ["provider unavailable"]) + ").")
            chosen = world.select_attractions(cat["attractions"], ctx.interests, n, ctx.avoid_crowded)
            ctx.selected_attraction_ids = [a["id"] for a in chosen]
            plan["attractions"] = chosen
            return f"{len(chosen)} of {len(cat['attractions'])} real places selected in {ctx.destination} (Google Maps via SerpApi)"
        plan["world"] = False
        want = set(ctx.interests) - {"food", "peaceful"} or {"history"}
        scored = []
        for a in catalog.attractions():
            if ctx.avoid_crowded and a["id"] in ("chandni-chowk", "jama-masjid"):
                continue
            if ctx.accessibility and ("steps" in a["accessibility"].lower() or "uneven" in a["accessibility"].lower() or "crowded" in a["accessibility"].lower()):
                continue
            s = 2 * len(want & set(a["tags"])) + (1 if ctx.peaceful and ({"peaceful", "garden"} & set(a["tags"])) else 0)
            s += 0.5 if "unesco" in a["tags"] else 0
            scored.append((s, a))
        scored.sort(key=lambda x: -x[0])
        chosen = [a for s, a in scored if s > 0][:n] or [a for _, a in scored][:n]
        ctx.selected_attraction_ids = [a["id"] for a in chosen]
        plan["attractions"] = chosen
        return f"{len(chosen)} attractions matched to interests {sorted(want)}"


class NeighbourhoodIntelligenceAgent(Agent):
    name = "neighbourhood_intelligence"

    def weights(self, ctx):
        w = dict(catalog.PRESETS.get(ctx.priority_preset or "", catalog.DEFAULT_WEIGHTS))
        if ctx.peaceful or ctx.avoid_noisy or ctx.avoid_polluted:
            w["environment"] = w.get("environment", 0.2) + 0.25
        if ctx.hotel_min_quality:
            w["hotel_quality"] = w.get("hotel_quality", 0.15) + 0.3
        w.update(ctx.weights)
        return w

    def run(self, ctx, plan):
        if ctx.is_world:
            w = dict(world.DEFAULT_WEIGHTS)
            if ctx.priority_preset == "budget":
                w.update(price=0.45, hotel_quality=0.15)
            elif ctx.priority_preset == "sightseeing":
                w.update(attractions=0.5)
            if ctx.hotel_min_quality:
                w["hotel_quality"] += 0.3
            w.update({k: v for k, v in ctx.weights.items() if k in w})
            plan["neighbourhoods"], plan["weights_used"] = [], w
            return "per-hotel location scoring (no neighbourhood dataset for this city)"
        sel = plan["attractions"]
        stats = {"quality": 0.7, "food": 0.7, "price_fit": 0.7}
        ranked = sorted((catalog.score_neighbourhood(nb, sel, stats, self.weights(ctx)) for nb in catalog.neighbourhoods()), key=lambda r: -r["score"])
        plan["neighbourhoods"] = ranked
        plan["weights_used"] = self.weights(ctx)
        return "top areas: " + ", ".join(n["neighbourhood"] for n in ranked[:3])


class HotelIntelligenceAgent(Agent):
    name = "hotel_intelligence"

    def run(self, ctx, plan):
        nights = ctx.nights
        cap = ctx.budget_inr * 0.6 / nights * ctx.cheaper_factor if ctx.budget_inr else None
        if ctx.hotel_min_quality:
            cap = cap * 1.8 if cap else None
        avoid = ["industrial"] if ctx.avoid_polluted else None
        if ctx.stay_home and ctx.is_world:  # day trips from home: no hotel, the home town is the base
            g = ctx.dest_geo
            home = {"id": "home", "name": f"Home base ({g['name']})", "lat": g["lat"], "lon": g["lon"], "type": "home", "stars": None, "rating": None, "reviews": None, "nightly": 0,
                    "price_per_night": 0, "total_price": 0, "rooms": 0, "over_budget": False, "score": None, "avg_km_to_attractions": 0, "neighbourhood": g["name"], "interiors": None,
                    "amenities": [], "images": [], "booking_url": None, "nights": nights,
                    "provenance": {"source": "your home town", "kind": "estimated", "fetched_at": "", "note": "No hotel is needed for day trips from home."}, "explanation": None}
            plan["hotel_candidates"], plan["hotel"] = [], home
            return "day trips from home: no hotel"
        if ctx.is_world:
            ranked = world.rank_hotels(plan["catalog"]["hotels"], plan["attractions"], nights, cap, max(ctx.travellers, 1), plan.get("weights_used"))
            if not ranked:
                raise ValueError("No hotel rates were returned for " + ctx.destination + " on those dates. Try different dates or ask again in a moment.")
            hp = plan["catalog"]["provenance"]["hotels"]
            for h in ranked:
                h["provenance"] = hp
        else:
            ranked = catalog.rank_hotels(nights, cap, plan.get("weights_used"), plan["attractions"], max(ctx.travellers, 1), avoid)
        plan["hotel_candidates"] = ranked[:6]
        if ctx.hotel_id:
            chosen = next((h for h in ranked if h["id"] == ctx.hotel_id), None)
            if not chosen:
                raise ValueError(f"Unknown hotel id {ctx.hotel_id}")
        else:
            pool = [h for h in ranked if not ctx.hotel_price_ceiling or h["price_per_night"] < ctx.hotel_price_ceiling] or ranked
            within = [h for h in pool if not h["over_budget"]]
            # best-scoring hotel inside the budget cap; if none fit, the cheapest of the best-scoring few
            chosen = within[0] if within else min(pool[:5], key=lambda h: h["price_per_night"])
        chosen = {**chosen, "nights": nights}
        plan["hotel"] = chosen
        return f"{chosen['name']} in {chosen['neighbourhood']} (score {chosen['score']}, ₹{chosen['price_per_night']:,.0f}/night, {'Google Hotels' if ctx.is_world else 'simulated'})"


class TransportationAgent(Agent):
    name = "transportation"
    critical = False

    def run(self, ctx, plan):
        plan.pop("journey", None)
        plan.pop("route_options", None)
        if ctx.stay_home:
            plan["journey_note"] = "Day trips from home: no long-distance travel. Local cab fares for each outing are in the itinerary."
            return "skipped (stay at home)"
        if not ctx.origin or ctx.origin == ctx.destination:
            plan["journey_note"] = "No origin provided: intercity transport not included in the estimate."
            return "skipped (no origin)"
        from ..data.seed import CITIES
        if ctx.is_world or ctx.origin not in CITIES:  # door-to-door route options for any pair of places (small towns included)
            og = ctx.origin_geo if ctx.origin_geo and ctx.origin_geo.get("query") == ctx.origin else None
            if not og:
                og = geocode.resolve(ctx.origin)
                if not og:
                    plan["journey_note"] = f"I couldn't locate '{ctx.origin}', so travel to {ctx.destination} is not included. Try the nearest city."
                    return "origin not found"
                og["query"] = ctx.origin
                ctx.origin_geo = og
            dg = ctx.dest_geo or {"name": "Delhi", "lat": 28.6139, "lon": 77.2090, "country_code": "IN"}
            allowance = ctx.budget_inr * 0.45 if ctx.budget_inr else None
            res = routes.build_options(og, dg, ctx.start_date, max(ctx.travellers, 1), allowance)
            plan["route_options"] = res
            if not res["options"]:
                plan["journey_note"] = " ".join(res.get("notes") or ["No route options found."]) + " Travel is not included in the estimate."
                return "no options"
            opts = res["options"]
            pick = None
            if ctx.chosen_route_index is not None and 0 <= ctx.chosen_route_index < len(opts):
                pick = opts[ctx.chosen_route_index]
            else:
                pool = opts if ctx.transport_explicit else ([o for o in opts if o.get("fits_budget", True)] or [min(opts, key=lambda o: o["total_fare_inr"])])  # nothing fits: cheapest
                pref = ctx.transport_pref or "best_value"
                key = {"cheapest": lambda o: o["total_fare_inr"], "fastest": lambda o: o["total_duration_min"], "comfortable": lambda o: (-o["comfort"], o["total_fare_inr"])}.get(pref)
                pick = min(pool, key=key) if key else pool[0]  # opts are already ordered by value
            plan["journey"], plan["journey_options"], plan["journey_labels"] = pick, opts, res["labels"]
            return f"{pick['summary']} ₹{pick['total_fare_inr']:,} one way ({len(opts)} options door to door)"
        if ctx.is_world:
            from ..data.airports import iata
            if not (iata(ctx.origin) and iata(ctx.destination)):
                plan["journey_note"] = f"Flight search is not available for {ctx.origin} → {ctx.destination} (no airport mapping). Intercity travel is not included in the estimate."
                return "no airport mapping"
            try:
                res = transport.search_journeys(ctx.origin, ctx.destination, ctx.start_date, max(ctx.travellers, 1), True, {})
            except ValueError as e:
                plan["journey_note"] = str(e)
                return "unavailable"
            if not res["journeys"]:
                plan["journey_note"] = (res.get("live_note") or "No flights found") + " Intercity travel is not included in the estimate."
                return "no flights"
        else:
            res = transport.search_journeys(ctx.origin, ctx.destination, ctx.start_date, max(ctx.travellers, 1))
        if not res["journeys"]:
            plan["journey_note"] = "No simulated journeys found."
            return "no journeys"
        pref = {"cheapest": "cheapest", "fastest": "fastest", "comfortable": "most_comfortable"}.get(ctx.transport_pref or "", "best_value")
        want = next(j for j in res["journeys"] if pref in j.get("badges", [])) if any(pref in j.get("badges", []) for j in res["journeys"]) else res["journeys"][0]
        plan["journey"], plan["journey_options"], plan["journey_labels"] = want, res["journeys"], res["labels"]
        return f"{want['summary']} ({pref}) ₹{want['total_fare_inr']:,} simulated"


class RouteOptimizationAgent(Agent):
    name = "route_optimization"

    def run(self, ctx, plan):
        h = plan["hotel"]
        pts = [(a["lat"], a["lon"]) for a in plan["attractions"]]
        if len(pts) < 2:
            return "nothing to optimise"
        naive = geo.path_length(pts, list(range(len(pts))))
        order = geo.optimize_order(pts, (h["lat"], h["lon"]))
        plan["route_stats"] = {"naive_km": round(naive, 1), "optimised_km": round(geo.path_length(pts, order), 1),
                               "method": "exact permutation search (<=8 stops/day) else NN+2-opt, haversine metric"}
        return f"stops ordered per day from hotel; straight-line path {naive:.1f} km unoptimised"


class ItineraryAgent(Agent):
    name = "itinerary"

    def run(self, ctx, plan):
        cat = plan.get("catalog") if ctx.is_world else None
        it = itinerary.build(ctx.selected_attraction_ids, ctx.days, plan["hotel"], max(ctx.travellers, 1), ctx.pace,
                             {"vegetarian": ctx.vegetarian, "vegan": ctx.vegan}, ctx.start_date,
                             pool=cat["attractions"] if cat else None, restaurants=cat["restaurants"] if cat else None)
        for i, d in enumerate(it["days"]):
            d["date"] = (date.fromisoformat(ctx.start_date) + timedelta(days=i)).isoformat()
        plan["itinerary"] = it
        return f"{len(it['days'])} days, {sum(len(d['stops']) for d in it['days'])} stops" + (f"; dropped for pace: {it['dropped_for_pace']}" if it["dropped_for_pace"] else "")


class FoodDiscoveryAgent(Agent):
    name = "food_discovery"
    critical = False

    def run(self, ctx, plan):
        sugg = {}
        for d in plan["itinerary"]["days"]:
            anchors = [(s["lat"], s["lon"]) for s in d["stops"] if s["type"] == "attraction"]
            if not anchors:
                continue
            c = (sum(a[0] for a in anchors) / len(anchors), sum(a[1] for a in anchors) / len(anchors))
            pool = [dict(r) for r in (plan["catalog"]["restaurants"] if ctx.is_world else catalog.restaurants()) if (not ctx.vegetarian or r.get("veg")) and (not ctx.vegan or r.get("vegan"))]
            for r in pool:
                r["distance_km"] = round(geo.haversine_km(c, (r["lat"], r["lon"])), 1)
            sugg[d["day"]] = sorted(pool, key=lambda r: r["distance_km"] - (r.get("rating") or 3.5) * 0.2)[:4]
        plan["food_suggestions"] = sugg
        return f"restaurant shortlists for {len(sugg)} days"


class TravelSafetyAgent(Agent):
    name = "travel_safety"
    critical = False

    def run(self, ctx, plan):
        h = plan["hotel"]
        if ctx.is_world:
            plan["safety"] = world.safety_context(ctx.dest_geo)
            return f"live weather/AQI for {ctx.destination}; advisory guidance (no live feed)"
        nb = next(n for n in catalog.neighbourhoods() if n["name"] == h["neighbourhood"])
        rep = safety.destination_safety(ctx.destination, h["lat"], h["lon"])
        rep["neighbourhood_report"] = safety.neighbourhood_report(nb["id"])
        plan["safety"] = rep
        return f"advisory + {nb['name']} environmental report (estimated/simulated inputs)"


class BudgetAgent(Agent):
    name = "budget"

    def run(self, ctx, plan):
        b = budget.compute(max(ctx.travellers, 1), ctx.nights, plan["hotel"], plan.get("journey"), plan["itinerary"], ctx.budget_inr,
                           round_trip=True)
        b["suggestions"] = budget.savings_suggestions(b, plan.get("hotel_candidates", []), plan["hotel"])
        plan["budget"] = b
        return f"estimated ₹{b['estimated_total_inr']:,}" + (" (within budget)" if b.get("within_budget") else " (OVER budget)" if "within_budget" in b else "")


class BookingAgent(Agent):
    name = "booking"
    critical = False

    def run(self, ctx, plan):
        if ctx.is_world:  # search-only providers: hand the user to the real booking sites; never fabricate a confirmation
            links = []
            h = plan["hotel"]
            if h.get("booking_url") and h["id"] != "home":
                links.append({"kind": "hotel", "label": f"{h['name']} · ₹{h['price_per_night']:,.0f}/night", "url": h["booking_url"]})
            j = plan.get("journey")
            fl = next((leg for leg in (j or {}).get("legs", []) if leg.get("booking_link")), None)
            if j and fl:
                links.append({"kind": "flight", "label": f"{fl['from']} → {fl['to']} ({fl['operator']}) · fare ₹{fl['fare_inr']:,} per person", "url": fl["booking_link"]})
            if h.get("booking_url") and h["id"] != "home" or h["id"] == "home":
                links = [x for x in links if not (h["id"] == "home" and x["kind"] == "hotel")]
            plan["bookable_items"], plan["booking_links"] = [], links
            return f"{len(links)} external booking link(s); booking happens on the provider's website"
        plan["bookable_items"] = booking.prepare_items(plan)
        return f"{len(plan['bookable_items'])} item(s) prepared; nothing booked - awaiting user approval"


class TravelRecoveryAgent(Agent):
    name = "travel_recovery"

    def propose(self, plan: dict, delay_min: int) -> dict:
        return recovery.handle_delay(plan, delay_min, plan["dates"][0])


class TravelCompanionAgent(Agent):
    name = "travel_companion"

    def day_brief(self, plan: dict, day: int = 1) -> dict:
        d = plan["itinerary"]["days"][day - 1]
        return {"day": day, "stops": [(s["start"], s["name"]) for s in d["stops"]], "emergency": plan.get("safety", {}).get("emergency_contacts")}


PLAN_PIPELINE = [TravelPlannerAgent, DestinationDiscoveryAgent, NeighbourhoodIntelligenceAgent, HotelIntelligenceAgent, TransportationAgent,
                 RouteOptimizationAgent, ItineraryAgent, FoodDiscoveryAgent, TravelSafetyAgent, BudgetAgent, BookingAgent]
# after a hotel change, only these downstream agents need re-running (dependency-aware partial replan)
HOTEL_CHANGE_PIPELINE = [HotelIntelligenceAgent, RouteOptimizationAgent, ItineraryAgent, FoodDiscoveryAgent, TravelSafetyAgent, BudgetAgent, BookingAgent]
TRANSPORT_CHANGE_PIPELINE = [TransportationAgent, BudgetAgent, BookingAgent]
BUDGET_ONLY = [BudgetAgent, BookingAgent]


def run_workflow(agents: list[type[Agent]], ctx: TripContext, plan: dict) -> list[dict]:
    wid = uuid.uuid4().hex[:12]
    steps = []
    for cls in agents:
        a = cls()
        r = a.execute(ctx, plan, wid)
        steps.append(r)
        if r["state"] == "failed":
            break
    return steps
