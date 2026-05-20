"""
commands.py — Telegram command handler for Avtoticket Bus Monitor
Handles incoming Telegram commands like /start

To enable webhook:
  1. Run: python webhook.py
  2. Expose via ngrok: ngrok http 8080
  3. Set webhook: python -c "from commands import set_webhook; set_webhook('https://your-ngrok-url.ngrok.io')"
"""

import logging
import requests
from typing import Optional

from config import BOT_TOKEN, MONITOR_URLS
from notifier import notify_trip_stats

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def set_webhook(webhook_url: str) -> bool:
    """Set the Telegram webhook URL."""
    url = f"{TELEGRAM_API_URL}/setWebhook"
    payload = {"url": webhook_url}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if data.get("ok"):
            logger.info(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            logger.error(f"❌ Webhook error: {data.get('description')}")
            return False
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return False


def handle_command(message: dict) -> Optional[str]:
    """
    Handle incoming Telegram command.
    
    Args:
        message: Update object from Telegram API
        
    Returns:
        Response text or None
    """
    if "text" not in message:
        return None
    
    text = message["text"]
    chat_id = message["chat"]["id"]
    
    logger.info(f"Command from {chat_id}: {text}")
    
    if text == "/start":
        # Send trip stats - note: this will use current seen_state from main.py
        # We'll handle this differently
        return "🚌 Avtoticket Bus Monitor started!\n\nUse /status to see current trip count."
    
    elif text == "/status":
        return "📊 Status: Monitoring active. Send /stats for trip count."
    
    elif text == "/help":
        return (
            "🚌 *Avtoticket Bus Monitor*\n\n"
            "Available commands:\n"
            "/start - Show welcome message\n"
            "/status - Show monitor status\n"
            "/help - Show this help message"
        )
    
    return None
