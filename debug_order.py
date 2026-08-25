from playwright.sync_api import sync_playwright


CINEMA_URL = (
    "https://www.planetcinema.co.il/"
    "cinemas/Rishon_Letziyon/1072"
)

# כרגע נגדיר את 4 השורות האמצעיות
PREFERRED_ROWS = {7, 8, 9, 10}

# הזוג חייב להיות בתוך 30% המרכזיים של השורה
MAX_CENTER_RATIO = 0.15

captured = {
    "seatplan": None,
    "status": None,
}


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


def click_wednesday(page):
    candidates = page.get_by_text(
        "ד׳",
        exact=True,
    )

    for i in range(candidates.count()):
        try:
            item = candidates.nth(i)

            if not item.is_visible():
                continue

            box = item.bounding_box()

            if box and box["y"] < 1000:
                item.click(timeout=5000)

                page.wait_for_timeout(3000)

                print(
                    "Wednesday selected."
                )

                return True

        except Exception:
            continue

    return False


def find_imax_1330(page):
    buttons = page.locator(
        'a[data-url][data-attrs*="imax"]'
    )

    for i in range(buttons.count()):
        try:
            button = buttons.nth(i)

            if "13:30" in button.inner_text():
                return button

        except Exception:
            continue

    return None


def capture_response(response):
    try:
        if "seatplanV2" in response.url:
            captured["seatplan"] = (
                response.json()
            )

            print("Seatplan captured.")

        elif "seats-statusV2" in response.url:
            captured["status"] = (
                response.json()
            )

            print("Seat status captured.")

    except Exception as exc:
        print(
            "Capture error:",
            exc,
        )


