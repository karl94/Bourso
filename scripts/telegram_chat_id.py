"""Affiche l'identifiant de votre conversation avec le bot.
1. Envoyez « bonjour » à votre bot sur Telegram.
2. Lancez : TELEGRAM_TOKEN=xxx python scripts/telegram_chat_id.py
"""
import os, requests
r = requests.get(f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/getUpdates", timeout=30).json()
ids = {u["message"]["chat"]["id"] for u in r.get("result", []) if "message" in u}
print("TELEGRAM_CHAT_ID =", ", ".join(map(str, ids)) or "aucun message reçu : écrivez d'abord au bot")
