# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""FERCHAU Job Provider Module.

This module handles searching and data extraction from ferchau.com using
the centralized SeleniumFactory.
Refactored (v. 00007) - Compliance: Fixed Ruff F841 by removing unused variables
and maintained CI/CD stability features.
"""

import contextlib
import os
import random
import re
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


class FerchauJobParser:
    """Helper class to parse a single FERCHAU job card from HTML."""

    def __init__(self, card: Tag, domain: str, query: str, req_loc: str) -> None:
        """Initializes the parser with context.

        Args:
            card: BeautifulSoup Tag containing the job card.
            domain: Base domain for link construction.
            query: The search keywords used.
            req_loc: The requested location filter.
        """
        self.card = card
        self.domain = domain
        self.query = query
        self.req_loc = req_loc

    def parse(self) -> Optional[Dict[str, Any]]:
        """Parses the job card into a standardized dictionary.

        Returns:
            Optional[Dict[str, Any]]: Normalized job data or None if invalid.
        """
        try:
            # 1. Title and Link
            link_tag = self.card.find("a", href=re.compile(r"/jobs/"))
            if not isinstance(link_tag, Tag):
                return None

            title = link_tag.get_text(strip=True)
            href = link_tag.get("href")
            if not isinstance(href, str) or not href:
                return None

            full_link = href if href.startswith("http") else f"{self.domain}{href}"

            # Extract job ID from the end of URL
            job_id_match = re.search(r"/(\d+)/?$", href)
            job_id = job_id_match.group(1) if job_id_match else href.split("/")[-1]

            # 2. Metadata (Location, Date)
            location = "Germany"
            loc_match = re.search(r"(?:in|Location:)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", title)
            if loc_match:
                location = loc_match.group(1)

            # 3. Description Preview
            desc_tag = self.card.find("p") or self.card.find("div", class_="teaser")
            description = desc_tag.get_text(separator=" ", strip=True) if desc_tag else ""

            return {
                "title": title,
                "company": "FERCHAU",
                "location": location,
                "link": full_link,
                "job_id": str(job_id),
                "provider": "ferchau",
                "posted_at_relative": "Recent",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": description,
                "relevance_score": 0,
                "work_location_type": "On-site",
                "employment_type": "Full-time",
                "search_criteria": f"{self.query} | {self.req_loc}",
            }
        except Exception:
            return None


class FerchauProvider:
    """Provider implementation for FERCHAU using Selenium."""

    BASE_URL: str = "https://www.ferchau.com"
    SEARCH_PATH: str = "/de/de/bewerber/jobs"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"
    HTTP_OK: int = 200

    SUPPORTS_LOCATION_FILTER: bool = True

    # Ferchau is Germany-based, mapping locations to appropriate context
    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the FERCHAU provider.

        Args:
            session: Shared requests Session.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches for jobs on ferchau.com using Selenium.

        Args:
            keywords: Search keywords.
            location: Target location.
            limit: Maximum results to fetch.

        Returns:
            List[Dict[str, Any]]: Normalized job data.
        """
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Deutschland")
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            query_url = f"{self.BASE_URL}{self.SEARCH_PATH}?search={keywords}&location={localized_loc}"

            print(f"   [TRACE] [FERCHAU] Navigating to: {query_url}")
            driver.get(query_url)

            # S311: Human-like delay
            time.sleep(random.uniform(2, 4))  # noqa: S311
            self._handle_cookies(driver)

            wait = WebDriverWait(driver, 20)
            item_class = "job-list-item"

            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, item_class)))
                time.sleep(1)
            except Exception:
                if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
                    self._dump_diagnostics(driver, f"ferchau_fail_{keywords[:5]}")

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards_raw = soup.find_all("div", class_=item_class)
            print(f"   [DEBUG] [FERCHAU] Found {len(cards_raw)} items for {location}.")

            for card in cards_raw[:limit]:
                if isinstance(card, Tag):
                    parser = FerchauJobParser(card, self.BASE_URL, keywords, location)
                    job_data = parser.parse()
                    if job_data:
                        found_jobs.append(job_data)

        except Exception as e:
            print(f"   [DEBUG] [FERCHAU] Search failed: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates driver service to avoid WinError 6 noise."""
        with contextlib.suppress(Exception):
            driver.close()
            driver.quit()

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Attempts to accept cookie consent."""
        with contextlib.suppress(Exception):
            selectors = [
                (By.ID, "uc-btn-accept-banner"),
                (By.CSS_SELECTOR, "button[data-testid='uc-accept-all']"),
            ]
            for by, val in selectors:
                buttons = driver.find_elements(by, val)
                if buttons and buttons[0].is_displayed():
                    driver.execute_script("arguments[0].click();", buttons[0])
                    time.sleep(1)
                    return

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Dumps page source for debugging."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        log_path = Path(f"logs/debug_{ts}_{name}.html")
        log_path.write_text(driver.page_source, encoding="utf-8")

    def fetch_full_description(self, url: str) -> str:
        """Fetches full description via requests.

        Args:
            url: The detail URL of the job.

        Returns:
            str: Cleaned text description.
        """
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == self.HTTP_OK:
                soup = BeautifulSoup(resp.text, "html.parser")
                desc = soup.find("div", class_="job-detail__content") or soup.find("article")
                if isinstance(desc, Tag):
                    return desc.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"   [DEBUG] [FERCHAU] Detail fetch error: {e}")

        return ""


# End of src/core/providers/ferchau.py (v. 00007)
