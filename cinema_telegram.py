import os
import re
import json
import requests

from pathlib import Path

from cinemacity import (
    search_movies,
    get_theaters,
    get_showings,
)


TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

ALLOWED_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)

API_URL = (
    f"https://api.telegram.org/"
    f"bot{TOKEN}"
)

STATE_FILE = Path(
    "telegram_state.json"
)


def load_last_update_id():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return data.get(
            "last_update_id"
        )

    except Exception:
        return None


def save_last_update_id(
    update_id,
):
    STATE_FILE.write_text(
        json.dumps(
            {
                "last_update_id":
                    update_id
            },
            indent=2,
        ),
        encoding="utf-8",
    )

def telegram_request(
    method,
    payload=None,
):
    response = requests.post(
        f"{API_URL}/{method}",
        json=payload or {},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            data
        )

    return data.get("result")


def send_message(
    chat_id,
    text,
    keyboard=None,
):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    if keyboard:
        payload["reply_markup"] = {
            "inline_keyboard":
                keyboard
        }

    telegram_request(
        "sendMessage",
        payload,
    )


def answer_callback(
    callback_id,
):
    try:
        telegram_request(
            "answerCallbackQuery",
            {
                "callback_query_id":
                    callback_id
            },
        )
    except Exception:
        pass


def is_allowed(chat_id):
    if not ALLOWED_CHAT_ID:
        return True

    return (
        str(chat_id)
        == str(ALLOWED_CHAT_ID)
    )


def date_key(text):
    if not text:
        return None

    match = re.search(
        r"(\d{1,2})/"
        r"(\d{1,2})/"
        r"(\d{4})",
        text,
    )

    if not match:
        return None

    day, month, year = (
        match.groups()
    )

    return (
        f"{year}"
        f"{int(month):02d}"
        f"{int(day):02d}"
    )


def handle_movie_search(
    chat_id,
    query,
):
    matches = search_movies(
        query
    )

    if not matches:
        send_message(
            chat_id,
            "לא מצאתי סרט בשם הזה "
            "ב-Cinema City.\n\n"
            "נסי לכתוב את השם "
            "בצורה מעט שונה.",
        )
        return

    keyboard = []

    for movie in matches[:10]:
        keyboard.append(
            [
                {
                    "text":
                        movie["Name"],

                    "callback_data":
                        f"m:"
                        f"{movie['MovieId']}",
                }
            ]
        )

    send_message(
        chat_id,
        "🎬 מצאתי את הסרטים "
        "הבאים ב-Cinema City.\n"
        "בחרי סרט:",
        keyboard,
    )


def handle_movie_selected(
    chat_id,
    movie_id,
):
    theaters = get_theaters(
        movie_id
    )

    # כרגע מציגים כל בית קולנוע
    # פעם אחת, בלי ליצור כפילות
    # של VIP / ONYX / Prime.
    unique = {}

    for theater in theaters:
        if (
            theater.get(
                "VenueTypeId"
            )
            != 1
        ):
            continue

        theater_id = theater.get(
            "TixTheatreId"
        )

        if not theater_id:
            continue

        unique[
            theater_id
        ] = theater

    if not unique:
        send_message(
            chat_id,
            "לא נמצאו בתי קולנוע "
            "עבור הסרט הזה.",
        )
        return

    keyboard = []

    for theater_id, theater in (
        unique.items()
    ):
        keyboard.append(
            [
                {
                    "text":
                        theater["Name"],

                    "callback_data":
                        (
                            f"t:"
                            f"{movie_id}:"
                            f"{theater_id}"
                        ),
                }
            ]
        )

    send_message(
        chat_id,
        "📍 באיזה בית קולנוע "
        "תרצי לראות את הסרט?",
        keyboard,
    )


def handle_theater_selected(
    chat_id,
    movie_id,
    theater_id,
):
    showings = get_showings(
        movie_id,
        theater_id,
    )

    if not showings:
        send_message(
            chat_id,
            "לא מצאתי הקרנות "
            "זמינות כרגע.",
        )
        return

    dates = {}

    for showing in showings:
        key = date_key(
            showing.get(
                "date"
            )
        )

        if not key:
            continue

        if key not in dates:
            dates[key] = (
                showing["date"]
            )

    keyboard = []

    for key, label in dates.items():
        keyboard.append(
            [
                {
                    "text": label,
                    "callback_data":
                        (
                            f"d:"
                            f"{movie_id}:"
                            f"{theater_id}:"
                            f"{key}"
                        ),
                }
            ]
        )

    send_message(
        chat_id,
        "📅 בחרי תאריך:",
        keyboard,
    )


