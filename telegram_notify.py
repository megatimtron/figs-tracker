"""Thin wrapper around Telegram's sendMessage API."""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] token or chat_id missing — skipping send")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.ok
    except requests.RequestException as e:
        print(f"[telegram] send failed: {e}")
        return False
