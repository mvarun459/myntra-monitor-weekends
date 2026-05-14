"""
Myntra BLINK Coupon Monitor
Scans gold coin listing page and checks each product for BLINK coupons.
Sends Telegram alert once when BLINK goes live, once when removed.
"""

import json, logging, re, requests, os
from datetime import datetime
from pathlib import Path

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

STATE_FILE   = Path(__file__).parent / "state.json"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SCRAPER_KEY  = os.environ.get("SCRAPER_API_KEY", "")
LISTING_URL  = "https://www.myntra.com/gold-coin?rawQuery=gold%20coin"


def fetch_page(url, render=False):
    params = {"api_key": SCRAPER_KEY, "url": url, "country_code": "in"}
    if render:
        params["render"] = "true"
    try:
        resp = requests.get("https://api.scraperapi.com", params=params, timeout=120)
        log.info("Fetch status=%s length=%d | %s", resp.status_code, len(resp.text), url[:70])
        if resp.status_code == 200 and len(resp.text) > 1000:
            return resp.text
        return None
    except Exception as e:
        log.error("Fetch failed: %s", e)
        return None


def find_blink_coupons(html):
    # Search near 'Coupon code:' text
    matches = re.findall(r'[Cc]oupon\s*[Cc]ode[:\s"]+([A-Z0-9]{4,20})', html.upper())
    blink = [c for c in matches if "BLINK" in c]
    # Raw search for BLINK* patterns (exclude CSS font name)
    raw = [c for c in re.findall(r'BLINK[A-Z0-9]{1,10}', html.upper())
           if c != "BLINKMACSYSTEMFONT"]
    return list(set(blink + raw))


def extract_product_urls(html):
    urls = re.findall(r'href="(/gold-coin/[^"]+/buy)"', html)
    urls += re.findall(r'"pdpUrl"\s*:\s*"([^"]+)"', html)
    full = []
    seen = set()
    for u in urls:
        full_url = u if u.startswith("http") else "https://www.myntra.com" + u
        if full_url not in seen:
            seen.add(full_url)
            full.append(full_url)
    log.info("Found %d product URLs", len(full))
    return full[:30]


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

    found_result = None  # (name, url, codes)

    # Fetch listing page
    html = fetch_page(LISTING_URL)
    if not html:
        html = fetch_page(LISTING_URL, render=True)

    if html:
        for url in extract_product_urls(html):
            product_html = fetch_page(url)
            if not product_html:
                continue
            codes = find_blink_coupons(product_html)
            if codes:
                name = url.split("/")[5].replace("-", " ").title() if len(url.split("/")) > 5 else url
                log.info("BLINK FOUND: %s → %s", name, codes)
                found_result = (name, url, codes)
                break  # stop at first match
    else:
        log.error("Could not fetch listing page")

    # Send alerts only on state change
    prev_active = state.get("blink_active", False)

    if found_result:
        name, url, codes = found_result
        if not prev_active:
            # Just went live — alert
            state["blink_active"] = True
            for code in codes:
                send_telegram(
                    f"🎉 *BLINK Coupon LIVE on Myntra!*\n\n"
                    f"Product: *{name}*\n"
                    f"Coupon: `{code}`\n"
                    f"Time: {now}\n\n"
                    f"[👉 Buy Now]({url})"
                )
        else:
            log.info("BLINK still active — no new alert")
    else:
        if prev_active:
            # Just went offline — alert
            state["blink_active"] = False
            send_telegram(
                f"⚠️ *BLINK Coupon removed from Myntra*\n"
                f"Time: {now}"
            )
        else:
            log.info("No BLINK coupon found, no change.")

    save_state(state)
    log.info("Done.")


if __name__ == "__main__":
    run()
