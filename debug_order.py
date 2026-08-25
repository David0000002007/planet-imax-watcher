import json
from playwright.sync_api import sync_playwright


CINEMA_URL = (
    "https://www.planetcinema.co.il/"
    "cinemas/Rishon_Letziyon/1072"
)


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
            button = page.get_by_text(text, exact=False)

            if button.count() and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(700)
                return
        except Exception:
            pass


def click_wednesday(page):
    candidates = page.get_by_text("ד׳", exact=True)

    for i in range(candidates.count()):
        try:
            item = candidates.nth(i)

            if not item.is_visible():
                continue

            box = item.bounding_box()

            if box and box["y"] < 1000:
                item.click(timeout=5000)
                page.wait_for_timeout(3000)

                print("Wednesday selected.")
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
    url = response.url

    try:
        if "seatplanV2" in url:
            print("\nCAPTURED SEATPLAN RESPONSE")
            print(url)

            captured["seatplan"] = response.json()

        elif "seats-statusV2" in url:
            print("\nCAPTURED SEAT STATUS RESPONSE")
            print(url)

            captured["status"] = response.json()

    except Exception as exc:
        print(
            "Could not decode response:",
            url,
            exc,
        )


def summarize(value, depth=0, max_depth=5):
    indent = "  " * depth

    if depth > max_depth:
        print(indent + "...")
        return

    if isinstance(value, dict):
        print(
            indent
            + "DICT keys: "
            + ", ".join(map(str, value.keys()))
        )

        for key, child in value.items():
            print(indent + f"[{key}]")

            summarize(
                child,
                depth + 1,
                max_depth,
            )

    elif isinstance(value, list):
        print(
            indent
            + f"LIST length={len(value)}"
        )

        for i, child in enumerate(value[:3]):
            print(indent + f"sample[{i}]")

            summarize(
                child,
                depth + 1,
                max_depth,
            )

    else:
        print(
            indent
            + repr(value)[:300]
        )


def find_seat_records(value, found=None):
    if found is None:
        found = []

    if len(found) >= 40:
        return found

    if isinstance(value, dict):
        keys = {
            str(key).lower()
            for key in value.keys()
        }

        seat_words = [
            "seat",
            "row",
            "column",
            "number",
            "position",
            "status",
            "available",
            "occupied",
        ]

        score = sum(
            any(word in key for key in keys)
            for word in seat_words
        )

        if score >= 2:
            found.append(value)

        for child in value.values():
            find_seat_records(
                child,
                found,
            )

    elif isinstance(value, list):
        for child in value:
            find_seat_records(
                child,
                found,
            )

    return found


def print_results():
    print("\n\n")
    print("=" * 70)
    print("SEATPLAN STRUCTURE")
    print("=" * 70)

    if captured["seatplan"] is None:
        print("NO SEATPLAN CAPTURED")
    else:
        summarize(
            captured["seatplan"],
            max_depth=4,
        )

        candidates = find_seat_records(
            captured["seatplan"]
        )

        print("\n")
        print("=" * 70)
        print("SEATPLAN CANDIDATE RECORDS")
        print("=" * 70)

        print(
            json.dumps(
                candidates[:30],
                ensure_ascii=False,
                indent=2,
            )
        )

    print("\n\n")
    print("=" * 70)
    print("SEAT STATUS STRUCTURE")
    print("=" * 70)

    if captured["status"] is None:
        print("NO STATUS CAPTURED")
    else:
        summarize(
            captured["status"],
            max_depth=4,
        )

        candidates = find_seat_records(
            captured["status"]
        )

        print("\n")
        print("=" * 70)
        print("STATUS CANDIDATE RECORDS")
        print("=" * 70)

        print(
            json.dumps(
                candidates[:40],
                ensure_ascii=False,
                indent=2,
            )
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
            wait_until="domcontentloaded",
            timeout=90000,
        )

        page.wait_for_timeout(6000)

        dismiss_cookies(page)

        if not click_wednesday(page):
            print("Could not select Wednesday.")
            browser.close()
            return

        target = find_imax_1330(page)

        if target is None:
            print(
                "Odyssey IMAX 13:30 "
                "was not found."
            )

            browser.close()
            return

        print(
            "Found Odyssey IMAX 13:30."
        )

        target.click(timeout=5000)

        page.wait_for_timeout(2000)

        guest_buttons = page.get_by_text(
            "הזמינו כאורח",
            exact=True,
        )

        guest = None

        for i in range(
            guest_buttons.count()
        ):
            try:
                candidate = (
                    guest_buttons.nth(i)
                )

                if candidate.is_visible():
                    guest = candidate
                    break

            except Exception:
                continue

        if guest is None:
            print(
                "Guest order button "
                "was not found."
            )

            browser.close()
            return

        print(
            "Clicking guest order..."
        )

        guest.click(timeout=5000)

        # Wait for the ticket system and seat APIs.
        page.wait_for_timeout(12000)

        print("\nFINAL PAGE:")
        print(page.url)

        print_results()

        browser.close()


if __name__ == "__main__":
    main()
