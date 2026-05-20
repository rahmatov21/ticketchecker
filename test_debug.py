"""
test_debug.py — Debug script to test parser and Telegram
"""

import logging
from bs4 import BeautifulSoup
from parser import fetch_and_parse, _extract_reys, Reys
from notifier import _send_telegram
from config import BOT_TOKEN, CHAT_ID, MONITOR_URLS

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test 1: Test with actual HTML from user
print("\n" + "=" * 70)
print("TEST 1: Parse HTML with nested <div>/<p> structure")
print("=" * 70)

html_sample = """
<table>
<tbody>
<tr data-v-0bbd401f="" class="bg_white">
    <td data-v-0bbd401f="">
        <div data-v-0bbd401f="" class="div_intd">
            <p data-v-0bbd401f="" class="div_intd_p">15:30</p>
            <p data-v-0bbd401f="" class="div_intd_p">2026-05-25</p>
        </div>
    </td>
    <td data-v-0bbd401f="">
        <div data-v-0bbd401f="" class="div_intd">
            <p data-v-0bbd401f="" class="div_intd_p">03:30</p>
            <p data-v-0bbd401f="" class="div_intd_p">2026-05-26</p>
        </div>
    </td>
    <td data-v-0bbd401f="" class="div_intd_p">Toshkent - Termiz (94) 808-00-04</td>
    <td data-v-0bbd401f="">0</td>
    <td data-v-0bbd401f="" class="div_intd_p">
        <div data-v-0bbd401f=""> 160000 </div>
    </td>
    <td data-v-0bbd401f="">YUTONG 51</td>
</tr>
</tbody>
</table>
"""

reys_list = _extract_reys(html_sample, "TEST_URL")
print(f"\n✓ Extracted {len(reys_list)} trips:")
for reys in reys_list:
    print(f"  - {reys.route} | {reys.departure_time} | {reys.seats} seats | {reys.price}")

if len(reys_list) == 0:
    print("\n❌ ERROR: No trips found! Parser not working correctly.")
else:
    print(f"\n✅ Parser works! Found {len(reys_list)} trip(s)")

# Test 2: Fetch from actual URL
print("\n" + "=" * 70)
print("TEST 2: Fetch from actual URL")
print("=" * 70)

if MONITOR_URLS:
    url = MONITOR_URLS[0]
    print(f"Fetching: {url}")
    reys_list = fetch_and_parse(url)
    if reys_list:
        print(f"\n✅ Fetched {len(reys_list)} trips:")
        for reys in reys_list:
            print(f"  - {reys.route} | {reys.departure_time} | {reys.seats} seats | {reys.price}")
    else:
        print("\n❌ ERROR: fetch_and_parse returned None or empty list")
else:
    print("No URLs configured in MONITOR_URLS")

# Test 3: Test Telegram
print("\n" + "=" * 70)
print("TEST 3: Test Telegram notification")
print("=" * 70)

print(f"BOT_TOKEN set: {'Yes' if BOT_TOKEN else 'No'}")
print(f"CHAT_ID set: {'Yes' if CHAT_ID else 'No'}")
print(f"BOT_TOKEN: {BOT_TOKEN[:20]}..." if BOT_TOKEN else "BOT_TOKEN not set")
print(f"CHAT_ID: {CHAT_ID}")

if BOT_TOKEN and CHAT_ID:
    test_message = "✅ Test message from debug script. If you see this, Telegram is working!"
    print(f"\nSending test message to Telegram...")
    _send_telegram(test_message)
    print("✓ Message sent (check Telegram)")
else:
    print("\n❌ ERROR: BOT_TOKEN or CHAT_ID not configured in .env")
