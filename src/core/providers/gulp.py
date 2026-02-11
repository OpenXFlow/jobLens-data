# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""GULP Job Provider Module (Undetected Selenium).

This module handles searching and data extraction from GULP.de (Randstad) using
the centralized SeleniumFactory. Optimized for Angular 21+ structure.
Refactored (v. 00017) - Compliance: Resolved Ruff SIM108 and TRY300.
Added rich badge extraction for immediate skill matching in Phase 1.
"""

import contextlib
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

import requests
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from bs4.element import Tag
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from src.core.selenium_factory import SeleniumFactory


class GulpJobParser:
    """Helper class to parse a single Angular search-project-card from GULP."""

    def __init__(self, card: Tag, domain: str, query: str, req_loc: str) -> None:
        """Initializes the parser."""
        self.card = card
        self.domain = domain
        self.query = query
        self.req_loc = req_loc

    def parse(self) -> Optional[Dict[str, Any]]:
        """Orchestrates the parsing sequence."""
        job_data: Dict[str, Any] = {}
        try:
            link_data = self._extract_link_and_title()
            if not link_data:
                return None

            meta = self._extract_metadata()
            description = self._extract_badges_description()

            job_data = {
                "title": link_data["title"],
                "company": "GULP Client",  # GULP rarely shows real company in list
                "location": meta["location"],
                "link": link_data["full_link"],
                "job_id": link_data["job_id"],
                "provider": "gulp",
                "posted_at_relative": meta["posted_at"],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": description,  # Rich text for Phase 1 scoring
                "relevance_score": 0,
                "work_location_type": "Remote" if meta["is_remote"] else "On-site",
                "employment_type": "Freelance",
                "search_criteria": f"{self.query} | {self.req_loc}",
            }
        except Exception:
            return None
        else:
            return job_data

    def _extract_link_and_title(self) -> Optional[Dict[str, str]]:
        """Extracts title and URL from the card header."""
        # Angular structure: <h3><a href="...">Title</a></h3> OR direct <a>
        link_tag = self.card.find("a", href=True)
        if not isinstance(link_tag, Tag):
            return None

        # SIM108 Fix: Use ternary operator
        h3 = self.card.find("h3")
        title = h3.get_text(strip=True) if h3 else link_tag.get_text(strip=True)

        href = link_tag.get("href")
        if not isinstance(href, str):
            return None

        full_link = href if href.startswith("http") else f"{self.domain}{href}"
        job_id = href.split("/")[-1]

        return {
            "title": title,
            "full_link": full_link,
            "job_id": job_id,
        }

    def _extract_metadata(self) -> Dict[str, Any]:
        """Parses icon lists for location and date."""
        meta = {"location": "Germany", "posted_at": "Recent", "is_remote": False}

        ul = self.card.find("ul", class_="small") or self.card.find("ul", class_="fa-ul")

        if ul:
            for li in ul.find_all("li"):
                text = li.get_text(strip=True)
                li_str = str(li)

                if "map-marker" in li_str:
                    meta["location"] = text
                elif "history" in li_str:
                    meta["posted_at"] = text
                elif "laptop-house" in li_str or "Remote" in text:
                    meta["is_remote"] = True

        if "Remote" in meta["location"]:
            meta["is_remote"] = True

        return meta

    def _extract_badges_description(self) -> str:
        """Extracts skill badges to populate description for engine matching."""
        parts = []
        badges = self.card.find_all("a", class_="badge")
        for b in badges:
            parts.append(b.get_text(strip=True))

        return " | ".join(parts)


class GulpProvider:
    """Provider implementation for GULP.de using Selenium."""

    BASE_URL: str = "https://www.gulp.de/gulp2/g/projekte"
    DOMAIN: str = "https://www.gulp.de"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"
    HTTP_OK: int = 200

    SUPPORTS_LOCATION_FILTER: bool = True

    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
        "Slovakia": "Andere Länder",
        "Europe": "Andere Länder",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the GULP provider.

        Args:
            session: Shared requests session.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches for jobs on GULP.de using Angular-aware selectors."""
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Deutschland")

        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()

            query_url = f"{self.BASE_URL}?query={keywords}&location={localized_loc}"
            print(f"   [TRACE] [GULP] Navigating to: {query_url}")
            driver.get(query_url)

            time.sleep(random.uniform(4, 6))  # noqa: S311
            self._handle_cookies(driver)

            # Wait for Angular to hydrate results
            with contextlib.suppress(Exception):
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "search-project-card")))

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Angular component selector (Primary)
            cards = soup.find_all("search-project-card")
            if not cards:
                # Fallback to old class just in case
                cards = soup.find_all("div", class_="list-result-item")

            print(f"   [DEBUG] [GULP] Found {len(cards)} items.")

            for card in cards[:limit]:
                if isinstance(card, Tag):
                    job = GulpJobParser(card, self.DOMAIN, keywords, location).parse()
                    if job:
                        found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] [GULP] Search Error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)
        return found_jobs

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches full description from detail page using the specific Angular structure."""
        print(f"   [DEBUG] [GULP] Fetching details: {url}")

        result: Union[str, Dict[str, str]] = ""
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            driver.get(url)
            time.sleep(random.uniform(3, 5))  # noqa: S311
            self._handle_cookies(driver)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            description = ""

            # 1. Main Description (Angular test-id)
            desc_val = soup.find(attrs={"data-testid": "readonlyValue"})
            if desc_val:
                description += desc_val.get_text(separator="\n", strip=True)

            # 2. Must-Have Skills (Angular test-id)
            skills_container = soup.find(attrs={"data-testid": "readonlyTagsContainer"})
            if skills_container:
                skills = [t.get_text(strip=True) for t in skills_container.find_all(class_="tag")]
                if skills:
                    description += "\n\nSkills: " + ", ".join(skills)

            # 3. Fallback for older pages
            if not description:
                container = soup.find("div", class_="project-details") or soup.find("div", class_="description-content")
                if container:
                    description = container.get_text(separator="\n", strip=True)

            if description:
                result = {
                    "description": description,
                    "title": self._extract_title(soup),
                    "company": "GULP Client",
                    "location": self._extract_location(soup),
                }

        except Exception as e:
            print(f"   [DEBUG] [GULP] Detail fetch error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)
        return result

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extracts title from detail page."""
        title_tag = soup.find(attrs={"data-testid": "projectTitle"})
        if title_tag:
            return title_tag.get_text(strip=True)
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """Extracts location from detail page."""
        icons = soup.find_all("i", class_=re.compile(r"map-marker"))
        for icon in icons:
            if icon.parent:
                text = icon.parent.get_text(strip=True)
                if "Location:" in text:
                    return text.replace("Location:", "").strip()
        return "Germany"

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates driver service."""
        with contextlib.suppress(Exception):
            time.sleep(0.5)
            driver.quit()

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Handles OneTrust banner."""
        with contextlib.suppress(Exception):
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            driver.execute_script("arguments[0].click();", btn)


# End of src/core/providers/gulp.py (v. 00017)
