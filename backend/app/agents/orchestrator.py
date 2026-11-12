"""Travel Orchestrator Agent: intent -> context update -> dependency-aware workflow -> reply. Holds no business logic itself."""
import re

from .. import db
from ..services import catalog
from . import core, nlu, tools
from ..providers import gemini
from .context import TripContext

QUESTIONS = {
    "destination": "Where in the world would you like to go?",
    "days": "How many days is the trip?",
    "travellers": "How many people are travelling (adults and children)?",
    "budget": "What is your total budget (for example ₹30,000)?",
    "origin": "Where are you starting from? (optional - I'll compare transport once I know)",
    "start_date": "Which date do you want to start (YYYY-MM-DD)? (optional - I assumed a date 2 weeks out)",
}


def _inr(v):
    return f"₹{round(v):,}"


def j_dur(m):
    return f"{int(m) // 60}h{int(m) % 60:02d}"


def compose_reply(ctx: TripContext, plan: dict, notes: list[str]) -> str:
    """Deterministic explanation. An LLM provider can rewrite this text but must not change numbers."""
    if "hotel" not in plan:
        return "\n".join(notes)
    h, b, it = plan["hotel"], plan["budget"], plan["itinerary"]
    lines = list(notes)
    lines.append(f"**Trip:** {ctx.days} days in {ctx.destination} for {ctx.travellers}, starting {ctx.start_date}" + (" (assumed date)" if ctx.dates_assumed else "") + ".")
    if ctx.stay_home:
        lines.append(f"**Base:** your home in {ctx.destination}. Day trips only: no hotel and no long-distance travel needed. Nearby places were searched within {plan.get('catalog', {}).get('radius_km', 60)} km.")
    elif ctx.is_world:
        lines.append(f"**Stay:** {h['name']}, {_inr(h['price_per_night'])}/night for your dates (Google Hotels), guest rating {h.get('rating') or 'n/a'}, "
                     f"{h['avg_km_to_attractions']} km on average from your chosen sights. Score {h['score']}/100 from provider data only.")
    else:
        top = plan["neighbourhoods"][0]
        lines.append(f"**Stay:** {h['name']} ({h['neighbourhood']}), {_inr(h['price_per_night'])}/night, score {h['score']}/100. "
                     f"Area score {top['score']} led by: " + ", ".join(f"{f['factor']}" for f in sorted(top['factors'], key=lambda f: -f['subscore'] * f['weight'])[:3]) + ". Environmental/safety inputs are simulated or estimated, not live.")
    if plan.get("journey"):
        j = plan["journey"]
        lines.append(f"**Getting there:** {j['summary']} from {ctx.origin}, about {j['total_duration_min'] // 60}h{j['total_duration_min'] % 60:02d}, {_inr(j['total_fare_inr'])} one way ({'live flight fare + estimated cab transfers' if j['provenance']['kind'] in ('live', 'cached') else 'estimated fares: verify with operators' if j['provenance']['kind'] == 'estimated' else 'simulated demo fares'}).")
        ro = plan.get("route_options")
        if ro and len(ro["options"]) > 1:
            lab = ro["labels"]
            alt = [f"{nm} {ro['options'][lab[k]]['summary']} {_inr(ro['options'][lab[k]]['round_trip_inr'])} round trip, {j_dur(ro['options'][lab[k]]['total_duration_min'])}" for k, nm in (("cheapest", "cheapest:"), ("fastest", "fastest:"), ("most_comfortable", "most comfortable:"))]
            lines.append("**Other ways to travel:** " + "; ".join(dict.fromkeys(alt)) + ".")
            if ro.get("stretch"):
                st = ro["stretch"][0]
                lines.append(f"**If you can stretch:** +{_inr(st['extra_round_trip_inr'])} round trip gets you {ro['options'][st['index']]['summary']}" + (f", saving about {st['saves_min'] // 60}h{st['saves_min'] % 60:02d}" if st["saves_min"] > 0 else "") + ".")
            for n in ro["options"][0]["notes"][:1] + ro.get("notes", [])[:1]:
                lines.append(f"Note: {n}")
    elif plan.get("journey_note"):
        lines.append(f"**Getting there:** {plan['journey_note']}")
    lines.append("**Itinerary:** " + "; ".join(f"Day {d['day']}: " + (", ".join(s['name'] for s in d['stops'] if s['type'] == 'attraction') or "free") for d in it["days"]) + ".")
    status = "within" if b.get("within_budget") else "OVER"
    lines.append(f"**Estimated cost:** {_inr(b['estimated_total_inr'])} ({_inr(b['per_person_inr'])} per person), {status} your {_inr(b['max_budget_inr'])} budget. These are estimates, not confirmed prices." if b.get("max_budget_inr") else f"**Estimated cost:** {_inr(b['estimated_total_inr'])}.")
    for a in b.get("alerts", []):
        lines.append(f"⚠ {a}")
    if b.get("unverified_entry_fees"):
        lines.append(f"{b['unverified_entry_fees']} attraction ticket price(s) are not provided by the data source and are counted as ₹0 - verify before paying.")
    for s in b.get("suggestions", []):
        lines.append(f"Tip: {s['text']}")
    if ctx.is_world:
        lines.append(f"**Booking:** {len(plan.get('booking_links', []))} external booking link(s) in the Bookings tab. Booking happens on the provider's own website; Plarno.ai does not make reservations for you.")
    else:
        lines.append(f"**Bookings:** {len(plan.get('bookable_items', []))} item(s) prepared. Nothing is booked until you approve; the booking service is a labelled simulation.")
    return "\n\n".join(lines)


