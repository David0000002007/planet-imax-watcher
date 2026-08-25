import json
from playwright.sync_api import sync_playwright


BASE_URL = "https://www.cinema-city.co.il"

# רק טקסט בדיקה.
# בהמשך זה יגיע ישירות מהודעת Telegram.
MOVIE_QUERY = "האודיסאה"


def normalize(text):
    if not text:
        return ""

    return (
        str(text)
        .strip()
        .lower()
        .replace('"', "")
        .replace("'", "")
        .replace("-", " ")
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="he-IL"
        )

        print("=" * 70)
        print("MOVIES API")
        print("=" * 70)

        response = context.request.get(
            f"{BASE_URL}/tickets/Movies"
        )

        print(
            "HTTP:",
            response.status,
        )

        print(
            "Content-Type:",
            response.headers.get(
                "content-type"
            ),
        )

        try:
            movies = response.json()

        except Exception:
            print(
                "Response was not JSON:"
            )

            print(
                response.text()[:3000]
            )

            browser.close()
            return

        print(
            "Result type:",
            type(movies).__name__,
        )

        if isinstance(movies, list):
            print(
                "Movie count:",
                len(movies),
            )

        print("\n")
        print("=" * 70)
        print("SAMPLE MOVIES")
        print("=" * 70)

        if isinstance(movies, list):
            for movie in movies[:10]:
                print(
                    json.dumps(
                        movie,
                        ensure_ascii=False,
                        indent=2,
                    )
                )

        print("\n")
        print("=" * 70)
        print("SEARCH RESULT")
        print("=" * 70)

        query = normalize(
            MOVIE_QUERY
        )

        matches = []

        if isinstance(movies, list):
            for movie in movies:
                # אנחנו עדיין לא יודעים
                # בדיוק איך Cinema City
                # קורא לשדה שם הסרט,
                # אז מחפשים בכל הערכים
                # הטקסטואליים.
                searchable = " ".join(
                    normalize(value)
                    for value
                    in movie.values()
                    if isinstance(
                        value,
                        (
                            str,
                            int,
                            float,
                        ),
                    )
                )

                if query in searchable:
                    matches.append(movie)

        print(
            "Query:",
            MOVIE_QUERY,
        )

        print(
            "Matches:",
            len(matches),
        )

        for movie in matches[:20]:
            print("\nMATCH:")

            print(
                json.dumps(
                    movie,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        print("\n")
        print("=" * 70)
        print("DONE")
        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    main()
