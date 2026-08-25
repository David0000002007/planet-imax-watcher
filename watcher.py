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
]

STATE_FILE = Path("state.json")


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets are missing.")
        return

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()
    print("Telegram message sent successfully.")


def load_state():
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


def dismiss_cookies(page):
    for text in [
        "דחה את כל העוגיות",
        "קבל את כל העוגיות",
    ]:
        try:
            button = page.get_by_text(text, exact=False)

            if button.count() and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(800)
                return
        except Exception:
            pass


def get_date(body_text):
    match = re.search(
        r"(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)"
        r"\s+\d{1,2}/\d{1,2}/\d{4}",
        body_text,
    )

    if match:
        return match.group(0)

    match = re.search(
        r"\d{1,2}/\d{1,2}/\d{4}",
        body_text,
    )

    return match.group(0) if match else "תאריך לא זוהה"


def is_movie_title_line(lines, index):
    if index + 1 >= len(lines):
        return False

    return bool(
        re.search(
            r"\|\s*\d+\s*דקות",
            lines[index + 1],
        )
    )


def get_odyssey_block(body_text):
    lines = [
        line.strip()
        for line in body_text.splitlines()
        if line.strip()
    ]

    start = None

    for i, line in enumerate(lines):
        if any(
            title.lower() == line.lower()
            for title in MOVIE_TITLES
        ):
            start = i
            break

    if start is None:
        return None

    block = []

    for i in range(start, len(lines)):
        if (
            i > start
            and is_movie_title_line(lines, i)
        ):
            break

        block.append(lines[i])

    return block


def looks_like_format(line):
    upper = line.upper()

    keywords = [
        "2D",
        "3D",
        "IMAX",
        "VIP",
        "SCREENX",
        "4DX",
    ]

    return any(word in upper for word in keywords)


def parse_formats(block):
    if not block:
        return []

    results = []
    current_format = None

    for line in block[2:]:
        if looks_like_format(line):
            current_format = line

            results.append({
                "format": line,
                "times": [],
            })

            continue

        times = re.findall(
            r"(?:[01]?\d|2[0-3]):[0-5]\d",
            line,
        )

        if times and current_format and results:
            results[-1]["times"].extend(times)

    for result in results:
        result["times"] = sorted(
            set(result["times"])
        )

    return results


def scan_current_day(page):
    body_text = page.locator("body").inner_text()

    date = get_date(body_text)
    block = get_odyssey_block(body_text)

    if not block:
        print(f"{date}: The Odyssey not found.")
        return {
            "date": date,
            "odyssey": False,
            "formats": [],
        }

    formats = parse_formats(block)

    print("\n============================")
    print(f"DATE: {date}")
    print("ODYSSEY BLOCK:")
    print("\n".join(block))
    print("PARSED FORMATS:", formats)
    print("============================\n")

    return {
        "date": date,
        "odyssey": True,
        "formats": formats,
    }


def click_day(page, label):
    try:
        candidates = page.get_by_text(
            label,
            exact=True,
        )

        for i in range(candidates.count()):
            item = candidates.nth(i)

            try:
                if not item.is_visible():
                    continue

                box = item.bounding_box()

                # Date navigation is near the top of the page.
                if box and box["y"] < 1000:
                    item.click(timeout=5000)
                    page.wait_for_timeout(2500)
                    return True

            except Exception:
                continue

    except Exception:
        pass

    return False


def main():
    print(
        "Checking Planet Rishon LeZion "
        "for The Odyssey IMAX..."
    )

    manual_run = (
        os.getenv("GITHUB_EVENT_NAME")
        == "workflow_dispatch"
    )

    scans = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            },
            locale="he-IL",
        )

        page.goto(
            CINEMA_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        page.wait_for_timeout(6000)

        dismiss_cookies(page)

        # Scan the currently selected day first.
        scans.append(scan_current_day(page))

        # Then try all other visible schedule days.
        day_labels = [
            "היום",
            "א׳",
            "ב׳",
            "ג׳",
            "ד׳",
            "ה׳",
            "ו׳",
            "ש׳",
        ]

        seen_dates = {
            scans[0]["date"]
        }

        for label in day_labels:
            if not click_day(page, label):
                continue

            result = scan_current_day(page)

            if result["date"] not in seen_dates:
                scans.append(result)
                seen_dates.add(result["date"])

        browser.close()

    imax_results = []
    non_imax_results = []

    for scan in scans:
        if not scan["odyssey"]:
            continue

        for item in scan["formats"]:
            entry = {
                "date": scan["date"],
                "format": item["format"],
                "times": item["times"],
            }

            if "IMAX" in item["format"].upper():
                if item["times"]:
                    imax_results.append(entry)
            else:
                non_imax_results.append(entry)

    print("IMAX RESULTS:")
    print(imax_results)

    print("NON-IMAX RESULTS:")
    print(non_imax_results)

    if manual_run:
        if imax_results:
            parts = []

            for result in imax_results:
                parts.append(
                    f"📅 {result['date']}\n"
                    f"🎞️ {result['format']}\n"
                    f"🕐 {', '.join(result['times'])}"
                )

            send_telegram(
                "✅ בדיקת הבוט הצליחה!\n\n"
                "🎬 נמצאה האודיסאה ב-IMAX "
                "בפלאנט ראשון לציון!\n\n"
                + "\n\n".join(parts)
                + "\n\n🎟️ לצפייה והזמנה:\n"
                + CINEMA_URL
            )

        else:
            details = []

            for result in non_imax_results:
                times = (
                    ", ".join(result["times"])
                    if result["times"]
                    else "ללא שעה שזוהתה"
                )

                details.append(
                    f"📅 {result['date']}\n"
                    f"🎞️ {result['format']}\n"
                    f"🕐 {times}"
                )

            extra = ""

            if details:
                extra = (
                    "\n\nהקרנות אחרות שנמצאו:\n\n"
                    + "\n\n".join(details)
                )

            send_telegram(
                "✅ בדיקת הבוט הצליחה.\n\n"
                "🔎 האודיסאה נבדקה בלוח ההקרנות "
                "של פלאנט ראשון לציון.\n"
                "כרגע לא זוהתה הקרנת IMAX."
                + extra
            )

    if not imax_results:
        print("No Odyssey IMAX screenings detected.")
        return

    fingerprint_data = json.dumps(
        imax_results,
        ensure_ascii=False,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        fingerprint_data.encode("utf-8")
    ).hexdigest()

    previous = load_state()

    if (
        not manual_run
        and fingerprint != previous
    ):
        parts = []

        for result in imax_results:
            parts.append(
                f"📅 {result['date']}\n"
                f"🕐 {', '.join(result['times'])}"
            )

        send_telegram(
            "🚨 נמצאה הקרנת IMAX חדשה "
            "של האודיסאה בראשון לציון!\n\n"
            + "\n\n".join(parts)
            + "\n\n🎟️ להזמנה:\n"
            + CINEMA_URL
        )

    if fingerprint != previous:
        save_state(fingerprint)

    print("Scan completed successfully.")


if __name__ == "__main__":
    main()
