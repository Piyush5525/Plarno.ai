"""Door-to-door route options between ANY two places: live flights (Google Flights) + transfers to/from the nearest airports,
direct cab, bus and train.

Honesty rules:
  * Flight fares are live. Everything else is an ESTIMATE from distance and says so; there is no live bus/train inventory here.
  * Train options run between two REAL major stations (data/stations.py), with the trip to and from them shown as its own leg.
    If no major station is near, no train option is offered and the reason is given. Nothing like "train stop" is invented.
  * Every leg carries its coordinates (for the map) and links to check real timings and book: Google Maps, IRCTC/erail, redBus.
Costs are one way unless stated."""
import re
from datetime import datetime, timedelta

from ..data import airports, stations
from ..providers import flights
from . import geo, live

CAB_PER_KM, CAB_MIN, CAB_SEATS = 14.0, 300.0, 4          # INR estimate per km / minimum fare / passengers per cab
AIRPORT_BUFFER_MIN, ARRIVAL_BUFFER_MIN = 150, 45         # be at the airport early; time to exit after landing
STATION_MAX_KM, STATION_WAIT_MIN = 150, 30               # how far a "nearest major station" may be; arrive-early buffer
ACCESS_CAB_MAX_KM = 60                                   # longer hops to a station/airport go by bus (far cheaper), not cab
HUB_MAX_KM, HUB_TRIP_MIN_KM = 60, 250                    # long-distance buses leave from a city bus stand, not from a village or campus
TRAIN_CLASSES = [("Sleeper", 40, 0.60), ("AC 3-tier", 80, 1.60), ("AC 2-tier", 100, 2.30)]   # (label, base INR, INR per rail km), per person
BUS_CLASSES = [("Ordinary", 30, 1.40), ("AC / Volvo", 60, 2.60)]
BUS_NOTE = "Estimated fare and time. Check redBus or the state transport site for real buses."
TRAIN_NOTE = "Estimated fare and time. Check trains, timings and seat availability before you plan around it."


def _est(note, conf=0.4):
    return {"source": "Plarno.ai distance-based estimate", "kind": "estimated", "fetched_at": "", "confidence": conf, "note": note}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _gmaps(a, b, mode: str) -> str:
    """Google Maps directions between two (lat, lon) points: real route, live traffic and, for transit, real departures."""
    return f"https://www.google.com/maps/dir/?api=1&origin={a[0]:.5f},{a[1]:.5f}&destination={b[0]:.5f},{b[1]:.5f}&travelmode={mode}"


def _road_km(a, b, directions=True) -> float:
    if directions:
        d = live.directions([a, b])
        if d:
            return d["distance_km"]
    return geo.haversine_km(a, b) * 1.3


