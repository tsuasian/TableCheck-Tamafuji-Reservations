"""Twilio SMS notification sender."""

from twilio.rest import Client

from src.checker.models import TimeSlot
from src.config import Config


class SMSSender:
    """Sends SMS alerts via Twilio when slots become available."""

    BOOKING_URL = Config.TABLECHECK_URL

    def __init__(self):
        if not Config.TWILIO_ACCOUNT_SID or not Config.TWILIO_AUTH_TOKEN:
            raise ValueError(
                "Twilio credentials not configured. "
                "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env"
            )
        self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        self.from_number = Config.TWILIO_FROM_NUMBER

    def send_availability_alert(
        self,
        slots: list[TimeSlot],
        to_number: str,
    ) -> list[str]:
        """Send SMS alert for newly available slots.

        Returns list of Twilio message SIDs.
        """
        if not slots:
            return []

        message_body = self._format_message(slots)
        sids = []

        message = self.client.messages.create(
            body=message_body,
            from_=self.from_number,
            to=to_number,
        )
        sids.append(message.sid)
        print(f"  SMS sent to {to_number}: {message.sid}")

        return sids

    def notify_all(self, slots: list[TimeSlot]) -> list[str]:
        """Send alerts to all configured recipients."""
        all_sids = []
        for phone in Config.NOTIFY_PHONES:
            try:
                sids = self.send_availability_alert(slots, phone)
                all_sids.extend(sids)
            except Exception as e:
                print(f"  ERROR sending to {phone}: {e}")
        return all_sids

    def send_test(self, to_number: str) -> str:
        """Send a test SMS to verify Twilio is working."""
        message = self.client.messages.create(
            body="Tamafuji Reservation Checker is active! You'll get alerts when slots open up.",
            from_=self.from_number,
            to=to_number,
        )
        print(f"  Test SMS sent to {to_number}: {message.sid}")
        return message.sid

    def _format_message(self, slots: list[TimeSlot]) -> str:
        """Format availability alert message."""
        if len(slots) == 1:
            s = slots[0]
            return (
                f"Tamafuji slot open!\n"
                f"{s.display_date} @ {s.display_time} (party of {s.party_size})\n"
                f"Book now: {self.BOOKING_URL}"
            )

        # Multiple slots
        lines = ["Tamafuji slots open!\n"]
        for s in slots[:5]:  # Cap at 5 to stay within SMS limits
            lines.append(f"- {s.display_date} @ {s.display_time}")

        if len(slots) > 5:
            lines.append(f"  ...and {len(slots) - 5} more")

        lines.append(f"\nParty of {slots[0].party_size}")
        lines.append(f"Book: {self.BOOKING_URL}")

        return "\n".join(lines)
