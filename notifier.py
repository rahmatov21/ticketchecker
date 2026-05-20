"""
notifier.py — Notification dispatcher for Avtoticket Bus Monitor
Handles both terminal (console) and Telegram notifications.
"""

import logging
import platform
import subprocess
from typing import Optional

import requests

from config import BOT_TOKEN, CHAT_ID, REQUEST_TIMEOUT_SECONDS
from parser import Reys

logger = logging.getLogger(__name__)

# Telegram Bot API endpoint
TELEGRAM_API_URL = f"https://api.telegram.org/bot{{token}}/sendMessage"


# ─── Public Notification Entrypoints ─────────────────────────────────────────

def notify_new_reys(reys: Reys) -> None:
    """Dispatch notifications for a newly discovered reys."""
    message = _build_new_reys_message(reys)
    _log_to_terminal(message, level="NEW")
    _send_terminal_alert(f"New reys: {reys.route} @ {reys.departure_time}")
    _send_telegram(message)


def notify_seat_change(reys: Reys, old_seats: int) -> None:
    """Dispatch notifications for a seat count change on an existing reys."""
    message = _build_seat_change_message(reys, old_seats)
    _log_to_terminal(message, level="CHANGE")
    _send_terminal_alert(f"Seats changed: {reys.route} — {old_seats} → {reys.seats}")
    _send_telegram(message)


def notify_trip_stats(available_count: int, unavailable_count: int, total_count: int, urls: list[str]) -> None:
    """Send monitoring stats (used for /start command)."""
    message = _build_stats_message(available_count, unavailable_count, total_count, urls)
    _log_to_terminal(message, level="STATS")
    _send_telegram(message)


def notify_trip_overview(url_trip_map: dict[str, dict[str, Reys]]) -> None:
    """Send a current trip overview message with seat availability and times."""
    message = _build_overview_message(url_trip_map)
    _log_to_terminal(message, level="OVERVIEW")
    _send_telegram(message)


# ─── Message Builders ─────────────────────────────────────────────────────────

def _build_new_reys_message(reys: Reys) -> str:
    return (
        "🚨 *NEW REYS FOUND*\n"
        f"🛣 *Route:* {reys.route}\n"
        f"🕒 *Departure:* {reys.departure_time}\n"
        f"📅 *Date:* {reys.departure_date}\n"
        f"🛬 *Arrival:* {reys.arrival_time} / {reys.arrival_date}\n"
        f"💺 *Seats:* {reys.seats}\n"
        f"💰 *Price:* {reys.price} UZS\n"
        f"🚌 *Bus:* {reys.bus_type}"
    )


def _build_seat_change_message(reys: Reys, old_seats: int) -> str:
    direction = "📈" if reys.seats > old_seats else "📉"
    return (
        f"⚠️ *SEAT COUNT CHANGED* {direction}\n"
        f"🛣 *Route:* {reys.route}\n"
        f"🕒 *Departure:* {reys.departure_time} / {reys.departure_date}\n"
        f"💺 *Seats:* {old_seats} → {reys.seats}\n"
        f"🚌 *Bus:* {reys.bus_type}"
    )


def _build_stats_message(available_count: int, unavailable_count: int, total_count: int, urls: list[str]) -> str:
    urls_list = "\n".join([f"  • {url}" for url in urls])
    return (
        f"📊 *MONITOR STATUS*\n"
        f"✅ *Available Trips:* {available_count}\n"
        f"❌ *Unavailable Trips:* {unavailable_count}\n"
        f"📋 *Total Trips:* {total_count}\n"
        f"\n🔗 *Monitoring URLs:*\n{urls_list}\n"
        f"\nMonitoring active. Checking every 60 seconds."
    )


def _build_overview_message(url_trip_map: dict[str, dict[str, Reys]]) -> str:
    available = 0
    unavailable = 0
    lines: list[str] = [
        "🚌 *CURRENT TRIP OVERVIEW*",
    ]

    for url, trips in url_trip_map.items():
        lines.append(f"\n🔗 *URL:* {url}")
        if not trips:
            lines.append("  • No trips found yet")
            continue

        sorted_trips = sorted(
            trips.values(),
            key=lambda r: (r.departure_date, r.departure_time),
        )

        for reys in sorted_trips:
            status = "available" if reys.seats > 0 else "unavailable"
            if reys.seats > 0:
                available += 1
            else:
                unavailable += 1
            lines.append(
                f"  • {reys.departure_time} {reys.departure_date} — {reys.seats} seats ({status}) — {reys.route}"
            )

    total = available + unavailable
    lines.insert(
        1,
        f"✅ Available: {available} — ❌ Unavailable: {unavailable} — 📋 Total: {total}",
    )

    lines.append("\nMonitoring updates every 5 minutes.")
    return "\n".join(lines)


# ─── Terminal Logging ─────────────────────────────────────────────────────────

def _log_to_terminal(message: str, level: str = "INFO") -> None:
    """Print a clearly formatted alert block to the console."""
    border = "=" * 55
    # Strip Markdown formatting for plain terminal output
    plain = (
        message
        .replace("*", "")
        .replace("_", "")
        .replace("`", "")
    )
    print(f"\n{border}")
    print(f"  [{level}]")
    print(border)
    print(plain)
    print(f"{border}\n")


# ─── OS Desktop Notification ──────────────────────────────────────────────────

def _send_terminal_alert(summary: str) -> None:
    """
    Send a native desktop notification (best-effort, non-blocking).
    Supports: Linux (notify-send), macOS (osascript), Windows (PowerShell toast).
    Silently skips if the tool isn't available (e.g. on a headless server).
    """
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.Popen(
                ["notify-send", "🚌 Avtoticket Monitor", summary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Darwin":
            script = f'display notification "{summary}" with title "Avtoticket Monitor"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            ps_cmd = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                f"$template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('Avtoticket Monitor')) | Out-Null;"
                f"$template.GetElementsByTagName('text')[1].AppendChild($template.CreateTextNode('{summary}')) | Out-Null;"
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Avtoticket').Show([Windows.UI.Notifications.ToastNotification]::new($template))"
            )
            subprocess.Popen(
                ["powershell", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except FileNotFoundError:
        logger.debug("Desktop notification tool not found — skipping OS alert")
    except Exception as e:
        logger.debug(f"Desktop notification failed (non-critical): {e}")


# ─── Telegram Sender ──────────────────────────────────────────────────────────

def _send_telegram(message: str) -> None:
    """
    Post a message to Telegram via the Bot API.
    Markdown formatting (V1) is used for bold/italic text.
    Skips silently if BOT_TOKEN or CHAT_ID are not configured.
    """
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram not configured (BOT_TOKEN / CHAT_ID missing). Skipping.")
        return

    url = TELEGRAM_API_URL.format(token=BOT_TOKEN)
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            logger.info("Telegram notification sent successfully.")
        else:
            logger.warning(f"Telegram API returned not-ok: {data}")
    except requests.exceptions.Timeout:
        logger.warning("Telegram request timed out.")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Telegram HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Telegram request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram message: {e}")
