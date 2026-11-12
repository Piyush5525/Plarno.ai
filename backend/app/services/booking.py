"""Booking orchestration with a human-approval gate and idempotency.
SAFETY RULES: agents can only *prepare* items and *request* approval. A booking row is only created by `approve()`,
called from an authenticated user action. The provider here is the MOCK provider: results are labelled SIMULATED, reference
prefix 'SIM-', and no real reservation/payment ever occurs. Card data is never accepted or stored."""
import json
import secrets

from .. import db
from ..provenance import now_iso

CANCEL_POLICY_DEFAULT = "Simulated policy: free cancellation up to 48h before start; afterwards 1 night / 1 fare retained."


class MockBookingProvider:
    name = "mock-booking (SIMULATED)"
    simulated = True

    def confirm(self, item: dict) -> dict:
        return {"reference": "SIM-" + secrets.token_hex(4).upper(), "status": "SIMULATED_CONFIRMED", "provider": self.name}

    def cancel(self, reference: str) -> dict:
        return {"status": "SIMULATED_CANCELLED", "reference": reference}


provider = MockBookingProvider()


def prepare_items(trip_plan: dict) -> list[dict]:
    items = []
    j = trip_plan.get("journey")
    if j:
        items.append({"category": "transport", "supplier": j["legs"][0]["operator"], "item": j["summary"],
                      "travel_dates": [j["legs"][0]["depart"], j["legs"][-1]["arrive"]], "amount_inr": j["total_fare_inr"],
                      "additional_charges": "Included in estimate (≈5%)", "cancellation_policy": CANCEL_POLICY_DEFAULT,
                      "terms": "Simulated product. Real fare/availability must be validated with the provider before payment."})
    h = trip_plan.get("hotel")
    if h:
        items.append({"category": "hotel", "supplier": "mock-supplier", "item": h["name"], "travel_dates": trip_plan.get("dates"),
                      "amount_inr": h["total_price"], "additional_charges": "Taxes may apply (not modelled)",
                      "cancellation_policy": CANCEL_POLICY_DEFAULT, "terms": "Simulated rate; availability unverified."})
    for it in items:
        it["travellers"] = trip_plan.get("travellers")
        it["simulated"] = True
    return items


def request_approval(user_id: int, trip_id: int | None, kind: str, payload: dict) -> dict:
    if kind not in ("book", "cancel", "modify", "rebook"):
        raise ValueError("invalid approval kind")
    aid = db.run("INSERT INTO approvals(user_id,trip_id,kind,payload) VALUES(?,?,?,?)", (user_id, trip_id, kind, json.dumps(payload, default=str)))
    db.audit(user_id, "approval_requested", {"id": aid, "kind": kind})
    return {"approval_id": aid, "status": "pending", "kind": kind, "payload": payload}


def decide(user_id: int, approval_id: int, approve: bool, idempotency_key: str) -> dict:
    ap = db.one("SELECT * FROM approvals WHERE id=? AND user_id=?", (approval_id, user_id))
    if not ap:
        raise KeyError("approval not found")
    if ap["status"] != "pending":  # idempotent replay -> return prior outcome, never double-execute
        bks = db.q("SELECT * FROM bookings WHERE approval_id=?", (approval_id,))
        return {"approval_id": approval_id, "status": ap["status"], "replayed": True, "bookings": bks}
    if not idempotency_key or len(idempotency_key) < 8:
        raise ValueError("idempotency_key (>=8 chars) required")
    db.run("UPDATE approvals SET status=?, decided_at=?, idempotency_key=? WHERE id=? AND status='pending'",
           ("approved" if approve else "rejected", now_iso(), idempotency_key, approval_id))
    db.audit(user_id, "approval_decided", {"id": approval_id, "approve": approve})
    if not approve:
        return {"approval_id": approval_id, "status": "rejected", "bookings": []}
    payload = json.loads(ap["payload"])
    created = []
    if ap["kind"] == "book":
        for item in payload["items"]:
            res = provider.confirm(item)
            bid = db.run(
                "INSERT INTO bookings(user_id,trip_id,approval_id,category,supplier,item,amount,status,simulated,reference,cancellation_policy,details) VALUES(?,?,?,?,?,?,?,?,1,?,?,?)",
                (user_id, ap["trip_id"], approval_id if not created else None, item["category"], item["supplier"], item["item"], item["amount_inr"],
                 res["status"], res["reference"], item["cancellation_policy"], json.dumps(item, default=str)))
            created.append(bid)
    elif ap["kind"] == "cancel":
        b = db.one("SELECT * FROM bookings WHERE id=? AND user_id=?", (payload["booking_id"], user_id))
        if not b:
            raise KeyError("booking not found")
        provider.cancel(b["reference"])
        db.run("UPDATE bookings SET status='SIMULATED_CANCELLED' WHERE id=?", (b["id"],))
    elif ap["kind"] in ("modify", "rebook"):
        if payload.get("booking_id"):
            b = db.one("SELECT * FROM bookings WHERE id=? AND user_id=?", (payload["booking_id"], user_id))
            if not b:
                raise KeyError("booking not found")
            db.run("UPDATE bookings SET status='SIMULATED_MODIFIED', item=? WHERE id=?", (payload.get("new_item", b["item"]), b["id"]))
    return {"approval_id": approval_id, "status": "approved", "simulated": True,
            "notice": "SIMULATED: no real reservation or payment was made.",
            "bookings": db.q("SELECT * FROM bookings WHERE trip_id IS ? AND user_id=?", (ap["trip_id"], user_id))}
