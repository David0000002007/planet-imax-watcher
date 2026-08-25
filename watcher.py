import os
import re
import json
import hashlib
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


CINEMA_URL = "https://www.planetcinema.co.il/cinemas/Rishon_Letziyon/1072"

MOVIE_TITLES = [
    "האודיסאה",
    "The Odyssey",
    "ОДИССЕЯ",
]

TARGET_FORMAT = "IMAX"

STATE_FILE = Path("state.json")


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets are not configured yet.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def load_previous_state():
    if not STATE_FILE.exists():
        return None

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        ).get("fingerprint")
    except Exception:
        return None


def save_state(fingerprint):
    STATE_FILE.write_text(
        json.dumps(
            {"fingerprint": fingerprint},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def find_odyssey_imax():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            locale="he-IL",
        )

        page.goto(
            CINEMA_URL,
            wait_until="networkidle",
            timeout=90000,
        )

        page.wait_for_timeout(5000)

        elements = page.locator("body *")
        count = elements.count()

        for i in range(count):
            try:
                element = elements.nth(i)
                text = element.inner_text(timeout=200)

                if not text:
                    continue

                movie_found = any(
                    title.lower() in text.lower()
                    for title in MOVIE_TITLES
                )

                if not movie_found:
                    continue

                if TARGET_FORMAT.lower() not in text.lower():
                    continue

                times = re.findall(
                    r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b",
                    text,
                )

                if not times:
                    continue

                # Ignore huge page containers.
                if len(text) > 2500:
                    continue

                links = element.locator("a")
                booking_links = []

                for j in range(min(links.count(), 20)):
                    href = links.nth(j).get_attribute("href")

                    if not href:
                        continue

                    if href.startswith("/"):
                        href = "https://www.planetcinema.co.il" + href

                    booking_links.append(href)

                results.append(
                    {
                        "text": text.strip(),
                        "times": sorted(set(times)),
                        "links": sorted(set(booking_links)),
                    }
                )

            except Exception:
                continue

        browser.close()

    # Remove duplicate results.
    unique = {}

    for result in results:
        key = tuple(result["times"])

        if key not in unique:
            unique[key] = result

    return list(unique.values())


def main():
    print("Checking Planet Rishon LeZion for The Odyssey IMAX...")

    results = find_odyssey_imax()

    if not results:
        print("No Odyssey IMAX screenings found.")
        return

    compact_data = json.dumps(
        results,
        ensure_ascii=False,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        compact_data.encode("utf-8")
    ).hexdigest()

    previous_fingerprint = load_previous_state()

    if fingerprint == previous_fingerprint:
        print("No change since previous check.")
        return

    all_times = []

    for result in results:
        all_times.extend(result["times"])

    all_times = sorted(set(all_times))

    message = (
        "🎬 נמצאה הקרנת IMAX של האודיסאה בפלאנט ראשון לציון!\n\n"
        f"🕐 שעות שנמצאו: {', '.join(all_times)}\n\n"
        "🎟️ לצפייה והזמנה:\n"
        f"{CINEMA_URL}"
    )

    send_telegram(message)

    save_state(fingerprint)

    print(message)


if __name__ == "__main__":
    main()
