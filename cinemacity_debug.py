import json
from playwright.sync_api import sync_playwright


BASE_URL = "https://www.cinema-city.co.il"

# האודיסאה משמשת רק כסרט בדיקה
MOVIE_ID = 6031


def pretty(value):
    print(
        json.dumps(
            value,
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
            locale="he-IL"
        )

        print("=" * 70)
        print("GET THEATERS")
        print("=" * 70)

        theaters_response = (
            context.request.get(
                f"{BASE_URL}/tickets/Theaters",
                params={
                    "MovieId": MOVIE_ID
                },
            )
        )

        theaters = (
            theaters_response.json()
        )

        # כרגע נבדוק רק בתי קולנוע רגילים,
        # בלי VIP / Prime / ONYX.
        base_theaters = [
            theater
            for theater in theaters
            if theater.get(
                "VenueTypeId"
            ) == 1
        ]

        for theater in base_theaters:
            print(
                theater["Name"],
                "| Id:",
                theater["Id"],
                "| TixTheatreId:",
                theater["TixTheatreId"],
            )

        print("\n")
        print("=" * 70)
        print("TEST EVENTS")
        print("=" * 70)

        successful = []

        for theater in base_theaters:
            name = theater["Name"]

            print("\n")
            print("-" * 70)
            print(name)
            print("-" * 70)

            # Cinema City משתמש בכמה סוגי IDs.
            # נבדוק את שניהם בלי לנחש.
            candidates = [
                (
                    "TixTheatreId",
                    theater["TixTheatreId"],
                ),
                (
                    "Id",
                    theater["Id"],
                ),
            ]

            found = False

            for id_type, theater_id in candidates:
                try:
                    response = (
                        context.request.get(
                            f"{BASE_URL}/tickets/Events",
                            params={
                                "TheatreId":
                                    theater_id,
                                "MovieId":
                                    MOVIE_ID,
                            },
                        )
                    )

                    print(
                        f"{id_type}={theater_id}"
                    )

                    print(
                        "HTTP:",
                        response.status,
                    )

                    try:
                        data = response.json()
                    except Exception:
                        text = response.text()

                        print(
                            "Not JSON:"
                        )

                        print(
                            text[:500]
                        )

                        continue

                    if isinstance(
                        data,
                        list,
                    ):
                        print(
                            "Result length:",
                            len(data),
                        )
                    else:
                        print(
                            "Result type:",
                            type(data).__name__,
                        )

                    if data:
                        print(
                            "SUCCESS - DATA FOUND"
                        )

                        pretty(data)

                        successful.append(
                            {
                                "theater":
                                    name,
                                "id_type":
                                    id_type,
                                "theater_id":
                                    theater_id,
                                "data":
                                    data,
                            }
                        )

                        found = True
                        break

                except Exception as exc:
                    print(
                        "Request error:",
                        exc,
                    )

            if not found:
                print(
                    "No events returned."
                )

        print("\n\n")
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)

        print(
            "Theaters with events:",
            len(successful),
        )

        for item in successful:
            print(
                item["theater"],
                "|",
                item["id_type"],
                "=",
                item["theater_id"],
            )

        browser.close()


if __name__ == "__main__":
    main()
