"""
config.py — Central configuration for Avtoticket Bus Monitor
All settings, environment variables, and constants are defined here.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Telegram Bot Credentials ─────────────────────────────────────────────────
# These are loaded from the .env file. Update .env with your credentials:
#   BOT_TOKEN=your_bot_token_here
#   CHAT_ID=your_chat_id_here
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
CHAT_ID: str = os.getenv("CHAT_ID", "")

# ─── Monitoring Targets ────────────────────────────────────────────────────────
# Add as many URLs as needed. Each will be polled independently.
MONITOR_URLS: list[str] = [
    "https://avtoticket.uz/trips/1726/1722401/2026-05-25",
    "https://avtoticket.uz/trips/1726/1722401/2026-05-28", 
]

# ─── Polling Settings ──────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS: int = 60          # How often to check each URL
SUMMARY_INTERVAL_SECONDS: int = 300      # How often to send summary notifications
REQUEST_TIMEOUT_SECONDS: int = 15        # Max wait for HTTP response
MAX_RETRIES: int = 3                     # Retry attempts on network failure
RETRY_DELAY_SECONDS: int = 10           # Wait between retries

# ─── History Persistence ──────────────────────────────────────────────────────
HISTORY_FILE: str = "history.json"       # JSON file to persist reys history

# ─── HTTP Request Headers ─────────────────────────────────────────────────────
# Mimic a real browser to avoid bot-detection blocks
REQUEST_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}
