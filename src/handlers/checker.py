"""Lambda handler — checks TableCheck availability and sends SMS alerts.

Triggered by EventBridge every 2 minutes:
  1. Read active WATCH items from DynamoDB
  2. Collect unique (date, party_size) pairs
  3. Call TableCheck API for each
  4. Detect newly available slots via DynamoDBStateTracker
  5. Send SMS to matching watchers (with dedup)
"""

import asyncio
import os
from collections import defaultdict
from datetime import date

import boto3
from boto3.dynamodb.conditions import Attr, Key

from src.checker.api_checker import check_multiple_dates
from src.checker.models import TimeSlot
from src.config import Config
from src.notifications.sms import SMSSender
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

    # 2. Collect unique (date, party_size) pairs
    checks_by_party_size = defaultdict(set)
    for w in watches:
        for d in w["dates"]:
            checks_by_party_size[w["party_size"]].add(d)

    print(f"Active watches: {len(watches)}, "
          f"unique checks: {sum(len(v) for v in checks_by_party_size.values())}")

    # 3. Check availability for each party size (skip closed days)
    all_newly_available = []
    for party_size, date_set in checks_by_party_size.items():
        all_dates = sorted(date_set)
        dates = [d for d in all_dates if d.weekday() not in Config.CLOSED_WEEKDAYS]
        skipped = len(all_dates) - len(dates)
        if skipped:
            print(f"Skipped {skipped} closed day(s) (Tue)")
        if not dates:
            continue
        print(f"Checking {len(dates)} date(s) for party of {party_size}")

        snapshots = asyncio.get_event_loop().run_until_complete(
            check_multiple_dates(dates, party_size)
        )

        # 4. Update state, collect newly available
        for snapshot in snapshots:
            newly = state.update(snapshot)
            if newly:
                print(f"  NEW: {len(newly)} slot(s) on {snapshot.slots[0].date}")
                all_newly_available.extend(newly)

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


def _send_alerts(
    watches: list[dict],
    newly_available: list[TimeSlot],
    state: DynamoDBStateTracker,
) -> int:
    """Send SMS alerts to watchers for their matching slots, with dedup."""
    try:
        sms = SMSSender()
    except ValueError as e:
        print(f"SMS not configured: {e}")
        return 0

    alerts_sent = 0
    for watch in watches:
        # Find slots matching this watch
        matching = []
        for slot in newly_available:
            if slot.date not in watch["dates"]:
                continue
            if slot.party_size != watch["party_size"]:
                continue
            if watch["preferred_times"] and slot.time not in watch["preferred_times"]:
                continue
            # Dedup check
            if state.has_been_notified(watch["phone"], slot):
                continue
            matching.append(slot)

        if not matching:
            continue

        print(f"Alerting {watch['phone']}: {len(matching)} slot(s)")
        try:
            sms.send_availability_alert(matching, watch["phone"])
            for slot in matching:
                state.record_notification(watch["phone"], slot, watch["watch_id"])
            alerts_sent += 1
        except Exception as e:
            print(f"  ERROR sending to {watch['phone']}: {e}")

    return alerts_sent
