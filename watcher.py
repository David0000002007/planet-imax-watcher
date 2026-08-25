import os
import re
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright


CINEMA_URL = (
    "https://www.planetcinema.co.il/"
    "cinemas/Rishon_Letziyon/1072"
)

STATE_FILE = Path("state.json")

# ארבע השורות האמצעיות באולם IMAX
PREFERRED_ROWS = {7, 8, 9, 10}

# הזוג צריך להיות בתוך 30% המרכזיים של השורה
# כלומר עד 15% לכל צד ממרכז השורה
MAX_CENTER_RATIO = 0.15


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
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return data.get("fingerprint")

    except Exception:
        return None


def save_state(fingerprint):
    STATE_FILE.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint
            },
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
            button = page.get_by_text(
                text,
                exact=False,
            )

            if (
                button.count()
                and button.first.is_visible()
            ):
                button.first.click(
                    timeout=3000
                )

                page.wait_for_timeout(700)
                return

        except Exception:
            pass


def get_date(page):
    text = page.locator(
        "body"
    ).inner_text()

    match = re.search(
        r"(?:ראשון|שני|שלישי|רביעי|"
        r"חמישי|שישי|שבת)"
        r"\s+\d{1,2}/\d{1,2}/\d{4}",
        text,
    )

    if match:
        return match.group(0)

    return "תאריך לא זוהה"


