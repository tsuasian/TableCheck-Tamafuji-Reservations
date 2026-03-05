"""Lambda handler — checks TableCheck availability and sends alerts.

Triggered by EventBridge every 2 minutes:
  1. Read active WATCH items from DynamoDB
  2. Collect unique (date, party_size) pairs
  3. Call TableCheck API for each
  4. Detect newly available slots via DynamoDBStateTracker
  5. Send SMS/email to matching watchers (with dedup)
"""

import asyncio
import os
from collections import defaultdict
from datetime import date, timedelta

import boto3
from boto3.dynamodb.conditions import Attr, Key

from src.checker.api_checker import TableCheckSession, check_multiple_dates
from src.checker.models import TimeSlot
from src.config import Config
from src.storage.dynamodb_state import DynamoDBStateTracker


def handler(event, context):
    """Lambda entry point."""
    table_name = os.environ["TABLE_NAME"]

    table = boto3.resource("dynamodb").Table(table_name)
    state = DynamoDBStateTracker(table_name)

    # 1. Read active watches
    watches = _get_active_watches(table)
    if not watches:
        print("No active watches found")
        return {"checked": 0, "alerts": 0}

    # 2. Collect unique (date, party_size) pairs within the booking window
    today = date.today()
    window_start = today + timedelta(days=Config.BOOKING_WINDOW_MIN_DAYS)
    window_end = today + timedelta(days=Config.BOOKING_WINDOW_MAX_DAYS)

    checks_by_party_size = defaultdict(set)
    skipped_out_of_window = 0
    for w in watches:
        for d in w["dates"]:
            if d < today or d < window_start or d > window_end:
                skipped_out_of_window += 1
                continue
            checks_by_party_size[w["party_size"]].add(d)

    total_checks = sum(len(v) for v in checks_by_party_size.values())
    print(f"Active watches: {len(watches)}, "
          f"dates in window: {total_checks}, "
          f"skipped (outside {Config.BOOKING_WINDOW_MIN_DAYS}-{Config.BOOKING_WINDOW_MAX_DAYS}d window): {skipped_out_of_window}")

    # 3. Check availability for each party size (skip closed days)
    #    Single session shared across all party sizes to avoid extra init requests
    all_newly_available = []
    all_newly_available = asyncio.get_event_loop().run_until_complete(
        _check_all(checks_by_party_size, state)
    )

    if not all_newly_available:
        print("No new availability found")
        return {"checked": sum(len(v) for v in checks_by_party_size.values()), "alerts": 0}

    # 5. Match to watches and send alerts (with dedup)
    alerts_sent = _send_alerts(watches, all_newly_available, state)

    return {
        "checked": sum(len(v) for v in checks_by_party_size.values()),
        "new_slots": len(all_newly_available),
        "alerts": alerts_sent,
    }


def _get_active_watches(table) -> list[dict]:
    """Scan for all active WATCH items."""
    resp = table.scan(
        FilterExpression=Attr("SK").begins_with("WATCH#") & Attr("is_active").eq(True),
    )
    watches = []
    for item in resp.get("Items", []):
        phone = item["PK"].replace("USER#", "")
        dates = []
        for d in item.get("dates", []):
            try:
                dates.append(date.fromisoformat(d))
            except (ValueError, TypeError):
                continue
        if not dates:
            continue
        watches.append({
            "phone": phone,
            "watch_id": item["SK"].replace("WATCH#", ""),
            "party_size": int(item.get("party_size", 2)),
            "dates": dates,
            "preferred_times": item.get("preferred_times"),
        })
    return watches


async def _check_all(
    checks_by_party_size: dict[int, set],
    state: DynamoDBStateTracker,
) -> list[TimeSlot]:
    """Check all party sizes using a single TableCheck session."""
    all_newly_available = []
    async with TableCheckSession() as session:
        for party_size, date_set in checks_by_party_size.items():
            all_dates = sorted(date_set)
            dates = [d for d in all_dates if d.weekday() not in Config.CLOSED_WEEKDAYS]
            skipped = len(all_dates) - len(dates)
            if skipped:
                print(f"Skipped {skipped} closed day(s) (Tue)")
            if not dates:
                continue
            print(f"Checking {len(dates)} date(s) for party of {party_size}")

            snapshots = await check_multiple_dates(dates, party_size, session=session)

            for snapshot in snapshots:
                newly = state.update(snapshot)
                if newly:
                    print(f"  NEW: {len(newly)} slot(s) on {snapshot.slots[0].date}")
                    all_newly_available.extend(newly)
    return all_newly_available


def _match_slots(
    watch: dict,
    newly_available: list[TimeSlot],
    state: DynamoDBStateTracker,
    recipient: str,
) -> list[TimeSlot]:
    """Find slots matching a watch for a given recipient, with dedup."""
    matching = []
    for slot in newly_available:
        if slot.date not in watch["dates"]:
            continue
        if slot.party_size != watch["party_size"]:
            continue
        if watch["preferred_times"] and slot.time not in watch["preferred_times"]:
            continue
        if state.has_been_notified(recipient, slot):
            continue
        matching.append(slot)
    return matching


def _send_alerts(
    watches: list[dict],
    newly_available: list[TimeSlot],
    state: DynamoDBStateTracker,
) -> int:
    """Send SMS and email alerts to watchers for their matching slots, with dedup."""
    alerts_sent = 0

    # --- SMS channel ---
    sms = None
    if Config.SMS_ENABLED:
        try:
            from src.notifications.sms import SMSSender
            sms = SMSSender()
        except (ValueError, Exception) as e:
            print(f"SMS not available: {e}")

    for watch in watches:
        if not sms:
            break
        matching = _match_slots(watch, newly_available, state, watch["phone"])
        if not matching:
            continue
        print(f"SMS alerting {watch['phone']}: {len(matching)} slot(s)")
        try:
            sms.send_availability_alert(matching, watch["phone"])
            for slot in matching:
                state.record_notification(watch["phone"], slot, watch["watch_id"])
            alerts_sent += 1
        except Exception as e:
            print(f"  ERROR sending SMS to {watch['phone']}: {e}")

    # --- Email channel ---
    email_sender = None
    if Config.NOTIFY_EMAILS:
        try:
            from src.notifications.email_sender import EmailSender
            email_sender = EmailSender()
        except (ValueError, Exception) as e:
            print(f"Email not available: {e}")

    if email_sender:
        for to_email in Config.NOTIFY_EMAILS:
            for watch in watches:
                matching = _match_slots(watch, newly_available, state, to_email)
                if not matching:
                    continue
                print(f"Email alerting {to_email}: {len(matching)} slot(s)")
                try:
                    email_sender.send_availability_alert(matching, to_email)
                    for slot in matching:
                        state.record_notification(to_email, slot, watch["watch_id"])
                    alerts_sent += 1
                except Exception as e:
                    print(f"  ERROR sending email to {to_email}: {e}")

    if not sms and not email_sender:
        print("No notification channels available")

    return alerts_sent
