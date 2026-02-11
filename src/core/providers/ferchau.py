# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""FERCHAU Job Provider Module.

This module handles searching and data extraction from the modern FERCHAU
Touch portal (touch.ferchau.com) using the centralized SeleniumFactory.
Refactored (v. 00012) - Consistency: Updated detail fetch to return full
metadata (work type, employment) to ensure parity between manual and auto modes.
"""

import contextlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

import requests
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.core.selenium_factory import SeleniumFactory


class FerchauProvider:
    """Provider implementation for the modern FERCHAU Touch portal."""

    BASE_URL: str = "https://touch.ferchau.com/de/de"
    HTTP_OK: int = 200
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"

    SUPPORTS_LOCATION_FILTER: bool = True

    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Poland": "Polen",
        "Remote": "Remote",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the FERCHAU provider."""
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches for jobs on touch.ferchau.com using modern parameters."""
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Deutschland")

        query_url = f"{self.BASE_URL}?type=3&searchTerm={keywords}&location={localized_loc}&sortingType=relevance"

        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()
            print(f"   [TRACE] [FERCHAU] Navigating to: {query_url}")
            driver.get(query_url)

            # S311: Human-like delay (noqa)
            time.sleep(random.uniform(4, 6))  # noqa: S311
            self._handle_cookies(driver)

            with contextlib.suppress(Exception):
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "search-result__offer")))

            found_jobs = self._extract_from_app_data(driver.page_source, keywords, location)

        except Exception as e:
            print(f"   [DEBUG] [FERCHAU] Global search error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs[:limit]

    def _extract_from_app_data(
        self, html: str, query: str, req_loc: str, target_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Parses the 'App.Data' JSON object injected into the page."""
        results = []
        try:
            pattern = r"App\.Data\s*=\s*(\{.*?\});"
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                return []

            raw_json = match.group(1)
            data = json.loads(raw_json)
            offers = data.get("ControllerResponse", {}).get("Data", {}).get("Offers", [])

            if target_id:
                offers = sorted(offers, key=lambda x: str(x.get("id")) == target_id, reverse=True)

            for offer in offers:
                title = str(offer.get("title", "")).replace("\u00ad", "").strip()
                description_parts = [
                    offer.get("intro", ""),
                    offer.get("tasks", ""),
                    offer.get("requirements", ""),
                    offer.get("benefits", ""),
                ]
                clean_desc = BeautifulSoup(" ".join(description_parts), "html.parser").get_text(
                    separator="\n", strip=True
                )

                # Standardize employment and work location types
                raw_emp = offer.get("jobTypeName", "Full-time")
                emp_type = "Full-time" if "Vollzeit" in raw_emp or "Full" in raw_emp else raw_emp
                if "Freiberuflich" in raw_emp:
                    emp_type = "Freelance"

                raw_work = offer.get("workplaceTypeName", "Hybrid")
                work_type = "Remote" if "Remote" in raw_work or "Mobil" in raw_work else raw_work

                results.append(
                    {
                        "title": title,
                        "company": "FERCHAU",
                        "location": f"{offer.get('locationCity', '')} {offer.get('locationCountry', '')}".strip(),
                        "link": f"https://touch.ferchau.com{offer.get('slug', '')}",
                        "job_id": str(offer.get("id")),
                        "provider": "ferchau",
                        "posted_at_relative": "Recent",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "description": clean_desc,
                        "relevance_score": 0,
                        "work_location_type": work_type,
                        "employment_type": emp_type,
                        "search_criteria": f"{query} | {req_loc}",
                    }
                )
        except Exception as e:
            print(f"   [DEBUG] [FERCHAU] AppData parse error: {e}")

        return results

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches full description and metadata for a single URL."""
        id_match = re.search(r"/job/(\d+)/", url)
        target_id = id_match.group(1) if id_match else None

        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()
            driver.get(url)
            time.sleep(4)

            jobs = self._extract_from_app_data(driver.page_source, "Manual", "N/A", target_id=target_id)
            if jobs:
                # Return dictionary to overwrite defaults in manual mode
                return {
                    "description": jobs[0]["description"],
                    "company": jobs[0]["company"],
                    "title": jobs[0]["title"],
                    "location": jobs[0]["location"],
                    "work_location_type": jobs[0]["work_location_type"],
                    "employment_type": jobs[0]["employment_type"],
                }
        except Exception as e:
            print(f"   [DEBUG] [FERCHAU] Detail fetch error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return ""

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Attempts to accept cookie consent."""
        with contextlib.suppress(Exception):
            btn = driver.find_element("css selector", "button[data-testid='uc-accept-all']")
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates the driver."""
        with contextlib.suppress(Exception):
            driver.quit()


# End of src/core/providers/ferchau.py (v. 00012)