def handle(user_id: int, trip_id: int | None, message: str) -> dict:
    row = db.one("SELECT * FROM trips WHERE id=? AND user_id=?", (trip_id, user_id)) if trip_id else None
    import json as _json
    ctx = TripContext(**_json.loads(row["context"])) if row else _context_from_prefs(user_id)
    plan = _json.loads(row["plan"]) if row and row["plan"] else {}
    has_plan = "itinerary" in plan
    _f = nlu.extract(message, TripContext())
    is_full_request = "days" in _f and "budget_inr" in _f
    intent = (None if is_full_request else tools.classify(message)) or nlu.classify_intent(message, has_plan)
    action = None
    kind = intent["intent"]
    notes: list[str] = []
    steps: list[dict] = []
    follow_ups: list[str] = []
    approval_hint = None
    reply = ""
    if kind == "chat" and not has_plan:  # slot-filling replies ("two people", "₹30000") arrive as plain chat
        kind = "plan" if nlu.extract(message, ctx) else "chat"
    found = nlu.extract(message, ctx) if kind in ("plan", "chat") or not has_plan else {}
    for raw_k, k in (("destination_raw", "destination"), ("origin_raw", "origin")):  # a place the user typed always beats the model's guess
        v = found.pop(raw_k, None)
        if v and k not in found and not getattr(ctx, k, None):
            found[k] = v
    if kind in ("plan", "chat") and not has_plan and len(message) > 15 and gemini.available():
        for k, v in gemini.extract_fields(message).items():  # the model only fills gaps the rules missed
            if k not in found and not getattr(ctx, k, None):
                found[k] = v
    if not has_plan and not ctx.destination and "destination" not in found and len(message.split()) <= 4 and re.fullmatch(r"[A-Za-zÀ-ÿ'’. -]{2,40}", message.strip()) \
            and message.strip().lower() not in ("hi", "hello", "hey", "help", "yes", "no", "ok", "thanks"):
        found["destination"] = message.strip().title()  # bare place name as an answer to "where would you like to go?"
        kind = "plan"
    for k, v in found.items():
        if k == "interests":
            ctx.interests = sorted(set(ctx.interests) | set(v))
        else:
            setattr(ctx, k, v)
        if k == "start_date":
            ctx.dates_assumed = False

    def replan(pipeline):
        nonlocal steps
        steps = core.run_workflow(pipeline, ctx, plan)

    if kind == "disruption":
        if not intent["delay_min"]:
            follow_ups = ["delay"]
            reply = "I'm sorry about the delay. About how long is it delayed (e.g. 3 hours)? I'll then check which activities are affected and find alternatives. I won't change anything without your approval."
        else:
            modes = {l["mode"] for l in (plan.get("journey") or {}).get("legs", [])}
            said = next((m for m in ("bus", "train", "flight", "cab") if re.search(rf"\b{m}\b", message.lower())), None)
            if said and modes and said not in modes:
                follow_ups = ["journey"]
                reply = f"Your planned journey uses {' + '.join(sorted(modes))}, not a {said}. Which journey is delayed? I won't change anything until you confirm."
                _save(user_id, trip_id, row, ctx, plan, message, reply)
                return _result(user_id, trip_id, row, ctx, plan, reply, steps, follow_ups, approval_hint)
            prop = core.TravelRecoveryAgent().propose(plan, intent["delay_min"])
            plan["pending_recovery"] = prop
            reply = (f"Understood: your journey is delayed ~{intent['delay_min']} min (new arrival {prop['disruption']['new_arrival']}). "
                     f"{len(prop['affected_activities'])} activity(ies) are affected: " + (", ".join(a["name"] for a in prop["affected_activities"]) or "none") + ". Options:\n" +
                     "\n".join(f"- {o['label']} ({'saves ' + _inr(-o['extra_cost_inr']) if o['extra_cost_inr'] < 0 else 'extra cost ' + _inr(o['extra_cost_inr'])}) - {o['detail']}" for o in prop["options"]) +
                     "\n\nTell me which option you prefer. Nothing is rebooked until you approve.")
            approval_hint = "recovery"
    elif kind == "retrieve_bookings":
        bks = db.q("SELECT id,category,supplier,item,amount,status,reference,cancellation_policy FROM bookings WHERE user_id=?", (user_id,))
        reply = ("Your bookings (all simulated):\n" + "\n".join(f"- #{b['id']} {b['category']}: {b['item']} - {b['status']} ({b['reference']})" for b in bks)) if bks else "You have no bookings yet."
        plan["bookings_view"] = bks
    elif kind in tools.TOOL_INTENTS:
        intent["text"] = message
        reply, action = tools.run(intent, plan, ctx)
    elif not has_plan or kind == "plan":
        missing = ctx.missing_required()
        if kind == "chat" and len(missing) == 4:
            reply = "Hi, I'm TRIP. Tell me where you want to go - for example: 'Plan a 5-day Delhi trip for two, budget ₹30,000'."
            follow_ups = missing
        elif missing:
            follow_ups = missing
            known = []
            if ctx.destination:
                known.append(ctx.destination)
            reply = ("Got it" + (f" - {', '.join(known)}" if known else "") + ". " + " ".join(QUESTIONS[m] for m in missing[:2]))
        else:
            if True:
                replan(core.PLAN_PIPELINE)
                # conflict resolution: budget agent vs hotel agent
                tries = 0
                while plan.get("budget") and not plan["budget"].get("within_budget", True) and tries < 4:
                    tries += 1
                    nxt = {"comfortable": "best_value", "fastest": "best_value", "best_value": "cheapest", None: "cheapest"}.get(ctx.transport_pref) if plan.get("journey") and ctx.chosen_route_index is None and not ctx.transport_explicit else None
                    if nxt:
                        # first relax the costliest soft preference (transport), keeping the stay the user cares about
                        ctx.transport_relaxed = True
                        notes.append(f"Over budget: switched travel from {ctx.transport_pref or 'best value'} to {nxt.replace('_', ' ')} before touching the hotel.")
                        ctx.transport_pref = nxt
                        replan(core.TRANSPORT_CHANGE_PIPELINE)
                    elif not ctx.hotel_id:
                        ctx.cheaper_factor *= 0.75
                        notes.append(f"Still over budget: re-selecting a cheaper hotel (attempt {tries}).")
                        replan(core.HOTEL_CHANGE_PIPELINE)
                    else:
                        break
                if plan.get("hotel") and (plan["hotel"].get("interiors") or 5) < 4.0 and (ctx.peaceful or "interiors" in message.lower()):
                    notes.append(f"⚠ Budget forced a hotel with a lower interiors rating ({plan['hotel']['interiors']}/5). Raise the budget or relax transport for a nicer stay.")
                failed = [s for s in steps if s["state"] == "failed"]
                reply = (failed[0]["error"] if failed[0]["agent"] in ("travel_planner", "destination_discovery", "hotel_intelligence") else f"I couldn't finish planning: {failed[0]['agent']} - {failed[0]['error']}") if failed else compose_reply(ctx, plan, notes)
                follow_ups = [] if failed else ctx.optional_follow_ups()
                if failed and failed[0]["agent"] == "travel_planner" and not ctx.destination:
                    follow_ups = ["destination"]
    else:  # modification intents
        if kind == "cheaper":
            ctx.cheaper_factor *= 0.7
            ctx.hotel_price_ceiling = plan["hotel"]["price_per_night"]
            ctx.hotel_id = None
            if ctx.transport_pref not in ("cheapest",):
                ctx.transport_pref = "cheapest"
            if not ctx.budget_inr:
                ctx.budget_inr = plan["budget"]["estimated_total_inr"] * 0.85
            notes.append("Looking for cheaper hotel and transport.")
            replan(core.PLAN_PIPELINE[3:])
        elif kind == "better_hotel":
            ctx.hotel_min_quality, ctx.hotel_id, ctx.hotel_price_ceiling = True, None, None
            replan(core.HOTEL_CHANGE_PIPELINE)
        elif kind == "change_hotel":
            h = nlu.mentioned_hotel(message, plan["catalog"]["hotels"] if ctx.is_world and plan.get("catalog") else catalog.hotels())
            if not h:
                follow_ups = ["hotel"]
                reply = "Which hotel? Options: " + ", ".join(x["name"] for x in plan.get("hotel_candidates", [])[:5])
                _save(user_id, trip_id, row, ctx, plan, message, reply)
                return _result(user_id, trip_id, row, ctx, plan, reply, steps, follow_ups, approval_hint)
            ctx.hotel_id = h["id"]
            old = plan["hotel"]["name"]
            replan(core.HOTEL_CHANGE_PIPELINE)
            notes.append(f"Changed hotel from {old} to {h['name']}; routes, travel times, restaurants, safety report and budget were recalculated.")
        elif kind == "more_sightseeing":
            ctx.extra_attractions += 2
            ctx.pace = "packed"
            replan(core.PLAN_PIPELINE[1:])
        elif kind == "reduce_travel":
            ctx.priority_preset = "sightseeing"
            ctx.hotel_id = None
            replan(core.PLAN_PIPELINE[2:])
        elif kind == "peaceful":
            ctx.peaceful = ctx.avoid_noisy = ctx.avoid_polluted = True
            ctx.hotel_id = None
            replan(core.PLAN_PIPELINE[1:])
        elif kind == "avoid_crowded":
            ctx.avoid_crowded = True
            replan(core.PLAN_PIPELINE[1:])
        elif kind == "change_transport":
            t = message.lower()
            ctx.chosen_route_index = None
            ctx.transport_pref = ("cheapest" if "cheap" in t else "fastest" if "fast" in t else "comfortable" if ("comfort" in t or "cab" in t or "taxi" in t or "convenien" in t) else
                                  "fastest" if "flight" in t else "cheapest" if ("bus" in t or "train" in t) else "comfortable")
            ctx.transport_explicit = True  # an explicit choice: the budget fallback must not override it
            replan(core.TRANSPORT_CHANGE_PIPELINE)
        elif kind in ("recalc_budget", "book"):
            replan(core.BUDGET_ONLY)
        elif kind == "add_restaurants":
            replan([core.FoodDiscoveryAgent])
            notes.append("Added restaurant shortlists near each day's stops.")
        elif kind == "explain":
            h = plan["hotel"]
            notes.append(f"{h['name']} scored {h['score']}/100. Factors: " + "; ".join(f"{f['factor']} {f['subscore']} (w {f['weight']}, {f['data_kind']})" for f in h["explanation"]["factors"]))
        elif kind == "safety":
            notes.append("Emergency numbers: " + ", ".join(f"{k} {v}" for k, v in plan["safety"]["emergency_contacts"].items()) + ". Safety indicators are estimated and not guarantees.")
        else:
            from . import tools as _t
            from ..services import guide as _guide
            if plan.get("itinerary") and _guide.is_packing_question(message):
                ans = _guide.packing(ctx, plan)  # from the forecast, air quality and the stops in the plan
            else:
                ans = gemini.answer(message, _t.facts_text(plan, ctx)) if plan.get("itinerary") else None  # grounded in this trip's data only
            notes.append(ans or "I can plan a trip, change hotel or travel mode, adjust the budget, or answer questions about your fares and schedule. What would you like?")
        failed = [s for s in steps if s["state"] == "failed"]
        reply = f"That change failed: {failed[0]['agent']} - {failed[0]['error']}" if failed else compose_reply(ctx, plan, notes) if "budget" in plan else "\n".join(notes)
        if kind in ("explain", "safety", "add_restaurants", "chat"):
            reply = "\n".join(notes)
    _save(user_id, trip_id, row, ctx, plan, message, reply)
    return _result(user_id, trip_id, row, ctx, plan, reply, steps, follow_ups, approval_hint, action)