def handle_date_selected(
    chat_id,
    movie_id,
    theater_id,
    selected_date,
):
    showings = get_showings(
        movie_id,
        theater_id,
    )

    selected = [
        showing
        for showing in showings
        if (
            date_key(
                showing.get(
                    "date"
                )
            )
            == selected_date
        )
    ]

    if not selected:
        send_message(
            chat_id,
            "לא מצאתי הקרנות "
            "בתאריך הזה.",
        )
        return

    keyboard = []

    for showing in selected:
        keyboard.append(
            [
                {
                    "text":
                        f"🕐 "
                        f"{showing['time']}",

                    "url":
                        showing["url"],
                }
            ]
        )

    send_message(
        chat_id,
        "🎟️ אלו שעות ההקרנה.\n"
        "לחיצה על שעה תפתח "
        "את ההזמנה:",
        keyboard,
    )


def handle_message(
    message,
):
    chat = message.get(
        "chat",
        {},
    )

    chat_id = chat.get("id")

    if not chat_id:
        return

    if not is_allowed(
        chat_id
    ):
        return

    text = (
        message
        .get(
            "text",
            "",
        )
        .strip()
    )

    if not text:
        return

    if text == "/start":
        send_message(
            chat_id,
            "🎬 בוט הקולנוע פעיל!\n\n"
            "כתבי לי שם של סרט "
            "ואחפש אותו עבורך.\n\n"
            "כרגע החיפוש מחובר "
            "ל-Cinema City.",
        )

        return

    handle_movie_search(
        chat_id,
        text,
    )


def handle_callback(
    callback,
):
    callback_id = callback.get(
        "id"
    )

    answer_callback(
        callback_id
    )

    message = callback.get(
        "message",
        {},
    )

    chat_id = (
        message
        .get(
            "chat",
            {},
        )
        .get("id")
    )

    if not chat_id:
        return

    if not is_allowed(
        chat_id
    ):
        return

    data = callback.get(
        "data",
        "",
    )

    parts = data.split(":")

    if not parts:
        return

    if (
        parts[0] == "m"
        and len(parts) == 2
    ):
        handle_movie_selected(
            chat_id,
            int(parts[1]),
        )

    elif (
        parts[0] == "t"
        and len(parts) == 3
    ):
        handle_theater_selected(
            chat_id,
            int(parts[1]),
            int(parts[2]),
        )

    elif (
        parts[0] == "d"
        and len(parts) == 4
    ):
        handle_date_selected(
            chat_id,
            int(parts[1]),
            int(parts[2]),
            parts[3],
        )


def get_updates(
    last_update_id=None,
):
    params = {
        "timeout": 0,
        "limit": 100,
    }

    if last_update_id is not None:
        params["offset"] = (
            last_update_id + 1
        )

    response = requests.get(
        f"{API_URL}/getUpdates",
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "result",
        []
    )


def confirm_updates(
    last_update_id,
):
    requests.get(
        f"{API_URL}/getUpdates",
        params={
            "offset":
                last_update_id + 1,

            "timeout": 0,
        },
        timeout=30,
    ).raise_for_status()


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN "
            "is missing."
        )

    last_processed = (
        load_last_update_id()
    )

    print(
        "Last processed update:",
        last_processed,
    )

    updates = get_updates(
        last_processed
    )

    print(
        "Updates received:",
        len(updates),
    )

    for update in updates:
        update_id = update.get(
            "update_id"
        )

        if update_id is None:
            continue

        if (
            last_processed
            is not None
            and update_id
            <= last_processed
        ):
            print(
                "Skipping old update:",
                update_id,
            )
            continue

        try:
            if "message" in update:
                handle_message(
                    update["message"]
                )

            elif (
                "callback_query"
                in update
            ):
                handle_callback(
                    update[
                        "callback_query"
                    ]
                )

            save_last_update_id(
                update_id
            )

            last_processed = (
                update_id
            )

            confirm_updates(
                update_id
            )

            print(
                "Processed update:",
                update_id,
            )

        except Exception as exc:
            print(
                "Update error:",
                exc,
            )

            # לא ממשיכים הלאה,
            # כדי שלא נאבד update
            # שנכשל באמצע.
            break

    print(
        "Telegram check completed."
    )
