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
    possible_buttons = [
        "דחה את כל העוגיות",
        "קבל את כל העוגיות",
        "קבל את כל קבצי",
    ]

    for text in possible_buttons:
        try:
            button = page.get_by_text(text, exact=False)

            if button.count() > 0 and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


def select_imax(page):
    print("Trying to select IMAX filter...")

    # First try a normal HTML <select>
    selects = page.locator("select")

    for i in range(selects.count()):
        try:
            select = selects.nth(i)
            options = select.locator("option").all_inner_texts()

            for option in options:
                if "IMAX" in option.upper():
                    print(f"Found native IMAX option: {option}")

                    select.select_option(label=option)

                    page.wait_for_timeout(4000)

                    print("IMAX filter selected.")
                    return True

        except Exception:
            continue

    # Planet may use a custom dropdown instead of <select>
    try:
        trigger = page.get_by_text(
            "בחרו סוג הקרנה",
            exact=True,
        )

        if trigger.count() == 0:
            print("Format dropdown was not found.")
            return False

        trigger.first.click(timeout=5000)

        page.wait_for_timeout(1000)

        imax_options = page.get_by_text(
            re.compile(r"^IMAX$", re.IGNORECASE)
        )

        for i in range(imax_options.count()):
            option = imax_options.nth(i)

            try:
                if option.is_visible():
                    print("Visible IMAX option found.")

                    option.click(timeout=5000)

                    page.wait_for_timeout(4000)

                    print("IMAX filter selected.")
                    return True

            except Exception:
                continue

    except Exception as exc:
        print(f"Could not open format filter: {exc}")

    print("Could not safely select IMAX.")
    return False


def get_date(body_text):
    match = re.search(
        r"(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)"
        r"\s+\d{1,2}/\d{1,2}/\d{4}",
        body_text,
    )

    if match:
        return match.group(0)

    return "תאריך לא זוהה"


def find_odyssey_section(body_text):
    lines = [
        line.strip()
        for line in body_text.splitlines()
        if line.strip()
    ]

    movie_index = None

    for i, line in enumerate(lines):
        if any(
            title.lower() in line.lower()
            for title in MOVIE_TITLES
        ):
            movie_index = i
            break

    if movie_index is None:
        return None

    section = [lines[movie_index]]

    # Read only the local movie block.
    for i in range(
        movie_index + 1,
        min(movie_index + 15, len(lines)),
    ):
        # A new movie normally has a title followed by
        # "genre | xxx דקות". Stop before that new title.
        if (
            i + 1 < len(lines)
            and re.search(
                r"\|\s*\d+\s*דקות",
                lines[i + 1],
            )
        ):
            break

        section.append(lines[i])

    section_text = "\n".join(section)

    times = re.findall(
        r"(?:[01]?\d|2[0-3]):[0-5]\d",
        section_text,
    )

    times = sorted(set(times))

    return {
        "text": section_text,
        "times": times,
    }


def main():
    print(
        "Checking Planet Rishon LeZion "
        "for The Odyssey IMAX..."
    )

    manual_run = (
        os.getenv("GITHUB_EVENT_NAME")
        == "workflow_dispatch"
    )

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

        imax_selected = select_imax(page)

        if not imax_selected:
            browser.close()

            print(
                "IMAX filter could not be selected. "
                "Stopping to avoid a false alert."
            )

            if manual_run:
                send_telegram(
                    "⚠️ בדיקת הבוט הסתיימה, "
                    "אבל לא הצלחתי לבחור את מסנן IMAX "
                    "באתר Planet.\n\n"
                    "לא נשלחה התראת כרטיסים כדי "
                    "להימנע מהתראת שווא."
                )

            return

        body_text = page.locator("body").inner_text()

        print("\n--- PAGE AFTER IMAX FILTER ---")
        print(body_text[:5000])
        print("--- END PAGE ---\n")

        date = get_date(body_text)

        result = find_odyssey_section(body_text)

        browser.close()

    if not result:
        print(
            "The Odyssey is NOT visible "
            "after selecting IMAX."
        )

        if manual_run:
            send_telegram(
                "✅ בדיקת הבוט הצליחה.\n\n"
                "🎬 מסנן IMAX הופעל בהצלחה.\n"
                "כרגע האודיסאה לא מופיעה "
                "בלוח ה-IMAX שנבדק."
            )

        return

    times = result["times"]

    print("ODYSSEY IMAX SECTION:")
    print(result["text"])
    print("Times:", times)

    if not times:
        print(
            "The Odyssey was visible after "
            "IMAX filtering, but no showtime "
            "was detected."
        )

        if manual_run:
            send_telegram(
                "✅ מסנן IMAX עובד והאודיסאה "
                "נמצאה, אבל עדיין לא זוהתה "
                "שעת הקרנה."
            )

        return

    fingerprint_source = json.dumps(
        {
            "date": date,
            "times": times,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()

    previous = load_state()

    message = (
        "🎬 נמצאה הקרנת IMAX של האודיסאה "
        "בפלאנט ראשון לציון!\n\n"
        f"📅 {date}\n"
        f"🕐 {', '.join(times)}\n\n"
        "🎟️ לצפייה והזמנה:\n"
        f"{CINEMA_URL}"
    )

    if manual_run:
        send_telegram(
            "✅ בדיקת הבוט הצליחה!\n\n"
            + message
        )

    elif fingerprint != previous:
        send_telegram(
            "🚨 הקרנת IMAX חדשה!\n\n"
            + message
        )

    if fingerprint != previous:
        save_state(fingerprint)

    print("Scan completed successfully.")


if __name__ == "__main__":
    main()
