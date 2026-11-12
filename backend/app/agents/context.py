"""Shared structured trip context - the single source of truth every agent reads and writes."""
from typing import Optional

from pydantic import BaseModel, Field


class TripContext(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    dates_assumed: bool = False
    days: Optional[int] = None
    adults: Optional[int] = None
    children: int = 0
    budget_inr: Optional[float] = None
    interests: list[str] = Field(default_factory=list)
    transport_pref: Optional[str] = None  # cheapest|fastest|comfortable|best_value
    vegetarian: bool = False
    vegan: bool = False
    pace: str = "balanced"
    peaceful: bool = False
    avoid_polluted: bool = False
    avoid_noisy: bool = False
    avoid_crowded: bool = False
    accessibility: list[str] = Field(default_factory=list)
    priority_preset: Optional[str] = None  # family|budget|sightseeing|peaceful
    weights: dict = Field(default_factory=dict)  # user-adjusted neighbourhood weights
    hotel_id: Optional[str] = None  # user-pinned hotel
    hotel_min_quality: bool = False
    extra_attractions: int = 0
    cheaper_factor: float = 1.0
    origin_geo: Optional[dict] = None
    stay_home: bool = False  # 'I live here': day trips from home, no hotel / no long-distance travel
    chosen_route_index: Optional[int] = None
    dest_geo: Optional[dict] = None  # verified geocode of the destination (any city worldwide)
    transport_relaxed: bool = False
    transport_explicit: bool = False  # the user chose a travel style in so many words: never relaxed automatically
    hotel_price_ceiling: Optional[float] = None  # 'make it cheaper' => must be strictly below this nightly price
    selected_attraction_ids: list[str] = Field(default_factory=list)

    @property
    def is_world(self) -> bool:
        """Delhi keeps the curated demo dataset; every other destination uses live worldwide providers."""
        return bool(self.destination) and self.destination.lower() not in ("delhi", "new delhi")

    @property
    def travellers(self) -> int:
        return (self.adults or 0) + self.children

    @property
    def nights(self) -> int:
        return max(1, (self.days or 1) - 1) if (self.days or 1) > 1 else 1

    def missing_required(self) -> list[str]:
        m = []
        if not self.destination:
            m.append("destination")
        if not self.days:
            m.append("days")
        if not self.adults:
            m.append("travellers")
        if not self.budget_inr:
            m.append("budget")
        return m

    def optional_follow_ups(self) -> list[str]:
        f = []
        if not self.origin and not self.stay_home:
            f.append("origin")
        if not self.start_date or self.dates_assumed:
            f.append("start_date")
        return f
