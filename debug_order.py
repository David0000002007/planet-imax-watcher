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

        # Print useful network activity.
        page.on(
            "request",
            lambda request: (
                print(
                    "REQUEST:",
                    request.method,
                    request.url,
                )
                if (
                    "order" in request.url.lower()
                    or "ticket" in request.url.lower()
                    or "seat" in request.url.lower()
                )
                else None
            ),
        )

        page.on(
            "response",
            lambda response: (
                print(
                    "RESPONSE:",
                    response.status,
                    response.url,
                )
                if (
                    "order" in response.url.lower()
                    or "ticket" in response.url.lower()
                    or "seat" in response.url.lower()
                )
                else None
            ),
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

        print("Current URL before click:")
        print(page.url)

        # Find the exact Odyssey IMAX 13:30 button.
        buttons = page.locator(
            'a[data-url][data-attrs*="imax"]'
        )

        target = None

        for i in range(buttons.count()):
            button = buttons.nth(i)

            try:
                text = button.inner_text().strip()

                if "13:30" in text:
                    target = button
                    break
            except Exception:
                continue

        if target is None:
            print("IMAX 13:30 button not found.")
            browser.close()
            return

        print("Found target button.")
        print(
            "data-url:",
            target.get_attribute("data-url"),
        )

        print("Clicking IMAX 13:30...")

        # The site may open a new tab/window.
        try:
            with context.expect_page(timeout=5000) as popup_info:
                target.click()

            order_page = popup_info.value
            order_page.wait_for_load_state(
                "domcontentloaded",
                timeout=30000,
            )

            print("NEW PAGE OPENED")

        except Exception:
            # If no popup was created, continue with current page.
            try:
                target.click(timeout=5000)
            except Exception:
                pass

            order_page = page

        order_page.wait_for_timeout(8000)

        print("\n==============================")
        print("FINAL URL:")
        print(order_page.url)

        print("\nTITLE:")
        print(order_page.title())

        print("\nBODY TEXT:")
        try:
            body = order_page.locator("body").inner_text()
            print(body[:8000])
        except Exception as exc:
            print("Could not read body:", exc)

        print("\nIFRAMES:")
        for frame in order_page.frames:
            print("FRAME:", frame.url)

        print("==============================")

        browser.close()


if __name__ == "__main__":
    main()
