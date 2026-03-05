"""AWS SES email notification sender."""

import boto3

from src.checker.models import TimeSlot
from src.config import Config


class EmailSender:
    """Sends email alerts via AWS SES when slots become available."""

    BOOKING_URL = Config.TABLECHECK_URL

    def __init__(self):
        if not Config.SES_FROM_EMAIL:
            raise ValueError(
                "SES not configured. Set SES_FROM_EMAIL in environment."
            )
        self.client = boto3.client("ses")
        self.from_email = Config.SES_FROM_EMAIL

    def send_availability_alert(
        self,
        slots: list[TimeSlot],
        to_email: str,
        name: str = None,
    ) -> str:
        """Send email alert for newly available slots.

        Returns SES message ID.
        """
        if not slots:
            return ""

        resp = self.client.send_email(
            Source=self.from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": self._format_subject(slots), "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": self._format_body_text(slots, name=name), "Charset": "UTF-8"},
                    "Html": {"Data": self._format_body_html(slots, name=name), "Charset": "UTF-8"},
                },
            },
        )
        message_id = resp["MessageId"]
        print(f"  Email sent to {to_email}: {message_id}")
        return message_id

    def notify_all(self, slots: list[TimeSlot]) -> list[str]:
        """Send alerts to all configured email recipients."""
        message_ids = []
        for email in Config.NOTIFY_EMAILS:
            try:
                mid = self.send_availability_alert(slots, email)
                if mid:
                    message_ids.append(mid)
            except Exception as e:
                print(f"  ERROR sending email to {email}: {e}")
        return message_ids

    def _format_subject(self, slots: list[TimeSlot]) -> str:
        if len(slots) == 1:
            s = slots[0]
            return f"Tamafuji: {s.display_date} @ {s.display_time} available!"
        return f"Tamafuji: {len(slots)} slots available!"

    def _format_body_text(self, slots: list[TimeSlot], name: str = None) -> str:
        """Plain text body (same format as SMS)."""
        greeting = f"Hi {name},\n\n" if name else ""
        if len(slots) == 1:
            s = slots[0]
            return (
                f"{greeting}Tamafuji slot open!\n"
                f"{s.display_date} @ {s.display_time} (party of {s.party_size})\n"
                f"Book now: {self.BOOKING_URL}"
            )

        lines = [f"{greeting}Tamafuji slots open!\n"]
        for s in slots:
            lines.append(f"- {s.display_date} @ {s.display_time}")
        lines.append(f"\nParty of {slots[0].party_size}")
        lines.append(f"Book: {self.BOOKING_URL}")
        return "\n".join(lines)

    def _format_body_html(self, slots: list[TimeSlot], name: str = None) -> str:
        """HTML body with table and booking link."""
        rows = ""
        for s in slots:
            rows += (
                f"<tr>"
                f"<td style='padding:6px 12px;border:1px solid #ddd'>{s.display_date}</td>"
                f"<td style='padding:6px 12px;border:1px solid #ddd'>{s.display_time}</td>"
                f"<td style='padding:6px 12px;border:1px solid #ddd'>{s.party_size}</td>"
                f"</tr>"
            )

        greeting = f"<p>Hi {name},</p>\n" if name else ""

        return f"""\
<html>
<body style="font-family:sans-serif;color:#333">
<h2 style="color:#b91c1c">Tamafuji Reservation Alert</h2>
{greeting}<p>New availability detected:</p>
<table style="border-collapse:collapse;margin:16px 0">
<tr style="background:#f3f4f6">
<th style="padding:6px 12px;border:1px solid #ddd;text-align:left">Date</th>
<th style="padding:6px 12px;border:1px solid #ddd;text-align:left">Time</th>
<th style="padding:6px 12px;border:1px solid #ddd;text-align:left">Party Size</th>
</tr>
{rows}
</table>
<p><a href="{self.BOOKING_URL}" style="background:#b91c1c;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;display:inline-block">Book Now</a></p>
<p style="color:#888;font-size:12px">Sent by Tamafuji Reservation Checker</p>
</body>
</html>"""
