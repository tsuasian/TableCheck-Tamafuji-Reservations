"""Direct HTTP-based availability checker for TableCheck.

Uses the discovered JSON API endpoints:
  - /sheets → bookable time slots with display names and epoch timestamps
  - /available/timetable → per-slot availability (available: true/false)

No browser needed — just httpx with a session cookie + CSRF token.
"""

import re
from datetime import date, datetime

import httpx

from src.checker.models import AvailabilitySnapshot, SlotStatus, TimeSlot
from src.config import Config


class TableCheckSession:
    """Manages a TableCheck session (CSRF token + cookies)."""

    BASE_URL = "https://www.tablecheck.com"

    def __init__(self, shop_slug: str = Config.TABLECHECK_SHOP_SLUG):
        self.shop_slug = shop_slug
        self._client: httpx.AsyncClient | None = None
        self._csrf: str = ""

    async def __aenter__(self):
        self._client = httpx.AsyncClient(follow_redirects=True)
        await self._init_session()
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _init_session(self):
        """Load the reservation page to get CSRF token and session cookie."""
        resp = await self._client.get(
            f"{self.BASE_URL}/en/shops/{self.shop_slug}/reserve",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

        match = re.search(
            r'name="authenticity_token"[^>]*value="([^"]+)"', resp.text
        )
        if not match:
            raise RuntimeError("Could not extract CSRF token from page")
        self._csrf = match.group(1)

    async def _api_get(self, path: str, params: dict) -> dict:
        """Make an authenticated GET request to a TableCheck API endpoint."""
        params["authenticity_token"] = self._csrf
        resp = await self._client.get(
            f"{self.BASE_URL}/en/shops/{self.shop_slug}/{path}",
            params=params,
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def get_sheets(
        self, target_date: date, party_size: int
    ) -> list[tuple[str, int]]:
        """Get bookable time slots for a date.

        Returns list of (display_time, epoch_timestamp) tuples.
        e.g. [("4:00 PM", 1776304800), ("5:30 PM", 1776310200), ...]
        """
        data = await self._api_get(
            "sheets",
            {
                "reservation[start_date]": target_date.isoformat(),
                "reservation[num_people_adult]": str(party_size),
            },
        )
        return [(s[0], s[1]) for s in data.get("slots", [])]

    async def get_timetable(
        self, target_date: date, party_size: int
    ) -> dict:
        """Get availability timetable for a date and surrounding dates.

        Returns the raw timetable data with per-slot availability.
        """
        data = await self._api_get(
            "available/timetable",
            {
                "reservation[start_date]": target_date.isoformat(),
                "reservation[num_people_adult]": str(party_size),
            },
        )
        return data.get("data", {})


def _seconds_to_time(seconds: int) -> str:
    """Convert seconds-since-midnight to HH:MM format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def _parse_display_time(display: str) -> str:
    """Convert '4:00 PM' to '16:00' format."""
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", display, re.IGNORECASE)
    if not match:
        return display
    hour = int(match.group(1))
    minute = match.group(2)
    period = match.group(3).upper()
    if period == "PM" and hour != 12:
        hour += 12
    elif period == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


async def check_availability(
    target_date: date,
    party_size: int = Config.DEFAULT_PARTY_SIZE,
) -> AvailabilitySnapshot:
    """Check slot availability for a specific date and party size."""
    async with TableCheckSession() as session:
        return await _check_with_session(session, target_date, party_size)


async def check_multiple_dates(
    dates: list[date],
    party_size: int = Config.DEFAULT_PARTY_SIZE,
) -> list[AvailabilitySnapshot]:
    """Check availability across multiple dates, reusing one session."""
    async with TableCheckSession() as session:
        results = []
        for d in dates:
            snapshot = await _check_with_session(session, d, party_size)
            results.append(snapshot)
        return results


async def _check_with_session(
    session: TableCheckSession,
    target_date: date,
    party_size: int,
) -> AvailabilitySnapshot:
    """Check availability using an existing session."""
    # Get bookable time slots (display names + epochs)
    sheets = await session.get_sheets(target_date, party_size)

    # Get availability timetable
    timetable = await session.get_timetable(target_date, party_size)

    # Cross-reference: for each bookable slot, check if it's available
    date_str = target_date.isoformat()
    date_slots = timetable.get("slots", {}).get(date_str, {})

    slots = []
    for display_time, epoch in sheets:
        epoch_str = str(epoch)
        slot_data = date_slots.get(epoch_str, {})
        is_available = slot_data.get("available", False)

        slots.append(TimeSlot(
            date=target_date,
            time=_parse_display_time(display_time),
            status=SlotStatus.AVAILABLE if is_available else SlotStatus.UNAVAILABLE,
            party_size=party_size,
        ))

    # If sheets returned nothing but timetable has data, extract from timetable
    if not slots and date_slots:
        for epoch_str, slot_data in date_slots.items():
            seconds = slot_data.get("seconds", 0)
            time_str = _seconds_to_time(seconds)
            is_available = slot_data.get("available", False)

            slots.append(TimeSlot(
                date=target_date,
                time=time_str,
                status=SlotStatus.AVAILABLE if is_available else SlotStatus.UNAVAILABLE,
                party_size=party_size,
            ))
        slots.sort(key=lambda s: s.time)

    return AvailabilitySnapshot(
        checked_at=datetime.now(),
        party_size=party_size,
        slots=slots,
    )
