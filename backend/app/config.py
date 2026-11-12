import os
from pathlib import Path


def _load_dotenv():
    """Minimal .env loader (repo root). Existing environment variables win. Keys are never logged."""
    f = Path(__file__).resolve().parent.parent.parent / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("PLARNO_DB", str(BASE_DIR / "plarno.db"))
SECRET_KEY = os.environ.get("PLARNO_SECRET", "")  # must be set in production
TOKEN_TTL_SECONDS = int(os.environ.get("PLARNO_TOKEN_TTL", "86400"))
CORS_ORIGINS = os.environ.get("PLARNO_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
LLM_PROVIDER = os.environ.get("PLARNO_LLM", "rules")  # "rules" (deterministic, default)
ROUTING_PROVIDER = os.environ.get("PLARNO_ROUTING", "haversine")  # or "osrm"
OSRM_URL = os.environ.get("OSRM_URL", "")
RATE_LIMIT_PER_MIN = int(os.environ.get("PLARNO_RATE_LIMIT", "300"))  # per IP; a page with a live map, guide and chat makes several calls at once
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("PLARNO_ADMIN_EMAILS", "").split(",") if e.strip()]
OFFLINE = os.environ.get("PLARNO_OFFLINE", "") == "1"  # disables all live provider calls (tests)
AQICN_KEY = os.environ.get("AQICN_API", "")
OPENWEATHER_KEY = os.environ.get("WEATHER_API", "")
MAPBOX_TOKEN = os.environ.get("MAPBOX_API", "")  # public pk. token, safe to expose to the browser
GEMINI_KEY = os.environ.get("GEMINI_API", "")
def _first(*names: str) -> str:
    """First non-empty env var among aliases (the original .env used names with spaces/mixed case)."""
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return ""


SERP_KEY = _first("SERP_API")
SERP_FLIGHTS_KEY = _first("SERP_GOOGLE_FLIGHTS_API_KEY", "SERP(GOOGLE FLIGHT)_API", "SERP_API")
RAPIDAPI_KEY = _first("RAPIDAPI_KEY", "RapidAPI")
STAYING_KEY = _first("STAYING_API", "Staying_API")
QRAIL_KEY = _first("QRAIL_API", "Qrail_API")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")   # emergency alerts are delivered by this bot (server-side only)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")       # the chat that receives them
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io/api/")  # as-you-type search incl. colleges/stations; self-host for heavy use
OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
SERP_DAILY_CAP = int(os.environ.get("PLARNO_SERP_DAILY_CAP", os.environ.get("PLARNO_FLIGHT_SEARCHES_PER_DAY", "100")))  # shared guard for ALL SerpApi calls (free plan: 250/month)
FLIGHT_SEARCHES_PER_DAY = SERP_DAILY_CAP
