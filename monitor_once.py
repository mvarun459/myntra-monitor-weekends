"""
Myntra Coupon Monitor
Checks for BLINK* coupons only and sends Telegram alert.
Uses ScraperAPI to bypass Myntra IP blocks.
"""

import json, logging, re, requests, os
from datetime import datetime
from pathlib import Path

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, MONITOR_TARGETS

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

STATE_FILE   = Path(__file__).parent / "state.json"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SCRAPER_KEY  = os.environ.get("SCRAPER_API_KEY", "")


def fetch_page(url):
    try:
        resp = requests.get(
            "https://api.scraperapi.com",
            params={"api_key": SCRAPER_KEY, "url": url, "country_code": "in"},
            timeout=60,
        )
        log.info("Fetch status=%s length=%d", resp.status_code, len(resp.text))
        return resp.text if len(resp.text) > 1000 else None
    except Exception as e:
        log.error("Fetch failed: %s", e)
        return None


def find_blink_coupons(html):
    """Find any coupon code containing BLINK near 'Coupon code:' text."""
    matches = re.findall(r'[Cc]oupon\s*[Cc]ode[:\s"]+([A-Z0-9]{4,20})', html.upper())
    return [c for c in matches if "BLINK" in c]


def send_telegram(msg):
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            r = requests.post(f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10)
            log.info("Telegram → %s : %s", chat_id, r.json().get("ok"))
        except Exception as e:
            log.error("Telegram failed: %s", e)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    except Exception:
        return {}


def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))


def run():
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()
    log.info("── Check at %s ──", now)

    for target in MONITOR_TARGETS:
        name = target["name"]
        url  = target["url"]

        if url not in state:
            state[url] = {"blink_codes": []}

        html = fetch_page(url)
        if not html:
            log.warning("Skipping %s — fetch failed", name)
            continue

        found = find_blink_coupons(html)
        prev  = state[url].get("blink_codes", [])

        log.info("BLINK coupons found: %s (prev: %s)", found, prev)

        if found:
            state[url]["blink_codes"] = found
            for code in found:
                send_telegram(
                    f"🎉 *BLINK Coupon LIVE on Myntra!*\n\n"
                    f"Product: *{name}*\n"
                    f"Coupon: `{code}`\n"
                    f"Time: {now}\n\n"
                    f"[👉 Buy Now]({url})"
                )
        elif prev:
            state[url]["blink_codes"] = []
            send_telegram(
                f"⚠️ *BLINK Coupon removed from Myntra*\n\n"
                f"Product: *{name}*\n"
                f"Was: `{', '.join(prev)}`\n"
                f"Time: {now}"
            )
        else:
            log.info("No BLINK coupon found, no change.")

    save_state(state)
    log.info("Done.")


if __name__ == "__main__":
    run()
