"""DynamoDB-backed state tracking for availability changes.

Replaces the local JSON StateTracker for Lambda deployment.

DynamoDB schema (single-table):
  AVAIL#<date>  SLOT#<time>#<party_size>  — slot availability records
  NOTIFY#<phone>#<date>  SLOT#<time>       — dedup records (TTL 2hr)
"""

import time
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

from src.checker.models import AvailabilitySnapshot, SlotStatus, TimeSlot


class DynamoDBStateTracker:
    """Tracks availability state in DynamoDB and detects changes."""

    NOTIFY_TTL_SECONDS = 2 * 60 * 60  # 2 hours

    def __init__(self, table_name: str):
        self._table = boto3.resource("dynamodb").Table(table_name)

    def update(self, snapshot: AvailabilitySnapshot) -> list[TimeSlot]:
        """Update state with new snapshot and return newly available slots."""
        newly_available = []
        now_iso = snapshot.checked_at.isoformat()

        for slot in snapshot.slots:
            # Skip UNKNOWN slots — no point tracking dates outside the booking window
            if slot.status == SlotStatus.UNKNOWN:
                continue

            pk = f"AVAIL#{slot.date.isoformat()}"
            sk = f"SLOT#{slot.time}#{slot.party_size}"

            # Read previous status
            resp = self._table.get_item(Key={"PK": pk, "SK": sk})
            prev = resp.get("Item", {})
            prev_status = prev.get("status", "unknown")

            new_status = slot.status.value
            changed = prev_status != new_status

            if slot.status == SlotStatus.AVAILABLE and prev_status != "available":
                newly_available.append(slot)

            self._table.put_item(Item={
                "PK": pk,
                "SK": sk,
                "status": new_status,
                "party_size": slot.party_size,
                "date": slot.date.isoformat(),
                "time": slot.time,
                "last_checked": now_iso,
                "last_changed": now_iso if changed else prev.get("last_changed", now_iso),
            })

        return newly_available

    def has_been_notified(self, phone: str, slot: TimeSlot) -> bool:
        """Check if we already sent a notification for this slot recently."""
        pk = f"NOTIFY#{phone}#{slot.date.isoformat()}"
        sk = f"SLOT#{slot.time}"
        resp = self._table.get_item(Key={"PK": pk, "SK": sk})
        item = resp.get("Item")
        if not item:
            return False
        # If TTL has passed but DynamoDB hasn't cleaned it up yet, treat as expired
        return item.get("ttl", 0) > int(time.time())

    def record_notification(self, phone: str, slot: TimeSlot, watch_id: str = "") -> None:
        """Record that we notified this phone about this slot (with TTL)."""
        pk = f"NOTIFY#{phone}#{slot.date.isoformat()}"
        sk = f"SLOT#{slot.time}"
        self._table.put_item(Item={
            "PK": pk,
            "SK": sk,
            "notified_at": datetime.now().isoformat(),
            "watch_id": watch_id,
            "ttl": int(time.time()) + self.NOTIFY_TTL_SECONDS,
        })

    def get_slot_status(self, date_str: str, time_str: str, party_size: int) -> str:
        """Get the last known status for a slot."""
        pk = f"AVAIL#{date_str}"
        sk = f"SLOT#{time_str}#{party_size}"
        resp = self._table.get_item(Key={"PK": pk, "SK": sk})
        return resp.get("Item", {}).get("status", "unknown")

    def get_all_available(self) -> list[dict]:
        """Get all AVAIL items with status=available.

        Note: This scans the table. Fine at our scale (<1000 items).
        """
        resp = self._table.scan(
            FilterExpression="begins_with(PK, :prefix) AND #s = :avail",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":prefix": "AVAIL#", ":avail": "available"},
        )
        return [
            {
                "date": item["date"],
                "time": item["time"],
                "party_size": int(item["party_size"]),
                "last_checked": item["last_checked"],
            }
            for item in resp.get("Items", [])
        ]
