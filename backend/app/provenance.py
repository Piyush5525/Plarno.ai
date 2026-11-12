"""Data provenance: every datum shown to a user is labelled live / cached / estimated / simulated."""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

Kind = Literal["live", "cached", "estimated", "simulated"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Provenance(BaseModel):
    source: str
    kind: Kind
    fetched_at: str
    confidence: float = 0.5
    note: Optional[str] = None


def simulated(source: str = "Plarno.ai demo dataset", note: str | None = None) -> dict:
    return Provenance(
        source=source, kind="simulated", fetched_at=now_iso(), confidence=0.3,
        note=note or "Synthetic demo data. Not a live fare, price or availability.",
    ).model_dump()


def estimated(source: str, note: str, confidence: float = 0.5) -> dict:
    return Provenance(source=source, kind="estimated", fetched_at=now_iso(),
                      confidence=confidence, note=note).model_dump()
