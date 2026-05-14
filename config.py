import os

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8679821911:AAGMNX9kY4Ojle-iANI0tczpfG6D0sEOBTs"
)

_ids = os.environ.get("TELEGRAM_CHAT_IDS", "")
TELEGRAM_CHAT_IDS = (
    [c.strip() for c in _ids.split(",") if c.strip()]
    if _ids else ["-5190911796"]   # Smartbuy group
)
