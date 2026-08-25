from cinemacity import (
    search_movies,
    get_theaters,
    get_showings,
)


MOVIE_NAME = "האודיסאה"


def main():
    print("=" * 70)
    print("SEARCH MOVIE BY NAME")
    print("=" * 70)

    matches = search_movies(
        MOVIE_NAME
    )

    print(
        "Search:",
        MOVIE_NAME
    )

    print(
        "Matches:",
        len(matches)
    )

    if not matches:
        print(
            "Movie not found."
        )
        return

    for movie in matches:
        print(
            movie["Name"],
            "| MovieId:",
            movie["MovieId"],
        )

    # ההתאמה המדויקת אמורה
    # להיות הראשונה.
    movie = matches[0]

    movie_id = movie["MovieId"]

    print("\n")
    print("=" * 70)
    print("SELECTED MOVIE")
    print("=" * 70)

    print(
        movie["Name"],
        "| MovieId:",
        movie_id,
    )

    print("\n")
    print("=" * 70)
    print("THEATERS")
    print("=" * 70)

    theaters = get_theaters(
        movie_id
    )

    # לבדיקה כרגע מציגים
    # את בתי הקולנוע הרגילים.
    base_theaters = [
        theater
        for theater in theaters
        if theater.get(
            "VenueTypeId"
        ) == 1
    ]

    print(
        "Theaters:",
        len(base_theaters)
    )

    for theater in base_theaters:
        print(
            "\n",
            theater["Name"],
            "|",
            theater["TixTheatreId"],
        )

        showings = get_showings(
            movie_id,
            theater[
                "TixTheatreId"
            ],
        )

        print(
            "Showings:",
            len(showings)
        )

        # רק שלוש הקרנות ראשונות
        # כדי שהפלט לא יהיה ענק.
        for showing in showings[:3]:
            print(
                showing["date"],
                "|",
                showing["time"],
            )

            print(
                showing["url"]
            )

    print("\n")
    print("=" * 70)
    print("SUCCESS")
    print("=" * 70)

    print(
        "Cinema City module "
        "works dynamically."
    )


if __name__ == "__main__":
    main()
