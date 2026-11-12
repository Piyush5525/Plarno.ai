"""Multimodal journey search over a hub graph. Fares/schedules are SIMULATED by deterministic formulas (no live provider).
Replace `SimulatedTransportProvider` with a real adapter implementing the same `legs()` contract."""
import hashlib
from datetime import datetime, timedelta

from ..data.seed import CITIES
from ..provenance import simulated
from . import geo

MODE = {  # speed km/h, fixed overhead min, base fare, fare/km, comfort 1-5, max km
    "flight": (700, 150, 1800, 4.2, 4.0, 4000), "train": (62, 40, 150, 1.1, 3.4, 2500),
    "bus": (42, 20, 100, 1.7, 2.6, 1000), "cab": (48, 10, 300, 13.0, 4.6, 650),
}
TRANSFER_BUFFER_MIN = 90


def _h(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


class SimulatedTransportProvider:
    name = "simulated-transport"

    def legs(self, a: str, b: str, date: str) -> list[dict]:
        la, lb = CITIES[a], CITIES[b]
        km = geo.haversine_km(la[:2], lb[:2])
        out = []
        for mode, (speed, ovh, base, per_km, comfort, max_km) in MODE.items():
            if km > max_km or km < 5:
                continue
            if mode == "flight" and not (la[2] and lb[2] and km > 250):
                continue
            if mode == "train" and not (la[3] and lb[3] and km > 50):
                continue
            if mode == "bus" and not (la[4] and lb[4]):
                continue
            road = km * (1.0 if mode == "flight" else 1.3)
            dur = road / speed * 60 + ovh
            fare = base + per_km * road
            for slot in range(2 if mode != "cab" else 1):
                h = _h(a, b, mode, slot, date)
                dep_min = (6 * 60 + (h % 14) * 60 + (slot * 5 * 60)) % (22 * 60)
                dep = datetime.fromisoformat(date) + timedelta(minutes=dep_min)
                jitter = 0.9 + (h % 25) / 100
                out.append({
                    "mode": mode, "from": a, "to": b, "operator": f"{mode.title()} operator (demo)",
                    "depart": dep.isoformat(timespec="minutes"), "arrive": (dep + timedelta(minutes=dur)).isoformat(timespec="minutes"),
                    "duration_min": round(dur), "distance_km": round(road), "fare_inr": round(fare * jitter, -1),
                    "extra_charges_inr": round(fare * 0.05, -1), "comfort": comfort, "available": None,
                    "availability_note": "Unknown - simulated, no live inventory",
                    "booking_link": None, "provenance": simulated("simulated-transport"),
                })
        return out


provider = SimulatedTransportProvider()


def _dist(a: str, b: str, coords: dict) -> int:
    pa = CITIES[a][:2] if a in CITIES else coords.get(a)
    pb = CITIES[b][:2] if b in CITIES else coords.get(b)
    return round(geo.haversine_km(pa, pb)) if pa and pb else 0


def leg_cost(leg: dict, travellers: int) -> float:
    """Cabs are priced per vehicle (4 seats); every other mode per passenger."""
    units = -(-travellers // 4) if leg["mode"] == "cab" else travellers
    return (leg["fare_inr"] + leg["extra_charges_inr"]) * units


def search_journeys(origin: str, dest: str, date: str, travellers: int = 1, live_flights: bool = False, coords: dict | None = None) -> dict:
    from ..data.airports import iata
    known = origin in CITIES and dest in CITIES
    if not known and not (live_flights and iata(origin) and iata(dest)):
        raise ValueError(f"No transport data for this pair. Supported without live flights: {', '.join(sorted(CITIES))}")
    if origin == dest:
        raise ValueError("Origin and destination are the same")
    datetime.fromisoformat(date)  # validates
    coords = coords or {}
    journeys = []
    for leg in (provider.legs(origin, dest, date) if known else []):
        journeys.append([leg])
    for mid in (CITIES if known else []):
        if mid in (origin, dest):
            continue
        for l1 in provider.legs(origin, mid, date):
            for l2 in provider.legs(mid, dest, date):
                # candidate second leg: first departing after arrival + buffer on same day, else next-day departure
                arr = datetime.fromisoformat(l1["arrive"])
                dep2 = datetime.fromisoformat(l2["depart"])
                if dep2 < arr + timedelta(minutes=TRANSFER_BUFFER_MIN):
                    continue
                if (dep2 - arr).total_seconds() > 8 * 3600:
                    continue
                # prune detours: combined distance must be <1.5x direct
                direct = geo.haversine_km(CITIES[origin][:2], CITIES[dest][:2])
                if l1["distance_km"] + l2["distance_km"] > 1.5 * max(direct, 1) + 50:
                    continue
                journeys.append([l1, l2])
    live_note = None
    if live_flights:
        from ..providers import flights as fl  # local import: keeps the module importable without network deps
        fres = fl.search(origin, dest, date, 1) if fl.available() else {"itineraries": [], "error": "Live flight provider not configured"}
        if fres["itineraries"]:
            journeys = [j for j in journeys if not (len(j) == 1 and j[0]["mode"] == "flight")]  # replace simulated direct flights
            for it in fres["itineraries"]:
                segs = it["legs"]
                journeys.append([{
                    "mode": "flight", "from": origin, "to": dest, "operator": ", ".join(dict.fromkeys(s["airline"] for s in segs if s.get("airline"))) or "Airline",
                    "flight_numbers": [s.get("flight_number") for s in segs], "airports": [segs[0]["from"], segs[-1]["to"]], "stops": it["stops"], "layovers": it["layovers"],
                    "depart": segs[0]["depart"], "arrive": segs[-1]["arrive"], "duration_min": it["total_duration_min"] or 0,
                    "distance_km": _dist(origin, dest, coords), "fare_inr": it["price_inr"], "extra_charges_inr": 0,
                    "comfort": 4.0, "available": True, "availability_note": "Shown by Google Flights at fetch time; re-check before booking",
                    "booking_link": fres.get("link"), "provenance": fres["provenance"]}])
            live_note = f"Live flight fares from {fres['provenance']['source']} ({fres['provenance']['kind']}). Booking happens on the airline/OTA site."
        else:
            live_note = f"Live flights unavailable: {fres.get('error') or 'no results'}. Showing simulated flights."
    results = []
    for legs in journeys:
        total_min = round((datetime.fromisoformat(legs[-1]["arrive"]) - datetime.fromisoformat(legs[0]["depart"])).total_seconds() / 60)
        fare = sum(leg_cost(l, travellers) for l in legs)
        comfort = sum(l["comfort"] * l["duration_min"] for l in legs) / sum(l["duration_min"] for l in legs)
        live = all(l["provenance"]["kind"] in ("live", "cached") for l in legs)
        results.append({"legs": legs, "summary": " + ".join(l["mode"] for l in legs), "transfers": len(legs) - 1,
                        "total_duration_min": total_min, "total_fare_inr": round(fare), "per_person_inr": round(fare / travellers),
                        "comfort": round(comfort, 2), "provenance": legs[0]["provenance"] if live else simulated("simulated-transport")})
    if not results:
        return {"journeys": [], "labels": {}, "note": "No simulated route found."}
    # de-duplicate identical mode combos keeping best per label later
    cheapest = min(results, key=lambda r: r["total_fare_inr"])
    fastest = min(results, key=lambda r: r["total_duration_min"])
    mx_f, mx_t = max(r["total_fare_inr"] for r in results), max(r["total_duration_min"] for r in results)

    def value(r):
        return (r["total_fare_inr"] / mx_f) * 0.5 + (r["total_duration_min"] / mx_t) * 0.5

    best_value = min(results, key=value)
    comfy = max(results, key=lambda r: (r["comfort"], -r["total_fare_inr"]))
    low_tr = min(results, key=lambda r: (r["transfers"], r["total_duration_min"]))
    convenient = min(results, key=lambda r: r["transfers"] * 120 + r["total_duration_min"])
    labels = {"cheapest": cheapest, "fastest": fastest, "best_value": best_value, "most_comfortable": comfy,
              "lowest_transfer": low_tr, "most_convenient": convenient}
    for k, v in labels.items():
        v.setdefault("badges", []).append(k)
    results.sort(key=value)
    return {"origin": origin, "destination": dest, "date": date, "travellers": travellers,
            "labels": {k: v["summary"] + f" (₹{v['total_fare_inr']}, {v['total_duration_min']} min)" for k, v in labels.items()},
            "journeys": results[:12], "live_note": live_note, "provenance": simulated("simulated-transport")}
