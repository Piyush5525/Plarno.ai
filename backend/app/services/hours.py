"""Parse Google Maps weekday opening-hour strings ("9 AM–12 AM", "7:50 AM–7 PM (note)", "Closed", "Open 24 hours", "9 AM–12 PM, 2–6 PM")
so the itinerary can schedule around real hours. Anything unparseable yields None: callers then treat hours as unknown, never guess."""
import re

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TIME = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", re.I)


def _clean(s: str) -> str:
    s = re.sub(r"\([^)]*\)", "", s)  # drop notes like "(Armistice Day might affect these hours)"
    return s.replace(" ", " ").replace(" ", " ").replace("–", "-").replace("—", "-").replace(" to ", "-").strip()


def _to_h(h: int, m: str | None, mer: str | None) -> float:
    h = h % 12 if mer else h
    if mer and mer.upper() == "PM":
        h += 12
    return h + (int(m) / 60 if m else 0)


def parse(s: str | None) -> dict | None:
    """-> {"kind": "closed"} | {"kind": "24h"} | {"kind": "range", "open": h, "close": h, "text": str} | None (unknown)."""
    if not s or not isinstance(s, str):
        return None
    c = _clean(s)
    low = c.lower()
    if low.startswith("closed"):
        return {"kind": "closed", "text": "Closed"}
    if "24 hours" in low or "open 24" in low:
        return {"kind": "24h", "text": "Open 24 hours"}
    opens, closes = [], []
    for part in c.split(","):
        pr = [p for p in part.split("-") if p.strip()]
        if len(pr) != 2:
            return None
        a, b = _TIME.search(pr[0]), _TIME.search(pr[1])
        if not a or not b:
            return None
        mer_b = b.group(3)
        mer_a = a.group(3) or mer_b  # "2-6 PM": the opening time shares the closing meridiem
        o, cl = _to_h(int(a.group(1)), a.group(2), mer_a), _to_h(int(b.group(1)), b.group(2), mer_b)
        if cl <= o:
            cl += 24  # "9 AM-12 AM" closes at midnight
        opens.append(o)
        closes.append(cl)
    if not opens:
        return None
    return {"kind": "range", "open": min(opens), "close": max(closes), "text": c}


def for_date(operating_hours: dict | None, day: "date") -> dict | None:  # noqa: F821
    if not operating_hours:
        return None
    return parse(operating_hours.get(WEEKDAYS[day.weekday()]))
