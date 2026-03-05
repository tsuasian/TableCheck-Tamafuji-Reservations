"""Tests for the API Lambda handler — watch CRUD with name/email fields."""

import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def api_handler(dynamodb_table):
    """Import handler with mocked DynamoDB table."""
    import src.handlers.api as api_module

    api_module._dynamo_table = dynamodb_table
    return api_module


def _make_event(method, path, body=None, path_params=None, query_params=None):
    """Build a minimal API Gateway v2 event."""
    route_key = f"{method} {path}"
    event = {"routeKey": route_key}
    if body is not None:
        event["body"] = json.dumps(body)
    if path_params:
        event["pathParameters"] = path_params
    if query_params:
        event["queryStringParameters"] = query_params
    return event


class TestCreateWatch:
    def test_create_watch_with_name_email(self, api_handler):
        body = {
            "name": "Tim",
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 201
        data = json.loads(resp["body"])
        assert data["name"] == "Tim"
        assert data["email"] == "tim@example.com"
        assert data["phone"] == "+18081234567"

    def test_create_watch_missing_name(self, api_handler):
        body = {
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400
        data = json.loads(resp["body"])
        assert any("name" in e for e in data["errors"])

    def test_create_watch_empty_name(self, api_handler):
        body = {
            "name": "   ",
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400

    def test_create_watch_missing_email(self, api_handler):
        body = {
            "name": "Tim",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400
        data = json.loads(resp["body"])
        assert any("email" in e for e in data["errors"])

    def test_create_watch_invalid_email(self, api_handler):
        body = {
            "name": "Tim",
            "email": "not-an-email",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400

    def test_create_watch_email_normalized(self, api_handler):
        body = {
            "name": "Tim",
            "email": "Tim@Example.COM",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 201
        data = json.loads(resp["body"])
        assert data["email"] == "tim@example.com"


class TestUpdateWatch:
    def _create_watch(self, api_handler):
        body = {
            "name": "Tim",
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        return json.loads(resp["body"])

    def test_update_name(self, api_handler):
        watch = self._create_watch(api_handler)
        event = _make_event(
            "PATCH",
            "/watches/{id}",
            body={"phone": "+18081234567", "name": "Timothy"},
            path_params={"id": watch["watch_id"]},
        )
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 200
        data = json.loads(resp["body"])
        assert data["name"] == "Timothy"

    def test_update_email(self, api_handler):
        watch = self._create_watch(api_handler)
        event = _make_event(
            "PATCH",
            "/watches/{id}",
            body={"phone": "+18081234567", "email": "new@example.com"},
            path_params={"id": watch["watch_id"]},
        )
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 200
        data = json.loads(resp["body"])
        assert data["email"] == "new@example.com"

    def test_update_invalid_email(self, api_handler):
        watch = self._create_watch(api_handler)
        event = _make_event(
            "PATCH",
            "/watches/{id}",
            body={"phone": "+18081234567", "email": "bad"},
            path_params={"id": watch["watch_id"]},
        )
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400

    def test_update_empty_name(self, api_handler):
        watch = self._create_watch(api_handler)
        event = _make_event(
            "PATCH",
            "/watches/{id}",
            body={"phone": "+18081234567", "name": ""},
            path_params={"id": watch["watch_id"]},
        )
        resp = api_handler.handler(event, None)
        assert resp["statusCode"] == 400


class TestFormatWatch:
    def test_format_includes_name_email(self, api_handler):
        body = {
            "name": "Tim",
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        event = _make_event("POST", "/watches", body=body)
        resp = api_handler.handler(event, None)
        data = json.loads(resp["body"])
        assert "name" in data
        assert "email" in data
        assert data["name"] == "Tim"
        assert data["email"] == "tim@example.com"

    def test_list_watches_includes_name_email(self, api_handler):
        # Create a watch first
        body = {
            "name": "Tim",
            "email": "tim@example.com",
            "phone": "+18081234567",
            "dates": ["2026-03-20"],
            "party_size": 2,
        }
        api_handler.handler(_make_event("POST", "/watches", body=body), None)

        # List watches
        event = _make_event(
            "GET", "/watches", query_params={"phone": "+18081234567"}
        )
        resp = api_handler.handler(event, None)
        data = json.loads(resp["body"])
        assert len(data["watches"]) == 1
        assert data["watches"][0]["name"] == "Tim"
        assert data["watches"][0]["email"] == "tim@example.com"


class TestPerWatchEmailNotification:
    def test_checker_sends_to_watch_email(self):
        """Verify checker uses watch email, not Config.NOTIFY_EMAILS."""
        from datetime import date as dt_date

        from src.checker.models import TimeSlot, SlotStatus
        from src.storage.dynamodb_state import DynamoDBStateTracker
        from unittest.mock import MagicMock, patch

        slot = TimeSlot(
            date=dt_date(2026, 3, 20),
            time="17:00",
            party_size=2,
            status=SlotStatus.AVAILABLE,
        )

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [dt_date(2026, 3, 20)],
                "preferred_times": None,
                "email": "user@example.com",
                "name": "Tim",
            }
        ]

        mock_state = MagicMock(spec=DynamoDBStateTracker)
        mock_state.has_been_notified.return_value = False

        mock_email_sender = MagicMock()

        with patch("src.handlers.checker.Config") as mock_config:
            mock_config.SMS_ENABLED = False
            mock_config.SES_FROM_EMAIL = "from@example.com"

            with patch(
                "src.notifications.email_sender.EmailSender",
                return_value=mock_email_sender,
            ):
                from src.handlers.checker import _send_alerts

                _send_alerts(watches, [slot], mock_state)

        mock_email_sender.send_availability_alert.assert_called_once()
        call_args = mock_email_sender.send_availability_alert.call_args
        assert call_args[0][1] == "user@example.com"
        assert call_args[1]["name"] == "Tim"

    def test_checker_skips_watch_without_email(self):
        """Watches without email field should be skipped for email alerts."""
        from datetime import date as dt_date

        from src.checker.models import TimeSlot, SlotStatus
        from src.storage.dynamodb_state import DynamoDBStateTracker
        from unittest.mock import MagicMock, patch

        slot = TimeSlot(
            date=dt_date(2026, 3, 20),
            time="17:00",
            party_size=2,
            status=SlotStatus.AVAILABLE,
        )

        watches = [
            {
                "phone": "+18081234567",
                "watch_id": "w1",
                "party_size": 2,
                "dates": [dt_date(2026, 3, 20)],
                "preferred_times": None,
                "email": None,
                "name": None,
            }
        ]

        mock_state = MagicMock(spec=DynamoDBStateTracker)
        mock_state.has_been_notified.return_value = False

        mock_email_sender = MagicMock()

        with patch("src.handlers.checker.Config") as mock_config:
            mock_config.SMS_ENABLED = False
            mock_config.SES_FROM_EMAIL = "from@example.com"

            with patch(
                "src.notifications.email_sender.EmailSender",
                return_value=mock_email_sender,
            ):
                from src.handlers.checker import _send_alerts

                _send_alerts(watches, [slot], mock_state)

        mock_email_sender.send_availability_alert.assert_not_called()
