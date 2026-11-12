"""Telegram bot: delivers emergency alerts (text + a live location that keeps updating) to the configured chat.
The bot token stays on the server and is never logged or returned. Message text is plain (no parse mode), so user-typed names cannot break or inject formatting."""
from .. import config
from . import base

API = "https://api.telegram.org/bot{token}/{method}"


def available() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID) and not config.OFFLINE


def _call(method: str, **payload) -> dict:
    """Returns Telegram's `result`; raises RuntimeError with Telegram's own description on failure (never includes the token)."""
    try:
        d = base.http_json("POST", API.format(token=config.TELEGRAM_BOT_TOKEN, method=method), retries=1, timeout=12, json=payload)
    except Exception as e:  # noqa: BLE001 - the URL contains the token: never let the original error text out
        raise RuntimeError(f"Telegram could not be reached ({type(e).__name__}).") from None
    if not d.get("ok"):
        raise RuntimeError("Telegram refused the message: " + str(d.get("description", "unknown error"))[:160])
    return d.get("result") or {}


def send_text(text: str, chat_id: str | None = None) -> int:
    return _call("sendMessage", chat_id=chat_id or config.TELEGRAM_CHAT_ID, text=text[:3900], disable_web_page_preview=True).get("message_id", 0)


def send_live_location(lat: float, lon: float, minutes: int = 15, chat_id: str | None = None) -> int:
    """A location pin that Telegram shows as live for `minutes`; returns its message id for later updates."""
    return _call("sendLocation", chat_id=chat_id or config.TELEGRAM_CHAT_ID, latitude=lat, longitude=lon, live_period=max(60, min(86400, minutes * 60))).get("message_id", 0)


def update_live_location(message_id: int, lat: float, lon: float, chat_id: str | None = None) -> None:
    try:
        _call("editMessageLiveLocation", chat_id=chat_id or config.TELEGRAM_CHAT_ID, message_id=message_id, latitude=lat, longitude=lon)
    except RuntimeError as e:
        if "not modified" not in str(e):  # the person has not moved: Telegram says so, and that is fine
            raise


def stop_live_location(message_id: int, chat_id: str | None = None) -> None:
    try:
        _call("stopMessageLiveLocation", chat_id=chat_id or config.TELEGRAM_CHAT_ID, message_id=message_id)
    except RuntimeError:
        pass  # already expired