def get_odyssey_container(page):
    titles = page.get_by_text(
        "האודיסאה",
        exact=True,
    )

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
                            (current.innerText || "")
                            .trim();

                        if (
                            text.includes("האודיסאה") &&
                            text.length < 3000 &&
                            (
                                text.includes("2DEN") ||
                                text
                                    .toUpperCase()
                                    .includes("IMAX")
                            )
                        ) {
                            return current;
                        }

                        current =
                            current.parentElement;
                    }

                    return null;
                }
                """,
                handle,
            )

            element = (
                container.as_element()
            )

            if element:
                return element

        except Exception:
            continue

    return None


def get_imax_showings(page):
    container = get_odyssey_container(
        page
    )

    if not container:
        return []

    results = page.evaluate(
        """
        (root) => {
            const links = Array.from(
                root.querySelectorAll(
                    "a[data-url]"
                )
            );

            return links.map(link => ({
                time:
                    (link.innerText || "")
                    .trim()
                    .match(
                        /(?:[01]?\\d|2[0-3]):[0-5]\\d/
                    )?.[0] || null,

                data_url:
                    link.getAttribute(
                        "data-url"
                    ),

                attrs:
                    link.getAttribute(
                        "data-attrs"
                    ) || ""
            }));
        }
        """,
        container,
    )

    imax = []

    for item in results:
        attrs = (
            item.get(
                "attrs",
                "",
            )
            .lower()
        )

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
        key = (
            item["time"],
            item["url"],
        )

        unique[key] = item

    return list(
        unique.values()
    )


def click_day(page, label):
    try:
        matches = page.get_by_text(
            label,
            exact=True,
        )

        for i in range(
            matches.count()
        ):
            item = matches.nth(i)

            try:
                if not item.is_visible():
                    continue

                box = (
                    item.bounding_box()
                )

                if (
                    box
                    and box["y"] < 1000
                ):
                    item.click(
                        timeout=5000
                    )

                    page.wait_for_timeout(
                        2500
                    )

                    return True

            except Exception:
                continue

    except Exception:
        pass

    return False


def date_sort_key(text):
    match = re.search(
        r"(\d{1,2})/"
        r"(\d{1,2})/"
        r"(\d{4})",
        text,
    )

    if not match:
        return datetime.max

    day, month, year = map(
        int,
        match.groups(),
    )

    return datetime(
        year,
        month,
        day,
    )


def scan_showings(browser):
    context = browser.new_context(
        locale="he-IL",
        viewport={
            "width": 1440,
            "height": 1200,
        },
    )

    page = context.new_page()

    page.goto(
        CINEMA_URL,
        wait_until="domcontentloaded",
        timeout=90000,
    )

    page.wait_for_timeout(6000)

    dismiss_cookies(page)

    all_showings = []
    seen_dates = set()

    def scan_current():
        date = get_date(page)

        if date in seen_dates:
            return

        seen_dates.add(date)

        showings = get_imax_showings(
            page
        )

        print(
            f"{date}: "
            f"{len(showings)} "
            f"Odyssey IMAX showings"
        )

        for showing in showings:
            all_showings.append(
                {
                    "date": date,
                    "time":
                        showing["time"],
                    "url":
                        showing["url"],
                }
            )

    scan_current()

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
        if click_day(
            page,
            label,
        ):
            scan_current()

    context.close()

    all_showings.sort(
        key=lambda item: (
            date_sort_key(
                item["date"]
            ),
            item["time"],
        )
    )

    return all_showings


def check_seats(
    browser,
    showing,
):
    print("\n")
    print("=" * 60)

    print(
        "Checking seats:",
        showing["date"],
        showing["time"],
    )

    print(
        showing["url"]
    )

    captured = {
        "seatplan": None,
        "status": None,
    }

    context = browser.new_context(
        locale="he-IL",
        viewport={
            "width": 1440,
            "height": 1200,
        },
    )

    page = context.new_page()

    def capture(response):
        try:
            if (
                "seatplanV2"
                in response.url
            ):
                captured[
                    "seatplan"
                ] = response.json()

            elif (
                "seats-statusV2"
                in response.url
            ):
                captured[
                    "status"
                ] = response.json()

        except Exception as exc:
            print(
                "Seat API capture error:",
                exc,
            )

    context.on(
        "response",
        capture,
    )

    try:
        page.goto(
            showing["url"],
            wait_until=(
                "domcontentloaded"
            ),
            timeout=90000,
        )

        # נותנים למערכת ההזמנות
        # זמן לטעון את שני API-י המושבים
        for _ in range(12):
            if (
                captured["seatplan"]
                and captured["status"]
            ):
                break

            page.wait_for_timeout(
                1000
            )

    except Exception as exc:
        print(
            "Order page error:",
            exc,
        )

    context.close()

    if (
        not captured["seatplan"]
        or not captured["status"]
    ):
        print(
            "Could not retrieve "
            "seat information."
        )

        return {
            "status": "unknown",
            "best": None,
            "closest": None,
        }

    return analyse_seats(
        captured["seatplan"],
        captured["status"],
    )


def analyse_seats(
    seatplan,
    status,
):
    try:
        rows = (
            seatplan
            ["S"]
            ["1"]
            ["G"]
            ["0"]
            ["R"]
        )

        status_seats = (
            status["seats"]
        )

    except Exception as exc:
        print(
            "Could not parse "
            "seat information:",
            exc,
        )

        return {
            "status": "unknown",
            "best": None,
            "closest": None,
        }

    pairs = []

    for (
        row_key,
        row_data,
    ) in rows.items():

        try:
            visible_row = int(
                row_data["n"]
            )

        except Exception:
            continue

        if (
            visible_row
            not in PREFERRED_ROWS
        ):
            continue

        try:
            left_x = float(
                row_data[
                    "rd"
                ]["l"]["x"]
            )

            right_x = float(
                row_data[
                    "rd"
                ]["r"]["x"]
            )

        except Exception:
            continue

        row_width = (
            right_x - left_x
        )

        if row_width <= 0:
            continue

        row_center = (
            left_x
            + right_x
        ) / 2

        available = []

        for (
            seat_key,
            seat_data,
        ) in (
            row_data
            .get(
                "S",
                {},
            )
            .items()
        ):
            try:
                visible_seat = int(
                    seat_data["n"]
                )

                x = float(
                    seat_data[
                        "rd"
                    ]["cx"]
                )

            except Exception:
                continue

            # לא מציעים אוטומטית
            # מושב נגיש.
            if seat_data.get("hc"):
                continue

            status_key = (
                f"1_"
                f"{seat_key}_"
                f"{row_key}"
            )

            # לפי הנתונים שקיבלנו
            # מהאתר: מושבים שמופיעים
            # ב-seats עם ערך 0
            # הם המועמדים הזמינים.
            is_available = (
                status_key
                in status_seats
                and status_seats[
                    status_key
                ] == 0
            )

            if is_available:
                available.append(
                    {
                        "number":
                            visible_seat,
                        "x":
                            x,
                    }
                )

        available.sort(
            key=lambda item:
            item["x"]
        )

        print(
            f"Row {visible_row}: "
            f"{[
                x['number']
                for x in available
            ]}"
        )

        for i in range(
            len(available) - 1
        ):
            first = available[i]
            second = available[
                i + 1
            ]

            number_gap = abs(
                first["number"]
                - second["number"]
            )

            x_gap = abs(
                first["x"]
                - second["x"]
            )

            if number_gap != 1:
                continue

            # לפי המפה מושבים צמודים
            # נמצאים במרווח של כ-60
            # יחידות. נותנים מעט מרווח.
            if x_gap > 75:
                continue

            pair_center = (
                first["x"]
                + second["x"]
            ) / 2

            center_distance = abs(
                pair_center
                - row_center
            )

            center_ratio = (
                center_distance
                / row_width
            )

            pairs.append(
                {
                    "row":
                        visible_row,

                    "seat1":
                        min(
                            first[
                                "number"
                            ],
                            second[
                                "number"
                            ],
                        ),

                    "seat2":
                        max(
                            first[
                                "number"
                            ],
                            second[
                                "number"
                            ],
                        ),

                    "center_ratio":
                        center_ratio,

                    "center_distance":
                        center_distance,

                    "row_distance":
                        abs(
                            visible_row
                            - 8.5
                        ),
                }
            )

    if not pairs:
        print(
            "No adjacent pairs "
            "in preferred rows."
        )

        return {
            "status": "no_pair",
            "best": None,
            "closest": None,
        }

    # שורות 8/9 בראש,
    # אחריהן 7/10.
    # בתוך אותה עדיפות,
    # הזוג הקרוב ביותר למרכז.
    pairs.sort(
        key=lambda pair: (
            pair["row_distance"],
            pair["center_distance"],
        )
    )

    closest = pairs[0]

    suitable = [
        pair
        for pair in pairs
        if (
            pair["center_ratio"]
            <= MAX_CENTER_RATIO
        )
    ]

    if not suitable:
        print(
            "No suitable "
            "middle/center pair."
        )

        print(
            "Closest:",
            f"row {closest['row']},",
            f"seats "
            f"{closest['seat1']}-"
            f"{closest['seat2']}",
            f"ratio="
            f"{closest['center_ratio']:.3f}",
        )

        return {
            "status": "no_suitable",
            "best": None,
            "closest": closest,
        }

    best = suitable[0]

    print(
        "SUITABLE PAIR:",
        f"row {best['row']},",
        f"seats "
        f"{best['seat1']}-"
        f"{best['seat2']}",
        f"ratio="
        f"{best['center_ratio']:.3f}",
    )

    return {
        "status": "suitable",
        "best": best,
        "closest": closest,
    }


def build_fingerprint(
    suitable_results,
):
    data = []

    for result in suitable_results:
        best = result["best"]

        data.append(
            {
                "date":
                    result["date"],
                "time":
                    result["time"],
                "row":
                    best["row"],
                "seat1":
                    best["seat1"],
                "seat2":
                    best["seat2"],
            }
        )

    text = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def main():
    print(
        "Planet IMAX Odyssey "
        "seat watcher starting..."
    )

    manual_run = (
        os.getenv(
            "GITHUB_EVENT_NAME"
        )
        == "workflow_dispatch"
    )

    with sync_playwright() as p:
        browser = (
            p.chromium.launch(
                headless=True
            )
        )

        showings = scan_showings(
            browser
        )

        print(
            "\nIMAX showings found:",
            len(showings),
        )

        checked = []

        for showing in showings:
            result = check_seats(
                browser,
                showing,
            )

            checked.append(
                {
                    **showing,
                    **result,
                }
            )

        browser.close()

    suitable_results = [
        item
        for item in checked
        if (
            item["status"]
            == "suitable"
        )
    ]

    unknown_results = [
        item
        for item in checked
        if (
            item["status"]
            == "unknown"
        )
    ]

    fingerprint = (
        build_fingerprint(
            suitable_results
        )
    )

    previous = load_state()

    if suitable_results:
        parts = []

        for result in suitable_results:
            best = result["best"]

            parts.append(
                f"📅 {result['date']}\n"
                f"🕐 {result['time']}\n"
                f"💺 שורה "
                f"{best['row']}, "
                f"מושבים "
                f"{best['seat1']}-"
                f"{best['seat2']}\n"
                f"🎟️ {result['url']}"
            )

        message = (
            "🎯 נמצאו מושבים טובים "
            "להאודיסאה ב-IMAX!\n\n"
            + "\n\n".join(parts)
        )

        if manual_run:
            send_telegram(
                "✅ בדיקת הבוט "
                "הסתיימה.\n\n"
                + message
            )

        elif fingerprint != previous:
            send_telegram(
                "🚨 נמצאו שני מושבים "
                "צמודים במרכז!\n\n"
                + "\n\n".join(parts)
            )

    elif manual_run:
        message = (
            "✅ בדיקת הבוט הסתיימה.\n\n"
            f"🎬 נבדקו "
            f"{len(showings)} "
            "הקרנות IMAX של האודיסאה.\n\n"
            "כרגע לא נמצא זוג "
            "מושבים מתאים בשורות "
            "האמצעיות ובמרכז השורה."
        )

        if unknown_results:
            message += (
                "\n\n⚠️ ב-"
                f"{len(unknown_results)} "
                "הקרנות לא הצלחתי "
                "לקרוא את מפת המושבים."
            )

        send_telegram(message)

    # שומרים גם מצב של "אין זוג".
    # כך אם זוג טוב יתפנה מאוחר יותר,
    # השינוי יגרום להתראה חדשה.
    if fingerprint != previous:
        save_state(fingerprint)

    print("\n====================")
    print("SUMMARY")
    print("====================")

    print(
        "IMAX showings:",
        len(showings),
    )

    print(
        "Suitable:",
        len(suitable_results),
    )

    print(
        "Unknown:",
        len(unknown_results),
    )

    print(
        "Watcher completed."
    )


if __name__ == "__main__":
    main()
