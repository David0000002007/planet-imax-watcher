import requests


BASE_URL = "https://www.cinema-city.co.il"


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
        .replace("–", " ")
    )


def get_movies():
    response = requests.get(
        f"{BASE_URL}/tickets/Movies",
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def search_movies(query):
    movies = get_movies()

    normalized_query = normalize(
        query
    )

    exact_matches = []
    partial_matches = []

    for movie in movies:
        name = movie.get(
            "Name",
            "",
        )

        normalized_name = normalize(
            name
        )

        if (
            normalized_name
            == normalized_query
        ):
            exact_matches.append(
                movie
            )

        elif (
            normalized_query
            in normalized_name
        ):
            partial_matches.append(
                movie
            )

    # התאמה מדויקת תמיד ראשונה
    if exact_matches:
        return (
            exact_matches
            + partial_matches
        )

    return partial_matches


def get_theaters(movie_id):
    response = requests.get(
        f"{BASE_URL}/tickets/Theaters",
        params={
            "MovieId": movie_id
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_showings(
    movie_id,
    theater_id,
):
    response = requests.get(
        f"{BASE_URL}/tickets/Events",
        params={
            "TheatreId": theater_id,
            "MovieId": movie_id,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    showings = []

    for movie_data in data:
        for event in movie_data.get(
            "Dates",
            [],
        ):
            event_id = event.get(
                "EventId"
            )

            tix_theater_id = (
                event.get(
                    "TheaterId"
                )
            )

            if (
                not event_id
                or not tix_theater_id
            ):
                continue

            showings.append(
                {
                    "date":
                        event.get(
                            "Day"
                        ),

                    "time":
                        event.get(
                            "Hour"
                        ),

                    "event_id":
                        event_id,

                    "theater_id":
                        tix_theater_id,

                    "url": (
                        f"{BASE_URL}/order/"
                        f"?eventID={event_id}"
                        f"&theaterId="
                        f"{tix_theater_id}"
                    ),
                }
            )

    return showings
