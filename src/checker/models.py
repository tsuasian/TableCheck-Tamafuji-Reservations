from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class SlotStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class TimeSlot:
    date: date
    time: str  # "16:00", "17:30", etc.
    status: SlotStatus
    party_size: int

    @property
    def display_time(self) -> str:
        h, m = self.time.split(":")
        hour = int(h)
        suffix = "AM" if hour < 12 else "PM"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        return f"{display_hour}:{m} {suffix}"

    @property
    def display_date(self) -> str:
        return self.date.strftime("%b %d (%a)")

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "time": self.time,
            "status": self.status.value,
            "party_size": self.party_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimeSlot":
        return cls(
            date=date.fromisoformat(data["date"]),
            time=data["time"],
            status=SlotStatus(data["status"]),
            party_size=data["party_size"],
        )


@dataclass
class AvailabilitySnapshot:
    checked_at: datetime
    party_size: int
    slots: list[TimeSlot] = field(default_factory=list)

    @property
    def available_slots(self) -> list[TimeSlot]:
        return [s for s in self.slots if s.status == SlotStatus.AVAILABLE]

    def to_dict(self) -> dict:
        return {
            "checked_at": self.checked_at.isoformat(),
            "party_size": self.party_size,
            "slots": [s.to_dict() for s in self.slots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AvailabilitySnapshot":
        return cls(
            checked_at=datetime.fromisoformat(data["checked_at"]),
            party_size=data["party_size"],
            slots=[TimeSlot.from_dict(s) for s in data["slots"]],
        )


@dataclass
class WatchConfig:
    party_size: int
    dates: list[date]
    preferred_times: list[str] | None = None  # None = any available slot

    def get_slots_for_date(self, d: date) -> list[str]:
        from src.config import Config

        is_weekend = d.weekday() >= 5
        all_slots = Config.WEEKEND_SLOTS if is_weekend else Config.WEEKDAY_SLOTS
        if self.preferred_times:
            return [t for t in all_slots if t in self.preferred_times]
        return all_slots
