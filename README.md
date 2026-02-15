# Tamafuji Reservation Checker

Monitors [Tamafuji](https://www.tablecheck.com/en/shops/tamafuji-us-kapahulu/reserve) on TableCheck for reservation availability and sends SMS alerts via Twilio.

## How it works

A Lambda runs every 2 minutes, reads watch items from DynamoDB, checks the TableCheck API for matching availability, and texts you when a slot opens up.

```
EventBridge (2 min) → Checker Lambda → TableCheck API
                          ↓
                      DynamoDB (state + watches)
                          ↓
                      Twilio SMS
```

A second Lambda behind API Gateway provides a REST API for managing watches (create, list, update, delete).

## Architecture

| Component | Resource |
|-----------|----------|
| Checker Lambda | Polls TableCheck, detects new slots, sends SMS |
| API Lambda | CRUD endpoints for watch management |
| DynamoDB | Stores watches, availability state, notification dedup |
| API Gateway (HTTP API) | REST interface at `/watches` |
| EventBridge | 2-minute schedule trigger |

## API

**Base URL**: Deployed via `sam deploy` — see stack output `ApiUrl`.

| Method | Path | Description |
|--------|------|-------------|
| `POST /watches` | Create a watch | Body: `{phone, dates, party_size, preferred_times?}` |
| `GET /watches?phone={e164}` | List watches for a phone | |
| `GET /watches/{id}?phone={e164}` | Get a single watch | |
| `PATCH /watches/{id}` | Update a watch | Body: `{phone, dates?, party_size?, preferred_times?, is_active?}` |
| `DELETE /watches/{id}?phone={e164}` | Delete a watch | |

Example:
```bash
curl -X POST $API_URL/watches \
  -H "Content-Type: application/json" \
  -d '{"phone":"+18081234567","dates":["2026-03-20"],"party_size":2}'
```

## Setup

### Prerequisites

- AWS CLI configured
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Docker (for `sam build --use-container`)
- Twilio account with phone number

### Deploy

```bash
cp .env.example .env   # fill in Twilio credentials

sam build --use-container
sam deploy --guided     # first time — saves config to samconfig.toml
sam deploy              # subsequent deploys
```

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-off availability check
python scripts/check_now.py

# Seed a watch into DynamoDB
python scripts/seed_watch.py
```

### Useful commands

```bash
# Tail checker logs
sam logs -n CheckerFunction --stack-name tamafuji-checker --tail

# List watches via API
curl "$API_URL/watches?phone=%2B18081234567"
```

## Project structure

```
src/
├── config.py                 # Environment config
├── checker/
│   ├── api_checker.py        # HTTP-based TableCheck availability checker
│   └── models.py             # TimeSlot, AvailabilitySnapshot models
├── handlers/
│   ├── checker.py            # Lambda: scheduled availability checker
│   └── api.py                # Lambda: REST API for watch CRUD
├── notifications/
│   └── sms.py                # Twilio SMS sender
└── storage/
    ├── dynamodb_state.py     # DynamoDB state tracker (availability + dedup)
    └── state.py              # Local JSON state tracker (dev)
scripts/
├── check_now.py              # One-off availability check
├── discover_api.py           # TableCheck API discovery tool
├── monitor.py                # Local monitor loop
└── seed_watch.py             # Seed a watch into DynamoDB
template.yaml                 # SAM template
```