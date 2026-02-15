"""Network interceptor for discovering TableCheck API endpoints.

Captures all XHR/fetch requests while interacting with the booking page
to discover the underlying API that the SPA uses.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field

from playwright.async_api import Request, Response, Route


@dataclass
class CapturedRequest:
    url: str
    method: str
    headers: dict
    post_data: str | None
    resource_type: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    response_status: int | None = None
    response_headers: dict = field(default_factory=dict)
    response_body: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "post_data": self.post_data,
            "resource_type": self.resource_type,
            "timestamp": self.timestamp,
            "response_status": self.response_status,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
        }


class NetworkInterceptor:
    """Captures and categorizes network requests from a Playwright page."""

    # Keywords that suggest availability-related API calls
    AVAILABILITY_KEYWORDS = [
        "availability", "avail", "slot", "slots", "reserve", "reservation",
        "booking", "book", "schedule", "calendar", "time", "seat",
        "capacity", "vacancy", "open", "check",
    ]

    # Domains/paths to ignore (static assets, analytics, etc.)
    IGNORE_PATTERNS = [
        "google-analytics", "googletagmanager", "facebook", "fbq",
        "hotjar", "clarity", "sentry", "segment", "amplitude",
        ".png", ".jpg", ".gif", ".svg", ".ico", ".woff", ".woff2",
        ".css", "fonts.googleapis", "cdn.jsdelivr",
    ]

    def __init__(self):
        self.requests: list[CapturedRequest] = []
        self._response_map: dict[str, CapturedRequest] = {}

    async def attach(self, page) -> None:
        """Attach interceptor to a Playwright page."""
        page.on("request", self._on_request)
        page.on("response", self._on_response)

    def _should_capture(self, request: Request) -> bool:
        """Decide whether to capture this request."""
        url = request.url.lower()

        # Skip ignored patterns
        if any(pat in url for pat in self.IGNORE_PATTERNS):
            return False

        # Capture XHR and fetch requests
        if request.resource_type in ("xhr", "fetch", "websocket"):
            return True

        # Capture document requests that might be API calls
        if request.resource_type == "document" and request.method != "GET":
            return True

        return False

    def _on_request(self, request: Request) -> None:
        """Handle outgoing request."""
        if not self._should_capture(request):
            return

        captured = CapturedRequest(
            url=request.url,
            method=request.method,
            headers=dict(request.headers),
            post_data=request.post_data,
            resource_type=request.resource_type,
        )
        self.requests.append(captured)
        self._response_map[request.url + request.method] = captured

    async def _on_response(self, response: Response) -> None:
        """Handle incoming response."""
        key = response.url + response.request.method
        captured = self._response_map.get(key)
        if not captured:
            return

        captured.response_status = response.status
        captured.response_headers = dict(response.headers)

        # Try to capture response body (may fail for some responses)
        try:
            body = await response.text()
            # Only store reasonable-sized responses
            if len(body) < 500_000:
                captured.response_body = body
        except Exception:
            pass

    def get_availability_requests(self) -> list[CapturedRequest]:
        """Filter requests that look related to availability checking."""
        results = []
        for req in self.requests:
            url_lower = req.url.lower()
            body_lower = (req.post_data or "").lower()
            resp_lower = (req.response_body or "").lower()

            if any(kw in url_lower or kw in body_lower for kw in self.AVAILABILITY_KEYWORDS):
                results.append(req)
            elif any(kw in resp_lower for kw in self.AVAILABILITY_KEYWORDS):
                results.append(req)

        return results

    def get_api_requests(self) -> list[CapturedRequest]:
        """Filter requests that look like API calls (JSON responses)."""
        results = []
        for req in self.requests:
            content_type = req.response_headers.get("content-type", "")
            if "json" in content_type or "application/json" in content_type:
                results.append(req)
            elif req.method in ("POST", "PUT", "PATCH"):
                results.append(req)

        return results

    def save_report(self, output_dir: str) -> str:
        """Save a JSON report of all captured requests."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report = {
            "captured_at": datetime.now().isoformat(),
            "total_requests": len(self.requests),
            "all_requests": [r.to_dict() for r in self.requests],
            "api_requests": [r.to_dict() for r in self.get_api_requests()],
            "availability_requests": [r.to_dict() for r in self.get_availability_requests()],
            "unique_endpoints": self._get_unique_endpoints(),
        }

        filepath = os.path.join(output_dir, f"network_capture_{timestamp}.json")
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        return filepath

    def _get_unique_endpoints(self) -> list[dict]:
        """Extract unique API endpoint patterns."""
        seen = set()
        endpoints = []
        for req in self.requests:
            # Normalize URL (remove query params for dedup)
            base_url = req.url.split("?")[0]
            key = f"{req.method} {base_url}"
            if key not in seen:
                seen.add(key)
                endpoints.append({
                    "method": req.method,
                    "url": base_url,
                    "has_query_params": "?" in req.url,
                    "response_status": req.response_status,
                    "content_type": req.response_headers.get("content-type", ""),
                })

        return endpoints

    def print_summary(self) -> None:
        """Print a human-readable summary of captured traffic."""
        print(f"\n{'='*60}")
        print(f"Network Capture Summary")
        print(f"{'='*60}")
        print(f"Total requests captured: {len(self.requests)}")

        api_requests = self.get_api_requests()
        print(f"API requests (JSON): {len(api_requests)}")

        avail_requests = self.get_availability_requests()
        print(f"Availability-related: {len(avail_requests)}")

        print(f"\n--- Unique Endpoints ---")
        for ep in self._get_unique_endpoints():
            status = ep["response_status"] or "?"
            print(f"  [{status}] {ep['method']} {ep['url']}")

        if avail_requests:
            print(f"\n--- Availability-Related Requests ---")
            for req in avail_requests:
                print(f"\n  {req.method} {req.url}")
                if req.post_data:
                    print(f"  Body: {req.post_data[:200]}")
                if req.response_body:
                    print(f"  Response: {req.response_body[:300]}")

        print(f"{'='*60}\n")
