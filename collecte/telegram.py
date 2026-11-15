"""Envoi des alertes sur Telegram (bot personnel)."""
from __future__ import annotations

import os
import requests


def envoyer(message: str) -> bool:
    jeton, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not jeton or not chat:
        print("[telegram] non configuré, message :\n" + message)
        return False
    r = requests.post(f"https://api.telegram.org/bot{jeton}/sendMessage",
                      json={"chat_id": chat, "text": message, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=30)
    if r.status_code >= 400:
        print(f"[telegram] échec {r.status_code} : {r.text[:200]}")
        return False
    return True
