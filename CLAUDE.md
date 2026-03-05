# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless app that monitors Tamafuji restaurant on TableCheck for reservation availability and sends SMS/email alerts. Two Lambda functions: a scheduled checker (every 5 min via EventBridge) and a REST API for watch CRUD.

**Stack**: Python 3.12, AWS SAM, Lambda, DynamoDB (single-table), API Gateway (HTTP API v2), Twilio, SES

## Build & Deploy Commands

```bash
# Build (always use --use-container)
sam build --use-container

# Deploy (always use --no-confirm-changeset)
sam deploy --no-confirm-changeset

# First-time deploy (saves config to samconfig.toml)
sam deploy --guided

# Tail logs
sam logs -n CheckerFunction --stack-name tamafuji-checker --tail
sam logs -n ApiFunction --stack-name tamafuji-checker --tail
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in Twilio creds

# One-off availability check
python scripts/check_now.py
python scripts/check_now.py --date 2026-03-15 --party-size 4

# Seed/list/delete watches in DynamoDB
python scripts/seed_watch.py --phone +18081234567 --dates 2026-03-20 --party-size 2
python scripts/seed_watch.py --list
python scripts/seed_watch.py --delete WATCH_ID --phone +18081234567

# Local monitor loop
python scripts/monitor.py
```

## Architecture

```
EventBridge (5 min) → CheckerFunction → TableCheck API (httpx async)
                           ↓
                       DynamoDB (state + watches + dedup)
                           ↓
                       Twilio SMS + SES Email

API Gateway → ApiFunction → DynamoDB (watch CRUD)
```

**Lambda entry points**: `src/handlers/checker.py:handler` and `src/handlers/api.py:handler`

### Checker Flow (src/handlers/checker.py)
1. Scan DynamoDB for active WATCH items
2. Collect unique (date, party_size) pairs, filter to booking window (7-30 days out), skip closed days (Tuesday)
3. Call TableCheck API via `api_checker.py` (async httpx, session reuse)
4. Detect newly available slots via `DynamoDBStateTracker`
5. Match slots to watches by date, party_size, preferred_times
6. Dedup check (skip if notified in last 2 hours)
7. Send SMS via Twilio + email via SES

### API Routes (src/handlers/api.py)
- `POST /watches` — create (body: `{phone, dates, party_size, preferred_times?}`)
- `GET /watches?phone=` — list
- `GET /watches/{id}?phone=` — get
- `PATCH /watches/{id}` — update (body includes `phone`)
- `DELETE /watches/{id}?phone=` — delete

Validation: phone in E.164 format, dates ISO future non-Tuesday, party_size 1-10.

## DynamoDB Single-Table Schema

Table name: `${stack}-table` (PAY_PER_REQUEST, TTL on `ttl` attribute)

| PK | SK | Purpose |
|----|-----|---------|
| `USER#{phone}` | `WATCH#{watch_id}` | Watch config (dates, party_size, preferred_times, is_active) |
| `AVAIL#{YYYY-MM-DD}` | `SLOT#{HH:MM}#{party}` | Availability state (status, last_checked, last_changed) |
| `NOTIFY#{phone}#{YYYY-MM-DD}` | `SLOT#{HH:MM}` | Notification dedup (2hr TTL) |

## Key Configuration (src/config.py)

- `WEEKDAY_SLOTS`: `["16:00", "17:30", "19:00", "20:30"]`
- `WEEKEND_SLOTS`: `["11:00", "12:30", "17:00", "18:30", "20:00"]`
- `CLOSED_WEEKDAYS`: `{1}` (Tuesday, 0=Monday)
- `TABLECHECK_SHOP_SLUG`: `"tamafuji-us-kapahulu"`
- `BOOKING_WINDOW_MIN_DAYS`: `7` (timetable returns empty before this)
- `BOOKING_WINDOW_MAX_DAYS`: `30` (timetable returns empty after this)

## Environment Variables

Required for Lambda (set via SAM parameters): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TABLE_NAME`, `SES_FROM_EMAIL`, `NOTIFY_EMAILS`, `SMS_ENABLED`

For local dev: copy `.env.example` to `.env`

## Deployment Config

- **Stack**: `tamafuji-checker` (us-west-2)
- **SAM config**: `samconfig.toml`
- Twilio credentials passed as SAM parameters (NoEcho)
- `ScheduleEnabled` parameter can disable the EventBridge trigger

## TableCheck API Behavior

Uses direct HTTP calls (not browser automation):
1. GET reservation page to extract CSRF token, maintain cookies
2. `/sheets` endpoint → bookable slot display names + epoch timestamps (always returns same slots for a day type regardless of availability)
3. `/available/timetable` endpoint → per-slot availability (true/false)
4. Async with session reuse across multiple date checks

**Booking window**: Timetable only returns data for dates ~7-30 days out. Dates outside this range return empty `{"slots": {}, "seconds": []}`. The checker filters to this window to avoid wasted API calls and marks out-of-window slots as UNKNOWN.

**Rate limiting**: TableCheck returns 429 on bursts. Implementation uses 1s delay between date checks and exponential backoff retries (5s/10s/20s, 3 retries).

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```
