import os
import re
import json
import hashlib
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


CINEMA_URL = "https://www.planetcinema.co.il/cinemas/Rishon_Letziyon/1072"
MOVIE_URL = "https://www.planetcinema.co.il/films/the-odyssey/7460s2r"

MOVIE_TITLES = [
    "האודיסאה",
    "The Odyssey",
    "ОДИССЕЯ",
]

STATE_FILE = Path("state.json")


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets are missing.")
        return False

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
    return True


def load_previous_state():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data.get("fingerprint")
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


def extract_date(text):
    patterns = [
        r"(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)\s+\d{1,2}/\d{1,2}/\d{4}",
        r"\d{1,2}/\d{1,2}/\d{4}",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return "תאריך לא זוהה"


def find_movie_cards(page):
    results = []

    for title in MOVIE_TITLES:
        locator = page.get_by_text(title, exact=False)

        try:
            count = min(locator.count(), 15)
        except Exception:
            continue

        for index in range(count):
            try:
                element = locator.nth(index)

                data = element.evaluate(
                    """
                    (el) => {
                        let current = el;

                        for (let level = 0; level < 10 && current; level++) {
                            const text = (current.innerText || "").trim();
                            const html = current.outerHTML || "";

                            const hasTime =
                                /(?:[01]?\\d|2[0-3]):[0-5]\\d/.test(text);

                            if (
                                hasTime &&
                                text.length >= 10 &&
                                text.length <= 6000
                            ) {
                                const links = Array.from(
                                    current.querySelectorAll("a")
                                ).map(a => a.href).filter(Boolean);

                                return {
                                    text: text,
                                    html: html.substring(0, 15000),
                                    links: links
                                };
                            }

                            current = current.parentElement;
                        }

                        return null;
                    }
                    """
                )

                if not data:
                    continue

                text = data["text"]
                html = data["html"]

                times = sorted(
                    set(
                        re.findall(
                            r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b",
                            text,
                        )
                    )
                )

                if not times:
                    continue

                # IMAX can appear as visible text, alt text,
                # title attribute or CSS/data attribute.
                imax_found = (
                    "imax" in text.lower()
                    or "imax" in html.lower()
                )

                results.append(
                    {
                        "title": title,
                        "date": extract_date(
                            page.locator("body").inner_text()
                        ),
                        "times": times,
                        "imax": imax_found,
                        "links": data.get("links", []),
                        "preview": text[:1200],
                    }
                )

            except Exception as exc:
                print(f"Candidate parsing error: {exc}")
                continue

    return results


def scan_page(page):
    all_results = []

    page.goto(
        CINEMA_URL,
        wait_until="domcontentloaded",
        timeout=90000,
    )

    page.wait_for_timeout(8000)

    body_text = page.locator("body").inner_text()

    print("Page loaded.")
    print(f"Body length: {len(body_text)}")

    title_seen = any(
        title.lower() in body_text.lower()
        for title in MOVIE_TITLES
    )

    print(f"Odyssey title visible on page: {title_seen}")

    if title_seen:
        lower_text = body_text.lower()

        for title in MOVIE_TITLES:
            position = lower_text.find(title.lower())

            if position != -1:
                start = max(0, position - 500)
                end = min(len(body_text), position + 1800)

                print("\n--- ODYSSEY DEBUG PREVIEW ---")
                print(body_text[start:end])
                print("--- END DEBUG PREVIEW ---\n")
                break

    all_results.extend(find_movie_cards(page))

    # Try the different day buttons in the weekly schedule.
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

    for label in day_labels:
        try:
            buttons = page.get_by_role(
                "button",
                name=label,
                exact=True,
            )

            if buttons.count() == 0:
                continue

            button = buttons.first

            if not button.is_visible():
                continue

            print(f"Checking schedule tab: {label}")

            button.click(timeout=5000)
            page.wait_for_timeout(2500)

            all_results.extend(find_movie_cards(page))

        except Exception as exc:
            print(f"Could not check tab {label}: {exc}")
            continue

    return all_results, title_seen


def clean_results(results):
    unique = {}

    for result in results:
        key = (
            result["date"],
            tuple(result["times"]),
            result["imax"],
        )

        unique[key] = result

    return list(unique.values())


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

        results, title_seen = scan_page(page)

        browser.close()

    results = clean_results(results)

    imax_results = [
        result
        for result in results
        if result["imax"]
    ]

    print(f"Movie cards found: {len(results)}")
    print(f"IMAX movie cards found: {len(imax_results)}")

    for result in results:
        print(
            "RESULT:",
            result["date"],
            result["times"],
            "IMAX =", result["imax"],
        )
        print(result["preview"])
        print("--------------------")

    # Manual GitHub run = always send a Telegram test
    if manual_run:
        if imax_results:
            lines = []

            for result in imax_results:
                lines.append(
                    f"📅 {result['date']}\n"
                    f"🕐 {', '.join(result['times'])}"
                )

            message = (
                "✅ בדיקת הבוט הצליחה!\n\n"
                "🎬 נמצאו הקרנות אפשריות של "
                "האודיסאה ב-IMAX בראשון לציון:\n\n"
                + "\n\n".join(lines)
                + "\n\n🎟️ "
                + CINEMA_URL
            )

        elif title_seen:
            message = (
                "✅ החיבור לטלגרם עובד!\n\n"
                "🎬 הבוט מצא את האודיסאה "
                "בלוח של פלאנט ראשון לציון,\n"
                "אבל כרגע לא זיהה הקרנת IMAX "
                "בתוך כרטיס ההקרנה.\n\n"
                "אנחנו ממשיכים לכייל את הזיהוי."
            )

        else:
            message = (
                "✅ החיבור לטלגרם עובד!\n\n"
                "🔎 הסריקה של פלאנט הסתיימה,\n"
                "אבל האודיסאה לא הופיעה כרגע "
                "בלוח ההקרנות שהאתר הציג לבוט."
            )

        send_telegram(message)

    if not imax_results:
        print("No Odyssey IMAX screening card detected.")
        return

    fingerprint_data = json.dumps(
        imax_results,
        ensure_ascii=False,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        fingerprint_data.encode("utf-8")
    ).hexdigest()

    previous = load_previous_state()

    if fingerprint == previous:
        print("No change since previous check.")
        return

    # For scheduled runs, alert only when something changes.
    if not manual_run:
        lines = []

        for result in imax_results:
            lines.append(
                f"📅 {result['date']}\n"
                f"🕐 {', '.join(result['times'])}"
            )

        send_telegram(
            "🚨 נמצאה הקרנת IMAX חדשה "
            "של האודיסאה!\n\n"
            + "\n\n".join(lines)
            + "\n\n🎟️ להזמנה:\n"
            + CINEMA_URL
        )

    save_state(fingerprint)

    print("Scan completed successfully.")


if __name__ == "__main__":
    main()
