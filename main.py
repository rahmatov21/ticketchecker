"""
main.py — Entry point for Avtoticket Bus Monitor
Polls configured URLs every POLL_INTERVAL_SECONDS, compares against the
previously seen state, and fires notifications on changes.

Usage:
    BOT_TOKEN=xxx CHAT_ID=yyy python main.py

On a server (24/7):
    nohup python main.py >> monitor.log 2>&1 &
    # or use a systemd service (see README for template)
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    HISTORY_FILE,
    MONITOR_URLS,
    POLL_INTERVAL_SECONDS,
    SUMMARY_INTERVAL_SECONDS,
)
from notifier import notify_new_reys, notify_seat_change, notify_trip_stats, notify_trip_overview
from parser import Reys, fetch_and_parse

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG for troubleshooting
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),        # Console output
        logging.FileHandler("monitor.log", encoding="utf-8"),  # File log
    ],
)
logger = logging.getLogger(__name__)


# ─── State: seen reys per URL ─────────────────────────────────────────────────
# Structure: { url: { unique_id: Reys } }
seen_state: dict[str, dict[str, Reys]] = {}


# ─── Trip Statistics ──────────────────────────────────────────────────────────

def _compute_trip_stats() -> tuple[int, int, int]:
    """
    Compute available, unavailable, and total trip counts from current state.
    
    Returns:
        (available_count, unavailable_count, total_count)
    """
    available = 0
    unavailable = 0
    
    for url_reys in seen_state.values():
        for reys in url_reys.values():
            if reys.seats > 0:
                available += 1
            else:
                unavailable += 1
    
    total = available + unavailable
    return available, unavailable, total


def _print_startup_stats() -> None:
    """Print initial trip statistics when monitor starts."""
    available, unavailable, total = _compute_trip_stats()
    logger.info("=" * 60)
    logger.info("🚌 AVTOTICKET BUS MONITOR — STARTUP REPORT")
    logger.info("=" * 60)
    logger.info(f"✅ Available Trips: {available}")
    logger.info(f"❌ Unavailable Trips: {unavailable}")
    logger.info(f"📋 Total Trips Found: {total}")
    logger.info(f"📡 Monitoring URLs: {len(MONITOR_URLS)}")
    logger.info("=" * 60)


# ─── History JSON Persistence ─────────────────────────────────────────────────

def _load_history() -> dict:
    """
    Load previously saved reys history from HISTORY_FILE.
    Returns an empty dict if the file doesn't exist or is corrupt.
    """
    path = Path(HISTORY_FILE)
    if not path.exists():
        logger.info(f"No history file found at '{HISTORY_FILE}' — starting fresh.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded history from '{HISTORY_FILE}'.")
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not read history file: {e} — starting fresh.")
        return {}


def _save_history(history: dict) -> None:
    """Persist the full reys history to HISTORY_FILE (JSON)."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning(f"Could not write history file: {e}")


def _append_to_history(history: dict, url: str, reys: Reys, event: str) -> None:
    """
    Append a single reys event to the history log.
    Each URL has a list of timestamped events.
    """
    if url not in history:
        history[url] = []
    history[url].append({
        "event": event,                              # "new_reys" | "seat_change"
        "timestamp": datetime.now().isoformat(),
        "data": reys.to_dict(),
    })


# ─── Core Comparison Logic ────────────────────────────────────────────────────

def _process_url(url: str, history: dict) -> None:
    """
    Fetch the page, compare against the last-seen state, and trigger
    notifications for new reys or seat count changes.
    """
    logger.info(f"Checking: {url}")
    current_reys_list: Optional[list[Reys]] = fetch_and_parse(url)

    if current_reys_list is None:
        # Fetch failed entirely — skip this cycle, state is preserved
        logger.warning(f"Skipping comparison for {url} (fetch failed).")
        return

    # Build a dict keyed by unique_id for fast lookup
    current_map: dict[str, Reys] = {r.unique_id: r for r in current_reys_list}

    if url not in seen_state:
        # First successful poll for this URL — initialise state, no notifications
        seen_state[url] = current_map
        logger.info(
            f"Initial snapshot for {url}: {len(current_map)} reys recorded. "
            "Monitoring from next poll…"
        )
        return

    previous_map = seen_state[url]

    # ── Detect NEW reys (IDs present now but not before) ──────────────────
    for uid, reys in current_map.items():
        if uid not in previous_map:
            logger.info(f"🆕 New reys detected: {uid}")
            notify_new_reys(reys)
            _append_to_history(history, url, reys, "new_reys")

    # ── Detect SEAT COUNT CHANGES on existing reys ─────────────────────────
    for uid, reys in current_map.items():
        if uid in previous_map:
            old_seats = previous_map[uid].seats
            if reys.seats != old_seats:
                logger.info(
                    f"💺 Seat change on '{reys.route}' "
                    f"{reys.departure_date} {reys.departure_time}: "
                    f"{old_seats} → {reys.seats}"
                )
                notify_seat_change(reys, old_seats)
                _append_to_history(history, url, reys, "seat_change")

    # ── Update in-memory state to the latest snapshot ─────────────────────
    seen_state[url] = current_map
    _save_history(history)


# ─── Main Loop ────────────────────────────────────────────────────────────────

def run() -> None:
    """
    Main monitoring loop. Polls all configured URLs in sequence,
    sleeps for POLL_INTERVAL_SECONDS, and repeats indefinitely.
    Designed to run 24/7 without crashing on transient errors.
    """
    if not MONITOR_URLS:
        logger.error("No URLs configured in MONITOR_URLS (config.py). Exiting.")
        sys.exit(1)

    logger.info("=" * 55)
    logger.info("  Avtoticket Bus Monitor — Starting up")
    logger.info(f"  Monitoring {len(MONITOR_URLS)} URL(s) every {POLL_INTERVAL_SECONDS}s")
    logger.info(f"  Summary notifications every {SUMMARY_INTERVAL_SECONDS}s")
    logger.info("=" * 55)

    # Load persisted history from disk (survives restarts)
    history = _load_history()

    first_cycle = True
    last_summary_time = time.monotonic() - SUMMARY_INTERVAL_SECONDS
    while True:
        cycle_start = time.monotonic()

        for url in MONITOR_URLS:
            try:
                _process_url(url, history)
            except Exception as e:
                # Catch-all: one URL failing must never kill the loop
                logger.error(
                    f"Unhandled error while processing {url}: {e}",
                    exc_info=True,
                )

        now = time.monotonic()
        should_send_summary = first_cycle or (now - last_summary_time >= SUMMARY_INTERVAL_SECONDS)

        if should_send_summary:
            _print_startup_stats()
            if seen_state:
                notify_trip_overview(seen_state)
            last_summary_time = now
            first_cycle = False

        elapsed = time.monotonic() - cycle_start
        sleep_time = max(0, POLL_INTERVAL_SECONDS - elapsed)

        logger.info(
            f"Cycle complete in {elapsed:.1f}s. "
            f"Next check in {sleep_time:.0f}s…"
        )
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user (KeyboardInterrupt). Goodbye.")
        sys.exit(0)
