"""Deterministic natural-language understanding (rules). The LLM provider interface in llm.py can replace/augment this;
rules remain the validated fallback so the system works offline and is testable."""
import re

from ..data.seed import CITIES
from .context import TripContext

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
INTEREST_KEYWORDS = {
    "history": ["histor", "heritage", "fort", "monument", "mughal"], "food": ["food", "foodie", "cuisine", "eat", "restaurant"],
    "museum": ["museum", "art gallery"], "religious": ["temple", "religious", "spiritual", "mosque"],
    "shopping": ["shopping", "market", "bazaar"], "garden": ["garden", "park", "nature", "green"],
    "peaceful": ["peaceful", "quiet", "calm", "serene"],
}


def _num(tok: str) -> int | None:
    tok = tok.lower()
    return int(tok) if tok.isdigit() else NUM_WORDS.get(tok)


def _find_city(text: str, after: str | None = None) -> str | None:
    t = text.lower()
    if after:
        m = re.search(rf"\b{after}\s+([a-z ()]+)", t)
        if m:
            for c in CITIES:
                if c.lower() in m.group(1)[:25]:
                    return c
        return None
    for c in CITIES:
        if re.search(rf"\b{re.escape(c.lower())}\b", t):
            return c
    return None


def parse_budget(text: str) -> float | None:
    t = text.lower().replace(",", "")
    m = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*(k|lakh|lac)?", t) or re.search(r"(\d+(?:\.\d+)?)\s*(k|lakh|lac)?\s*(?:rupees|inr)", t) \
        or re.search(r"budget[^0-9]{0,25}(\d+(?:\.\d+)?)\s*(k|lakh|lac)?", t)
    if not m:
        return None
    v = float(m.group(1))
    mult = {"k": 1000, "lakh": 100000, "lac": 100000}.get(m.group(2) or "", 1)
    return v * mult


