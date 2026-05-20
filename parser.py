"""
parser.py — HTML parser for Avtoticket.uz trip listings
Extracts all reys (bus trips) from a given URL using Selenium (JavaScript rendering) + BeautifulSoup4.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS, MAX_RETRIES, RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class Reys:
    """
    Represents a single bus trip (reys) extracted from the page.
    The unique_id is used to track identity across polls.
    """
    route: str
    departure_time: str
    departure_date: str
    arrival_time: str
    arrival_date: str
    seats: int
    price: str
    bus_type: str
    unique_id: str = field(init=False)

    def __post_init__(self):
        # Build a stable unique identifier from route + departure datetime
        # This lets us detect seat count changes on the SAME reys
        self.unique_id = f"{self.route}|{self.departure_date}|{self.departure_time}"

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON persistence."""
        return {
            "unique_id": self.unique_id,
            "route": self.route,
            "departure_time": self.departure_time,
            "departure_date": self.departure_date,
            "arrival_time": self.arrival_time,
            "arrival_date": self.arrival_date,
            "seats": self.seats,
            "price": self.price,
            "bus_type": self.bus_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Reys":
        """Deserialize from a plain dict (used when loading from history.json)."""
        return cls(
            route=data["route"],
            departure_time=data["departure_time"],
            departure_date=data["departure_date"],
            arrival_time=data["arrival_time"],
            arrival_date=data["arrival_date"],
            seats=int(data["seats"]),
            price=data["price"],
            bus_type=data["bus_type"],
        )


def _parse_datetime_cell(cell) -> tuple[str, str]:
    """
    Parse a datetime cell that may have nested <div>/<p> tags.
    Structure: <td><div><p>TIME</p><p>DATE</p></div></td>
    Or plain text: '18:00 / 2026-05-25'
    
    Returns ('time', 'date') or ('', '') if parsing fails.
    """
    # Try to find <p> tags first (Vue.js structure)
    p_tags = cell.find_all("p") if hasattr(cell, 'find_all') else []
    if len(p_tags) >= 2:
        time_text = p_tags[0].get_text(strip=True)
        date_text = p_tags[1].get_text(strip=True)
        logger.debug(f"Parsed nested p-tags: time='{time_text}', date='{date_text}'")
        return time_text, date_text
    
    # Fallback: parse plain text
    cell_text = cell.get_text(strip=True) if hasattr(cell, 'get_text') else str(cell)
    parts = [p.strip() for p in cell_text.split("/")]
    if len(parts) == 2:
        return parts[0], parts[1]
    
    # Last resort: split on space
    tokens = cell_text.strip().split()
    if len(tokens) >= 2:
        return tokens[0], tokens[1]
    
    logger.warning(f"Could not parse datetime from: '{cell_text}'")
    return cell_text.strip(), ""


def _safe_int(value: str) -> int:
    """Parse an integer safely, returning -1 on failure."""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return -1


def fetch_and_parse(url: str) -> Optional[list[Reys]]:
    """
    Fetch the given Avtoticket URL and extract all reys from the <tbody> rows.

    Returns:
        List of Reys objects, or None if the page could not be fetched.
    """
    html = _fetch_with_retry(url)
    if html is None:
        return None

    return _extract_reys(html, url)


def _fetch_with_retry(url: str) -> Optional[str]:
    """
    Fetch the raw HTML of a URL using Selenium (JavaScript rendering).
    Uses headless Chrome to wait for the trip table to load.
    Retries up to MAX_RETRIES times on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        driver = None
        try:
            logger.debug(f"[Attempt {attempt}/{MAX_RETRIES}] Fetching with Selenium: {url}")
            
            # Configure headless Chrome
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={REQUEST_HEADERS['User-Agent']}")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Create driver with auto-downloaded ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(REQUEST_TIMEOUT_SECONDS)
            
            # Navigate to URL
            driver.get(url)
            
            # Wait for table or tbody to appear (max 10 seconds)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                )
                logger.debug("✓ Table loaded successfully")
            except:
                logger.debug("⚠ Timeout waiting for tbody, trying with table rows directly")
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tr td"))
                    )
                except:
                    logger.warning("No table structure found after JavaScript rendering")
            
            # Get rendered HTML
            html = driver.page_source
            logger.debug(f"✓ Received {len(html)} bytes of rendered HTML")
            driver.quit()
            return html

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt} for {url}")
        except Exception as e:
            logger.warning(f"Error on attempt {attempt}: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        if attempt < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY_SECONDS}s…")
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"All {MAX_RETRIES} fetch attempts failed for {url}")
    return None


def _extract_reys(html: str, source_url: str) -> list[Reys]:
    """
    Parse the HTML and extract all <tr> rows (from <tbody> or directly from <table>).
    Handles both plain text cells and Vue.js component structure with nested <div>/<p> tags.
    
    Shows ALL trips including unavailable/grayed out ones for debugging.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try to find rows: first look in <tbody>, then in <table> directly
    tbody = soup.find("tbody")
    rows = []
    
    if tbody:
        rows = tbody.find_all("tr")
        logger.debug(f"Found {len(rows)} rows in <tbody>")
    else:
        # Fallback: look for any <tr> in the entire page or in <table>
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")
            logger.warning(f"No <tbody> found, but found {len(rows)} rows in <table> directly")
        else:
            rows = soup.find_all("tr")
            logger.warning(f"No <tbody> or <table> found, but found {len(rows)} <tr> rows in page")

    if not rows:
        logger.warning(f"No <tr> rows found on {source_url} — page structure may have changed")
        logger.debug(f"HTML snippet: {html[:500]}")
        return []

    reys_list: list[Reys] = []

    for idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Log row info for debugging
        cells_preview = [c.get_text(strip=True)[:20] for c in cells[:3]]
        logger.debug(f"Row {idx}: {len(cells)} cells — {cells_preview}")

        # Skip rows that don't have the expected number of columns
        if len(cells) < 6:
            logger.debug(f"  → Skipping row {idx}: only {len(cells)} cells (expected ≥6)")
            continue

        try:
            # Pass cell objects to parser so it can extract nested <p> tags
            dep_time, dep_date = _parse_datetime_cell(cells[0])
            arr_time, arr_date = _parse_datetime_cell(cells[1])
            route     = cells[2].get_text(strip=True)
            seats     = _safe_int(cells[3].get_text(strip=True))
            price     = cells[4].get_text(strip=True)
            bus_type  = cells[5].get_text(strip=True)

            # Include ALL trips, even unavailable ones (seats=0 or -1)
            reys = Reys(
                route=route,
                departure_time=dep_time,
                departure_date=dep_date,
                arrival_time=arr_time,
                arrival_date=arr_date,
                seats=seats,
                price=price,
                bus_type=bus_type,
            )
            reys_list.append(reys)
            
            # Log what we found
            availability = "✓ AVAILABLE" if seats > 0 else "✗ UNAVAILABLE"
            logger.info(f"  → Row {idx}: {availability} | {route} | {dep_time} | {seats} seats | {price}")

        except Exception as e:
            logger.warning(f"  → Row {idx}: Failed to parse: {e}")

    logger.info(f"✓ SUCCESS: Parsed {len(reys_list)} reys from {source_url}")
    return reys_list
