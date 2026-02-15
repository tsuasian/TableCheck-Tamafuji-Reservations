#!/usr/bin/env python3
"""Seed a WATCH item in DynamoDB for testing.

Usage:
    python scripts/seed_watch.py --phone +18084782204 --dates 2026-03-14 2026-03-15 --party-size 2
    python scripts/seed_watch.py --phone +18084782204 --dates 2026-03-14 --times 17:00 18:30
    python scripts/seed_watch.py --list                # list all watches
    python scripts/seed_watch.py --delete WATCH_ID --phone +18084782204

Requires TABLE_NAME env var or --table flag.
"""

import argparse
import sys
import uuid
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Attr


def get_table(table_name: str):
    return boto3.resource("dynamodb").Table(table_name)


def seed_watch(table, phone: str, dates: list[str], party_size: int,
               preferred_times: list[str] | None = None) -> str:
    watch_id = str(uuid.uuid4())[:8]
    item = {
        "PK": f"USER#{phone}",
        "SK": f"WATCH#{watch_id}",
        "party_size": party_size,
        "dates": dates,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }
    if preferred_times:
        item["preferred_times"] = preferred_times

    table.put_item(Item=item)
    print(f"Created watch {watch_id} for {phone}")
    print(f"  Dates: {', '.join(dates)}")
    print(f"  Party size: {party_size}")
    if preferred_times:
        print(f"  Preferred times: {', '.join(preferred_times)}")
    return watch_id


def list_watches(table):
    resp = table.scan(
        FilterExpression=Attr("SK").begins_with("WATCH#"),
    )
    items = resp.get("Items", [])
    if not items:
        print("No watches found")
        return

    for item in sorted(items, key=lambda x: x.get("created_at", "")):
        phone = item["PK"].replace("USER#", "")
        watch_id = item["SK"].replace("WATCH#", "")
        active = item.get("is_active", False)
        dates = item.get("dates", [])
        party = item.get("party_size", "?")
        times = item.get("preferred_times")
        status = "ACTIVE" if active else "INACTIVE"
        print(f"[{status}] {watch_id}  phone={phone}  party={party}  dates={dates}"
              + (f"  times={times}" if times else ""))


def delete_watch(table, phone: str, watch_id: str):
    table.delete_item(Key={"PK": f"USER#{phone}", "SK": f"WATCH#{watch_id}"})
    print(f"Deleted watch {watch_id} for {phone}")


def main():
    import os

    parser = argparse.ArgumentParser(description="Seed WATCH items in DynamoDB")
    parser.add_argument("--table", default=os.environ.get("TABLE_NAME", ""),
                        help="DynamoDB table name (or set TABLE_NAME env var)")
    parser.add_argument("--phone", help="Phone number in E.164 format")
    parser.add_argument("--dates", nargs="+", help="Dates to watch (YYYY-MM-DD)")
    parser.add_argument("--party-size", type=int, default=2)
    parser.add_argument("--times", nargs="+", help="Preferred times (HH:MM, 24h)")
    parser.add_argument("--list", action="store_true", help="List all watches")
    parser.add_argument("--delete", metavar="WATCH_ID", help="Delete a watch by ID")
    args = parser.parse_args()

    if not args.table:
        print("ERROR: Set TABLE_NAME env var or pass --table", file=sys.stderr)
        sys.exit(1)

    table = get_table(args.table)

    if args.list:
        list_watches(table)
    elif args.delete:
        if not args.phone:
            print("ERROR: --phone is required for --delete", file=sys.stderr)
            sys.exit(1)
        delete_watch(table, args.phone, args.delete)
    else:
        if not args.phone or not args.dates:
            print("ERROR: --phone and --dates are required", file=sys.stderr)
            sys.exit(1)
        seed_watch(table, args.phone, args.dates, args.party_size, args.times)


if __name__ == "__main__":
    main()
