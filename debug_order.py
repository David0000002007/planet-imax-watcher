import json
from collections import defaultdict
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
    try:
        if "seatplanV2" in response.url:
            captured["seatplan"] = response.json()
            print("Seatplan captured.")

        elif "seats-statusV2" in response.url:
            captured["status"] = response.json()
            print("Seat status captured.")

    except Exception as exc:
        print("Capture error:", exc)


def print_status_summary():
    print("\n")
    print("=" * 70)
    print("STATUS BY ROW")
    print("=" * 70)

    if not captured["status"]:
        print("NO STATUS")
        return

    seats = captured["status"].get("seats", {})

    rows = defaultdict(list)

    for key, value in seats.items():
        parts = key.split("_")

        if len(parts) != 3:
            continue

        try:
            section = int(parts[0])
            seat = int(parts[1])
            row = int(parts[2])
        except ValueError:
            continue

        rows[row].append(
            {
                "seat": seat,
                "value": value,
                "section": section,
            }
        )

    for row in sorted(rows):
        items = sorted(
            rows[row],
            key=lambda x: x["seat"],
        )

        seats_in_row = [
            x["seat"]
            for x in items
        ]

        values = sorted(
            set(
                str(x["value"])
                for x in items
            )
        )

        print(
            f"ROW {row}: "
            f"{seats_in_row}"
        )

        print(
            f"STATUS VALUES: {values}"
        )


def print_raw_rows():
    print("\n")
    print("=" * 70)
    print("RAW SEATPLAN ROWS")
    print("=" * 70)

    try:
        rows = (
            captured["seatplan"]
            ["S"]["1"]["G"]["0"]["R"]
        )
    except Exception as exc:
        print(
            "Could not reach "
            "S -> 1 -> G -> 0 -> R"
        )
        print(exc)

        print("\nFULL SEATPLAN:")
        print(
            json.dumps(
                captured["seatplan"],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print("TYPE:", type(rows).__name__)

    if isinstance(rows, dict):
        print(
            "ROW KEYS:",
            list(rows.keys()),
        )

        for key, value in rows.items():
            print("\n")
            print("-" * 70)
            print(f"ROW KEY: {key}")
            print("-" * 70)

            print(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                )
            )

    elif isinstance(rows, list):
        print(
            f"NUMBER OF ROWS: {len(rows)}"
        )

        for index, value in enumerate(rows):
            print("\n")
            print("-" * 70)
            print(f"ROW INDEX: {index}")
            print("-" * 70)

            print(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                )
            )

    else:
        print(
            json.dumps(
                rows,
                ensure_ascii=False,
                indent=2,
            )
        )


def inspect_dom(page):
    print("\n")
    print("=" * 70)
    print("SEAT DOM SAMPLE")
    print("=" * 70)

    try:
        result = page.evaluate(
            """
            () => {
                const nodes = Array.from(
                    document.querySelectorAll("*")
                );

                return nodes
                    .filter(el => {
                        const cls =
                            (el.className || "").toString();

                        const aria =
                            el.getAttribute("aria-label") || "";

                        const id =
                            el.id || "";

                        return (
                            cls.toLowerCase().includes("seat") ||
                            aria.toLowerCase().includes("seat") ||
                            id.toLowerCase().includes("seat")
                        );
                    })
                    .slice(0, 80)
                    .map(el => ({
                        tag: el.tagName,
                        id: el.id || null,
                        class:
                            (el.className || "").toString(),
                        aria:
                            el.getAttribute("aria-label"),
                        title:
                            el.getAttribute("title"),
                        data:
                            Array.from(el.attributes)
                                .filter(a =>
                                    a.name.startsWith("data-")
                                )
                                .reduce(
                                    (obj, a) => {
                                        obj[a.name] = a.value;
                                        return obj;
                                    },
                                    {}
                                ),
                        text:
                            (el.innerText || "")
                            .trim()
                            .substring(0, 150)
                    }));
            }
            """
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

    except Exception as exc:
        print("DOM inspection failed:", exc)


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
                "Odyssey IMAX 13:30 not found."
            )
            browser.close()
            return

        print("Found Odyssey IMAX 13:30.")

        target.click(timeout=5000)
        page.wait_for_timeout(2000)

        options = page.get_by_text(
            "הזמינו כאורח",
            exact=True,
        )

        guest = None

        for i in range(options.count()):
            try:
                candidate = options.nth(i)

                if candidate.is_visible():
                    guest = candidate
                    break
            except Exception:
                continue

        if guest is None:
            print("Guest button not found.")
            browser.close()
            return

        print("Clicking guest order...")

        guest.click(timeout=5000)

        page.wait_for_timeout(12000)

        print("\nFINAL URL:")
        print(page.url)

        print_status_summary()
        print_raw_rows()
        inspect_dom(page)

        browser.close()


if __name__ == "__main__":
    main()