def analyse_seats():
    seatplan = captured["seatplan"]
    status = captured["status"]

    if not seatplan or not status:
        print(
            "Seat information is missing."
        )
        return

    try:
        rows = (
            seatplan
            ["S"]
            ["1"]
            ["G"]
            ["0"]
            ["R"]
        )

        status_seats = status["seats"]

    except Exception as exc:
        print(
            "Could not read seat data:",
            exc,
        )
        return

    print("\n")
    print("=" * 70)
    print("SEAT SEARCH RESULT")
    print("=" * 70)

    print(
        "Status records:",
        len(status_seats),
    )

    status_values = sorted(
        {
            str(value)
            for value
            in status_seats.values()
        }
    )

    print(
        "Status values found:",
        status_values,
    )

    all_pairs = []

    for row_key, row_data in rows.items():
        try:
            visible_row = int(
                row_data["n"]
            )
        except Exception:
            continue

        # כרגע אנחנו מעוניינים רק
        # בשורות האמצעיות.
        if visible_row not in PREFERRED_ROWS:
            continue

        try:
            left_x = float(
                row_data["rd"]["l"]["x"]
            )

            right_x = float(
                row_data["rd"]["r"]["x"]
            )

        except Exception:
            continue

        row_width = right_x - left_x

        row_center = (
            left_x + right_x
        ) / 2

        seats = []

        for (
            seat_key,
            seat_data,
        ) in row_data.get(
            "S",
            {},
        ).items():

            try:
                visible_seat = int(
                    seat_data["n"]
                )

                x = float(
                    seat_data["rd"]["cx"]
                )

            except Exception:
                continue

            # hc = מקום נגיש.
            # לא נציע אותו אוטומטית.
            if seat_data.get("hc"):
                continue

            status_key = (
                f"1_{seat_key}_{row_key}"
            )

            # לפי מבנה ה-API שראינו,
            # מושב שמופיע ברשימה עם 0
            # נחשב כרגע מועמד פנוי.
            available = (
                status_key
                in status_seats
                and status_seats[
                    status_key
                ] == 0
            )

            if available:
                seats.append(
                    {
                        "number":
                            visible_seat,
                        "x":
                            x,
                        "seat_key":
                            seat_key,
                    }
                )

        # מסדרים לפי המיקום הפיזי
        # באולם ולא לפי המספר.
        seats.sort(
            key=lambda seat:
            seat["x"]
        )

        print(
            f"\nRow {visible_row}:"
        )

        print(
            "Available seat numbers:",
            [
                seat["number"]
                for seat in seats
            ],
        )

        # חיפוש זוגות צמודים
        for i in range(
            len(seats) - 1
        ):
            first = seats[i]
            second = seats[i + 1]

            number_difference = abs(
                first["number"]
                - second["number"]
            )

            x_difference = abs(
                first["x"]
                - second["x"]
            )

            # גם מספרים עוקבים וגם
            # פיזית אחד ליד השני.
            if number_difference != 1:
                continue

            if x_difference > 75:
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
                if row_width
                else 999
            )

            pair = {
                "row":
                    visible_row,

                "seat1":
                    min(
                        first["number"],
                        second["number"],
                    ),

                "seat2":
                    max(
                        first["number"],
                        second["number"],
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

            all_pairs.append(pair)

    if not all_pairs:
        print("\nNO ADJACENT PAIRS")
        return

    # קודם עדיפות לשורות 8-9,
    # ואז למרחק ממרכז השורה.
    all_pairs.sort(
        key=lambda pair: (
            pair["row_distance"],
            pair["center_distance"],
        )
    )

    print("\n")
    print("-" * 70)
    print("BEST AVAILABLE PAIRS")
    print("-" * 70)

    for pair in all_pairs[:10]:
        print(
            f"Row {pair['row']} | "
            f"Seats "
            f"{pair['seat1']}-"
            f"{pair['seat2']} | "
            f"Center ratio: "
            f"{pair['center_ratio']:.3f}"
        )

    suitable = [
        pair
        for pair in all_pairs
        if pair[
            "center_ratio"
        ] <= MAX_CENTER_RATIO
    ]

    print("\n")
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    if not suitable:
        print(
            "NO SUITABLE "
            "MIDDLE/CENTER PAIR"
        )

        best = all_pairs[0]

        print(
            "Closest available pair:"
        )

        print(
            f"Row {best['row']}, "
            f"Seats "
            f"{best['seat1']}-"
            f"{best['seat2']}"
        )

        return

    best = suitable[0]

    print("SUITABLE PAIR FOUND!")

    print(
        f"Row: {best['row']}"
    )

    print(
        f"Seats: "
        f"{best['seat1']}-"
        f"{best['seat2']}"
    )

    print(
        f"Center ratio: "
        f"{best['center_ratio']:.3f}"
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="he-IL",
            viewport={
                "width": 1440,
                "height": 1200,
            },
        )

        page = context.new_page()

        context.on(
            "response",
            capture_response,
        )

        page.goto(
            CINEMA_URL,
            wait_until=(
                "domcontentloaded"
            ),
            timeout=90000,
        )

        page.wait_for_timeout(6000)

        dismiss_cookies(page)

        if not click_wednesday(page):
            print(
                "Could not select Wednesday."
            )
            browser.close()
            return

        target = find_imax_1330(page)

        if target is None:
            print(
                "Odyssey IMAX "
                "13:30 not found."
            )
            browser.close()
            return

        print(
            "Found Odyssey IMAX 13:30."
        )

        target.click(timeout=5000)

        page.wait_for_timeout(2000)

        choices = page.get_by_text(
            "הזמינו כאורח",
            exact=True,
        )

        guest = None

        for i in range(
            choices.count()
        ):
            try:
                candidate = (
                    choices.nth(i)
                )

                if candidate.is_visible():
                    guest = candidate
                    break

            except Exception:
                continue

        if guest is None:
            print(
                "Guest button not found."
            )
            browser.close()
            return

        print(
            "Clicking guest order..."
        )

        guest.click(timeout=5000)

        page.wait_for_timeout(12000)

        analyse_seats()

        browser.close()


if __name__ == "__main__":
    main()
