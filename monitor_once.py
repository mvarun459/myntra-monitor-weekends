"""
Myntra BLINK Coupon Monitor
----------------------------
1. First checks specific product URLs
2. If those fail, scans the gold coin listing page
   and checks each product for BLINK coupons
3. Sends Telegram alert if any BLINK coupon found
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

# Listing page to scan if specific URLs fail
LISTING_URL = "https://www.myntra.com/gold-coin?rawQuery=gold%20coin"


# ── Fetch via ScraperAPI ──────────────────────────────────────
def fetch_page(url, render=False):
    params = {
        "api_key": SCRAPER_KEY,
        "url": url,
        "country_code": "in",
    }
    if render:
        params["render"] = "true"
    try:
        resp = requests.get("https://api.scraperapi.com", params=params, timeout=120)
        log.info("Fetch %s status=%s length=%d", url[:60], resp.status_code, len(resp.text))
        if resp.status_code == 200 and len(resp.text) > 1000:
            return resp.text
        return None
    except Exception as e:
        log.error("Fetch failed: %s", e)
        return None


# ── Find BLINK coupons in HTML ────────────────────────────────
def find_blink_coupons(html):
    matches = re.findall(r'[Cc]oupon\s*[Cc]ode[:\s"]+([A-Z0-9]{4,20})', html.upper())
    blink = [c for c in matches if "BLINK" in c]
    # Also do a raw search for any BLINKDEAL/BLINKSALE etc pattern
    raw = re.findall(r'BLINK[A-Z0-9]{1,10}', html.upper())
    # Filter out CSS font name
    raw = [c for c in raw if c != "BLINKMACSYSTEMFONT"]
    return list(set(blink + raw))


# ── Extract product URLs from listing page ────────────────────
def extract_product_urls(html):
    # Myntra listing page has product links like /gold-coin/.../buy
    urls = re.findall(r'href="(/gold-coin/[^"]+/buy)"', html)
    # Also try data attributes
    urls += re.findall(r'"pdpUrl"\s*:\s*"([^"]+)"', html)
    full_urls = []
    for u in urls:
        if u.startswith("http"):
            full_urls.append(u)
        else:
            full_urls.append("https://www.myntra.com" + u)
    # Deduplicate
    seen = set()
    result = []
    for u in full_urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    log.info("Found %d product URLs in listing", len(result))
    return result[:30]  # check first 30 products max


# ── Telegram ──────────────────────────────────────────────────
def send_telegram(msg):
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            r = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
            log.info("Telegram → %s : %s", chat_id, r.json().get("ok"))
        except Exception as e:
            log.error("Telegram failed: %s", e)


# ── State ─────────────────────────────────────────────────────
def load_state():
    try:
        return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    except Exception:
        return {}

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))


# ── Check specific product URLs ───────────────────────────────
def check_specific_urls(now):
    results = []  # list of (name, url, [blink_codes])
    any_success = False

    for target in MONITOR_TARGETS:
        name = target["name"]
        url  = target["url"]

        # Try without render first (faster, cheaper)
        html = fetch_page(url, render=False)
        if not html:
            # Try with render
            html = fetch_page(url, render=True)
        if not html:
            log.warning("Could not fetch %s", name)
            continue

        any_success = True
        found = find_blink_coupons(html)
        log.info("BLINK found for %s: %s", name, found)
        if found:
            results.append((name, url, found))

    return results, any_success


# ── Scan listing page ─────────────────────────────────────────
def scan_listing_page(now):
    log.info("Falling back to listing page scan...")
    results = []

    html = fetch_page(LISTING_URL, render=False)
    if not html:
        html = fetch_page(LISTING_URL, render=True)
    if not html:
        log.error("Could not fetch listing page either")
        return results

    product_urls = extract_product_urls(html)
    if not product_urls:
        log.warning("No product URLs found in listing page")
        return results

    for url in product_urls:
        html = fetch_page(url, render=False)
        if not html:
            continue
        found = find_blink_coupons(html)
        if found:
            # Extract product name from URL
            parts = url.split("/")
            name = parts[5].replace("-", " ").title() if len(parts) > 5 else url
            log.info("BLINK FOUND in listing scan: %s → %s", name, found)
            results.append((name, url, found))
            # Found at least one — stop scanning
            break

    return results


# ── Main ──────────────────────────────────────────────────────
def run():
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()
    log.info("── Check at %s ──", now)

    # Step 1: check specific URLs
    results, any_success = check_specific_urls(now)

    # Step 2: if all specific URLs failed, scan listing page
    if not any_success:
        log.info("All specific URLs failed — scanning listing page")
        results = scan_listing_page(now)

    # Step 3: send alerts
    state_key = "blink_active"
    prev_active = state.get(state_key, False)

    if results:
        state[state_key] = True
        for name, url, codes in results:
            for code in codes:
                send_telegram(
                    f"🎉 *BLINK Coupon LIVE on Myntra!*\n\n"
                    f"Product: *{name}*\n"
                    f"Coupon: `{code}`\n"
                    f"Time: {now}\n\n"
                    f"[👉 Buy Now]({url})"
                )
    else:
        if prev_active:
            state[state_key] = False
            send_telegram(
                f"⚠️ *BLINK Coupon no longer found on Myntra*\n"
                f"Time: {now}"
            )
        else:
            log.info("No BLINK coupon found, no change.")

    save_state(state)
    log.info("Done.")


if __name__ == "__main__":
    run()
