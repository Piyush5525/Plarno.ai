"""Deterministic budget engine. All numbers are ESTIMATES until a booking is confirmed (see `confirmed_inr`)."""
BREAKFAST_PP = 250      # estimated per person per day when not included
LOCAL_FARE_PER_KM = 14  # estimated cab fare per km
MISC_RATE = 0.05
CATEGORIES = ["intercity_transport", "hotels", "food", "entry_tickets", "local_transport", "misc"]


def compute(travellers: int, nights: int, hotel: dict | None, journey: dict | None, itinerary: dict | None,
            max_budget: float | None = None, round_trip: bool = True, confirmed_inr: float = 0.0, expenses: list[dict] | None = None) -> dict:
    if travellers < 1:
        raise ValueError("travellers must be >= 1")
    cats = {c: 0.0 for c in CATEGORIES}
    daily: dict[int, float] = {}
    unverified_fees = 0
    if journey:
        cats["intercity_transport"] = journey["total_fare_inr"] * (2 if round_trip else 1)
    if hotel:
        cats["hotels"] = hotel["price_per_night"] * nights
    days = itinerary["days"] if itinerary else []
    for d in days:
        day_cost = BREAKFAST_PP * travellers
        cats["food"] += BREAKFAST_PP * travellers
        for s in d["stops"]:
            if s["type"] == "meal":
                cats["food"] += s["cost_inr"]
                day_cost += s["cost_inr"]
            else:
                cats["entry_tickets"] += s["cost_inr"]
                day_cost += s["cost_inr"]
                unverified_fees += 0 if s.get("fee_known") else 1
        local = d["distance_km"] * LOCAL_FARE_PER_KM
        cats["local_transport"] += local
        day_cost += local
        daily[d["day"]] = round(day_cost)
    subtotal = sum(cats.values())
    cats["misc"] = round(subtotal * MISC_RATE)
    total = round(sum(cats.values()))
    out = {"currency": "INR", "estimated_total_inr": total, "per_person_inr": round(total / travellers),
           "breakdown": {k: round(v) for k, v in cats.items()}, "daily_inr": daily, "status": "estimate",
           "confirmed_inr": round(confirmed_inr), "unverified_entry_fees": unverified_fees,
           "note": "Estimates only. Entry fees marked unverified are counted as ₹0 until confirmed."}
    if max_budget:
        out["max_budget_inr"] = max_budget
        out["remaining_inr"] = round(max_budget - total)
        out["within_budget"] = total <= max_budget
        out["alerts"] = ([] if total <= max_budget else [f"Estimated cost exceeds budget by ₹{total - round(max_budget):,}"]) + (
            [f"Over 90% of budget used"] if max_budget * 0.9 < total <= max_budget else [])
    if expenses is not None:
        spent = sum(e["amount"] for e in expenses)
        out["actual_spent_inr"] = round(spent)
        out["planned_vs_actual_inr"] = round(spent - total)
    return out


def split_expenses(expenses: list[dict], members: list[str]) -> dict:
    """Equal split settle-up: who owes whom (greedy)."""
    if not members:
        raise ValueError("members required")
    paid = {m: 0.0 for m in members}
    for e in expenses:
        if e["paid_by"] not in paid:
            raise ValueError(f"unknown payer {e['paid_by']}")
        paid[e["paid_by"]] += e["amount"]
    share = sum(paid.values()) / len(members)
    bal = {m: round(paid[m] - share, 2) for m in members}
    debtors = sorted([(m, -b) for m, b in bal.items() if b < -0.01], key=lambda x: -x[1])
    creditors = sorted([(m, b) for m, b in bal.items() if b > 0.01], key=lambda x: -x[1])
    transfers, i, j = [], 0, 0
    debtors, creditors = [list(x) for x in debtors], [list(x) for x in creditors]
    while i < len(debtors) and j < len(creditors):
        amt = min(debtors[i][1], creditors[j][1])
        transfers.append({"from": debtors[i][0], "to": creditors[j][0], "amount": round(amt, 2)})
        debtors[i][1] -= amt
        creditors[j][1] -= amt
        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1
    return {"share_each": round(share, 2), "balances": bal, "transfers": transfers}


def savings_suggestions(budget: dict, hotels_ranked: list[dict], current_hotel: dict | None) -> list[dict]:
    tips = []
    if not budget.get("within_budget", True) and current_hotel:
        cheaper = [h for h in hotels_ranked if h["price_per_night"] < current_hotel["price_per_night"] and h["score"] >= current_hotel["score"] - 15]
        if cheaper:
            h = cheaper[0]
            tips.append({"type": "hotel", "text": f"Switch to {h['name']} (₹{h['price_per_night']:,.0f}/night)",
                         "hotel_id": h["id"], "saves_inr": round((current_hotel["price_per_night"] - h["price_per_night"]) * (current_hotel.get("nights") or 1))})
    if budget["breakdown"]["local_transport"] > 0.1 * budget["estimated_total_inr"]:
        tips.append({"type": "transport", "text": "Cab fares are over 10% of the total: group nearby stops on the same day, share rides, or use local buses/metro where they exist (these are estimates)."})
    return tips
