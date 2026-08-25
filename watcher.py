import os
import re
import json
import hashlib
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


CINEMA_URL = "https://www.planetcinema.co.il/cinemas/Rishon_Letziyon/1072"

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
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
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


def dismiss_cookies(page):
    for text in [
        "דחה את כל העוגיות",
        "קבל את כל העוגיות",
    ]:
        try:
            button = page.get_by_text(text, exact=False)

            if button.count() and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(700)
                return

        except Exception:
            pass


def get_date(page):
    text = page.locator("body").inner_text()

    match = re.search(
        r"(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)"
        r"\s+\d{1,2}/\d{1,2}/\d{4}",
        text,
    )

    if match:
        return match.group(0)

    return "תאריך לא זוהה"


def get_odyssey_container(page):
    titles = page.get_by_text("האודיסאה", exact=True)

    for i in range(titles.count()):
        try:
            title = titles.nth(i)

            if not title.is_visible():
                continue

            handle = title.element_handle()

            if not handle:
                continue

            container = page.evaluate_handle(
                """
                (el) => {
                    let current = el;

                    for (
                        let level = 0;
                        level < 12 && current;
                        level++
                    ) {
                        const text =
                            (current.innerText || "").trim();

                        if (
                            text.includes("האודיסאה") &&
                            text.length < 3000 &&
                            (
                                text.includes("2DEN") ||
                                text.toUpperCase().includes("IMAX")
                            )
                        ) {
                            return current;
                        }

                        current = current.parentElement;
                    }

                    return null;
                }
                """,
                handle,
            )

            element = container.as_element()

            if element:
                return element

        except Exception:
            continue

    return None


def get_imax_showings(page):
    container = get_odyssey_container(page)

    if not container:
        print("Odyssey container not found.")
        return []

    results = page.evaluate(
        """
        (root) => {
            const links = Array.from(
                root.querySelectorAll("a[data-url]")
            );

            return links.map(link => {
                return {
                    time:
                        (link.innerText || "")
                        .trim()
                        .match(
                            /(?:[01]?\\d|2[0-3]):[0-5]\\d/
                        )?.[0] || null,

                    data_url:
                        link.getAttribute("data-url"),

                    attrs:
                        link.getAttribute("data-attrs") || ""
                };
            });
        }
        """,
        container,
    )

    imax = []

    for item in results:
        attrs = item.get("attrs", "").lower()
        time = item.get("time")
        url = item.get("data_url")
        if url:
            url = url.replace(
                "/api/order/",
                "/order/",
            )

        if (
            "imax" in attrs
            and time
            and url
        ):
            imax.append(
                {
                    "time": time,
                    "url": url,
                }
            )

    unique = {}

    for item in imax:
        unique[
            (item["time"], item["url"])
        ] = item

    return list(unique.values())


def click_day(page, label):
    try:
        matches = page.get_by_text(
            label,
            exact=True,
        )

        for i in range(matches.count()):
            item = matches.nth(i)

            try:
                if not item.is_visible():
                    continue

                box = item.bounding_box()

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

    all_showings = []

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

        seen_dates = set()

        def scan():
            date = get_date(page)

            if date in seen_dates:
                return

            seen_dates.add(date)

            showings = get_imax_showings(page)

            print(
                f"{date}: "
                f"{len(showings)} IMAX showings"
            )

            for showing in showings:
                print(
                    date,
                    showing["time"],
                    showing["url"],
                )

                all_showings.append(
                    {
                        "date": date,
                        "time": showing["time"],
                        "url": showing["url"],
                    }
                )

        # Current day
        scan()

        # Remaining schedule days
        for label in [
            "היום",
            "א׳",
            "ב׳",
            "ג׳",
            "ד׳",
            "ה׳",
            "ו׳",
            "ש׳",
        ]:
            if click_day(page, label):
                scan()

        browser.close()

    all_showings.sort(
        key=lambda x: (
            x["date"],
            x["time"],
        )
    )

    print("\nFINAL IMAX SHOWINGS:")
    print(
        json.dumps(
            all_showings,
            ensure_ascii=False,
            indent=2,
        )
    )

    if not all_showings:
        print("No Odyssey IMAX showings found.")

        if manual_run:
            send_telegram(
                "✅ הבוט פועל.\n\n"
                "🔎 כרגע לא נמצאו הקרנות IMAX "
                "של האודיסאה בפלאנט ראשון לציון."
            )

        return

    fingerprint_source = json.dumps(
        all_showings,
        ensure_ascii=False,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()

    previous = load_state()

    parts = []

    for showing in all_showings:
        parts.append(
            f"📅 {showing['date']}\n"
            f"🕐 {showing['time']}\n"
            f"🎟️ {showing['url']}"
        )

    message = (
        "🎬 האודיסאה — IMAX ראשון לציון\n\n"
        + "\n\n".join(parts)
    )

    if manual_run:
        send_telegram(
            "✅ בדיקת הבוט הצליחה!\n\n"
            + message
        )

    elif fingerprint != previous:
        send_telegram(
            "🚨 נמצאה הקרנת IMAX חדשה!\n\n"
            + message
        )

    if fingerprint != previous:
        save_state(fingerprint)

    print("Scan completed successfully.")


if __name__ == "__main__":
    main()
