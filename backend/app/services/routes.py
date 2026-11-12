"""Door-to-door route options between ANY two places: live flights (Google Flights) + cab transfers to/from the nearest airports,
direct cab, bus and train. Honesty rules: flight fares are live; everything else is an ESTIMATE from distance formulas and says so;
no live bus/train inventory exists here, so those options carry a 'verify on the operator site' note. Costs are one way unless stated."""
from datetime import datetime, timedelta

from ..data import airports
from ..providers import flights
from . import geo, live

CAB_PER_KM, CAB_MIN, CAB_SEATS = 14.0, 300.0, 4          # INR estimate per km / minimum fare / passengers per cab
AIRPORT_BUFFER_MIN, ARRIVAL_BUFFER_MIN = 150, 45         # be at the airport early; time to exit after landing
LAND = {  # mode: (avg km/h, overhead min, base fare, per-km fare per person, comfort 1-5, max road km, note)
    "bus": (42, 20, 100, 1.7, 2.6, 1100, "Estimate from distance. Check operators (e.g. RedBus/state transport) for real fares and times."),
    "train": (62, 40, 150, 1.1, 3.4, 2500, "Estimate (mix of classes). Check the national rail booking site for real fares and trains."),
}


def _est(note, conf=0.4):
    return {"source": "Plarno.ai distance-based estimate", "kind": "estimated", "fetched_at": "", "confidence": conf, "note": note}


def _road_km(a, b, directions=True) -> float:
    if directions:
        d = live.directions([a, b])
        if d:
            return d["distance_km"]
    return geo.haversine_km(a, b) * 1.3


