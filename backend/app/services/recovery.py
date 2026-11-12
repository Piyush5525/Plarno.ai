"""Disruption handling. Produces an explained proposal; executing it requires a user approval (booking.decide)."""
from datetime import datetime, timedelta

from . import transport

CHECKIN_BUFFER_MIN = 90  # arrival -> hotel -> ready to go out (estimate)


def handle_delay(plan: dict, delay_min: int, date: str) -> dict:
    j = plan.get("journey")
    it = plan.get("itinerary")
    if not j or not it:
        raise ValueError("Trip has no journey/itinerary to disrupt")
    if delay_min <= 0:
        raise ValueError("delay_min must be positive")
    orig_arrive = datetime.fromisoformat(j["legs"][-1]["arrive"])
    new_arrive = orig_arrive + timedelta(minutes=delay_min)
    ready = new_arrive + timedelta(minutes=CHECKIN_BUFFER_MIN)
    ready_h = ready.hour + ready.minute / 60
    day1 = it["days"][0] if it["days"] else None
    affected, kept = [], []
    arrives_on_day1 = new_arrive.date() == datetime.fromisoformat(date).date()
    if day1 and arrives_on_day1:
        for s in day1["stops"]:
            h, m = map(int, s["start"].split(":"))
            (affected if h + m / 60 < ready_h else kept).append(s)
    elif day1:  # arrival slips to next day: all of day 1 is lost
        affected = list(day1["stops"])
    # alternatives: journeys that still reach the destination earlier than the delayed one
    live = j["legs"][0].get("provenance", {}).get("kind") in ("live", "cached")  # a live-flight trip needs live alternatives
    try:
        res = transport.search_journeys(j["legs"][0]["from"], j["legs"][-1]["to"], date, plan.get("travellers", 1), live_flights=live)
    except ValueError:
        res = {"journeys": []}
    alts = []
    for cand in res["journeys"]:
        if cand["summary"] == j["summary"] and cand["legs"][0]["depart"] == j["legs"][0]["depart"]:
            continue
        arr = datetime.fromisoformat(cand["legs"][-1]["arrive"])
        if arr < new_arrive:
            alts.append({"journey": cand, "saves_min": round((new_arrive - arr).total_seconds() / 60),
                         "extra_cost_inr": cand["total_fare_inr"] - j["total_fare_inr"]})
    alts.sort(key=lambda a: (-a["saves_min"], a["extra_cost_inr"]))
    proposal = {
        "disruption": {"type": "transport_delay", "delay_min": delay_min, "original_arrival": orig_arrive.isoformat(timespec="minutes"),
                       "new_arrival": new_arrive.isoformat(timespec="minutes")},
        "affected_activities": [{"name": s["name"], "start": s["start"], "type": s["type"]} for s in affected],
        "unaffected_activities": [s["name"] for s in kept],
        "options": [
            {"id": "keep", "label": "Keep the booked journey and shift Day 1", "extra_cost_inr": 0,
             "detail": f"Day 1 resumes around {ready.strftime('%H:%M')}; {len(affected)} stop(s) move to a free day or are dropped."},
            *[{"id": f"alt{i}", "label": f"Rebook: {a['journey']['summary']}", "extra_cost_inr": a["extra_cost_inr"],
               "detail": f"Arrives {a['saves_min']} min earlier than the delayed journey (fares simulated; cancellation/refund of the original must be checked)",
               "journey": a["journey"]} for i, a in enumerate(alts[:3])],
        ],
        "requires_approval": True,
        "explanation": "No change is made until you approve. Rebooking may incur cancellation charges on the original ticket; "
                       "simulated fares must be re-validated with the provider.",
    }
    return proposal
