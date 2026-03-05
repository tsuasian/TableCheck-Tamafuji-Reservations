"""Tests for DynamoDB state tracker — UNKNOWN slot handling."""

from datetime import datetime

import pytest
from moto import mock_aws

from src.checker.models import AvailabilitySnapshot, SlotStatus, TimeSlot
from src.storage.dynamodb_state import DynamoDBStateTracker


@mock_aws
def test_update_skips_unknown_slots(dynamodb_table):
    """UNKNOWN slots should not be written to DynamoDB."""
    tracker = DynamoDBStateTracker("test-table")

    from datetime import date

    snapshot = AvailabilitySnapshot(
        checked_at=datetime.now(),
        party_size=2,
        slots=[
            TimeSlot(date=date(2026, 3, 15), time="16:00", status=SlotStatus.UNKNOWN, party_size=2),
            TimeSlot(date=date(2026, 3, 15), time="17:30", status=SlotStatus.UNAVAILABLE, party_size=2),
        ],
    )

    newly = tracker.update(snapshot)

    assert newly == []

    # UNKNOWN slot should NOT be in DynamoDB
    resp = dynamodb_table.get_item(Key={"PK": "AVAIL#2026-03-15", "SK": "SLOT#16:00#2"})
    assert "Item" not in resp

    # UNAVAILABLE slot SHOULD be in DynamoDB
    resp = dynamodb_table.get_item(Key={"PK": "AVAIL#2026-03-15", "SK": "SLOT#17:30#2"})
    assert resp["Item"]["status"] == "unavailable"


@mock_aws
def test_update_detects_newly_available(dynamodb_table):
    """Slot transitioning from unavailable to available should be detected."""
    tracker = DynamoDBStateTracker("test-table")
    from datetime import date

    # First check: slot is unavailable
    snap1 = AvailabilitySnapshot(
        checked_at=datetime.now(),
        party_size=2,
        slots=[
            TimeSlot(date=date(2026, 3, 15), time="16:00", status=SlotStatus.UNAVAILABLE, party_size=2),
        ],
    )
    newly = tracker.update(snap1)
    assert newly == []

    # Second check: slot becomes available (cancellation!)
    snap2 = AvailabilitySnapshot(
        checked_at=datetime.now(),
        party_size=2,
        slots=[
            TimeSlot(date=date(2026, 3, 15), time="16:00", status=SlotStatus.AVAILABLE, party_size=2),
        ],
    )
    newly = tracker.update(snap2)

    assert len(newly) == 1
    assert newly[0].time == "16:00"
    assert newly[0].status == SlotStatus.AVAILABLE


@mock_aws
def test_dedup_prevents_duplicate_notifications(dynamodb_table):
    """Notification dedup should prevent re-alerting within TTL window."""
    tracker = DynamoDBStateTracker("test-table")
    from datetime import date

    slot = TimeSlot(date=date(2026, 3, 15), time="16:00", status=SlotStatus.AVAILABLE, party_size=2)

    assert not tracker.has_been_notified("test@example.com", slot)

    tracker.record_notification("test@example.com", slot, "watch123")

    assert tracker.has_been_notified("test@example.com", slot)
