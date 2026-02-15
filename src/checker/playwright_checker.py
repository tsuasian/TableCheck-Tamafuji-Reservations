"""Browser-based availability checker for TableCheck."""

import asyncio
from datetime import date, datetime

from playwright.async_api import async_playwright, Page, Browser

from src.checker.models import AvailabilitySnapshot, SlotStatus, TimeSlot
from src.config import Config


async def check_availability(
    target_date: date,
    party_size: int = Config.DEFAULT_PARTY_SIZE,
    headless: bool = True,
) -> AvailabilitySnapshot:
    """Check slot availability for a specific date and party size."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        try:
            page = await browser.new_page()
            slots = await _scrape_slots(page, target_date, party_size)
            return AvailabilitySnapshot(
                checked_at=datetime.now(),
                party_size=party_size,
                slots=slots,
            )
        finally:
            await browser.close()


async def check_multiple_dates(
    dates: list[date],
    party_size: int = Config.DEFAULT_PARTY_SIZE,
    headless: bool = True,
) -> list[AvailabilitySnapshot]:
    """Check availability across multiple dates, reusing one browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        try:
            page = await browser.new_page()
            results = []
            for d in dates:
                slots = await _scrape_slots(page, d, party_size)
                results.append(AvailabilitySnapshot(
                    checked_at=datetime.now(),
                    party_size=party_size,
                    slots=slots,
                ))
            return results
        finally:
            await browser.close()


async def _scrape_slots(
    page: Page,
    target_date: date,
    party_size: int,
) -> list[TimeSlot]:
    """Navigate to the reservation page and extract slot availability."""
    url = Config.TABLECHECK_URL
    await page.goto(url, wait_until="networkidle")

    # Wait for the reservation widget to load
    # TableCheck uses a SPA — wait for the form elements
    await page.wait_for_timeout(3000)

    # Step 1: Set party size
    await _set_party_size(page, party_size)
    await page.wait_for_timeout(1000)

    # Step 2: Select date
    await _select_date(page, target_date)
    await page.wait_for_timeout(2000)

    # Step 3: Read available time slots
    slots = await _read_time_slots(page, target_date, party_size)

    return slots


async def _set_party_size(page: Page, party_size: int) -> None:
    """Select party size from the dropdown."""
    # Look for party size selector — TableCheck uses various selectors
    # Try common patterns
    selectors = [
        'select[name*="party"]',
        'select[name*="seat"]',
        'select[name*="guest"]',
        'select[name*="pax"]',
        '[data-testid*="party"]',
        '[data-testid*="seat"]',
        '.party-size select',
        '#num_people',
        'select:first-of-type',
    ]

    for selector in selectors:
        element = await page.query_selector(selector)
        if element:
            await element.select_option(str(party_size))
            print(f"  Set party size to {party_size} via {selector}")
            return

    # Fallback: try clicking a party size button/option
    party_buttons = await page.query_selector_all(
        f'button:has-text("{party_size}"), [role="option"]:has-text("{party_size}")'
    )
    if party_buttons:
        await party_buttons[0].click()
        print(f"  Set party size to {party_size} via button click")
        return

    print(f"  WARNING: Could not find party size selector, proceeding with default")


async def _select_date(page: Page, target_date: date) -> None:
    """Navigate the calendar to select the target date."""
    # TableCheck calendars typically show month view with clickable dates
    # Need to navigate forward/back to reach the target month

    target_month = target_date.strftime("%B %Y")  # e.g., "March 2026"
    target_day = str(target_date.day)

    # Navigate to the correct month
    for _ in range(12):  # Max 12 months ahead
        # Check if we're on the right month
        calendar_header = await page.query_selector(
            '.calendar-header, [class*="month"], [class*="calendar"] h2, '
            '[class*="calendar"] [class*="title"], [aria-label*="month"]'
        )
        if calendar_header:
            header_text = await calendar_header.inner_text()
            if target_month.lower() in header_text.lower():
                break

        # Also check for YYYY-MM format or just month name
        month_name = target_date.strftime("%B")
        page_content = await page.content()
        if month_name.lower() in page_content.lower():
            # Might be on the right month already
            pass

        # Click next month button
        next_buttons = [
            'button[aria-label*="next"]',
            'button[aria-label*="Next"]',
            '[class*="next"]',
            '[class*="forward"]',
            '.calendar-nav-next',
            'button:has-text(">")',
            'button:has-text("›")',
        ]
        clicked = False
        for selector in next_buttons:
            btn = await page.query_selector(selector)
            if btn:
                await btn.click()
                await page.wait_for_timeout(500)
                clicked = True
                break
        if not clicked:
            break

    # Click the target date
    # Try multiple strategies for finding the day cell
    day_selectors = [
        f'td[data-date="{target_date.isoformat()}"]',
        f'[data-date="{target_date.isoformat()}"]',
        f'button[aria-label*="{target_date.strftime("%B")} {target_date.day}"]',
        f'.calendar-day:has-text("{target_day}")',
        f'td:has-text("{target_day}")',
    ]

    for selector in day_selectors:
        elements = await page.query_selector_all(selector)
        for el in elements:
            # Make sure it's the right day (not from adjacent months)
            text = await el.inner_text()
            if text.strip() == target_day:
                is_disabled = await el.get_attribute("disabled")
                classes = await el.get_attribute("class") or ""
                if not is_disabled and "disabled" not in classes:
                    await el.click()
                    print(f"  Selected date {target_date.isoformat()} via {selector}")
                    return

    print(f"  WARNING: Could not click date {target_date.isoformat()}")


