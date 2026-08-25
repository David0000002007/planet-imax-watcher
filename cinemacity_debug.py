from playwright.sync_api import sync_playwright


MOVIE_URL = (
    "https://www.cinema-city.co.il/movie/6031"
)


KEYWORDS = [
    "api",
    "movie",
    "cinema",
    "show",
    "screen",
    "schedule",
    "performance",
    "booking",
    "ticket",
]


def interesting_url(url):
    lower = url.lower()

    return any(
        word in lower
        for word in KEYWORDS
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

        def on_response(response):
            try:
                if interesting_url(
                    response.url
                ):
                    print(
                        "RESPONSE",
                        response.status,
                        response.url,
                    )
            except Exception:
                pass

        page.on(
            "response",
            on_response,
        )

        print(
            "Opening Cinema City movie page..."
        )

        page.goto(
            MOVIE_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        page.wait_for_timeout(8000)

        print("\n")
        print("=" * 70)
        print("FINAL URL")
        print("=" * 70)

        print(page.url)

        print("\n")
        print("=" * 70)
        print("PAGE TEXT")
        print("=" * 70)

        try:
            body = page.locator(
                "body"
            ).inner_text()

            print(body[:6000])

        except Exception as exc:
            print(
                "Could not read body:",
                exc,
            )

        print("\n")
        print("=" * 70)
        print("SELECT ELEMENTS")
        print("=" * 70)

        selects = page.locator("select")

        print(
            "Select count:",
            selects.count(),
        )

        for i in range(
            selects.count()
        ):
            try:
                select = selects.nth(i)

                print(
                    f"\nSELECT {i}"
                )

                print(
                    "name:",
                    select.get_attribute(
                        "name"
                    ),
                )

                print(
                    "id:",
                    select.get_attribute(
                        "id"
                    ),
                )

                options = (
                    select
                    .locator("option")
                )

                for j in range(
                    min(
                        options.count(),
                        30,
                    )
                ):
                    option = options.nth(j)

                    print(
                        "OPTION:",
                        repr(
                            option.inner_text()
                        ),
                        "VALUE:",
                        repr(
                            option.get_attribute(
                                "value"
                            )
                        ),
                    )

            except Exception as exc:
                print(
                    "Select error:",
                    exc,
                )

        print("\n")
        print("=" * 70)
        print("BUTTONS")
        print("=" * 70)

        buttons = page.locator(
            "button"
        )

        for i in range(
            min(
                buttons.count(),
                80,
            )
        ):
            try:
                button = buttons.nth(i)

                text = (
                    button.inner_text()
                    .strip()
                )

                if text:
                    print(
                        f"BUTTON {i}:",
                        repr(text),
                    )

            except Exception:
                pass

        print("\n")
        print("=" * 70)
        print("LINKS")
        print("=" * 70)

        links = page.locator("a")

        shown = 0

        for i in range(
            links.count()
        ):
            if shown >= 100:
                break

            try:
                link = links.nth(i)

                text = (
                    link.inner_text()
                    .strip()
                )

                href = (
                    link.get_attribute(
                        "href"
                    )
                )

                combined = (
                    f"{text} {href}"
                    .lower()
                )

                if (
                    text
                    and (
                        "הזמ" in text
                        or "כרטיס" in text
                        or "שעה" in text
                        or "תאריך" in text
                        or interesting_url(
                            combined
                        )
                    )
                ):
                    print(
                        "LINK:",
                        repr(text),
                        "HREF:",
                        repr(href),
                    )

                    shown += 1

            except Exception:
                pass

        print("\n")
        print("=" * 70)
        print("DONE")
        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    main()
