# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""GULP Job Provider Module (Undetected Selenium).

This module handles searching and data extraction from GULP.de using
the centralized SeleniumFactory.
Refactored (v. 00015) - Stability: Improved process cleanup to prevent
'WinError 6' noise and added German location mapping for better targeting.
"""

import contextlib
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


class GulpJobParser:
    """Helper class to parse a single GULP job card from HTML."""

    def __init__(self, card: Tag, domain: str, query: str, req_loc: str) -> None:
        """Initializes the parser."""
        self.card = card
        self.domain = domain
        self.query = query
        self.req_loc = req_loc
        self.location = "Germany/Remote"
        self.start_date = "ASAP"
        self.company = "GULP Client"
        self.remote_possible = False

    def parse(self) -> Optional[Dict[str, Any]]:
        """Orchestrates the parsing sequence."""
        link_data = self._extract_link_and_title()
        if not link_data:
            return None
        self._extract_metadata()

        return {
            "title": link_data["title"],
            "company": self.company,
            "location": self.location,
            "link": link_data["full_link"],
            "job_id": str(link_data["job_id"]),
            "provider": "gulp",
            "posted_at_relative": self._extract_posted_date(),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "description": self._extract_description(),
            "relevance_score": 0,
            "work_location_type": "Remote" if self.remote_possible or "remote" in self.location.lower() else "On-site",
            "employment_type": "Freelance",
            "search_criteria": f"{self.query} | {self.req_loc}",
        }

    def _extract_link_and_title(self) -> Optional[Dict[str, str]]:
        """Extracts title and URL."""
        h1 = self.card.find("h1")
        if not h1:
            return None
        link_tag = h1.find("a")
        if not isinstance(link_tag, Tag):
            return None
        href = link_tag.get("href")
        if not isinstance(href, str):
            return None
        return {
            "title": link_tag.get_text(strip=True),
            "full_link": href if href.startswith("http") else f"{self.domain}{href}",
            "job_id": href.split("/")[-1],
        }

    def _extract_metadata(self) -> None:
        """Parses icon lists."""
        info_list = self.card.find("ul", class_="fa-ul")
        if not isinstance(info_list, Tag):
            return
        for li in info_list.find_all("li"):
            text = li.get_text(strip=True)
            if "Location:" in text:
                self.location = text.replace("Location:", "").strip()
            elif "Start Date:" in text:
                self.start_date = text.replace("Start Date:", "").strip()
            elif "Project Provider:" in text:
                self.company = text.replace("Project Provider:", "").strip()
            elif "Remote Work Possible" in text:
                self.remote_possible = True

    def _extract_description(self) -> str:
        """Builds description string."""
        parts = [f"Start: {self.start_date}", f"Location: {self.location}"]
        skills_div = self.card.find("div", class_="skills")
        if isinstance(skills_div, Tag):
            tags = [s.get_text(strip=True) for s in skills_div.find_all("span", class_="label")]
            if tags:
                parts.append("Skills: " + ", ".join(tags))
        desc_tag = self.card.find("p", class_="description")
        if isinstance(desc_tag, Tag):
            parts.append(desc_tag.get_text(separator=" ", strip=True))
        return " \n ".join(parts)

    def _extract_posted_date(self) -> str:
        """Gets posted date."""
        t = self.card.find("small", class_="time-ago")
        return t.get_text(strip=True) if t else "Recent"


class GulpProvider:
    """Provider implementation for GULP.de using Selenium."""

    BASE_URL: str = "https://www.gulp.de/gulp2/g/projekte"
    DOMAIN: str = "https://www.gulp.de"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"
    HTTP_OK: int = 200

    SUPPORTS_LOCATION_FILTER: bool = True

    # Mapping English keys to German parameters for GULP URL/UI
    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
        "Slovakia": "Andere Länder",
        "Czech Republic": "Andere Länder",
        "USA": "Andere Länder",
        "Europe": "Andere Länder",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the GULP provider."""
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches for jobs on GULP.de."""
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Andere Länder")

        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()
            query_url = f"{self.BASE_URL}?query={keywords}&location={localized_loc}"
            print(f"   [DEBUG] Opening GULP Chrome: {query_url}")
            driver.get(query_url)

            # S311: Standard random is safe here
            time.sleep(random.uniform(2, 4))  # noqa: S311
            self._handle_cookies(driver)

            with contextlib.suppress(Exception):
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "list-result-item")))

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.find_all("div", class_="list-result-item")
            print(f"   [DEBUG] GULP: Found {len(cards)} items for {location}.")

            for card in cards[:limit]:
                if isinstance(card, Tag):
                    job = GulpJobParser(card, self.DOMAIN, keywords, location).parse()
                    if job:
                        found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] GULP Error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)
        return found_jobs

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates driver service."""
        with contextlib.suppress(Exception):
            driver.close()
            driver.quit()

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Handles consent banner."""
        with contextlib.suppress(Exception):
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            driver.execute_script("arguments[0].click();", btn)

    def fetch_full_description(self, url: str) -> str:
        """Fetches full description from detail page."""
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == self.HTTP_OK:
                soup = BeautifulSoup(resp.text, "html.parser")
                cont = soup.find("div", class_="project-details") or soup.find("div", class_="description-content")
                if cont:
                    return cont.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"   [DEBUG] GULP Fetch Error: {e}")
        return ""


# End of src/core/providers/gulp.py (v. 00015)
