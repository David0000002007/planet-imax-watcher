from flask import Flask, request

from cinema_telegram import (
    handle_message,
    handle_callback,
)


app = Flask(__name__)


@app.get("/api")
def health():
    return {
        "status": "ok",
        "service": "cinema-telegram-bot",
    }


@app.post("/api/telegram")
def telegram_webhook():
    update = request.get_json(
        silent=True
    ) or {}

    try:
        if "message" in update:
            handle_message(
                update["message"]
            )

        elif "callback_query" in update:
            handle_callback(
                update["callback_query"]
            )

    except Exception as exc:
        print(
            "Webhook error:",
            exc,
        )

        return {
            "ok": False
        }, 500

    return {
        "ok": True
    }
