import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available in Lambda — env vars set via SAM template


class Config:
    # TableCheck
    TABLECHECK_URL = os.getenv(
        "TABLECHECK_URL",
        "https://www.tablecheck.com/en/shops/tamafuji-us-kapahulu/reserve",
    )
    TABLECHECK_SHOP_SLUG = os.getenv("TABLECHECK_SHOP_SLUG", "tamafuji-us-kapahulu")

    # DynamoDB
    TABLE_NAME = os.getenv("TABLE_NAME", "")

    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

    # Notification recipients
    NOTIFY_PHONES = [
        p.strip()
        for p in os.getenv("NOTIFY_PHONES", "").split(",")
        if p.strip()
    ]
    NOTIFY_EMAILS = [
        e.strip()
        for e in os.getenv("NOTIFY_EMAILS", "").split(",")
        if e.strip()
    ]
    SMS_ENABLED = os.getenv("SMS_ENABLED", "true").lower() == "true"

    # SES
    SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL", "")

    # Checker settings
    CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))
    DEFAULT_PARTY_SIZE = int(os.getenv("DEFAULT_PARTY_SIZE", "2"))

    # Paths
    STATE_FILE = os.getenv("STATE_FILE", "data/state.json")
    DISCOVERY_OUTPUT_DIR = os.getenv("DISCOVERY_OUTPUT_DIR", "discovery_output")

    # Booking window — timetable only returns data within this range
    BOOKING_WINDOW_MIN_DAYS = int(os.getenv("BOOKING_WINDOW_MIN_DAYS", "7"))
    BOOKING_WINDOW_MAX_DAYS = int(os.getenv("BOOKING_WINDOW_MAX_DAYS", "30"))

    # Known time slots
    WEEKDAY_SLOTS = ["16:00", "17:30", "19:00", "20:30"]
    WEEKEND_SLOTS = ["11:00", "12:30", "17:00", "18:30", "20:00"]

    # Restaurant closed days (0=Monday, 6=Sunday)
    CLOSED_WEEKDAYS = {1}  # Tuesday
