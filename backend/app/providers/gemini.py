"""Gemini (generativelanguage API) provider: structured trip-field extraction and grounded travel Q&A.
Design rule: the model only fills *language-understanding* fields that are validated here; every number the user sees
(prices, distances, scores) still comes from deterministic services. Results are cached; failures fall back to rules."""
import json
import re

from .. import config
from . import base

import os

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")  # alias: survives model retirements (gemini-2.5-flash is closed to new accounts)
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
CITIES = {"Delhi", "Jaipur", "Agra", "Chandigarh", "Manali", "Kullu (Bhuntar)", "Mumbai", "Bengaluru", "Kolkata", "Lucknow", "Varanasi", "Goa"}
SCHEMA_HINT = """Extract travel-planning fields from the user's message. Reply with ONLY JSON using these optional keys (omit unknown ones, never guess):
origin (city name anywhere in the world), destination (city/place name anywhere in the world), start_date (YYYY-MM-DD), days (int), adults (int), children (int), budget_inr (number, total trip budget in INR),
interests (array of: history, food, museum, religious, shopping, garden, peaceful), vegetarian (bool), vegan (bool), peaceful (bool),
avoid_polluted (bool), avoid_noisy (bool), avoid_crowded (bool), transport_pref (cheapest|fastest|comfortable|best_value), pace (relaxed|balanced|packed)."""


def available() -> bool:
    return bool(config.GEMINI_KEY) and not config.OFFLINE


def _call(system: str, user: str, json_mode: bool) -> str | None:
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1 if json_mode else 0.4, "maxOutputTokens": 700, **({"responseMimeType": "application/json"} if json_mode else {})}}
    d = base.http_json("POST", URL, retries=1, timeout=25, headers={"x-goog-api-key": config.GEMINI_KEY}, json=body)
    parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts) or None


def validate(raw: dict) -> dict:
    """Strict whitelist + type/range checks; anything doubtful is dropped."""
    out: dict = {}
    for k in ("origin", "destination"):  # any real-world place: geocoding validates it afterwards
        v = raw.get(k)
        if isinstance(v, str) and 2 <= len(v.strip()) <= 60 and not re.search(r"[\d@/\\]", v):
            out[k] = v.strip()
    if isinstance(raw.get("days"), int) and 1 <= raw["days"] <= 30:
        out["days"] = raw["days"]
    if isinstance(raw.get("adults"), int) and 1 <= raw["adults"] <= 20:
        out["adults"] = raw["adults"]
    if isinstance(raw.get("children"), int) and 0 <= raw["children"] <= 20:
        out["children"] = raw["children"]
    if isinstance(raw.get("budget_inr"), (int, float)) and 1000 <= raw["budget_inr"] <= 10_000_000:
        out["budget_inr"] = float(raw["budget_inr"])
    if isinstance(raw.get("start_date"), str) and len(raw["start_date"]) == 10:
        out["start_date"] = raw["start_date"]
    ints = [i for i in (raw.get("interests") or []) if i in {"history", "food", "museum", "religious", "shopping", "garden", "peaceful"}]
    if ints:
        out["interests"] = ints
    for k in ("vegetarian", "vegan", "peaceful", "avoid_polluted", "avoid_noisy", "avoid_crowded"):
        if raw.get(k) is True:
            out[k] = True
    if raw.get("transport_pref") in ("cheapest", "fastest", "comfortable", "best_value"):
        out["transport_pref"] = raw["transport_pref"]
    if raw.get("pace") in ("relaxed", "balanced", "packed"):
        out["pace"] = raw["pace"]
    return out


def extract_fields(message: str) -> dict:
    if not available():
        return {}
    data, _, _ = base.cached_fetch("gemini:extract:" + message.strip().lower()[:400], 86400,
                                   lambda: {"t": _call(SCHEMA_HINT, message, True)})
    try:
        return validate(json.loads(data["t"])) if data and data.get("t") else {}
    except (ValueError, TypeError):
        return {}


def answer(question: str, facts: str) -> str | None:
    """Grounded Q&A: the model may only use the supplied facts (live app data) and general travel knowledge, never invent prices."""
    if not available():
        return None
    system = ("You are TRIP, the assistant of Plarno.ai, a travel planner. Answer in <=4 short sentences. Use ONLY the FACTS for any number, price, "
              "time, rating or availability; if they are absent say you don't have that data. Never claim anything is guaranteed safe.")
    try:
        return _call(system, f"FACTS:\n{facts}\n\nQUESTION: {question}", False)
    except Exception:  # noqa: BLE001
        return None
