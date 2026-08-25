from playwright.sync_api import sync_playwright


CINEMA_URL = (
    "https://www.planetcinema.co.il/"
    "cinemas/Rishon_Letziyon/1072"
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
            text = button.inner_text().strip()

            if "13:30" in text:
                return button

        except Exception:
            continue

    return None


def print_page_info(page, name):
    print("\n================================")
    print(name)
    print("URL:")
    print(page.url)

    print("\nTITLE:")
    try:
        print(page.title())
    except Exception:
        pass

    print("\nBODY:")
    try:
        body = page.locator("body").inner_text()
        print(body[:12000])
    except Exception as exc:
        print("BODY ERROR:", exc)

    print("\nIFRAMES:")
    for frame in page.frames:
        print("FRAME:", frame.url)

    print("================================\n")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            locale="he-IL",
            viewport={
                "width": 1440,
                "height": 1200,
            },
        )

        page = context.new_page()

        def log_request(request):
            url = request.url.lower()

            if any(
                word in url
                for word in [
                    "order",
                    "seat",
                    "ticket",
                    "booking",
                    "performance",
                    "session",
                ]
            ):
                print(
                    "REQUEST:",
                    request.method,
                    request.url,
                )

        def log_response(response):
            url = response.url.lower()

            if any(
                word in url
                for word in [
                    "order",
                    "seat",
                    "ticket",
                    "booking",
                    "performance",
                    "session",
                ]
            ):
                print(
                    "RESPONSE:",
                    response.status,
                    response.url,
                )

        context.on("request", log_request)
        context.on("response", log_response)

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
            print("IMAX 13:30 button not found.")
            browser.close()
            return

        print("Found Odyssey IMAX 13:30.")
        print(
            "ORDER DATA URL:",
            target.get_attribute("data-url"),
        )

        # Click the screening ONCE.
        target.click(timeout=5000)

        page.wait_for_timeout(2500)

        print("\nAfter screening click:")
        print(page.url)

        # Planet should now display the login/guest modal.
        guest = page.get_by_text(
            "הזמינו כאורח",
            exact=True,
        )

        if guest.count() == 0:
            print("Guest-order button was not found.")
            print_page_info(
                page,
                "PAGE AFTER SHOWING CLICK",
            )
            browser.close()
            return

        guest_button = None

        for i in range(guest.count()):
            try:
                candidate = guest.nth(i)

                if candidate.is_visible():
                    guest_button = candidate
                    break
            except Exception:
                continue

        if guest_button is None:
            print(
                "Guest-order button exists "
                "but is not visible."
            )
            browser.close()
            return

        print("Guest-order button found.")
        print("Clicking 'הזמינו כאורח'...")

        old_pages = len(context.pages)

        guest_button.click(timeout=5000)

        # Give Planet time to initialize the order.
        page.wait_for_timeout(10000)

        print(
            "Number of pages before:",
            old_pages,
        )
        print(
            "Number of pages after:",
            len(context.pages),
        )

        # Inspect every open page.
        for index, current_page in enumerate(
            context.pages
        ):
            try:
                current_page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=10000,
                )
            except Exception:
                pass

            print_page_info(
                current_page,
                f"OPEN PAGE #{index + 1}",
            )

        browser.close()


if __name__ == "__main__":
    main()
