"""Tests for api_checker availability detection logic."""

import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.checker.api_checker import _check_with_session, _parse_display_time
from src.checker.models import SlotStatus


class FakeSession:
    """Fake TableCheckSession for testing without HTTP calls."""

    def __init__(self, sheets_response, timetable_response):
        self._sheets = sheets_response
        self._timetable = timetable_response

    async def get_sheets(self, target_date, party_size):
        return self._sheets

    async def get_timetable(self, target_date, party_size):
        return self._timetable


class TestParseDisplayTime:
    def test_pm(self):
        assert _parse_display_time("4:00 PM") == "16:00"

    def test_am(self):
        assert _parse_display_time("11:00 AM") == "11:00"

    def test_noon(self):
        assert _parse_display_time("12:00 PM") == "12:00"

    def test_midnight(self):
        assert _parse_display_time("12:00 AM") == "00:00"


class TestCheckWithSession:
    def test_timetable_with_available_slots(self):
        """When timetable has data with available=true, slots should be AVAILABLE."""
        target = date(2026, 3, 15)
        session = FakeSession(
            sheets_response=[("4:00 PM", 1776304800), ("5:30 PM", 1776310200)],
            timetable_response={
                "slots": {
                    "2026-03-15": {
                        "1776304800": {"available": True, "seconds": 57600},
                        "1776310200": {"available": False, "seconds": 63000},
                    }
                },
                "seconds": [57600, 63000],
            },
        )

        snapshot = asyncio.run(_check_with_session(session, target, 2))

        assert len(snapshot.slots) == 2
        assert snapshot.slots[0].status == SlotStatus.AVAILABLE
        assert snapshot.slots[0].time == "16:00"
        assert snapshot.slots[1].status == SlotStatus.UNAVAILABLE
        assert snapshot.slots[1].time == "17:30"

    def test_timetable_all_unavailable(self):
        """When timetable has data but all available=false, slots should be UNAVAILABLE."""
        target = date(2026, 3, 15)
        session = FakeSession(
            sheets_response=[("4:00 PM", 1776304800)],
            timetable_response={
                "slots": {
                    "2026-03-15": {
                        "1776304800": {"available": False, "seconds": 57600},
                    }
                },
                "seconds": [57600],
            },
        )

        snapshot = asyncio.run(_check_with_session(session, target, 2))

        assert len(snapshot.slots) == 1
        assert snapshot.slots[0].status == SlotStatus.UNAVAILABLE

    def test_empty_timetable_marks_unknown(self):
        """When timetable returns empty data, slots should be UNKNOWN (not UNAVAILABLE)."""
        target = date(2026, 4, 15)
        session = FakeSession(
            sheets_response=[("4:00 PM", 1776304800), ("5:30 PM", 1776310200)],
            timetable_response={"slots": {}, "seconds": []},
        )

        snapshot = asyncio.run(_check_with_session(session, target, 2))

        assert len(snapshot.slots) == 2
        assert all(s.status == SlotStatus.UNKNOWN for s in snapshot.slots)

    def test_no_sheets_no_timetable(self):
        """Closed day (e.g. Tuesday) — sheets empty, timetable empty."""
        target = date(2026, 3, 10)  # Tuesday
        session = FakeSession(
            sheets_response=[],
            timetable_response={"slots": {}, "seconds": []},
        )

        snapshot = asyncio.run(_check_with_session(session, target, 2))

        assert len(snapshot.slots) == 0

    def test_timetable_data_for_different_date_ignored(self):
        """Timetable may return surrounding dates — only use the target date's data."""
        target = date(2026, 3, 15)
        session = FakeSession(
            sheets_response=[("4:00 PM", 1776304800)],
            timetable_response={
                "slots": {
                    # Data for a different date — should not be used
                    "2026-03-14": {
                        "1776304800": {"available": True, "seconds": 57600},
                    }
                },
                "seconds": [57600],
            },
        )

        snapshot = asyncio.run(_check_with_session(session, target, 2))

        # No data for target date → UNKNOWN
        assert len(snapshot.slots) == 1
        assert snapshot.slots[0].status == SlotStatus.UNKNOWN