async def _read_time_slots(
    page: Page,
    target_date: date,
    party_size: int,
) -> list[TimeSlot]:
    """Read available time slots from the page after date selection."""
    is_weekend = target_date.weekday() >= 5
    expected_times = Config.WEEKEND_SLOTS if is_weekend else Config.WEEKDAY_SLOTS
    slots = []

    # Strategy 1: Look for a time slot selector/dropdown
    time_selectors = [
        'select[name*="time"]',
        'select[name*="slot"]',
        '#time',
        '[data-testid*="time"]',
    ]
    for selector in time_selectors:
        element = await page.query_selector(selector)
        if element:
            options = await element.query_selector_all("option")
            available_times = set()
            for opt in options:
                value = await opt.get_attribute("value")
                text = await opt.inner_text()
                disabled = await opt.get_attribute("disabled")
                if value and not disabled and value != "":
                    available_times.add(value)

            for time_str in expected_times:
                status = (
                    SlotStatus.AVAILABLE
                    if time_str in available_times
                    else SlotStatus.UNAVAILABLE
                )
                slots.append(TimeSlot(
                    date=target_date,
                    time=time_str,
                    status=status,
                    party_size=party_size,
                ))
            if slots:
                return slots

    # Strategy 2: Look for time slot buttons/cards
    time_buttons = await page.query_selector_all(
        '[class*="time-slot"], [class*="timeslot"], '
        '[class*="slot"], [data-testid*="slot"], '
        'button[class*="time"], .time-option'
    )
    if time_buttons:
        available_times = set()
        for btn in time_buttons:
            text = await btn.inner_text()
            disabled = await btn.get_attribute("disabled")
            classes = await btn.get_attribute("class") or ""

            # Extract time from text like "4:00 PM" or "16:00"
            time_str = _parse_time_text(text.strip())
            if time_str and not disabled and "disabled" not in classes and "unavailable" not in classes:
                available_times.add(time_str)

        for time_str in expected_times:
            status = (
                SlotStatus.AVAILABLE
                if time_str in available_times
                else SlotStatus.UNAVAILABLE
            )
            slots.append(TimeSlot(
                date=target_date,
                time=time_str,
                status=status,
                party_size=party_size,
            ))
        if slots:
            return slots

    # Strategy 3: Check calendar day cells for availability indicators
    # Some TableCheck pages show X marks on unavailable dates
    page_content = await page.content()

    # Look for any indication of available slots in the page
    for time_str in expected_times:
        display = _format_display_time(time_str)
        # Check if this time appears as available on the page
        is_available = display.lower() in page_content.lower()
        slots.append(TimeSlot(
            date=target_date,
            time=time_str,
            status=SlotStatus.AVAILABLE if is_available else SlotStatus.UNKNOWN,
            party_size=party_size,
        ))

    if not any(s.status == SlotStatus.AVAILABLE for s in slots):
        # Mark all as unknown if we couldn't determine anything
        print(f"  WARNING: Could not reliably read time slots for {target_date}")

    return slots


def _parse_time_text(text: str) -> str | None:
    """Parse display time like '4:00 PM' into 24hr format '16:00'."""
    import re

    # Try 12-hour format: "4:00 PM", "11:00 AM"
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", text, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = match.group(2)
        period = match.group(3).upper()
        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute}"

    # Try 24-hour format: "16:00", "17:30"
    match = re.match(r"(\d{2}):(\d{2})", text)
    if match:
        return match.group(0)

    return None


def _format_display_time(time_24h: str) -> str:
    """Convert '16:00' to '4:00 PM'."""
    h, m = time_24h.split(":")
    hour = int(h)
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{m} {suffix}"


def run_check(
    target_date: date,
    party_size: int = Config.DEFAULT_PARTY_SIZE,
    headless: bool = True,
) -> AvailabilitySnapshot:
    """Synchronous wrapper for check_availability."""
    return asyncio.run(check_availability(target_date, party_size, headless))


def run_check_multiple(
    dates: list[date],
    party_size: int = Config.DEFAULT_PARTY_SIZE,
    headless: bool = True,
) -> list[AvailabilitySnapshot]:
    """Synchronous wrapper for check_multiple_dates."""
    return asyncio.run(check_multiple_dates(dates, party_size, headless))
