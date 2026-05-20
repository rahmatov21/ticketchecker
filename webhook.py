"""
webhook.py — Flask webhook server for Telegram commands
Run this alongside main.py to handle /start and other commands.

Usage:
  1. Run: python webhook.py
  2. Set webhook via: python -c "from commands import set_webhook; set_webhook('https://your-url')"
"""

import logging
import json
import requests
from flask import Flask, request, jsonify

from config import BOT_TOKEN, CHAT_ID
from commands import handle_command
from notifier import _send_telegram

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Expected webhook token for security (add to config if needed)
WEBHOOK_SECRET = "avtoticket_webhook_secret"


@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def handle_update():
    """Handle Telegram webhook update."""
    try:
        update = request.get_json()
        
        # Extract message
        if "message" not in update:
            return jsonify({"ok": True})
        
        message = update["message"]
        chat_id = message.get("chat", {}).get("id")
        
        # Handle command
        response = handle_command(message)
        if response:
            _send_telegram_reply(chat_id, response)
        
        return jsonify({"ok": True})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


def _send_telegram_reply(chat_id: int, text: str) -> None:
    """Send a reply to a specific chat."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send reply: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting webhook server on port 8080...")
    logger.info(f"Webhook URL: http://localhost:8080/webhook/{WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=8080, debug=False)
