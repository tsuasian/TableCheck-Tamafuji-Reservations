"""Local JSON-based state tracking for availability changes."""

import json
import os
from datetime import datetime

from src.checker.models import AvailabilitySnapshot, SlotStatus, TimeSlot


class StateTracker:
    """Tracks availability state in a local JSON file and detects changes."""

    def __init__(self, state_file: str = "data/state.json"):
        self.state_file = state_file
        self._state: dict = self._load()

    def _load(self) -> dict:
        """Load state from disk."""
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {"slots": {}, "last_checked": None}

    def _save(self) -> None:
        """Persist state to disk."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2)

    def _slot_key(self, slot: TimeSlot) -> str:
        """Create a unique key for a slot."""
        return f"{slot.date.isoformat()}|{slot.time}|{slot.party_size}"

    def update(self, snapshot: AvailabilitySnapshot) -> list[TimeSlot]:
        """Update state with new snapshot and return newly available slots.

        Returns only slots that changed from unavailable/unknown → available.
        """
        newly_available = []

        for slot in snapshot.slots:
            key = self._slot_key(slot)
            prev_status = self._state["slots"].get(key, {}).get("status", "unknown")

            if (
                slot.status == SlotStatus.AVAILABLE
                and prev_status != SlotStatus.AVAILABLE.value
            ):
                newly_available.append(slot)

            self._state["slots"][key] = {
                "status": slot.status.value,
                "last_checked": snapshot.checked_at.isoformat(),
                "last_changed": (
                    datetime.now().isoformat()
                    if prev_status != slot.status.value
                    else self._state["slots"].get(key, {}).get(
                        "last_changed", datetime.now().isoformat()
                    )
                ),
            }

        self._state["last_checked"] = snapshot.checked_at.isoformat()
        self._save()

        return newly_available

    def get_slot_status(self, date_str: str, time: str, party_size: int) -> str:
        """Get the last known status for a slot."""
        key = f"{date_str}|{time}|{party_size}"
        return self._state["slots"].get(key, {}).get("status", "unknown")

    def get_all_available(self) -> list[dict]:
        """Get all slots currently marked as available."""
        available = []
        for key, data in self._state["slots"].items():
            if data["status"] == "available":
                date_str, time, party_size = key.split("|")
                available.append({
                    "date": date_str,
                    "time": time,
                    "party_size": int(party_size),
                    "last_checked": data["last_checked"],
                })
        return available

    def clear(self) -> None:
        """Reset all state."""
        self._state = {"slots": {}, "last_checked": None}
        self._save()
