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

# ── Products to monitor ───────────────────────────────────────
# Only notifies when a BLINK* coupon is found
MONITOR_TARGETS = [
    {
        "name": "Malabar Gold Rose Gold Bar 1g",
        "url": "https://www.myntra.com/gold-coin/malabar+gold+%26+diamonds/malabar-gold--diamonds-24kt-999-purity-rose-gold-bar---1-g/40324062/buy",
    },
    {
        "name": "Joyalukkas Lord Krishna Gold Coin 2gm",
        "url": "https://www.myntra.com/gold-coin/joyalukkas/joyalukkas-lord-krishna-gold-coin--2-gm/29872342/buy",
    },
    # Add more URLs here:
    # {"name": "Product Name", "url": "https://www.myntra.com/..."},
]
