"""Tests for the checker Lambda handler — booking window filtering."""

import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config


class TestBookingWindowFiltering:
    """Test that only dates within the booking window are checked."""

    def test_past_dates_excluded(self):
        """Dates in the past should be excluded from checks."""
        today = date.today()
        past = today - timedelta(days=5)
        in_window = today + timedelta(days=14)

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [past, in_window],
                "preferred_times": None,
            }
        ]

        dates_to_check = _filter_dates_like_handler(watches, today)
        assert past not in dates_to_check
        assert in_window in dates_to_check

    def test_too_close_dates_excluded(self):
        """Dates closer than BOOKING_WINDOW_MIN_DAYS should be excluded."""
        today = date.today()
        too_close = today + timedelta(days=3)
        in_window = today + timedelta(days=14)

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [too_close, in_window],
                "preferred_times": None,
            }
        ]

        dates_to_check = _filter_dates_like_handler(watches, today)
        assert too_close not in dates_to_check
        assert in_window in dates_to_check

    def test_too_far_dates_excluded(self):
        """Dates beyond BOOKING_WINDOW_MAX_DAYS should be excluded."""
        today = date.today()
        too_far = today + timedelta(days=60)
        in_window = today + timedelta(days=14)

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [too_far, in_window],
                "preferred_times": None,
            }
        ]

        dates_to_check = _filter_dates_like_handler(watches, today)
        assert too_far not in dates_to_check
        assert in_window in dates_to_check

    def test_window_boundaries_inclusive(self):
        """Dates exactly at window boundaries should be included."""
        today = date.today()
        at_min = today + timedelta(days=Config.BOOKING_WINDOW_MIN_DAYS)
        at_max = today + timedelta(days=Config.BOOKING_WINDOW_MAX_DAYS)

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [at_min, at_max],
                "preferred_times": None,
            }
        ]

        dates_to_check = _filter_dates_like_handler(watches, today)
        assert at_min in dates_to_check
        assert at_max in dates_to_check

    def test_reduces_api_calls_significantly(self):
        """A 2-month watch range should be reduced to ~3 weeks of checks."""
        today = date.today()
        # Simulate a watch with 60 dates (2 months)
        all_dates = [today + timedelta(days=i) for i in range(60)]

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": all_dates,
                "preferred_times": None,
            }
        ]

        dates_to_check = _filter_dates_like_handler(watches, today)
        window_size = Config.BOOKING_WINDOW_MAX_DAYS - Config.BOOKING_WINDOW_MIN_DAYS + 1
        assert len(dates_to_check) <= window_size
        assert len(dates_to_check) < len(all_dates)


def _filter_dates_like_handler(watches, today):
    """Replicate the date filtering logic from the handler."""
    window_start = today + timedelta(days=Config.BOOKING_WINDOW_MIN_DAYS)
    window_end = today + timedelta(days=Config.BOOKING_WINDOW_MAX_DAYS)

    all_dates = set()
    for w in watches:
        for d in w["dates"]:
            if d < today or d < window_start or d > window_end:
                continue
            all_dates.add(d)
    return all_dates