_STOP = {"i", "we", "my", "our", "the", "a", "an", "plan", "please", "hi", "hello", "can", "could", "would", "want", "need", "looking", "january", "february", "march", "april",
         "may", "june", "july", "august", "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "budget", "inr"}
_PLACE = r"((?:[A-Z][\w'’.-]*)(?:[ -](?:[A-Z][\w'’.-]*|of|de|la|el|del|da|do|di|le|les|al|el))*(?:,\s*[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*)*)?)"


def _place_after(text: str, words: str) -> str | None:
    for m in re.finditer(rf"\b(?:{words})\s+{_PLACE}", text):
        toks = []
        for tok in m.group(1).split():
            if tok.endswith(".") and len(tok.rstrip(".")) > 3:  # a full stop after a real word ends the sentence ("...in Kishangarh. Plan a trip")
                toks.append(tok.rstrip("."))
                break
            toks.append(tok)  # keep abbreviation periods such as "St." and the comma in "Paris, France"
        while toks and toks[-1].strip(",").lower() in _STOP:
            toks.pop()
        if toks and toks[0].lower() not in _STOP and len(" ".join(toks)) >= 3:
            return " ".join(toks).strip(" .,-")
    return None


def extract(text: str, ctx: TripContext) -> dict:
    """Return the fields detected in `text` (not merged). Never overwrites with None."""
    t = text.lower()
    out: dict = {}
    m = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[\s-]*(?:day|days|night|nights)\b", t)
    if m and _num(m.group(1)):
        n = _num(m.group(1))
        out["days"] = n + 1 if "night" in m.group(0) else n
    elif re.search(r"\bweekend\b", t):
        out["days"] = 3
    elif re.search(r"\b(?:a|one|1)\s+week\b", t):
        out["days"] = 7
    elif re.search(r"\b(two|2)\s+weeks\b", t):
        out["days"] = 14
    b = parse_budget(text)
    if b:
        out["budget_inr"] = b
    bare = re.fullmatch(r"\s*(\d{1,7})\s*(?:people|persons|adults|travell?ers|pax)?\s*[.!]?\s*", t)
    if bare:  # a bare number answering a pending question
        n = int(bare.group(1))
        if ctx.adults is None and 1 <= n <= 20:
            out["adults"] = n
        elif ctx.budget_inr is None and n >= 1000:
            out["budget_inr"] = float(n)
        elif ctx.days is None and 1 <= n <= 30:
            out["days"] = n
    m = re.search(r"\b(?:for|with|of)\s+(\d+|one|two|three|four|five|six)\s+(?:people|persons|adults|travell?ers|of us)\b", t) \
        or re.search(r"\b(\d+|two|three|four|five|six)\s+(?:people|persons|adults)\b", t)
    if not m:
        m = re.search(r"\b(\d{1,2}|two|three|four|five|six|seven|eight)\s+of us\b", t) or \
            re.search(r"\b(?:we are|we're|there are|party of|group of)\s+(\d{1,2}|two|three|four|five|six|seven|eight)\b(?![\s-]*(?:day|night|week|k\b))", t)
    if not m:
        m = re.search(r"\bfor\s+(\d{1,2}|two|three|four|five|six)(?!\d)(?![\s-]*(?:day|night|hour|week|k\b|lakh))", t)
    if m and _num(m.group(1)) and _num(m.group(1)) <= 20:
        out["adults"] = _num(m.group(1))
    elif re.search(r"\b(solo|alone|by myself|myself|just me|only me)\b", t):
        out["adults"] = 1
    elif re.search(r"\b(couple|my (?:wife|husband|partner|girlfriend|boyfriend)|honeymoon)\b", t):
        out["adults"] = 2
    elif re.search(r"\bfamily\b", t):
        out["adults"] = ctx.adults or 2
        out["priority_preset"] = "family"
    m = re.search(r"(\d+|one|two|three)\s+(?:kids?|child|children)", t)
    if m and _num(m.group(1)):
        out["children"] = _num(m.group(1))
    org = _find_city(text, "from")
    if org:
        out["origin"] = org
    dest = _find_city(text, "to") or _find_city(text, "explore") or _find_city(text, "visit") or _find_city(text, "in")
    if not dest:
        c = _find_city(text)
        dest = c if c and c != org else None
    if dest and dest != org:
        out["destination"] = dest
    if "destination" not in out:  # any city in the world: resolved/validated later by geocoding
        d = _place_after(text, "to|in|visit|visiting|explore|exploring|around|at|trip to|going to|travel to")
        if d and d != out.get("origin") and d.lower() not in (c.lower() for c in CITIES):
            out["destination_raw"] = d
    if "origin" not in out:
        o = _place_after(text, "from")
        if o and o.lower() not in (c.lower() for c in CITIES) and o != out.get("destination_raw"):
            out["origin_raw"] = o
    if re.search(r"\b(my home ?town|hometown|where i live|i live (in|here)|near me|day trips? (from|around|near) (home|my)|from (my )?home|stay(ing)? (at )?home|around my (town|city|village)|my own (town|city))\b", t):
        out["stay_home"] = True
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if iso:
        out["start_date"] = iso.group(1)
    interests = [k for k, ws in INTEREST_KEYWORDS.items() if any(w in t for w in ws)]
    if interests:
        out["interests"] = interests
    if re.search(r"\b(vegetarian|veg only|pure veg)\b", t):
        out["vegetarian"] = True
    if re.search(r"\bvegan\b", t):
        out["vegan"] = out["vegetarian"] = True
    if re.search(r"peaceful|quiet|calm|serene|tranquil", t):
        out["peaceful"] = True
    if re.search(r"pollut|clean air|\baqi\b|industrial", t):
        out["avoid_polluted"] = True
    if re.search(r"noisy|noise|loud", t):
        out["avoid_noisy"] = True
    if re.search(r"avoid.*crowd|less crowd|not crowded|crowded places", t) and "avoid" in t:
        out["avoid_crowded"] = True
    if re.search(r"wheelchair|accessib|elderly|senior", t):
        out["accessibility"] = ["step-free"]
    if re.search(r"comfort", t):
        out["transport_pref"] = "comfortable"
    elif re.search(r"cheapest|budget transport|save on transport", t):
        out["transport_pref"] = "cheapest"
    elif re.search(r"fastest|quickest", t):
        out["transport_pref"] = "fastest"
    if re.search(r"relaxed|slow pace|leisure", t):
        out["pace"] = "relaxed"
    elif re.search(r"packed|as much as|action[- ]packed", t):
        out["pace"] = "packed"
    return out


def classify_intent(text: str, has_plan: bool) -> dict:
    t = text.lower()
    if re.search(r"\b(delayed|delay|late|cancelled flight|missed|stuck)\b", t) and has_plan:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", t)
        mins = None
        if m:
            v = float(m.group(1))
            mins = int(v * 60) if m.group(2).startswith("h") else int(v)
        return {"intent": "disruption", "delay_min": mins}
    if re.search(r"\b(my bookings?|booking status|voucher|confirmation)\b", t):
        return {"intent": "retrieve_bookings"}
    if re.search(r"change (my )?hotel|switch (to )?(the )?hotel|stay (at|in) (the )?[a-z]", t) and has_plan:
        return {"intent": "change_hotel"}
    if has_plan:
        for pat, name in [(r"cheaper|reduce (the )?(cost|budget)|save money|lower (the )?cost|less expensive", "cheaper"),
                          (r"better hotel|upgrade|nicer hotel|better stay", "better_hotel"),
                          (r"more sightseeing|add more (places|sights|attractions)|more places", "more_sightseeing"),
                          (r"reduce travel|less travel|shorter travel|reduce commute|travel time", "reduce_travel"),
                          (r"peaceful|quiet|calm", "peaceful"),
                          (r"avoid.*crowd|less crowd", "avoid_crowded"),
                          (r"add (more )?restaurants?|more food|better food|good restaurants", "add_restaurants"),
                          (r"change (my )?transport|different transport|train instead|flight instead|bus instead|cab instead|(switch|change|use|choose|take|go with|pick|select).{0,30}(cheapest|fastest|most comfortable|most convenient|cab|taxi|train|bus|flight|travel option)", "change_transport"),
                          (r"recalculate|recalc|budget", "recalc_budget"),
                          (r"why|explain|how did you", "explain"),
                          (r"safe|safety|emergency|hospital|police", "safety"),
                          (r"book|reserve|confirm", "book")]:
            if re.search(pat, t):
                return {"intent": name}
    if re.search(r"plan|trip|itinerary|visit|explore|going to|travel", t):
        return {"intent": "plan"}
    return {"intent": "chat"}


def mentioned_hotel(text: str, hotels: list[dict]) -> dict | None:
    t = text.lower()
    best = None
    for h in hotels:
        toks = [w for w in re.findall(r"[a-z]+", h["name"].lower()) if w not in ("the", "hotel", "inn", "stay", "house", "guest")]
        hit = sum(w in t for w in toks)
        if hit >= max(1, min(2, len(toks))) and (not best or hit > best[0]):
            best = (hit, h)
    return best[1] if best else None
