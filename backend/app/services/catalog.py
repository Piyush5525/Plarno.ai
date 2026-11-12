"""Destination / attraction / restaurant / neighbourhood / hotel catalog with provenance and neighbourhood scoring."""
from ..data import seed
from ..provenance import estimated, simulated
from . import geo

DEFAULT_WEIGHTS = {"attractions": 0.2, "environment": 0.2, "transit": 0.15, "hotel_quality": 0.15, "food": 0.1, "price": 0.1, "safety": 0.1}
PRESETS = {
    "family": {"safety": 0.25, "transit": 0.2, "environment": 0.25, "attractions": 0.1, "hotel_quality": 0.1, "food": 0.05, "price": 0.05},
    "budget": {"price": 0.35, "transit": 0.25, "attractions": 0.15, "safety": 0.1, "environment": 0.05, "hotel_quality": 0.05, "food": 0.05},
    "sightseeing": {"attractions": 0.4, "transit": 0.2, "price": 0.1, "environment": 0.1, "hotel_quality": 0.05, "food": 0.05, "safety": 0.1},
    "peaceful": {"environment": 0.4, "safety": 0.15, "attractions": 0.1, "transit": 0.1, "hotel_quality": 0.15, "food": 0.05, "price": 0.05},
}

_ATTR_KEYS = ["id", "name", "category", "lat", "lon", "area", "visit_min", "fee_inr", "best_time", "tags", "accessibility"]
_NB_KEYS = ["id", "name", "lat", "lon", "industrial_km", "green", "aqi_est", "noise_db_est", "traffic", "safety_idx", "transit", "hospitals", "police"]
_H_KEYS = ["id", "name", "neighbourhood_id", "lat", "lon", "type", "stars", "rating", "cleanliness", "interiors", "food_quality", "base_price"]
_R_KEYS = ["id", "name", "lat", "lon", "area", "cuisine", "price_for_two", "veg", "vegan", "rating", "kind"]


def attractions(category: str | None = None, area: str | None = None, tags: list[str] | None = None) -> list[dict]:
    out = []
    for row in seed.ATTRACTIONS:
        a = dict(zip(_ATTR_KEYS, row))
        a["city"] = "Delhi"
        a["opening_hours"] = None  # unknown: verify at official source
        a["fee_note"] = "Free" if a["fee_inr"] == 0 else ("Not available in demo data - verify at official source" if a["fee_inr"] is None else "Estimate")
        a["provenance"] = simulated("Plarno.ai demo dataset", "Location approximate; fees/hours not verified.")
        if category and a["category"] != category:
            continue
        if area and area.lower() not in a["area"].lower() and area.lower() not in a["name"].lower():
            continue
        if tags and not set(t.lower() for t in tags) & set(a["tags"]):
            continue
        out.append(a)
    return out


def neighbourhoods() -> list[dict]:
    out = []
    for row in seed.NEIGHBOURHOODS:
        n = dict(zip(_NB_KEYS, row))
        n["provenance"] = {
            "industrial_km": estimated("geographic proxy (distance to industrial zones)", "Proxy, not an emission measurement.", 0.5),
            "aqi_est": simulated("demo AQI estimate", "NOT a live reading. Wire CPCB/OpenAQ for measurements."),
            "noise_db_est": estimated("modelled estimate", "No noise-monitor data connected.", 0.3),
            "safety_idx": estimated("demo heuristic", "Not verified safety data; never a guarantee.", 0.3),
        }
        out.append(n)
    return out


def hotels() -> list[dict]:
    out = []
    for row in seed.HOTELS:
        h = dict(zip(_H_KEYS, row))
        h["city"] = "Delhi"
        h["provenance"] = simulated("Plarno.ai demo dataset", "Synthetic rate; not live availability.")
        out.append(h)
    return out


def restaurants() -> list[dict]:
    out = []
    for row in seed.RESTAURANTS:
        r = dict(zip(_R_KEYS, row))
        r["provenance"] = simulated("Plarno.ai demo dataset", "Fictional venue names modelled on local cuisine; price is an estimate.")
        out.append(r)
    return out


