# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""SOLCOM Job Provider Module (Undetected Selenium).

This module handles searching and data extraction from SOLCOM.de using
localized URL parameters.
Refactored (v. 00039) - Compliance: Fixed Ruff S110 by using contextlib.suppress
for silent driver termination.
"""

import contextlib
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import requests
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from bs4.element import Tag
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from src.core.selenium_factory import SeleniumFactory


class SolcomProvider:
    """Provider implementation for SOLCOM using localized URL parameters."""

    BASE_URL: str = "https://www.solcom.de/de/projektportal/projektangebote"
    DOMAIN: str = "https://www.solcom.de"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"
    HTTP_OK: int = 200

    SUPPORTS_LOCATION_FILTER: bool = True

    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
        "Slovakia": "Andere Länder",
        "Czech Republic": "Andere Länder",
        "Poland": "Andere Länder",
        "Europe": "Andere Länder",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the Solcom provider.

        Args:
            session: Shared requests session.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for projects on Solcom.de using localized URL.

        Args:
            keywords: Search term.
            location: Target location (English key).
            limit: Maximum results per query.

        Returns:
            List[Dict[str, Any]]: List of normalized job objects.
        """
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location)

        if not localized_loc:
            return []

        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            driver.set_page_load_timeout(60)

            base_p = "--contenance_solcom-portal_project_index"
            url = (
                f"{self.BASE_URL}?"
                f"{base_p}[searchArguments][searchParameter]={keywords}&"
                f"{base_p}[searchArguments][location]={localized_loc}&"
                f"{base_p}[itemsPerPage]={limit}"
            )

            print(f"   [TRACE] [SOLCOM] Navigating to: {url}")
            driver.get(url)

            # S311: Standard random is safe for human-like delays
            time.sleep(random.uniform(3, 5))  # noqa: S311
            self._handle_cookies(driver)

            wait = WebDriverWait(driver, 20)
            item_class = "contenance-solcom-portal-project-item"

            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, item_class)))
                time.sleep(1)
            except Exception:
                if "keine projekte gefunden" not in driver.page_source.lower():
                    print(f"   [DEBUG] [SOLCOM] Timeout for '{keywords}' in '{localized_loc}'.")
                    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
                        self._dump_diagnostics(driver, f"solcom_fail_{keywords[:5]}")

            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.find_all("div", class_=item_class)
            print(f"   [DEBUG] [SOLCOM] Found {len(items)} items for {location}.")

            for card in items[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)

        except Exception as e:
            print(f"   [DEBUG] [SOLCOM] Search failed: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates the driver to avoid WinError 6 noise.

        Args:
            driver: The active Chrome driver instance.
        """
        # S110: contextlib.suppress is the preferred way to ignore exceptions
        with contextlib.suppress(Exception):
            driver.close()
            driver.quit()

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Attempts to accept cookie consent."""
        with contextlib.suppress(Exception):
            selectors = ["button.acceptall", "#uc-btn-accept-banner", ".cookie-accept-all"]
            for selector in selectors:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        return

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Dumps page source and screenshot for debugging."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        log_path = Path(f"logs/debug_{ts}_{name}.html")
        log_path.write_text(driver.page_source, encoding="utf-8")
        img_path = Path(f"logs/debug_{ts}_{name}.png")
        with contextlib.suppress(Exception):
            driver.save_screenshot(str(img_path))

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Parses a single project card from SOLCOM list view."""
        try:
            h_div = card.find("div", class_="project-header")
            if not isinstance(h_div, Tag):
                return None
            link_tag = h_div.find("a")
            if not isinstance(link_tag, Tag):
                return None

            title_tag = link_tag.find("h2")
            title = title_tag.get_text(strip=True) if isinstance(title_tag, Tag) else "Unknown"
            href = link_tag.get("href")
            if not isinstance(href, str):
                return None

            full_link = href if href.startswith("http") else f"{self.DOMAIN}{href}"
            job_id = link_tag.get("data-projectid") or href.split("/")[-1]

            location, posted_at, emp_type = "Germany", "Recent", "Freelance"
            infos = card.find("div", class_="project-infos")
            if isinstance(infos, Tag):
                pin = infos.find("li", class_="pin-icon")
                if pin:
                    location = pin.get_text(strip=True)
                cal = infos.find("li", class_="calendar-icon")
                if cal:
                    posted_at = f"Start: {cal.get_text(strip=True)}"
                bag = infos.find("li", class_="bag-icon")
                if bag:
                    emp_type = bag.get_text(strip=True)

            return {
                "title": title,
                "company": "SOLCOM Client",
                "location": location,
                "link": full_link,
                "job_id": str(job_id),
                "provider": "solcom",
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": f"Employment: {emp_type}",
                "relevance_score": 0,
                "work_location_type": "Remote" if "remote" in (title + location).lower() else "On-site",
                "employment_type": emp_type,
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> str:
        """Fetches full description via requests."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == self.HTTP_OK:
                soup = BeautifulSoup(resp.text, "html.parser")
                desc = soup.find("div", class_="project-details") or soup.find("div", class_="description-content")
                if isinstance(desc, Tag):
                    return desc.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"   [DEBUG] [SOLCOM] Detail fetch error: {e}")
        return ""


# End of src/core/providers/solcom.py (v. 00039)
