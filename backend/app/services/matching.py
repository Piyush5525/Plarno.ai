"""Multi-supplier duplicate detection + room matching + offer ranking. Explainable; originals are never mutated."""
import re

from rapidfuzz import fuzz

from ..data import seed
from . import geo

_STOP = {"hotel", "the", "inn", "suites", "spa", "new", "delhi", "guest", "house", "guesthouse", "resort", "and", "&"}


def normalize_name(name: str) -> str:
    toks = re.findall(r"[a-z0-9]+", name.lower())
    return " ".join(t for t in toks if t not in _STOP)


def listing_dict(row) -> dict:
    keys = ["supplier", "listing_id", "name", "lat", "lon", "room", "beds", "occupancy", "meal", "price", "truth"]
    return dict(zip(keys, row))


def score_pair(a: dict, b: dict) -> dict:
    km = geo.haversine_km((a["lat"], a["lon"]), (b["lat"], b["lon"]))
    na, nb = normalize_name(a["name"]), normalize_name(b["name"])
    name_sim = max(fuzz.token_set_ratio(na, nb), fuzz.WRatio(na, nb)) / 100
    geo_sim = 1.0 if km < 0.15 else max(0.0, 1 - km / 2.0)
    # hard gate: different location (>2km) can never merge, even with identical names
    score = 0.0 if km > 2.0 else 0.65 * name_sim + 0.35 * geo_sim
    return {"score": round(score, 3), "name_similarity": round(name_sim, 3), "distance_km": round(km, 3),
            "reasons": [f"normalized names '{na}' vs '{nb}' similarity {name_sim:.2f}", f"{km * 1000:.0f} m apart",
                        "hard geo gate (>2 km never merges)" if km > 2 else "within geo gate"]}


def cluster_listings(listings: list[dict], auto_threshold: float = 0.85, review_threshold: float = 0.70,
                     rejected: set[frozenset] | None = None, forced: set[frozenset] | None = None) -> dict:
    """Union-find over pairs. Pairs >= auto merge; between review and auto are queued for human verification."""
    rejected, forced = rejected or set(), forced or set()
    n = len(listings)
    ids = [l["listing_id"] for l in listings]
    members = {i: {ids[i]} for i in range(n)}  # root -> listing ids
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def violates(ra, rb):  # would merging put a human-rejected (cannot-link) pair in one cluster?
        return any(frozenset((x, y)) in rejected for x in members[ra] for y in members[rb])

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri == rj:
            return True
        if violates(ri, rj):
            return False
        parent[ri] = rj
        members[rj] |= members.pop(ri)
        return True

    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            key = frozenset((ids[i], ids[j]))
            if key in rejected:
                continue
            candidates.append((i, j, key, score_pair(listings[i], listings[j])))
    candidates.sort(key=lambda c: -c[3]["score"])  # strongest evidence first; human approvals override score
    evidence, review = {}, []
    for i, j, key, s in candidates:
        if key in forced or s["score"] >= auto_threshold:
            if union(i, j):
                evidence[tuple(sorted(key))] = s
            else:
                review.append({"a": ids[i], "b": ids[j], **s, "blocked_by": "cannot-link constraint from admin rejection"})
        elif s["score"] >= review_threshold:
            review.append({"a": ids[i], "b": ids[j], **s})
    groups: dict[int, list[dict]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(listings[i])
    return {"clusters": [{"canonical_name": max((l["name"] for l in g), key=len), "members": g} for g in groups.values()],
            "evidence": [{"pair": list(k), **v} for k, v in evidence.items()], "needs_review": review}


_BED_ALIAS = {"king": "king", "twin": "twin", "double": "double", "single": "single", "queen": "queen"}


def room_signature(l: dict) -> tuple:
    beds = l["beds"].lower()
    bed = next((v for k, v in _BED_ALIAS.items() if k in beds), beds)
    return (bed, l["occupancy"])


def match_rooms(group: list[dict]) -> list[list[dict]]:
    """Rooms are equivalent if bed config and occupancy agree; meal plan is compared separately (never merged away)."""
    buckets: dict[tuple, list[dict]] = {}
    for l in group:
        buckets.setdefault(room_signature(l), []).append(l)
    return list(buckets.values())


def rank_offers(group: list[dict], budget_per_night: float | None = None) -> list[dict]:
    sups = seed.SUPPLIERS
    prices = [l["price"] for l in group]
    lo, hi = min(prices), max(prices)
    out = []
    for l in group:
        s = sups.get(l["supplier"], {"reliability": 0.5, "cancel": "unknown", "payment": "unknown"})
        price_score = 1.0 if hi == lo else 1 - (l["price"] - lo) / (hi - lo)
        flex = 1.0 if "free" in s["cancel"] else 0.0
        meal = 1.0 if "breakfast" in l["meal"].lower() else 0.0
        score = 0.4 * price_score + 0.25 * s["reliability"] + 0.2 * flex + 0.15 * meal
        out.append({**{k: v for k, v in l.items() if k != "truth"}, "supplier_reliability": s["reliability"],
                    "cancellation": s["cancel"], "payment_terms": s["payment"], "offer_score": round(score * 100, 1),
                    "why": f"price {price_score:.2f}, reliability {s['reliability']}, cancellation {'flexible' if flex else 'restricted'}, {'breakfast' if meal else 'room only'}",
                    "provenance": "simulated supplier listing"})
    return sorted(out, key=lambda o: -o["offer_score"])


def evaluate(listings: list[dict]) -> dict:
    """Pairwise precision/recall/false-merge-rate against `truth` labels (evaluation only)."""
    res = cluster_listings(listings)
    pred = {}
    for ci, c in enumerate(res["clusters"]):
        for m in c["members"]:
            pred[m["listing_id"]] = ci
    tp = fp = fn = tn = 0
    for i in range(len(listings)):
        for j in range(i + 1, len(listings)):
            a, b = listings[i], listings[j]
            same_t = a["truth"] == b["truth"]
            same_p = pred[a["listing_id"]] == pred[b["listing_id"]]
            tp += same_t and same_p
            fp += (not same_t) and same_p
            fn += same_t and (not same_p)
            tn += (not same_t) and (not same_p)
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    return {"precision": round(prec, 3), "recall": round(rec, 3), "false_merge_rate": round(fp / (fp + tn) if fp + tn else 0, 4),
            "pairs": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}