def _norm(v, lo, hi, invert=False):
    x = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    return 1 - x if invert else x


def score_neighbourhood(nb: dict, attractions_sel: list[dict], hotel_stats: dict, weights: dict | None = None) -> dict:
    """Explainable weighted score in [0,100]. Each factor is returned with its raw value, 0-1 sub-score and data kind."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_w = sum(w.values()) or 1
    pts = [(a["lat"], a["lon"]) for a in attractions_sel]
    center = (nb["lat"], nb["lon"])
    avg_km = sum(geo.haversine_km(center, p) for p in pts) / len(pts) if pts else 8.0
    env = (0.4 * _norm(nb["aqi_est"], 100, 300, True) + 0.2 * _norm(nb["noise_db_est"], 50, 90, True)
           + 0.25 * _norm(nb["industrial_km"], 0, 8) + 0.15 * nb["green"]) * 1.0
    f = {
        "attractions": (_norm(avg_km, 1, 14, True), f"avg {avg_km:.1f} km to selected attractions", "estimated"),
        "environment": (env, f"AQI~{nb['aqi_est']} (simulated), noise~{nb['noise_db_est']} dB (est.), industrial zone {nb['industrial_km']} km (proxy), green {nb['green']}", "simulated"),
        "transit": (nb["transit"], f"transit access index {nb['transit']}", "estimated"),
        "hotel_quality": (hotel_stats.get("quality", 0.5), f"best-fit hotel quality {hotel_stats.get('quality', 0):.2f}", "simulated"),
        "food": (min(1.0, hotel_stats.get("food", 0.5)), "hotel food rating", "simulated"),
        "price": (hotel_stats.get("price_fit", 0.5), "price vs budget", "simulated"),
        "safety": (nb["safety_idx"], f"demo safety index {nb['safety_idx']} - not verified, not a guarantee", "estimated"),
    }
    score = sum(f[k][0] * w[k] for k in f) / total_w * 100
    return {
        "neighbourhood": nb["name"], "id": nb["id"], "score": round(score, 1),
        "factors": [{"factor": k, "subscore": round(v[0], 2), "weight": round(w[k] / total_w, 3), "detail": v[1], "data_kind": v[2]} for k, v in f.items()],
        "avg_km_to_attractions": round(avg_km, 1),
        "disclaimer": "Environmental and safety inputs are simulated/estimated proxies. No location is guaranteed safe or pollution-free.",
    }


def rank_hotels(nights: int, budget_per_night: float | None, weights: dict | None, attractions_sel: list[dict],
                travellers: int = 2, avoid: list[str] | None = None) -> list[dict]:
    nbs = {n["id"]: n for n in neighbourhoods()}
    rooms = max(1, (travellers + 1) // 2)
    result = []
    for h in hotels():
        nb = nbs[h["neighbourhood_id"]]
        cost_night = h["base_price"] * rooms
        price_fit = 1.0 if not budget_per_night else _norm(cost_night, budget_per_night * 0.4, budget_per_night * 1.6, True)
        stats = {"quality": (h["rating"] / 5 * 0.4 + h["cleanliness"] / 5 * 0.3 + h["interiors"] / 5 * 0.3),
                 "food": h["food_quality"] / 5, "price_fit": price_fit}
        sc = score_neighbourhood(nb, attractions_sel, stats, weights)
        over = bool(budget_per_night and cost_night > budget_per_night)
        penalty = 15 if over else 0
        result.append({**h, "price_per_night": cost_night, "rooms": rooms, "total_price": cost_night * nights,
                       "over_budget": over, "score": round(max(0, sc["score"] - penalty), 1), "explanation": sc,
                       "avg_km_to_attractions": sc["avg_km_to_attractions"], "neighbourhood": nb["name"]})
    if avoid:
        for r in result:
            if "industrial" in avoid and r["explanation"]["factors"][1]["subscore"] < 0.5:
                r["score"] = round(r["score"] - 10, 1)
    return sorted(result, key=lambda r: -r["score"])
