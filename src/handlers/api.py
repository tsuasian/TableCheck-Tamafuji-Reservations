"""API Gateway Lambda handler — CRUD for watch items in DynamoDB.

Routes (HTTP API v2 format):
  POST   /watches              — Create a new watch
  GET    /watches              — List watches for a phone (query param)
  GET    /watches/{id}         — Get a single watch
  PATCH  /watches/{id}         — Update a watch
  DELETE /watches/{id}         — Delete a watch
"""

import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import boto3

# Validation constants
PHONE_RE = re.compile(r"^\+\d{10,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLOSED_WEEKDAYS = {1}  # Tuesday (0=Monday)
MAX_PARTY_SIZE = 10


def handler(event, context):
    """Lambda entry point — route dispatcher."""
    route_key = event.get("routeKey", "")
    try:
        if route_key == "POST /watches":
            return _create_watch(event)
        elif route_key == "GET /watches":
            return _list_watches(event)
        elif route_key == "GET /watches/{id}":
            return _get_watch(event)
        elif route_key == "PATCH /watches/{id}":
            return _update_watch(event)
        elif route_key == "DELETE /watches/{id}":
            return _delete_watch(event)
        else:
            return _response(404, {"error": f"Not found: {route_key}"})
    except Exception as e:
        print(f"Unhandled error on {route_key}: {e}")
        return _response(500, {"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _create_watch(event):
    body = _parse_body(event)
    if not body:
        return _response(400, {"error": "Invalid JSON body"})

    phone = body.get("phone")
    name = body.get("name")
    email = body.get("email")
    dates = body.get("dates")
    party_size = body.get("party_size")
    preferred_times = body.get("preferred_times")

    # Validate required fields
    errors = []
    if not name or not isinstance(name, str) or not name.strip():
        errors.append("name is required and must be a non-empty string")
    if not email or not isinstance(email, str) or not EMAIL_RE.match(email):
        errors.append("email is required and must be a valid email address")
    if not phone or not PHONE_RE.match(phone):
        errors.append("phone is required and must be E.164 format (e.g. +18081234567)")
    if not dates or not isinstance(dates, list):
        errors.append("dates is required and must be a list of ISO date strings")
    else:
        date_errors = _validate_dates(dates)
        if date_errors:
            errors.extend(date_errors)
    if party_size is None or not isinstance(party_size, int) or party_size < 1 or party_size > MAX_PARTY_SIZE:
        errors.append(f"party_size is required and must be an integer 1-{MAX_PARTY_SIZE}")
    if preferred_times is not None:
        if not isinstance(preferred_times, list) or not all(isinstance(t, str) for t in preferred_times):
            errors.append("preferred_times must be a list of time strings")

    if errors:
        return _response(400, {"errors": errors})

    watch_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "PK": f"USER#{phone}",
        "SK": f"WATCH#{watch_id}",
        "phone": phone,
        "name": name.strip(),
        "email": email.strip().lower(),
        "watch_id": watch_id,
        "dates": dates,
        "party_size": party_size,
        "preferred_times": preferred_times,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    _table().put_item(Item=item)

    return _response(201, _format_watch(item))


def _list_watches(event):
    params = event.get("queryStringParameters") or {}
    phone = params.get("phone")
    if not phone or not PHONE_RE.match(phone):
        return _response(400, {"error": "phone query parameter is required (E.164 format)"})

    resp = _table().query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"USER#{phone}")
        & boto3.dynamodb.conditions.Key("SK").begins_with("WATCH#"),
    )

    watches = [_format_watch(item) for item in resp.get("Items", [])]
    return _response(200, {"watches": watches})


def _get_watch(event):
    watch_id = event["pathParameters"]["id"]
    params = event.get("queryStringParameters") or {}
    phone = params.get("phone")
    if not phone or not PHONE_RE.match(phone):
        return _response(400, {"error": "phone query parameter is required (E.164 format)"})

    resp = _table().get_item(Key={"PK": f"USER#{phone}", "SK": f"WATCH#{watch_id}"})
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "Watch not found"})

    return _response(200, _format_watch(item))


