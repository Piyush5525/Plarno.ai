"""Plarno.ai API. Run: uvicorn app.main:app --reload"""
import csv
import io
import json
import re
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config, db, security
from .agents import core, orchestrator
from .agents.context import TripContext
from .data import seed
from .providers import telegram as ptelegram, nearby as pnearby, suggest as psuggest, geocode as pgeocode, serp_places as pserp, base as pbase, flights as pflights, gemini as pgemini, overpass as poverpass, staying as pstaying
from .services import routes as proutes, booking, budget, catalog, geo, guide, itinerary, live, matching, safety, transport

app = FastAPI(title="Plarno.ai", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    now = time.time()
    q = _hits[ip]
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MIN:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    q.append(now)
    return await call_next(request)


# ---------- auth ----------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)
    name: str | None = None


def user_dep(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    data = security.read_token(authorization[7:])
    if not data:
        raise HTTPException(401, "Invalid or expired token")
    u = db.one("SELECT id,email,name,role,preferences FROM users WHERE id=?", (data["uid"],))
    if not u:
        raise HTTPException(401, "Unknown user")
    return u


def admin_dep(u: dict = Depends(user_dep)) -> dict:
    if u["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return u


@app.post("/api/auth/register")
def register(c: Credentials):
    email = c.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Invalid email")
    if db.one("SELECT 1 x FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email already registered")
    role = "admin" if email in config.ADMIN_EMAILS else "user"
    uid = db.run("INSERT INTO users(email,password_hash,name,role) VALUES(?,?,?,?)", (email, security.hash_password(c.password), c.name, role))
    db.audit(uid, "register")
    return {"token": security.make_token(uid, role), "user": {"id": uid, "email": email, "name": c.name, "role": role}}


@app.post("/api/auth/login")
def login(c: Credentials):
    u = db.one("SELECT * FROM users WHERE email=?", (c.email.strip().lower(),))
    if not u or not security.verify_password(c.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    db.audit(u["id"], "login")
    return {"token": security.make_token(u["id"], u["role"]), "user": {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"]}}


@app.get("/api/me")
def me(u: dict = Depends(user_dep)):
    return {**u, "preferences": json.loads(u["preferences"] or "{}")}


@app.put("/api/me/preferences")
def set_prefs(prefs: dict, u: dict = Depends(user_dep)):
    allowed = {"vegetarian", "vegan", "pace", "currency", "language", "priority_preset", "weights", "share_location_consent", "trusted_contact", "emergency_name", "emergency_phone"}
    clean = {k: v for k, v in prefs.items() if k in allowed}
    for k in ("emergency_name", "emergency_phone", "trusted_contact"):
        if k in clean:
            clean[k] = str(clean[k] or "").strip()[:80]
    if clean.get("emergency_phone") and not re.fullmatch(r"\+?[\d\s().-]{6,20}", clean["emergency_phone"]):
        raise HTTPException(422, "Enter the emergency contact's phone number with digits only (a leading + is fine).")
    db.run("UPDATE users SET preferences=? WHERE id=?", (json.dumps(clean), u["id"]))
    return {"preferences": clean}


# ---------- conversational agent ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    trip_id: int | None = None


@app.post("/api/chat")
def chat(body: ChatIn, u: dict = Depends(user_dep)):
    if body.trip_id and not db.one("SELECT 1 x FROM trips WHERE id=? AND user_id=?", (body.trip_id, u["id"])):
        raise HTTPException(404, "Trip not found")
    return orchestrator.handle(u["id"], body.trip_id, body.message)


# ---------- trips ----------
def _trip(u, trip_id):
    r = db.one("SELECT * FROM trips WHERE id=? AND user_id=?", (trip_id, u["id"]))
    if not r:
        raise HTTPException(404, "Trip not found")
    return r, TripContext(**json.loads(r["context"])), json.loads(r["plan"] or "{}")


def _save_trip(trip_id, ctx, plan):
    db.run("UPDATE trips SET context=?, plan=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (ctx.model_dump_json(), json.dumps(plan, default=str), trip_id))


@app.get("/api/trips")
def trips(u: dict = Depends(user_dep)):
    return db.q("SELECT id,title,created_at,updated_at FROM trips WHERE user_id=? ORDER BY updated_at DESC", (u["id"],))


@app.get("/api/trips/{trip_id}")
def trip(trip_id: int, u: dict = Depends(user_dep)):
    r, ctx, plan = _trip(u, trip_id)
    msgs = db.q("SELECT role,content,created_at FROM conversations WHERE trip_id=? ORDER BY id", (trip_id,))
    return {"id": trip_id, "title": r["title"], "context": ctx.model_dump(), "plan": plan, "messages": msgs}


@app.delete("/api/trips/{trip_id}")
def del_trip(trip_id: int, u: dict = Depends(user_dep)):
    _trip(u, trip_id)
    db.run("DELETE FROM conversations WHERE trip_id=?", (trip_id,))
    db.run("DELETE FROM expenses WHERE trip_id=?", (trip_id,))
    db.run("DELETE FROM trips WHERE id=?", (trip_id,))
    return {"deleted": trip_id}


class RebuildIn(BaseModel):
    attraction_ids: list[str] | None = None
    hotel_id: str | None = None
    pace: str | None = None


@app.post("/api/trips/{trip_id}/itinerary/rebuild")
def rebuild(trip_id: int, body: RebuildIn, u: dict = Depends(user_dep)):
    """User edits (add/remove/reorder attractions, change hotel/pace) -> recompute routes, meals and budget."""
    _, ctx, plan = _trip(u, trip_id)
    if "itinerary" not in plan:
        raise HTTPException(409, "Trip has no plan yet")
    pool = plan["catalog"]["attractions"] if ctx.is_world and plan.get("catalog") else catalog.attractions()
    valid = {a["id"] for a in pool}
    if body.attraction_ids is not None:
        bad = [i for i in body.attraction_ids if i not in valid]
        if bad or not body.attraction_ids:
            raise HTTPException(422, f"Invalid attraction ids: {bad}" if bad else "Select at least one attraction")
        ctx.selected_attraction_ids = body.attraction_ids
        byid = {a["id"]: a for a in pool}
        plan["attractions"] = [byid[i] for i in body.attraction_ids]  # keeps the user's order
    if body.pace:
        if body.pace not in ("relaxed", "balanced", "packed"):
            raise HTTPException(422, "pace must be relaxed|balanced|packed")
        ctx.pace = body.pace
    pipeline = core.HOTEL_CHANGE_PIPELINE
    if body.hotel_id:
        ctx.hotel_id = body.hotel_id
    elif body.attraction_ids is not None:
        pipeline = [core.RouteOptimizationAgent, core.ItineraryAgent, core.FoodDiscoveryAgent, core.BudgetAgent, core.BookingAgent]
    steps = core.run_workflow(pipeline, ctx, plan)
    if any(s["state"] == "failed" for s in steps):
        raise HTTPException(422, next(s["error"] for s in steps if s["state"] == "failed"))
    _save_trip(trip_id, ctx, plan)
    return {"plan": plan, "workflow": steps}


# ---------- catalog / discovery ----------
@app.get("/api/destinations")
def destinations(category: str | None = None, area: str | None = None, tag: str | None = None):
    return {"cities": [{"name": k, "lat": v[0], "lon": v[1]} for k, v in seed.CITIES.items()],
            "attractions": catalog.attractions(category, area, [tag] if tag else None)}


@app.get("/api/neighbourhoods")
def neighbourhoods(preset: str | None = None, attractions: str | None = None):
    sel = [a for a in catalog.attractions() if not attractions or a["id"] in attractions.split(",")]
    w = catalog.PRESETS.get(preset or "", None)
    stats = {"quality": 0.7, "food": 0.7, "price_fit": 0.7}
    return sorted((catalog.score_neighbourhood(n, sel, stats, w) for n in catalog.neighbourhoods()), key=lambda r: -r["score"])


class ScoreIn(BaseModel):
    weights: dict[str, float]
    attraction_ids: list[str] = []


@app.post("/api/neighbourhoods/score")
def score_custom(body: ScoreIn):
    if any(k not in catalog.DEFAULT_WEIGHTS for k in body.weights) or any(v < 0 for v in body.weights.values()):
        raise HTTPException(422, f"weights must be >=0 and keys in {list(catalog.DEFAULT_WEIGHTS)}")
    return neighbourhoods(None, ",".join(body.attraction_ids) or None) if not body.weights else sorted(
        (catalog.score_neighbourhood(n, [a for a in catalog.attractions() if a["id"] in body.attraction_ids], {"quality": 0.7, "food": 0.7, "price_fit": 0.7}, body.weights)
         for n in catalog.neighbourhoods()), key=lambda r: -r["score"])


@app.get("/api/hotels")
def hotels(nights: int = 4, budget_per_night: float | None = None, travellers: int = 2, preset: str | None = None, attractions: str | None = None):
    if nights < 1 or travellers < 1:
        raise HTTPException(422, "nights and travellers must be >= 1")
    sel = [a for a in catalog.attractions() if not attractions or a["id"] in attractions.split(",")]
    return catalog.rank_hotels(nights, budget_per_night, catalog.PRESETS.get(preset or ""), sel, travellers)


@app.get("/api/restaurants")
def restaurants(veg: bool = False, vegan: bool = False, max_price_for_two: float | None = None, near_lat: float | None = None, near_lon: float | None = None):
    out = catalog.restaurants()
    if veg:
        out = [r for r in out if r["veg"]]
    if vegan:
        out = [r for r in out if r["vegan"]]
    if max_price_for_two:
        out = [r for r in out if r["price_for_two"] <= max_price_for_two]
    if near_lat is not None and near_lon is not None:
        for r in out:
            r["distance_km"] = round(geo.haversine_km((near_lat, near_lon), (r["lat"], r["lon"])), 2)
        out.sort(key=lambda r: r["distance_km"])
    return out


@app.get("/api/safety")
def safety_info(city: str = "Delhi", lat: float | None = None, lon: float | None = None, neighbourhood: str | None = None):
    try:
        rep = safety.destination_safety(city, lat, lon)
        if neighbourhood:
            rep["neighbourhood_report"] = safety.neighbourhood_report(neighbourhood)
        return rep
    except KeyError:
        raise HTTPException(404, "Unknown neighbourhood")


@app.get("/api/transport/search")
def transport_search(origin: str, destination: str, date: str, travellers: int = 1, live_flights: bool = False):
    if travellers < 1 or travellers > 20:
        raise HTTPException(422, "travellers must be 1..20")
    try:
        return transport.search_journeys(origin, destination, date, travellers, live_flights)
    except ValueError as e:
        raise HTTPException(422, str(e))


class RouteIn(BaseModel):
    attraction_ids: list[str] = Field(min_length=1)
    start_lat: float | None = None
    start_lon: float | None = None


@app.post("/api/route/optimize")
def route_optimize(body: RouteIn):
    by_id = {a["id"]: a for a in catalog.attractions()}
    if any(i not in by_id for i in body.attraction_ids):
        raise HTTPException(422, "Unknown attraction id")
    sel = [by_id[i] for i in body.attraction_ids]
    pts = [(a["lat"], a["lon"]) for a in sel]
    start = (body.start_lat, body.start_lon) if body.start_lat is not None and body.start_lon is not None else None
    order = geo.optimize_order(pts, start)
    seq = ([start] if start else []) + [pts[i] for i in order]
    legs = [geo.route(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]
    return {"order": [sel[i]["id"] for i in order], "names": [sel[i]["name"] for i in order], "legs": legs,
            "total_km": round(sum(l["distance_km"] for l in legs), 1), "total_min": round(sum(l["duration_min"] for l in legs)),
            "naive_km": round(geo.path_length(pts, list(range(len(pts)))), 1)}


# ---------- budget ----------
class ExpenseIn(BaseModel):
    category: str
    amount: float = Field(gt=0)
    paid_by: str
    note: str | None = None


@app.post("/api/trips/{trip_id}/expenses")
def add_expense(trip_id: int, e: ExpenseIn, u: dict = Depends(user_dep)):
    _trip(u, trip_id)
    eid = db.run("INSERT INTO expenses(trip_id,user_id,category,amount,paid_by,note) VALUES(?,?,?,?,?,?)", (trip_id, u["id"], e.category, e.amount, e.paid_by, e.note))
    return {"id": eid}


@app.get("/api/trips/{trip_id}/budget")
def trip_budget(trip_id: int, members: str = "", u: dict = Depends(user_dep)):
    _, ctx, plan = _trip(u, trip_id)
    exps = db.q("SELECT category,amount,paid_by,note FROM expenses WHERE trip_id=?", (trip_id,))
    confirmed = sum(b["amount"] for b in db.q("SELECT amount FROM bookings WHERE trip_id=? AND status LIKE 'SIMULATED_CONFIRMED'", (trip_id,)))
    b = budget.compute(max(ctx.travellers, 1), ctx.nights, plan.get("hotel"), plan.get("journey"), plan.get("itinerary"), ctx.budget_inr, True, confirmed, exps)
    split = budget.split_expenses(exps, [m.strip() for m in members.split(",") if m.strip()]) if members else None
    return {**b, "expenses": exps, "split": split}


# ---------- booking (approval-gated) ----------
@app.post("/api/trips/{trip_id}/booking/prepare")
def booking_prepare(trip_id: int, u: dict = Depends(user_dep)):
    _, ctx, plan = _trip(u, trip_id)
    items = booking.prepare_items(plan)
    if not items:
        raise HTTPException(409, "Nothing to book yet")
    return {**booking.request_approval(u["id"], trip_id, "book", {"items": items, "total_inr": sum(i["amount_inr"] for i in items)}),
            "notice": "SIMULATED booking service. Review details and approve explicitly; nothing is booked until then."}


class DecideIn(BaseModel):
    approve: bool
    idempotency_key: str = Field(min_length=8, max_length=100)


@app.post("/api/approvals/{approval_id}/decide")
def decide(approval_id: int, body: DecideIn, u: dict = Depends(user_dep)):
    try:
        res = booking.decide(u["id"], approval_id, body.approve, body.idempotency_key)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    ap = db.one("SELECT * FROM approvals WHERE id=?", (approval_id,))
    if res["status"] == "approved" and not res.get("replayed") and ap["kind"] == "rebook" and ap["trip_id"]:
        _apply_recovery(ap["trip_id"], u, json.loads(ap["payload"]))
    return res


@app.get("/api/approvals")
def approvals(u: dict = Depends(user_dep)):
    return [{**a, "payload": json.loads(a["payload"])} for a in db.q("SELECT * FROM approvals WHERE user_id=? ORDER BY id DESC", (u["id"],))]


@app.get("/api/bookings")
def bookings(u: dict = Depends(user_dep)):
    return [{**b, "details": json.loads(b["details"] or "{}"), "simulated": bool(b["simulated"])} for b in db.q("SELECT * FROM bookings WHERE user_id=? ORDER BY id DESC", (u["id"],))]


@app.post("/api/bookings/{booking_id}/cancel-request")
def cancel_request(booking_id: int, u: dict = Depends(user_dep)):
    b = db.one("SELECT * FROM bookings WHERE id=? AND user_id=?", (booking_id, u["id"]))
    if not b:
        raise HTTPException(404, "Booking not found")
    if b["status"] == "SIMULATED_CANCELLED":
        raise HTTPException(409, "Already cancelled")
    return {**booking.request_approval(u["id"], b["trip_id"], "cancel", {"booking_id": booking_id, "item": b["item"], "policy": b["cancellation_policy"]}),
            "notice": "Cancellation needs your explicit approval. Policy: " + (b["cancellation_policy"] or "unknown")}


# ---------- disruption recovery ----------
class DelayIn(BaseModel):
    delay_min: int = Field(gt=0, le=72 * 60)


@app.post("/api/trips/{trip_id}/recovery/propose")
def recovery_propose(trip_id: int, body: DelayIn, u: dict = Depends(user_dep)):
    _, ctx, plan = _trip(u, trip_id)
    try:
        prop = core.TravelRecoveryAgent().propose(plan, body.delay_min)
    except ValueError as e:
        raise HTTPException(409, str(e))
    plan["pending_recovery"] = prop
    _save_trip(trip_id, ctx, plan)
    return prop


class OptionIn(BaseModel):
    option_id: str


@app.post("/api/trips/{trip_id}/recovery/request-approval")
def recovery_request(trip_id: int, body: OptionIn, u: dict = Depends(user_dep)):
    _, ctx, plan = _trip(u, trip_id)
    prop = plan.get("pending_recovery")
    opt = next((o for o in (prop or {}).get("options", []) if o["id"] == body.option_id), None)
    if not opt:
        raise HTTPException(404, "No such recovery option")
    bk = db.one("SELECT id FROM bookings WHERE trip_id=? AND category='transport' AND status LIKE 'SIMULATED_%' AND status!='SIMULATED_CANCELLED'", (trip_id,))
    return booking.request_approval(u["id"], trip_id, "rebook", {"option": opt, "affected": prop["affected_activities"], "booking_id": bk["id"] if bk else None,
                                                                 "new_item": opt.get("journey", {}).get("summary")})


def _apply_recovery(trip_id: int, u: dict, payload: dict):
    _, ctx, plan = _trip(u, trip_id)
    opt = payload["option"]
    if opt.get("journey"):
        plan["journey"] = opt["journey"]
    names = {a["name"] for a in payload["affected"]}
    for d in plan["itinerary"]["days"][:1]:
        for s in d["stops"]:
            if s["name"] in names:
                s["status"] = "needs_reschedule"
    plan["pending_recovery"] = None
    core.run_workflow([core.BudgetAgent, core.BookingAgent], ctx, plan)
    _save_trip(trip_id, ctx, plan)


# ---------- supplier intelligence (admin) ----------
def _listings(uploaded: list[dict] | None = None) -> list[dict]:
    base = [matching.listing_dict(r) for r in seed.SUPPLIER_LISTINGS]
    for up in db.q("SELECT records FROM supplier_uploads"):
        base += json.loads(up["records"])
    return base


def _decisions():
    rej, forced = set(), set()
    for d in db.q("SELECT a,b,decision FROM match_decisions ORDER BY id"):
        k = frozenset((d["a"], d["b"]))
        if d["decision"] == "reject":
            rej.add(k)
            forced.discard(k)
        else:
            forced.add(k)
            rej.discard(k)
    return rej, forced


class UploadIn(BaseModel):
    supplier: str
    format: str = "json"  # json | csv
    data: str


REQ = ["listing_id", "name", "lat", "lon", "room", "beds", "occupancy", "meal", "price"]


@app.post("/api/admin/suppliers/upload")
def supplier_upload(body: UploadIn, a: dict = Depends(admin_dep)):
    try:
        rows = json.loads(body.data) if body.format == "json" else list(csv.DictReader(io.StringIO(body.data)))
    except Exception as e:
        raise HTTPException(422, f"Cannot parse: {e}")
    clean, errors = [], []
    for i, r in enumerate(rows):
        miss = [k for k in REQ if r.get(k) in (None, "")]
        if miss:
            errors.append({"row": i, "missing": miss})
            continue
        try:
            clean.append({"supplier": body.supplier, "listing_id": str(r["listing_id"]), "name": str(r["name"]), "lat": float(r["lat"]), "lon": float(r["lon"]),
                          "room": str(r["room"]), "beds": str(r["beds"]), "occupancy": int(r["occupancy"]), "meal": str(r["meal"]), "price": float(r["price"]), "truth": r.get("truth", "")})
        except (ValueError, TypeError) as e:
            errors.append({"row": i, "error": str(e)})
    if clean:
        db.run("INSERT INTO supplier_uploads(supplier,records) VALUES(?,?)", (body.supplier, json.dumps(clean)))
    db.audit(a["id"], "supplier_upload", {"supplier": body.supplier, "accepted": len(clean), "rejected": len(errors)})
    return {"accepted": len(clean), "rejected": errors}


@app.get("/api/admin/matching")
def admin_matching(a: dict = Depends(admin_dep)):
    rej, forced = _decisions()
    res = matching.cluster_listings(_listings(), rejected=rej, forced=forced)
    for c in res["clusters"]:
        c["rooms"] = [[m["listing_id"] for m in g] for g in matching.match_rooms(c["members"])]
        c["ranked_offers"] = matching.rank_offers(c["members"])
    return res


class DecisionIn(BaseModel):
    a: str
    b: str
    decision: str = Field(pattern="^(approve|reject)$")


@app.post("/api/admin/matching/decision")
def admin_decision(body: DecisionIn, a: dict = Depends(admin_dep)):
    db.run("INSERT INTO match_decisions(a,b,decision,admin_id) VALUES(?,?,?,?)", (body.a, body.b, body.decision, a["id"]))
    db.audit(a["id"], "match_decision", body.model_dump())
    return {"ok": True}


@app.get("/api/admin/evaluation")
def admin_eval(a: dict = Depends(admin_dep)):
    return matching.evaluate([matching.listing_dict(r) for r in seed.SUPPLIER_LISTINGS])


@app.get("/api/admin/agent-logs")
def agent_logs(a: dict = Depends(admin_dep)):
    return db.q("SELECT * FROM agent_logs ORDER BY id DESC LIMIT 200")


@app.get("/api/health")
def health():
    return {"status": "ok", "data_mode": "simulated", "llm": config.LLM_PROVIDER, "routing": config.ROUTING_PROVIDER}


@app.get("/api/config")
def public_config():
    """Only values safe for the browser. The Mapbox pk. token is a public token by design; all other keys stay server-side."""
    return {"mapbox_token": config.MAPBOX_TOKEN or None, "live": {"aqi": bool(config.AQICN_KEY) and not config.OFFLINE,
            "weather": bool(config.OPENWEATHER_KEY) and not config.OFFLINE, "routing": bool(config.MAPBOX_TOKEN) and not config.OFFLINE}}


class DirIn(BaseModel):
    points: list[tuple[float, float]] = Field(min_length=2, max_length=25)  # (lat, lon)
    profile: str = Field(default="driving", pattern="^(driving|walking|cycling)$")


@app.post("/api/route/directions")
def route_directions(body: DirIn):
    r = live.directions(body.points, body.profile)
    if r:
        return r
    legs = [geo.route(body.points[i], body.points[i + 1]) for i in range(len(body.points) - 1)]
    return {"distance_km": round(sum(l["distance_km"] for l in legs), 1), "duration_min": round(sum(l["duration_min"] for l in legs)),
            "geometry": [[lo, la] for la, lo in body.points], "provenance": legs[0]["provenance"]}


@app.get("/api/places/nearby")
def places_nearby(category: str, lat: float = 28.6139, lon: float = 77.2090, radius_m: int | None = None):
    if category not in poverpass.QUERIES:
        raise HTTPException(422, f"category must be one of {list(poverpass.QUERIES)}")
    if radius_m is not None and not 100 <= radius_m <= 15000:
        raise HTTPException(422, "radius_m must be 100..15000")
    return poverpass.nearby(category, lat, lon, radius_m)


@app.get("/api/hotels/provider")
def hotels_provider(location: str = "New Delhi, India", check_in: str = "2026-12-05", check_out: str = "2026-12-09", adults: int = 2):
    """Raw provider search (StayingAPI). Sandbox results are flagged and are not used in recommendations."""
    return pstaying.search(location, check_in, check_out, adults)


@app.get("/api/providers/health")
def providers_health(check: bool = False):
    """Configuration + (optionally) a cheap connectivity probe per provider. Never returns key values."""
    def row(name, configured, role, note=None, status=None, key=None):
        o = pbase.last_outcome.get(key or "", None)
        st = status or ("no key" if not configured else "degraded" if (o and not o["ok"]) else "verified" if (o and o["ok"]) else "ready (not yet used)")
        if o and not o["ok"]:
            note = f"{note + '. ' if note else ''}Last attempt failed ({o.get('error')}) at {o['at']}"
        return {"provider": name, "configured": bool(configured), "role": role, "status": st, "note": note}
    out = [row("Gemini", config.GEMINI_KEY, "language understanding, grounded Q&A", f"model {pgemini.MODEL}"),
           row("OpenWeather", config.OPENWEATHER_KEY, "current weather"), row("AQICN", config.AQICN_KEY, "air quality"),
           row("SerpApi Google Maps", config.SERP_KEY, "worldwide places and restaurants", key="serpplaces"), row("SerpApi Google Hotels", config.SERP_KEY, "worldwide hotel rates", key="serphotels"),
           row("Nominatim (OpenStreetMap)", True, "place geocoding", key="nominatim"),
           row("Mapbox", config.MAPBOX_TOKEN, "map tiles, road directions"),
           row("SerpApi Google Flights", config.SERP_FLIGHTS_KEY, "flight search", f"shared guard {config.SERP_DAILY_CAP} SerpApi searches/day", key="serpflights"),
           row("StayingAPI", config.STAYING_KEY, "hotel search", "SANDBOX key: fixture data only, not used for recommendations" if pstaying.is_sandbox() else None,
               "sandbox" if pstaying.is_sandbox() else None),
           row("OpenStreetMap Overpass", True, "optional nearby places (Delhi demo)", "public servers; circuit breaker + 7-day cache" + ("; cooling down after failures" if pbase.breaker_open("overpass") else ""), key="overpass"),
           row("Qrail", config.QRAIL_KEY, "Indian railways", "Not integrated: API host/docs unknown. Provide documentation URL.", "not integrated" if config.QRAIL_KEY else None),
           row("RapidAPI", config.RAPIDAPI_KEY, "unspecified", "Not integrated: subscribed API hosts unknown.", "not integrated" if config.RAPIDAPI_KEY else None)]
    if check and not config.OFFLINE:
        acc = pstaying.account()
        for r in out:
            if r["provider"] == "StayingAPI" and acc:
                r["note"] = f"{acc['plan']} ({acc['env']}), {acc['credits']} credits, {acc['rpm']} req/min"
    return out


@app.get("/api/geocode")
def geocode_endpoint(q: str):
    g = pgeocode.resolve(q)
    if not g:
        raise HTTPException(404, f"No place found for '{q}'")
    return g


@app.get("/api/world/discover")
def world_discover(city: str, kind: str = "attractions", interest: str | None = None, nights: int = 3, adults: int = 2, check_in: str | None = None):
    """Real places/hotels for any city worldwide (Google Maps / Google Hotels via SerpApi). Cached; guarded by a shared daily quota."""
    if kind not in ("attractions", "restaurants", "hotels"):
        raise HTTPException(422, "kind must be attractions|restaurants|hotels")
    if not 1 <= nights <= 30:
        raise HTTPException(422, "nights must be 1..30")
    g = pgeocode.resolve(city)
    if not g:
        raise HTTPException(404, f"I couldn't find a place called '{city}'. Try the city name, optionally with the country.")
    if kind == "hotels":
        from datetime import date, timedelta
        try:
            start = date.fromisoformat(check_in) if check_in else date.today() + timedelta(days=14)
        except ValueError:
            raise HTTPException(422, "check_in must be YYYY-MM-DD")
        if start < date.today():
            raise HTTPException(422, "check_in cannot be in the past")
        ci, co = start.isoformat(), (start + timedelta(days=nights)).isoformat()
        r = pserp.hotels(g["name"], ci, co, adults)
        return {"geo": g, "kind": kind, "hotels": r["hotels"], "dates": [ci, co], "provenance": r["provenance"], "error": r.get("error")}
    r = pserp.places(kind, g["name"], g["lat"], g["lon"], interest)
    return {"geo": g, "kind": kind, "places": r["places"], "provenance": r["provenance"], "error": r.get("error")}


@app.get("/api/geocode/suggest")
def geocode_suggest(q: str = "", limit: int = 8):
    if len(q) > 80:
        raise HTTPException(422, "query too long")
    return psuggest.suggest(q, max(1, min(limit, 10)))


@app.get("/api/routes/options")
def routes_options(origin: str, destination: str, date: str, travellers: int = 1, budget: float | None = None, trip: str = "one_way",
                   origin_lat: float | None = None, origin_lon: float | None = None, dest_lat: float | None = None, dest_lon: float | None = None):
    """Door-to-door ways to travel between ANY two places: live flights (+ transfers to the nearest airports), cab, bus, train between real stations.
    `budget` is the money for THIS journey (all travellers), compared with the one-way or the round-trip cost according to `trip`.
    Coordinates, when given (a picked suggestion or "my location"), are used exactly instead of looking the name up again."""
    if trip not in ("one_way", "round_trip"):
        raise HTTPException(422, "trip must be one_way or round_trip")
    if budget is not None and budget <= 0:
        raise HTTPException(422, "budget must be positive")
    from datetime import date as _d
    if not 1 <= travellers <= 20:
        raise HTTPException(422, "travellers must be 1..20")
    try:
        when = _d.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    if when < _d.today():
        raise HTTPException(422, "date cannot be in the past")
    og = pgeocode.at(origin_lat, origin_lon, origin) if origin_lat is not None and origin_lon is not None else pgeocode.resolve(origin)
    dg = pgeocode.at(dest_lat, dest_lon, destination) if dest_lat is not None and dest_lon is not None else pgeocode.resolve(destination)
    if not og:
        raise HTTPException(404, f"I couldn't find a place called '{origin}'.")
    if not dg:
        raise HTTPException(404, f"I couldn't find a place called '{destination}'.")
    res = proutes.build_options(og, dg, date, travellers, budget, budget_basis=trip, budget_share=None)
    for opt in res.get("options", []):  # a ride from/to a specific spot (a college, a station) is labelled with that spot, not just its town
        first, last = opt["legs"][0], opt["legs"][-1]
        if og.get("spot") and first["mode"] == "cab" and first["from"] == og["name"]:
            first["from"] = opt["via"][0] = og["spot"]
        if dg.get("spot") and last["mode"] == "cab" and last["to"] == dg["name"]:
            last["to"] = opt["via"][-1] = dg["spot"]
        if og.get("spot"):  # "24 km from Jaipur" reads wrong when the start is a campus in Jaipur
            opt["notes"] = [n.replace(f"from {og['name']}.", f"from {og['spot']}.").replace(f"station to {og['name']}:", f"station to {og['spot']}:") for n in opt["notes"]]
    keys = ("name", "display", "lat", "lon", "country", "country_code", "spot")
    return {"origin": {k: og.get(k) for k in keys}, "destination": {k: dg.get(k) for k in keys}, "date": date, "trip": trip, **res}


@app.get("/api/geocode/reverse")
def geocode_reverse(lat: float, lon: float):
    """Name for a point (used by "Use my location"). The coordinates never leave this request: nothing is stored."""
    g = pgeocode.at(lat, lon, None)
    if not g:
        raise HTTPException(404, "Could not work out where that is. Type the place instead.")
    label = ", ".join(dict.fromkeys(p.strip() for p in (g["display"] or g["name"]).split(",") if p.strip()))  # "Jaipur, Jaipur, Rajasthan" -> "Jaipur, Rajasthan"
    return {"name": g["name"], "label": label, "lat": lat, "lon": lon, "country_code": g["country_code"]}


@app.get("/api/live")
def live_conditions(lat: float, lon: float):
    """Live weather, air quality, 5-day forecast and local clock offset for any point. Missing pieces are null, never guessed."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "lat/lon out of range")
    return guide.snapshot(lat, lon)


@app.get("/api/trips/{trip_id}/guide")
def trip_guide(trip_id: int, ai: bool = True, u: dict = Depends(user_dep)):
    """Live guide for a planned trip: conditions now, forecast matched to itinerary days, smart tips, recommendations and an AI briefing."""
    _, ctx, plan = _trip(u, trip_id)
    if "itinerary" not in plan:
        raise HTTPException(409, "Trip has no plan yet")
    world_cat = plan.get("catalog") if ctx.is_world else None
    pool = world_cat["attractions"] if world_cat else catalog.attractions()
    rest = world_cat["restaurants"] if world_cat else catalog.restaurants()
    return guide.build(ctx, plan, pool, rest, ai)


@app.get("/api/nearby")
def nearby_places(lat: float, lon: float, kind: str = "pharmacy"):
    """Essentials near a point: pharmacy | hospital | grocery | supermarket | atm | police. Real listings with distance, address and phone when listed."""
    if kind not in pnearby.KINDS:
        raise HTTPException(422, f"kind must be one of {list(pnearby.KINDS)}")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "lat/lon out of range")
    return pnearby.search(kind, lat, lon)


# ---------- emergency alert (SOS) ----------
_sos: dict[int, dict] = {}   # user id -> the live alert in progress {message_id, started, last, until}
SOS_MINUTES = 15


class SosIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=200)
    test: bool = False


def _prefs(u: dict) -> dict:
    return json.loads(u.get("preferences") or "{}")


@app.get("/api/sos/status")
def sos_status(u: dict = Depends(user_dep)):
    p, cur = _prefs(u), _sos.get(u["id"])
    active = bool(cur and cur["until"] > time.time())
    return {"configured": ptelegram.available(), "channel": "Telegram", "contact": {"name": p.get("emergency_name") or "", "phone": p.get("emergency_phone") or ""},
            "active": active, "seconds_left": max(0, int(cur["until"] - time.time())) if active else 0, "minutes": SOS_MINUTES}


@app.post("/api/sos")
def sos_send(body: SosIn, u: dict = Depends(user_dep)):
    """Sends an emergency alert with the person's live location. Only ever triggered by the signed-in person pressing the button."""
    if not ptelegram.available():
        raise HTTPException(503, "Emergency alerts are not set up on this server yet. Call the local emergency number instead.")
    cur = _sos.get(u["id"])
    if cur and time.time() - cur["started"] < 20:
        raise HTTPException(429, "An alert was sent a moment ago. Your location is still being shared.")
    p = _prefs(u)
    who = (u.get("name") or "").strip() or u["email"]
    place = pgeocode.at(body.lat, body.lon, None)
    maps = f"https://www.google.com/maps?q={body.lat:.6f},{body.lon:.6f}"
    lines = [("TEST ALERT (no action needed)" if body.test else "EMERGENCY ALERT") + " from Plarno.ai", "",
             f"{who} pressed the SOS button" + (" to test the alert." if body.test else " and may need help."),
             f"Account: {u['email']}"]
    if p.get("emergency_name") or p.get("emergency_phone"):
        lines.append("Emergency contact on file: " + " ".join(x for x in (p.get("emergency_name"), p.get("emergency_phone")) if x))
    else:
        lines.append("Emergency contact on file: none saved")
    if body.note:
        lines.append(f"Message: {body.note.strip()}")
    lines += ["", "Location: " + (place["display"] if place else "(name not available)"), f"Coordinates: {body.lat:.5f}, {body.lon:.5f}" + (f" (accurate to about {round(body.accuracy_m)} m)" if body.accuracy_m else ""),
              f"Open in Google Maps: {maps}", "", f"Sent {time.strftime('%d %b %Y %H:%M UTC', time.gmtime())}. A live location follows and updates for up to {SOS_MINUTES} minutes while their app stays open."]
    try:
        ptelegram.send_text("\n".join(lines))
        mid = ptelegram.send_live_location(body.lat, body.lon, SOS_MINUTES)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    now = time.time()
    _sos[u["id"]] = {"message_id": mid, "started": now, "last": now, "until": now + SOS_MINUTES * 60}
    db.audit(u["id"], "sos_test" if body.test else "sos", {"lat": round(body.lat, 4), "lon": round(body.lon, 4)})
    return {"sent": True, "channel": "Telegram", "minutes": SOS_MINUTES, "place": place["display"] if place else None, "maps_url": maps}


@app.post("/api/sos/update")
def sos_update(body: SosIn, u: dict = Depends(user_dep)):
    cur = _sos.get(u["id"])
    if not cur or cur["until"] < time.time():
        raise HTTPException(409, "No alert is active.")
    if time.time() - cur["last"] < 8:
        return {"updated": False, "seconds_left": int(cur["until"] - time.time())}
    try:
        ptelegram.update_live_location(cur["message_id"], body.lat, body.lon)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    cur["last"] = time.time()
    return {"updated": True, "seconds_left": int(cur["until"] - time.time())}


@app.post("/api/sos/stop")
def sos_stop(u: dict = Depends(user_dep)):
    cur = _sos.pop(u["id"], None)
    if cur and ptelegram.available():
        ptelegram.stop_live_location(cur["message_id"])
        try:
            ptelegram.send_text(f"{(u.get('name') or '').strip() or u['email']} stopped sharing their location and marked themselves safe.")
        except RuntimeError:
            pass
    return {"stopped": bool(cur)}


class JourneyIn(BaseModel):
    index: int = Field(ge=0)


@app.post("/api/trips/{trip_id}/journey")
def choose_journey(trip_id: int, body: JourneyIn, u: dict = Depends(user_dep)):
    """Pick one of the trip's route options; budget and bookings are recalculated. Changes nothing outside the plan (no purchases)."""
    _, ctx, plan = _trip(u, trip_id)
    opts = (plan.get("route_options") or {}).get("options") or []
    if body.index >= len(opts):
        raise HTTPException(422, "No such route option")
    ctx.chosen_route_index, ctx.transport_explicit = body.index, True
    steps = core.run_workflow(core.TRANSPORT_CHANGE_PIPELINE, ctx, plan)
    if any(x["state"] == "failed" for x in steps):
        raise HTTPException(422, next(x["error"] for x in steps if x["state"] == "failed"))
    _save_trip(trip_id, ctx, plan)
    return {"plan": plan, "workflow": steps}
