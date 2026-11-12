"""Geo maths + routing. Routing is an ESTIMATE (haversine x road-factor / avg speed) unless an OSRM provider is configured."""
import itertools
import math

from ..provenance import estimated

ROAD_FACTOR = 1.35
SPEEDS_KMH = {"walk": 4.5, "drive": 22.0, "metro": 30.0, "cab": 22.0}  # urban averages, estimated


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(d))


def route(a: tuple[float, float], b: tuple[float, float], mode: str = "drive") -> dict:
    km = haversine_km(a, b) * ROAD_FACTOR
    speed = SPEEDS_KMH.get(mode, 22.0)
    return {
        "distance_km": round(km, 2), "duration_min": round(km / speed * 60 + (3 if mode != "walk" else 0), 1), "mode": mode,
        "provenance": estimated("haversine x 1.35 road factor", "Straight-line estimate; not turn-by-turn routing.", 0.5),
    }


def path_length(points: list[tuple[float, float]], order: list[int]) -> float:
    return sum(haversine_km(points[order[i]], points[order[i + 1]]) for i in range(len(order) - 1))


def optimize_order(points: list[tuple[float, float]], start: tuple[float, float] | None = None) -> list[int]:
    """Shortest open path from `start` through all points. Exact (brute force) for <=8 stops, else NN + 2-opt."""
    n = len(points)
    if n <= 1:
        return list(range(n))
    pts = ([start] if start else []) + list(points)
    off = 1 if start else 0

    def cost(perm):
        seq = ([0] if start else []) + [p + off for p in perm]
        return sum(haversine_km(pts[seq[i]], pts[seq[i + 1]]) for i in range(len(seq) - 1))

    if n <= 8:
        return list(min(itertools.permutations(range(n)), key=cost))
    # nearest neighbour + 2-opt
    cur = 0 if not start else min(range(n), key=lambda i: haversine_km(start, points[i]))
    order, left = [cur], set(range(n)) - {cur}
    while left:
        nxt = min(left, key=lambda i: haversine_km(points[order[-1]], points[i]))
        order.append(nxt)
        left.remove(nxt)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if cost(cand) + 1e-9 < cost(order):
                    order, improved = cand, True
    return order


def cluster_days(points: list[tuple[float, float]], k: int) -> list[list[int]]:
    """Geographic grouping into k day-clusters (deterministic k-means, farthest-first init), balanced by size."""
    n = len(points)
    k = max(1, min(k, n))
    if k == 1:
        return [list(range(n))]
    centers = [points[0]]
    while len(centers) < k:
        centers.append(max(points, key=lambda p: min(haversine_km(p, c) for c in centers)))
    groups: list[list[int]] = []
    for _ in range(20):
        groups = [[] for _ in range(k)]
        cap = math.ceil(n / k)
        order = sorted(range(n), key=lambda i: min(haversine_km(points[i], c) for c in centers))
        for i in order:
            for g in sorted(range(k), key=lambda g: haversine_km(points[i], centers[g])):
                if len(groups[g]) < cap:
                    groups[g].append(i)
                    break
        new = [(sum(points[i][0] for i in g) / len(g), sum(points[i][1] for i in g) / len(g)) if g else centers[idx]
               for idx, g in enumerate(groups)]
        if new == centers:
            break
        centers = new
    return [g for g in groups if g]