def _update_watch(event):
    watch_id = event["pathParameters"]["id"]
    body = _parse_body(event)
    if not body:
        return _response(400, {"error": "Invalid JSON body"})

    phone = body.get("phone")
    if not phone or not PHONE_RE.match(phone):
        return _response(400, {"error": "phone is required in body (E.164 format)"})

    # Fetch existing
    table = _table()
    key = {"PK": f"USER#{phone}", "SK": f"WATCH#{watch_id}"}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "Watch not found"})

    # Build update expression
    errors = []
    update_fields = {}

    if "name" in body:
        n = body["name"]
        if not isinstance(n, str) or not n.strip():
            errors.append("name must be a non-empty string")
        else:
            update_fields["name"] = n.strip()

    if "email" in body:
        e = body["email"]
        if not isinstance(e, str) or not EMAIL_RE.match(e):
            errors.append("email must be a valid email address")
        else:
            update_fields["email"] = e.strip().lower()

    if "dates" in body:
        if not isinstance(body["dates"], list):
            errors.append("dates must be a list of ISO date strings")
        else:
            date_errors = _validate_dates(body["dates"])
            if date_errors:
                errors.extend(date_errors)
            else:
                update_fields["dates"] = body["dates"]

    if "party_size" in body:
        ps = body["party_size"]
        if not isinstance(ps, int) or ps < 1 or ps > MAX_PARTY_SIZE:
            errors.append(f"party_size must be an integer 1-{MAX_PARTY_SIZE}")
        else:
            update_fields["party_size"] = ps

    if "preferred_times" in body:
        pt = body["preferred_times"]
        if pt is not None and (not isinstance(pt, list) or not all(isinstance(t, str) for t in pt)):
            errors.append("preferred_times must be a list of time strings or null")
        else:
            update_fields["preferred_times"] = pt

    if "is_active" in body:
        if not isinstance(body["is_active"], bool):
            errors.append("is_active must be a boolean")
        else:
            update_fields["is_active"] = body["is_active"]

    if errors:
        return _response(400, {"errors": errors})

    if not update_fields:
        return _response(400, {"error": "No valid fields to update"})

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    expr_parts = []
    expr_names = {}
    expr_values = {}
    for i, (field, value) in enumerate(update_fields.items()):
        attr_name = f"#f{i}"
        attr_value = f":v{i}"
        expr_parts.append(f"{attr_name} = {attr_value}")
        expr_names[attr_name] = field
        expr_values[attr_value] = value

    table.update_item(
        Key=key,
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    # Return updated item
    resp = table.get_item(Key=key)
    return _response(200, _format_watch(resp["Item"]))


def _delete_watch(event):
    watch_id = event["pathParameters"]["id"]
    params = event.get("queryStringParameters") or {}
    phone = params.get("phone")
    if not phone or not PHONE_RE.match(phone):
        return _response(400, {"error": "phone query parameter is required (E.164 format)"})

    key = {"PK": f"USER#{phone}", "SK": f"WATCH#{watch_id}"}

    # Check existence first
    resp = _table().get_item(Key=key)
    if not resp.get("Item"):
        return _response(404, {"error": "Watch not found"})

    _table().delete_item(Key=key)
    return _response(204, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_dynamo_table = None


def _table():
    global _dynamo_table
    if _dynamo_table is None:
        _dynamo_table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _dynamo_table


def _parse_body(event):
    body = event.get("body")
    if not body:
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None


def _validate_dates(dates):
    """Validate a list of date strings. Returns list of error messages."""
    errors = []
    today = date.today()
    for d in dates:
        if not isinstance(d, str) or not DATE_RE.match(d):
            errors.append(f"Invalid date format: {d} (expected YYYY-MM-DD)")
            continue
        try:
            parsed = date.fromisoformat(d)
        except ValueError:
            errors.append(f"Invalid date: {d}")
            continue
        if parsed < today:
            errors.append(f"Date {d} is in the past")
        if parsed.weekday() in CLOSED_WEEKDAYS:
            errors.append(f"Date {d} is a Tuesday (restaurant closed)")
    return errors


def _format_watch(item):
    """Format a DynamoDB item into an API response dict."""
    result = {
        "watch_id": item.get("watch_id", item["SK"].replace("WATCH#", "")),
        "phone": item.get("phone", item["PK"].replace("USER#", "")),
        "name": item.get("name"),
        "email": item.get("email"),
        "dates": item.get("dates", []),
        "party_size": int(item.get("party_size", 2)),
        "preferred_times": item.get("preferred_times"),
        "is_active": item.get("is_active", True),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    # Convert Decimal to int (DynamoDB returns Decimal for numbers)
    if isinstance(result["party_size"], Decimal):
        result["party_size"] = int(result["party_size"])
    return result


def _response(status_code, body):
    """Build an API Gateway v2 response."""
    resp = {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
    }
    if body is not None:
        resp["body"] = json.dumps(body, default=str)
    return resp
