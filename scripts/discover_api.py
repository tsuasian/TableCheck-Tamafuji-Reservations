#!/usr/bin/env python3
"""API Discovery Script — Visible browser with full network interception.

Opens the TableCheck reservation page in a visible browser, captures all
network requests while you interact with the page (change party sizes,
click dates, open time pickers), and identifies API endpoints.

Usage:
    python scripts/discover_api.py [--duration 60]
"""

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from playwright.async_api import async_playwright

from src.config import Config
from src.discovery.network_interceptor import NetworkInterceptor


async def discover(duration: int = 60) -> None:
    url = Config.TABLECHECK_URL
    print(f"Opening {url} in a visible browser...")
    print(f"Capturing network traffic for {duration} seconds.")
    print("Interact with the page: change party size, click dates, open time pickers.")
    print("Press Ctrl+C to stop early.\n")

    interceptor = NetworkInterceptor()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,  # Slight slowdown so we can see what's happening
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # Attach network interceptor
        await interceptor.attach(page)

        # Navigate to the page
        await page.goto(url, wait_until="networkidle")
        print("Page loaded. Capturing traffic...\n")

        # Automated interactions to trigger API calls
        await _automated_interactions(page)

        # Wait for manual interaction
        print(f"\nBrowser is open. Interact with the page for {duration}s...")
        print("(Change party sizes, click different dates, open time dropdowns)")

        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            pass

        await browser.close()

    # Print and save results
    interceptor.print_summary()

    filepath = interceptor.save_report(Config.DISCOVERY_OUTPUT_DIR)
    print(f"Full report saved to: {filepath}")

    # Test discovered endpoints with httpx
    avail_requests = interceptor.get_availability_requests()
    if avail_requests:
        print("\nTesting discovered availability endpoints with httpx...")
        await _test_endpoints(avail_requests)
    else:
        print("\nNo availability-specific endpoints found.")
        print("Check the full report for API patterns.")


async def _automated_interactions(page) -> None:
    """Perform automated interactions to trigger API calls."""
    print("Running automated interactions...")

    # Wait for page to fully render
    await page.wait_for_timeout(3000)

    # Try clicking on party size selectors
    party_selectors = [
        'select[name*="party"]',
        'select[name*="seat"]',
        'select[name*="guest"]',
        'select[name*="pax"]',
        '#num_people',
        'select:first-of-type',
    ]
    for selector in party_selectors:
        el = await page.query_selector(selector)
        if el:
            print(f"  Found party selector: {selector}")
            # Try different party sizes to trigger API calls
            for size in ["1", "2", "4"]:
                try:
                    await el.select_option(size)
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass
            break

    # Try clicking on calendar dates
    await page.wait_for_timeout(1000)

    # Click various day cells
    day_cells = await page.query_selector_all(
        'td[class*="day"], div[class*="day"], button[class*="day"], '
        '[role="gridcell"], .calendar td'
    )
    print(f"  Found {len(day_cells)} calendar day cells")
    for cell in day_cells[:5]:  # Click first 5 available dates
        try:
            classes = await cell.get_attribute("class") or ""
            if "disabled" not in classes and "past" not in classes:
                await cell.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

    # Try clicking on time slots
    time_elements = await page.query_selector_all(
        '[class*="time"], [class*="slot"], select[name*="time"]'
    )
    print(f"  Found {len(time_elements)} time-related elements")
    for el in time_elements[:3]:
        try:
            await el.click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass


async def _test_endpoints(requests: list) -> None:
    """Test discovered endpoints with raw httpx to check if browser is needed."""
    import httpx

    async with httpx.AsyncClient() as client:
        for req in requests[:5]:
            print(f"\n  Testing: {req.method} {req.url}")
            try:
                if req.method == "GET":
                    resp = await client.get(req.url, headers=_clean_headers(req.headers))
                elif req.method == "POST":
                    resp = await client.post(
                        req.url,
                        headers=_clean_headers(req.headers),
                        content=req.post_data,
                    )
                else:
                    continue

                print(f"  Status: {resp.status_code}")
                print(f"  Content-Type: {resp.headers.get('content-type', 'unknown')}")
                if resp.status_code == 200:
                    print(f"  Works without browser!")
                    body = resp.text[:200]
                    print(f"  Response preview: {body}")
                else:
                    print(f"  Might need browser session/cookies")
            except Exception as e:
                print(f"  Error: {e}")


def _clean_headers(headers: dict) -> dict:
    """Remove browser-specific headers that would cause issues with httpx."""
    skip = {
        "host", "connection", "sec-ch-ua", "sec-ch-ua-mobile",
        "sec-ch-ua-platform", "sec-fetch-site", "sec-fetch-mode",
        "sec-fetch-dest", "accept-encoding", "content-length",
    }
    return {k: v for k, v in headers.items() if k.lower() not in skip}


def main():
    parser = argparse.ArgumentParser(description="Discover TableCheck API endpoints")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Seconds to keep browser open for manual interaction (default: 60)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(discover(args.duration))
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