def _save(user_id, trip_id, row, ctx, plan, message, reply):
    import json as _json
    title = f"{ctx.days or '?'}-day {ctx.destination or 'trip'}"
    if row:
        db.run("UPDATE trips SET context=?, plan=?, title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (ctx.model_dump_json(), _json.dumps(plan, default=str), title, row["id"]))
        tid = row["id"]
    else:
        tid = db.run("INSERT INTO trips(user_id,title,context,plan) VALUES(?,?,?,?)", (user_id, title, ctx.model_dump_json(), _json.dumps(plan, default=str)))
    db.run("INSERT INTO conversations(trip_id,user_id,role,content) VALUES(?,?,?,?)", (tid, user_id, "user", message))
    db.run("INSERT INTO conversations(trip_id,user_id,role,content) VALUES(?,?,?,?)", (tid, user_id, "assistant", reply))
    return tid


def _result(user_id, trip_id, row, ctx, plan, reply, steps, follow_ups, approval_hint, action=None):
    tid = row["id"] if row else db.one("SELECT id FROM trips WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))["id"]
    return {"trip_id": tid, "reply": reply, "context": ctx.model_dump(), "plan": plan, "workflow": steps,
            "action": action or ({"to": "/workspace"} if plan.get("itinerary") else None), "follow_ups": follow_ups, "questions": [QUESTIONS.get(f, "") for f in follow_ups], "approval_hint": approval_hint}


def _context_from_prefs(user_id: int) -> TripContext:
    """New trips start from the user's saved preferences (Profile page) so they are real defaults, not decoration."""
    import json as _json
    u = db.one("SELECT preferences FROM users WHERE id=?", (user_id,))
    try:
        prefs = _json.loads((u or {}).get("preferences") or "{}")
    except ValueError:
        prefs = {}
    ctx = TripContext()
    if prefs.get("vegetarian"):
        ctx.vegetarian = True
    if prefs.get("vegan"):
        ctx.vegan = ctx.vegetarian = True
    if prefs.get("pace") in ("relaxed", "balanced", "packed"):
        ctx.pace = prefs["pace"]
    if prefs.get("priority_preset") in ("family", "budget", "sightseeing", "peaceful"):
        ctx.priority_preset = prefs["priority_preset"]
    return ctx