def _cab_leg(frm: str, to: str, a, b, travellers: int, km: float | None = None, operator: str = "Cab / taxi (estimated fare)") -> dict:
    km = km if km is not None else _road_km(a, b)
    vehicles = -(-travellers // CAB_SEATS)
    fare = max(CAB_MIN, km * CAB_PER_KM)
    return {"mode": "cab", "from": frm, "to": to, "from_pt": list(a), "to_pt": list(b), "operator": operator, "duration_min": round(km / 40 * 60 + 8), "distance_km": round(km),
            "fare_inr": int(round(fare * vehicles, -1)), "extra_charges_inr": int(round(fare * vehicles * 0.08, -1)), "comfort": 4.5, "available": None,
            "availability_note": f"Estimate: ₹{CAB_PER_KM:.0f}/km, {vehicles} cab{'s' if vehicles > 1 else ''} for {travellers}. Confirm with the driver or app.",
            "booking_link": None, "links": [{"label": "Driving directions", "url": _gmaps(a, b, "driving")}],
            "provenance": _est("Cab fare estimated from distance; no live cab pricing source is connected.")}


def _bus_leg(frm: str, to: str, a, b, km: float | None = None, india: bool = True) -> dict:
    km = km if km is not None else _road_km(a, b, directions=geo.haversine_km(a, b) < 900)
    fares = [{"label": lab, "inr": int(round(base + per * km, -1))} for lab, base, per in BUS_CLASSES]
    links = ([{"label": "Find buses on redBus", "url": f"https://www.redbus.in/bus-tickets/{_slug(frm)}-to-{_slug(to)}"}] if india and _slug(frm) and _slug(to) else []) + \
        [{"label": "Timings on Google Maps", "url": _gmaps(a, b, "transit")}]
    return {"mode": "bus", "from": frm, "to": to, "from_pt": list(a), "to_pt": list(b), "operator": "Bus (estimated)", "duration_min": round(km / 42 * 60 + 20), "distance_km": round(km),
            "fare_inr": fares[0]["inr"], "extra_charges_inr": 0, "fare_options": fares, "comfort": 2.6, "available": None, "availability_note": BUS_NOTE,
            "booking_link": None, "links": links, "provenance": _est(BUS_NOTE)}


def _train_leg(sa: dict, sb: dict) -> dict:
    a, b = (sa["lat"], sa["lon"]), (sb["lat"], sb["lon"])
    km = geo.haversine_km(a, b) * 1.25                   # rail lines are longer than the straight line
    fares = [{"label": lab, "inr": int(round(base + per * km, -1))} for lab, base, per in TRAIN_CLASSES]
    return {"mode": "train", "from": f"{sa['name']} ({sa['code']})", "to": f"{sb['name']} ({sb['code']})", "from_pt": list(a), "to_pt": list(b), "from_code": sa["code"], "to_code": sb["code"],
            "operator": "Indian Railways (estimated)", "duration_min": round(km / 55 * 60 + STATION_WAIT_MIN), "distance_km": round(km),
            "fare_inr": fares[0]["inr"], "extra_charges_inr": 0, "fare_options": fares, "comfort": 3.4, "available": None, "availability_note": TRAIN_NOTE, "booking_link": None,
            "links": [{"label": "Trains & timings", "url": f"https://erail.in/trains-between-stations/{_slug(sa['name'])}-{sa['code']}/{_slug(sb['name'])}-{sb['code']}"},
                      {"label": "Book on IRCTC", "url": "https://www.irctc.co.in/nget/train-search"}],
            "provenance": _est(TRAIN_NOTE)}


def _access(frm: str, to: str, a, b, travellers: int, india: bool, to_label: str | None = None, bus_from: str | None = None) -> dict | None:
    """The hop between a place and a station/bus stand/airport: nothing if they are the same spot, a cab when close, a bus when far.
    A bus runs between towns, so it is labelled (and searched for) by town name: `to_label` / `bus_from` give those when the hop ends at a station."""
    straight = geo.haversine_km(a, b)
    if straight < 1.5:
        return None
    km = _road_km(a, b, directions=straight < 400)
    if km <= ACCESS_CAB_MAX_KM:
        return _cab_leg(frm, to, a, b, travellers, km)
    return _bus_leg(bus_from or frm, to_label or to, a, b, km, india)


def _cost(legs: list[dict], travellers: int) -> int:
    t = 0
    for leg in legs:
        if leg["mode"] == "cab":
            t += leg["fare_inr"] + leg["extra_charges_inr"]  # already for the whole cab(s)
        else:
            t += (leg["fare_inr"] + leg["extra_charges_inr"]) * travellers
    return round(t)


def _summary(legs: list[dict], flight_detail: str = "") -> str:
    parts = []
    for leg in legs:
        word = "Flight" + flight_detail if leg["mode"] == "flight" else leg["mode"].title()
        if not parts or parts[-1] != word:
            parts.append(word)
    return " + ".join([parts[0]] + [p if p.startswith("Flight") else p.lower() for p in parts[1:]]) if parts else ""


def _finish(legs, summary, travellers, notes=None, flight_live=False):
    has_flight = any(leg["mode"] == "flight" for leg in legs)
    total_min = sum(leg["duration_min"] for leg in legs) + (AIRPORT_BUFFER_MIN + ARRIVAL_BUFFER_MIN if has_flight else 0)
    fare = _cost(legs, travellers)
    comfort = sum(leg["comfort"] * leg["duration_min"] for leg in legs) / max(1, sum(leg["duration_min"] for leg in legs))
    stops = [legs[0]["from"]] + [leg["to"] for leg in legs]
    return {"legs": legs, "summary": summary, "via": stops, "transfers": sum(1 for a, b in zip(legs, legs[1:]) if a["mode"] != b["mode"]), "total_duration_min": round(total_min),
            "total_distance_km": round(sum(leg.get("distance_km") or 0 for leg in legs)),
            "total_fare_inr": fare, "per_person_inr": round(fare / travellers), "round_trip_inr": fare * 2, "comfort": round(comfort, 2), "modes": [leg["mode"] for leg in legs],
            "notes": notes or [], "provenance": {"source": "Google Flights (fare) + estimates (transfers)" if flight_live else "Plarno.ai distance-based estimate",
                                                 "kind": "live" if flight_live else "estimated", "fetched_at": "", "confidence": 0.7 if flight_live else 0.4,
                                                 "note": "Flight fare is live; transfers are estimated." if flight_live else "All figures are estimates; verify with operators."}}


def _train_option(o, d, po, pd, travellers) -> tuple[dict | None, str | None]:
    """Train between the nearest major stations, or (None, reason)."""
    sa, sb = stations.nearest_station(*po, STATION_MAX_KM), stations.nearest_station(*pd, STATION_MAX_KM + 100)
    if not sa or not sb:
        return None, f"No train option: there is no major railway station within reach of {o['name'] if not sa else d['name']}."
    if sa["code"] == sb["code"]:
        return None, None  # both ends use the same station: a train makes no sense
    train = _train_leg(sa, sb)
    if train["distance_km"] < 60:
        return None, None
    first = _access(o["name"], f"{sa['name']} ({sa['code']})", po, (sa["lat"], sa["lon"]), travellers, True, sa["city"])
    last = _access(f"{sb['name']} ({sb['code']})", d["name"], (sb["lat"], sb["lon"]), pd, travellers, True, bus_from=sb["city"])  # buses leave from the city, not the platform
    legs = [x for x in (first, train, last) if x]
    notes = [f"Nearest major station to {o['name']}: {sa['name']} ({sa['code']}), about {sa['km']:.0f} km away." if sa["km"] > 8 else "",
             f"{d['name']} has no major station of its own: the closest is {sb['name']} ({sb['code']}), about {sb['km']:.0f} km away, then {last['mode']} for the last stretch." if last and sb["km"] > 25 else "",
             f"Fares shown use {TRAIN_CLASSES[0][0]} class. {TRAIN_CLASSES[1][0]} is about ₹{train['fare_options'][1]['inr']:,} per person."]
    return _finish(legs, _summary(legs), travellers, [n for n in notes if n]), None


def _bus_option(o, d, po, pd, road, travellers, india) -> dict:
    """Bus: direct for short trips; for long ones via the nearest city bus stand when the start is a village or campus."""
    hub = stations.nearest_station(*po, HUB_MAX_KM) if india and road > HUB_TRIP_MIN_KM else None
    if hub and hub["km"] > 8:
        hp = (hub["lat"], hub["lon"])
        first = _access(o["name"], f"{hub['city']} bus stand", po, hp, travellers, india, hub["city"])
        bus = _bus_leg(hub["city"], d["name"], hp, pd, india=india)
        legs = [x for x in (first, bus) if x]
        return _finish(legs, _summary(legs), travellers, [f"Long-distance buses usually leave from a city bus stand: the nearest is in {hub['city']}, about {hub['km']:.0f} km from {o['name']}.",
                                                          f"Fares shown are for an ordinary bus. AC / Volvo is about ₹{bus['fare_options'][1]['inr']:,} per person."])
    bus = _bus_leg(o["name"], d["name"], po, pd, road, india)
    return _finish([bus], "Bus", travellers, [f"Fares shown are for an ordinary bus. AC / Volvo is about ₹{bus['fare_options'][1]['inr']:,} per person."])


def build_options(o: dict, d: dict, date: str, travellers: int = 1, allowance_round_trip: float | None = None, use_flights: bool = True,
                  budget_basis: str = "round_trip", budget_share: float | None = 0.45) -> dict:
    """o/d: {name, lat, lon, country_code}. Returns ranked options, labels, a budget split and explanatory notes.
    Budget: `allowance_round_trip` is the money available for travel. It is compared with the round-trip cost (budget_basis='round_trip',
    the trip planner's case, where it is `budget_share` of the whole trip budget) or with the one-way cost (budget_basis='one_way')."""
    datetime.fromisoformat(date)
    po, pd = (o["lat"], o["lon"]), (d["lat"], d["lon"])
    straight = geo.haversine_km(po, pd)
    same_country = bool(o.get("country_code") and o.get("country_code") == d.get("country_code"))
    india = same_country and o.get("country_code") == "IN"
    options, notes = [], []
    if straight < 3:
        return {"options": [], "labels": {}, "notes": ["Origin and destination are the same place."], "straight_km": round(straight, 1)}

    if same_country:
        road = _road_km(po, pd, directions=straight < 1200)
        if straight * 1.3 <= 1000:
            cab = _cab_leg(o["name"], d["name"], po, pd, travellers, road, "Private cab / self-drive (estimated)")
            cab.update(duration_min=round(road / 48 * 60 + 10), comfort=4.6, extra_charges_inr=int(round(cab["fare_inr"] * 0.1, -1)),
                       availability_note=f"Estimate: ₹{CAB_PER_KM:.0f}/km + ~10% tolls/parking, {-(-travellers // CAB_SEATS)} cab(s). Door to door, leave when you like.")
            options.append(_finish([cab], "Cab, door to door", travellers))
        if road <= 1100:
            options.append(_bus_option(o, d, po, pd, road, travellers, india))
        if india:
            opt, why = _train_option(o, d, po, pd, travellers)
            if opt:
                options.append(opt)
            elif why:
                notes.append(why)
        elif road <= 2500:  # no station table outside India: one clearly labelled estimate, with a link to real connections
            km = road
            leg = {"mode": "train", "from": o["name"], "to": d["name"], "from_pt": list(po), "to_pt": list(pd), "operator": "Train (estimated, if a rail connection exists)",
                   "duration_min": round(km / 62 * 60 + 40), "distance_km": round(km), "fare_inr": int(round(150 + 1.1 * km, -1)), "extra_charges_inr": 0, "comfort": 3.4, "available": None,
                   "availability_note": "Estimate from distance. Check that a rail connection exists and its real fares.", "booking_link": None,
                   "links": [{"label": "Connections on Google Maps", "url": _gmaps(po, pd, "transit")}], "provenance": _est("Estimate from distance; rail connection not verified.")}
            options.append(_finish([leg], "Train", travellers, ["Rail connection not verified for this pair: open Google Maps to see real services."]))

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
            pa, pb = (oa["lat"], oa["lon"]), (da["lat"], da["lon"])
            for it in res.get("itineraries", [])[:5]:
                segs = it["legs"]
                f_dep = datetime.fromisoformat(segs[0]["depart"]) if segs[0].get("depart") else None
                f_arr = datetime.fromisoformat(segs[-1]["arrive"]) if segs[-1].get("arrive") else None
                km1 = geo.haversine_km(po, pa) * 1.35 if oa["km"] > 15 else 20
                km2 = geo.haversine_km(pb, pd) * 1.35 if da["km"] > 15 else 20
                g1 = _cab_leg(o["name"], f"{oa['city']} airport", po, pa, travellers, km1) if km1 <= ACCESS_CAB_MAX_KM * 2.5 else _bus_leg(o["name"], f"{oa['city']} airport", po, pa, km1, india)
                g2 = _cab_leg(f"{da['city']} airport", d["name"], pb, pd, travellers, km2) if km2 <= ACCESS_CAB_MAX_KM * 2.5 else _bus_leg(f"{da['city']} airport", d["name"], pb, pd, km2, india)
                flight = {"mode": "flight", "from": f"{oa['city']} ({oa['iata']})", "to": f"{da['city']} ({da['iata']})", "from_pt": list(pa), "to_pt": list(pb),
                          "operator": ", ".join(dict.fromkeys(s["airline"] for s in segs if s.get("airline"))) or "Airline",
                          "flight_numbers": [s.get("flight_number") for s in segs], "airports": [segs[0]["from"], segs[-1]["to"]], "stops": it["stops"], "layovers": it["layovers"],
                          "depart": segs[0]["depart"], "arrive": segs[-1]["arrive"], "duration_min": it["total_duration_min"] or 0, "distance_km": round(geo.haversine_km(pa, pb)), "fare_inr": it["price_inr"],
                          "extra_charges_inr": 0, "comfort": 4.0, "available": True, "availability_note": "Fare shown by Google Flights at fetch time; confirm before booking",
                          "booking_link": res.get("link"), "links": [{"label": "View & book on Google Flights", "url": res["link"]}] if res.get("link") else [], "provenance": res["provenance"]}
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
                options.append(_finish([g1, flight, g2], f"{g1['mode'].title()} + Flight ({flight['operator']}{stops}) + {g2['mode'].title()}", travellers, nts, flight_live=True))

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
    one_way = budget_basis == "one_way"
    cost = (lambda r: r["total_fare_inr"]) if one_way else (lambda r: r["round_trip_inr"])
    for i, r in enumerate(options):
        r["index"] = i
        if allowance_round_trip is not None:
            r["fits_budget"] = cost(r) <= allowance_round_trip
            r["over_by_inr"] = max(0, round(cost(r) - allowance_round_trip))
    out = {"options": options, "labels": {k: v["index"] for k, v in labels.items()}, "notes": [n for n in notes if n], "airports": airports_info, "straight_km": round(straight),
           "allowance_round_trip_inr": None if one_way else allowance_round_trip,   # kept for saved plans and the chat tools
           "budget_inr": allowance_round_trip, "budget_basis": "one_way" if one_way else "round_trip", "budget_share": None if one_way else budget_share, "travellers": travellers}
    if allowance_round_trip is not None:
        within = [r for r in options if r["fits_budget"]]
        ref = min(within, key=lambda r: r["total_fare_inr"]) if within else min(options, key=lambda r: r["total_fare_inr"])
        out["stretch"] = [{"index": r["index"], "extra_round_trip_inr": cost(r) - cost(ref), "saves_min": ref["total_duration_min"] - r["total_duration_min"],
                           "comfort_gain": round(r["comfort"] - ref["comfort"], 1), "badges": r.get("badges", [])}
                          for r in options if not r["fits_budget"] and (r["total_duration_min"] < ref["total_duration_min"] - 30 or r["comfort"] > ref["comfort"] + 0.3)]
        out["reference_index"] = ref["index"]
    return out
