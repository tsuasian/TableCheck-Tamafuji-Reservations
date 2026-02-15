#!/usr/bin/env python3
"""Continuous availability monitor.

Checks availability at regular intervals and sends SMS when new slots open.

Usage:
    python scripts/monitor.py                                    # Monitor 30 days out
    python scripts/monitor.py --dates 2026-03-15 2026-03-16      # Specific dates
    python scripts/monitor.py --days 28 29 30                    # Days from today
    python scripts/monitor.py --party-size 4                     # Party of 4
    python scripts/monitor.py --interval 60                      # Check every 60s
    python scripts/monitor.py --no-sms                           # Print only, no SMS
"""

import argparse
import asyncio
import signal
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, ".")

from src.checker.api_checker import check_multiple_dates
from src.checker.models import SlotStatus
from src.config import Config
from src.storage.state import StateTracker


def main():
    parser = argparse.ArgumentParser(description="Monitor Tamafuji availability")
    parser.add_argument(
        "--dates",
        type=str,
        nargs="+",
        help="Dates to monitor (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--days",
        type=int,
        nargs="+",
        help="Days from today to monitor",
    )
    parser.add_argument(
        "--party-size",
        type=int,
        default=Config.DEFAULT_PARTY_SIZE,
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=Config.CHECK_INTERVAL_SECONDS,
        help=f"Check interval in seconds (default: {Config.CHECK_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--no-sms",
        action="store_true",
        help="Disable SMS notifications (print only)",
    )
    args = parser.parse_args()

    # Determine dates
    if args.dates:
        dates = [date.fromisoformat(d) for d in args.dates]
    elif args.days:
        today = date.today()
        dates = [today + timedelta(days=d) for d in args.days]
    else:
        today = date.today()
        dates = [today + timedelta(days=30)]

    # Initialize components
    state = StateTracker(Config.STATE_FILE)
    sms_sender = None

    if not args.no_sms:
        try:
            from src.notifications.sms import SMSSender

            sms_sender = SMSSender()
            print(f"SMS notifications enabled -> {', '.join(Config.NOTIFY_PHONES)}")
        except Exception as e:
            print(f"SMS disabled: {e}")
            print("Run with --no-sms to suppress this warning.\n")

    print(f"Tamafuji Availability Monitor")
    print(f"{'='*40}")
    print(f"  Dates: {', '.join(d.isoformat() for d in dates)}")
    print(f"  Party size: {args.party_size}")
    print(f"  Interval: {args.interval}s")
    print(f"  SMS: {'ON' if sms_sender else 'OFF'}")
    print(f"{'='*40}")
    print(f"Press Ctrl+C to stop.\n")

    # Handle graceful shutdown
    shutdown = False

    def handle_signal(sig, frame):
        nonlocal shutdown
        print("\nShutting down...")
        shutdown = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Main loop
    check_count = 0
    while not shutdown:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Check #{check_count}...")

        try:
            snapshots = asyncio.run(
                check_multiple_dates(dates, args.party_size)
            )

            all_newly_available = []
            for snapshot in snapshots:
                newly_available = state.update(snapshot)
                if newly_available:
                    all_newly_available.extend(newly_available)

                # Print status
                if snapshot.slots:
                    target = snapshot.slots[0].date
                    avail = [s for s in snapshot.slots if s.status == SlotStatus.AVAILABLE]
                    total = len(snapshot.slots)
                    print(f"  {target}: {len(avail)}/{total} available", end="")
                    if avail:
                        times = ", ".join(s.display_time for s in avail)
                        print(f" [{times}]")
                    else:
                        print()
                else:
                    print(f"  (no slots in booking window)")

            if all_newly_available:
                print(f"\n  ** NEW SLOTS AVAILABLE! **")
                for slot in all_newly_available:
                    print(f"    >>> {slot.display_date} @ {slot.display_time}")

                if sms_sender:
                    sms_sender.notify_all(all_newly_available)
            else:
                print(f"  No new slots.")

        except Exception as e:
            print(f"  ERROR: {e}")

        if shutdown:
            break

        # Wait for next check
        print(f"  Next check in {args.interval}s...\n")
        for _ in range(args.interval):
            if shutdown:
                break
            time.sleep(1)

    print("Monitor stopped.")
    available = state.get_all_available()
    if available:
        print(f"\nCurrently known available slots:")
        for s in available:
            print(f"  {s['date']} @ {s['time']} (party of {s['party_size']})")


if __name__ == "__main__":
    main()
