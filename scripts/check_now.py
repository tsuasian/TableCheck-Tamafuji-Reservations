#!/usr/bin/env python3
"""One-shot availability check.

Checks a specific date (or today + N days) and prints results.

Usage:
    python scripts/check_now.py                          # Check 30 days from now
    python scripts/check_now.py --date 2026-03-15        # Check specific date
    python scripts/check_now.py --days 14 21 30          # Check multiple offsets
    python scripts/check_now.py --party-size 4           # Party of 4
    python scripts/check_now.py --browser                # Use Playwright instead of API
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

from src.checker.models import SlotStatus
from src.config import Config


async def main():
    parser = argparse.ArgumentParser(description="Check Tamafuji availability")
    parser.add_argument("--date", type=str, help="Date to check (YYYY-MM-DD)")
    parser.add_argument(
        "--days",
        type=int,
        nargs="+",
        help="Days from today to check (e.g., 14 21 30)",
    )
    parser.add_argument(
        "--party-size",
        type=int,
        default=Config.DEFAULT_PARTY_SIZE,
        help=f"Party size (default: {Config.DEFAULT_PARTY_SIZE})",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Use Playwright browser instead of direct API",
    )
    args = parser.parse_args()

    # Determine which dates to check
    if args.date:
        dates = [date.fromisoformat(args.date)]
    elif args.days:
        today = date.today()
        dates = [today + timedelta(days=d) for d in args.days]
    else:
        today = date.today()
        dates = [today + timedelta(days=30)]

    party_size = args.party_size

    if args.browser:
        from src.checker.playwright_checker import check_availability, check_multiple_dates
        checker_name = "Playwright"
    else:
        from src.checker.api_checker import check_availability, check_multiple_dates
        checker_name = "API"

    print(f"Checking Tamafuji availability ({checker_name} checker)")
    print(f"  Party size: {party_size}")
    print(f"  Dates: {', '.join(d.isoformat() for d in dates)}")
    print()

    if len(dates) == 1:
        snapshot = await check_availability(dates[0], party_size)
        _print_snapshot(snapshot)
    else:
        snapshots = await check_multiple_dates(dates, party_size)
        for snapshot in snapshots:
            _print_snapshot(snapshot)
            print()


def _print_snapshot(snapshot):
    """Print a formatted availability snapshot."""
    if not snapshot.slots:
        print(f"  No slots found (checked at {snapshot.checked_at.strftime('%H:%M:%S')})")
        print(f"  Date may be outside the booking window.")
        return

    target_date = snapshot.slots[0].date
    is_weekend = target_date.weekday() >= 5
    day_type = "Weekend" if is_weekend else "Weekday"

    print(f"  {target_date.strftime('%A, %B %d, %Y')} ({day_type})")
    print(f"  Checked at: {snapshot.checked_at.strftime('%H:%M:%S')}")
    print(f"  Party size: {snapshot.party_size}")
    print()

    available_count = 0
    for slot in snapshot.slots:
        if slot.status == SlotStatus.AVAILABLE:
            icon = "O"
            available_count += 1
        elif slot.status == SlotStatus.UNAVAILABLE:
            icon = "X"
        else:
            icon = "?"
        print(f"    [{icon}] {slot.display_time}")

    print()
    if available_count > 0:
        print(f"  {available_count} slot(s) AVAILABLE!")
    else:
        print(f"  No slots available.")


if __name__ == "__main__":
    asyncio.run(main())
