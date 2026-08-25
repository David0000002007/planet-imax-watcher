import re
from playwright.sync_api import sync_playwright


MOVIE_ID = 6031

BASE_URL = (
    "https://www.cinema-city.co.il"
)

MOVIE_URL = (
    f"{BASE_URL}/movie/{MOVIE_ID}"
)

THEATERS_URL = (
    f"{BASE_URL}/tickets/"
    f"Theaters?MovieId={MOVIE_ID}"
)

JS_URL = (
    f"{BASE_URL}/js/"
    "ticketsNew2.js?c=2"
)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="he-IL"
        )

        page = context.new_page()

        print(
            "Opening movie page..."
        )

        page.goto(
            MOVIE_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        page.wait_for_timeout(3000)

        print("\n")
        print("=" * 70)
        print("THEATERS RESPONSE")
        print("=" * 70)

        theaters_response = (
            context.request.get(
                THEATERS_URL
            )
        )

        print(
            "Status:",
            theaters_response.status,
        )

        print(
            "Content-Type:",
            theaters_response.headers.get(
                "content-type"
            ),
        )

        theaters_text = (
            theaters_response.text()
        )

        print(theaters_text[:12000])

        print("\n")
        print("=" * 70)
        print("TICKET API ENDPOINTS IN JS")
        print("=" * 70)

        js_response = (
            context.request.get(
                JS_URL
            )
        )

        print(
            "JS status:",
            js_response.status,
        )

        js_text = (
            js_response.text()
        )

        patterns = [
            r'["\']([^"\']*'
            r'/tickets/'
            r'[^"\']*)["\']',

            r'url\s*:\s*'
            r'["\']([^"\']+)["\']',
        ]

        found = set()

        for pattern in patterns:
            for match in re.findall(
                pattern,
                js_text,
                re.IGNORECASE,
            ):
                if isinstance(
                    match,
                    tuple,
                ):
                    match = match[0]

                if (
                    "ticket" in
                    match.lower()
                ):
                    found.add(match)

        print(
            "\nPossible endpoints:"
        )

        for item in sorted(found):
            print(item)

        print("\n")
        print("=" * 70)
        print("JS SNIPPETS")
        print("=" * 70)

        lower = js_text.lower()

        keywords = [
            "theaters",
            "dates",
            "shows",
            "hours",
            "movieid",
            "theaterid",
        ]

        printed = set()

        for keyword in keywords:
            start = 0

            while True:
                pos = lower.find(
                    keyword,
                    start,
                )

                if pos == -1:
                    break

                snippet = js_text[
                    max(0, pos - 300):
                    min(
                        len(js_text),
                        pos + 500,
                    )
                ]

                if snippet not in printed:
                    print("\n---")
                    print(
                        snippet.replace(
                            "\n",
                            " "
                        )
                    )

                    printed.add(
                        snippet
                    )

                start = pos + len(
                    keyword
                )

                if len(printed) >= 30:
                    break

            if len(printed) >= 30:
                break

        print("\n")
        print("=" * 70)
        print("DONE")
        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    main()