def _cab_leg(frm: str, to: str, km: float, travellers: int) -> dict:
    vehicles = -(-travellers // CAB_SEATS)
    fare = max(CAB_MIN, km * CAB_PER_KM)
    return {"mode": "cab", "from": frm, "to": to, "operator": "Cab / taxi (estimated fare)", "duration_min": round(km / 40 * 60 + 8), "distance_km": round(km),
            "fare_inr": round(fare * vehicles, -1), "extra_charges_inr": round(fare * vehicles * 0.08, -1), "comfort": 4.5, "available": None,
            "availability_note": f"Estimate: ₹{CAB_PER_KM:.0f}/km, {vehicles} cab(s) for {travellers}. Confirm with the driver or app.",
            "booking_link": None, "provenance": _est("Cab fare estimated from distance; no live cab pricing source is connected.")}


def _cost(legs: list[dict], travellers: int) -> int:
    t = 0
    for leg in legs:
        if leg["mode"] == "cab":
            t += leg["fare_inr"] + leg["extra_charges_inr"]  # already for the whole cab(s)
        else:
            t += (leg["fare_inr"] + leg["extra_charges_inr"]) * travellers
    return round(t)


def _finish(legs, summary, travellers, notes=None, flight_live=False):
    has_flight = any(leg["mode"] == "flight" for leg in legs)
    total_min = sum(leg["duration_min"] for leg in legs) + (AIRPORT_BUFFER_MIN + ARRIVAL_BUFFER_MIN if has_flight else 0)
    fare = _cost(legs, travellers)
    comfort = sum(leg["comfort"] * leg["duration_min"] for leg in legs) / max(1, sum(leg["duration_min"] for leg in legs))
    return {"legs": legs, "summary": summary, "transfers": sum(1 for a, b in zip(legs, legs[1:]) if a["mode"] != b["mode"]), "total_duration_min": round(total_min),
            "total_fare_inr": fare, "per_person_inr": round(fare / travellers), "round_trip_inr": fare * 2, "comfort": round(comfort, 2), "modes": [leg["mode"] for leg in legs],
            "notes": notes or [], "provenance": {"source": "Google Flights (fare) + estimates (transfers)" if flight_live else "Plarno.ai distance-based estimate",
                                                 "kind": "live" if flight_live else "estimated", "fetched_at": "", "confidence": 0.7 if flight_live else 0.4,
                                                 "note": "Flight fare is live; cab transfers are estimated." if flight_live else "All figures are estimates; verify with operators."}}


def build_options(o: dict, d: dict, date: str, travellers: int = 1, allowance_round_trip: float | None = None, use_flights: bool = True) -> dict:
    """o/d: {name, lat, lon, country_code}. Returns options (ranked), labels, budget split and explanatory notes."""
    datetime.fromisoformat(date)
    po, pd = (o["lat"], o["lon"]), (d["lat"], d["lon"])
    straight = geo.haversine_km(po, pd)
    same_country = bool(o.get("country_code") and o.get("country_code") == d.get("country_code"))
    options, notes = [], []
    if straight < 3:
        return {"options": [], "labels": {}, "notes": ["Origin and destination are the same place."], "straight_km": round(straight, 1)}

    if same_country and straight * 1.3 <= 1000:
        road = _road_km(po, pd)
        vehicles = -(-travellers // CAB_SEATS)
        fare = max(CAB_MIN, road * CAB_PER_KM)
        cab = {"mode": "cab", "from": o["name"], "to": d["name"], "operator": "Private cab / self-drive (estimated)", "duration_min": round(road / 48 * 60 + 10), "distance_km": round(road),
               "fare_inr": round(fare * vehicles, -1), "extra_charges_inr": round(fare * vehicles * 0.1, -1), "comfort": 4.6, "available": None,
               "availability_note": f"Estimate: ₹{CAB_PER_KM:.0f}/km + ~10% tolls/parking, {vehicles} cab(s). Door to door, leave when you like.", "booking_link": None,
               "provenance": _est("Cab fare estimated from road distance.")}
        options.append(_finish([cab], "Cab, door to door", travellers))
    if same_country:
        road = _road_km(po, pd, directions=straight < 1200)
        for mode, (spd, ovh, base, per_km, comfort, max_km, note) in LAND.items():
            if road <= max_km:
                leg = {"mode": mode, "from": o["name"], "to": d["name"], "operator": f"{mode.title()} (estimated)", "duration_min": round(road / spd * 60 + ovh), "distance_km": round(road),
                       "fare_inr": round(base + per_km * road, -1), "extra_charges_inr": round((base + per_km * road) * 0.05, -1), "comfort": comfort, "available": None,
                       "availability_note": note, "booking_link": None, "provenance": _est(note)}
                legs = [leg]
                if road > 40:  # get to/from the station or bus stand
                    legs = [_cab_leg(o["name"], f"{mode} stop", 8, travellers), leg, _cab_leg(f"{mode} stop", d["name"], 8, travellers)]
                options.append(_finish(legs, ("Cab + " if len(legs) > 1 else "") + mode.title() + (" + cab" if len(legs) > 1 else ""), travellers, [note]))

    airports_info = {}
    if use_flights and straight > 250:
        oa, da = airports.nearest_airport(*po), airports.nearest_airport(*pd)
        airports_info = {"origin": oa, "destination": da}
        if not oa or not da:
            notes.append("No airport found within 400 km of " + (o["name"] if not oa else d["name"]) + ": flights are not offered for this trip.")
        elif oa["iata"] == da["iata"]:
            notes.append("Both places use the same nearest airport, so no flight is needed.")
        else:
            res = flights.search(oa["city"], da["city"], date, 1)
            if res.get("error"):
                notes.append("Live flights unavailable: " + res["error"])
            for it in res.get("itineraries", [])[:5]:
                segs = it["legs"]
                f_dep = datetime.fromisoformat(segs[0]["depart"]) if segs[0].get("depart") else None
                f_arr = datetime.fromisoformat(segs[-1]["arrive"]) if segs[-1].get("arrive") else None
                km1 = geo.haversine_km(po, (oa["lat"], oa["lon"])) * 1.35 if oa["km"] > 15 else 20
                km2 = geo.haversine_km((da["lat"], da["lon"]), pd) * 1.35 if da["km"] > 15 else 20
                g1, g2 = _cab_leg(o["name"], f"{oa['city']} airport", km1, travellers), _cab_leg(f"{da['city']} airport", d["name"], km2, travellers)
                flight = {"mode": "flight", "from": oa["city"], "to": da["city"], "operator": ", ".join(dict.fromkeys(s["airline"] for s in segs if s.get("airline"))) or "Airline",
                          "flight_numbers": [s.get("flight_number") for s in segs], "airports": [segs[0]["from"], segs[-1]["to"]], "stops": it["stops"], "layovers": it["layovers"],
                          "depart": segs[0]["depart"], "arrive": segs[-1]["arrive"], "duration_min": it["total_duration_min"] or 0, "distance_km": round(straight), "fare_inr": it["price_inr"],
                          "extra_charges_inr": 0, "comfort": 4.0, "available": True, "availability_note": "Fare shown by Google Flights at fetch time; confirm before booking",
                          "booking_link": res.get("link"), "provenance": res["provenance"]}
                if f_dep:
                    g1["depart"] = (f_dep - timedelta(minutes=AIRPORT_BUFFER_MIN + g1["duration_min"])).isoformat(timespec="minutes")
                    g1["arrive"] = (f_dep - timedelta(minutes=AIRPORT_BUFFER_MIN)).isoformat(timespec="minutes")
                if f_arr:
                    g2["depart"] = (f_arr + timedelta(minutes=ARRIVAL_BUFFER_MIN)).isoformat(timespec="minutes")
                    g2["arrive"] = (f_arr + timedelta(minutes=ARRIVAL_BUFFER_MIN + g2["duration_min"])).isoformat(timespec="minutes")
                stops = (f", {it['stops']} stop{'s' if it['stops'] != 1 else ''}" if it["stops"] else ", non-stop") + (f", departs {segs[0]['depart'][11:16]}" if segs[0].get("depart") else "")
                nts = []
                if oa["km"] > 25:
                    nts.append(f"Nearest airport to {o['name']} is {oa['city']} ({oa['iata']}), about {oa['km']:.0f} km away.")
                if da["km"] > 25:
                    nts.append(f"Nearest airport to {d['name']} is {da['city']} ({da['iata']}), about {da['km']:.0f} km away.")
                options.append(_finish([g1, flight, g2], f"Cab + Flight ({flight['operator']}{stops}) + Cab", travellers, nts, flight_live=True))

    if not options:
        return {"options": [], "labels": {}, "notes": [n for n in notes if n] or ["No route options could be built for this pair."], "airports": airports_info, "straight_km": round(straight)}

    mx_f, mx_t = max(r["total_fare_inr"] for r in options), max(r["total_duration_min"] for r in options)

    def val(r):
        return r["total_fare_inr"] / mx_f * 0.5 + r["total_duration_min"] / mx_t * 0.5
    labels = {"cheapest": min(options, key=lambda r: r["total_fare_inr"]), "fastest": min(options, key=lambda r: r["total_duration_min"]),
              "most_comfortable": max(options, key=lambda r: (r["comfort"], -r["total_fare_inr"])), "best_value": min(options, key=val),
              "most_convenient": min(options, key=lambda r: (r["transfers"], r["total_duration_min"]))}
    for k, v in labels.items():
        v.setdefault("badges", []).append(k)
    options.sort(key=val)
    for i, r in enumerate(options):
        r["index"] = i
        if allowance_round_trip is not None:
            r["fits_budget"] = r["round_trip_inr"] <= allowance_round_trip
            r["over_by_inr"] = max(0, round(r["round_trip_inr"] - allowance_round_trip))
    out = {"options": options, "labels": {k: v["index"] for k, v in labels.items()}, "notes": [n for n in notes if n], "airports": airports_info, "straight_km": round(straight),
           "allowance_round_trip_inr": allowance_round_trip}
    if allowance_round_trip is not None:
        within = [r for r in options if r["fits_budget"]]
        ref = min(within, key=lambda r: r["total_fare_inr"]) if within else min(options, key=lambda r: r["total_fare_inr"])
        out["stretch"] = [{"index": r["index"], "extra_round_trip_inr": r["round_trip_inr"] - ref["round_trip_inr"], "saves_min": ref["total_duration_min"] - r["total_duration_min"],
                           "comfort_gain": round(r["comfort"] - ref["comfort"], 1), "badges": r.get("badges", [])}
                          for r in options if not r["fits_budget"] and (r["total_duration_min"] < ref["total_duration_min"] - 30 or r["comfort"] > ref["comfort"] + 0.3)]
        out["reference_index"] = ref["index"]
    return out
