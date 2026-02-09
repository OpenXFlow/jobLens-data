# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Freelancermap Job Provider Module.

This module handles searching and data extraction from Freelancermap.de using
the centralized SeleniumFactory.
Refactored (v. 00012) - Stability: Added localized URL support and safe cleanup
to prevent 'WinError 6' noise in Windows environments.
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


class FreelancermapProvider:
    """Provider implementation for Freelancermap.de using Selenium."""

    BASE_URL: str = "https://www.freelancermap.de/projektboerse.html"
    DOMAIN: str = "https://www.freelancermap.de"
    HTTP_OK: int = 200
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"

    SUPPORTS_LOCATION_FILTER: bool = True

    # Mapping English keys to German parameters for better hit rate
    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the Freelancermap provider.

        Args:
            session: Shared requests session for detail page fetching.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for projects on Freelancermap.de using Selenium.

        Args:
            keywords: Search term.
            location: Target location (English key).
            limit: Maximum results per page.

        Returns:
            List[Dict[str, Any]]: List of normalized job objects.
        """
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "")
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()

            # Construct search URL (sort=2 is for 'latest')
            url = f"{self.BASE_URL}?query={keywords}&sort=2"
            if localized_loc:
                url += f"&location={localized_loc}"

            print(f"   [TRACE] [FM] Navigating to: {url}")
            driver.get(url)

            # S311: Standard random is safe for non-cryptographic delays
            time.sleep(random.uniform(3, 5))  # noqa: S311
            self._handle_cookies(driver)

            # Wait for project cards
            wait = WebDriverWait(driver, 20)
            item_class = "project-card"

            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, item_class)))
                time.sleep(1)
            except Exception:
                if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
                    self._dump_diagnostics(driver, f"fm_fail_{keywords[:5]}")

            soup = BeautifulSoup(driver.page_source, "html.parser")
            project_items = soup.find_all("div", class_=item_class)
            print(f"   [DEBUG] [FM] Found {len(project_items)} items for {location}.")

            for card in project_items[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)

        except Exception as e:
            print(f"   [DEBUG] [FM] Global search failed: {e}")
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
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.acceptall"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Dumps page source and screenshot for debugging."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        log_path = Path(f"logs/debug_{ts}_{name}.html")
        log_path.write_text(driver.page_source, encoding="utf-8")
        img_path = Path(f"logs/debug_{ts}_{name}.png")
        with contextlib.suppress(Exception):
            driver.save_screenshot(str(img_path))

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Extracts data from a single project card."""
        try:
            # 1. Title and Link
            link_tag = card.find("a", attrs={"data-testid": "title"})
            if not isinstance(link_tag, Tag):
                return None

            title = link_tag.get_text(strip=True)
            href = link_tag.get("href", "")
            if not isinstance(href, str):
                return None
            full_link = f"{self.DOMAIN}{href}" if href.startswith("/") else href
            job_id = href.split("/")[-1]

            # 2. Meta Info
            location = "Germany"
            city_div = card.find("div", attrs={"data-testid": "city"})
            if city_div:
                location = city_div.get_text(" ", strip=True).replace(",", "").strip()

            posted_at = "Recent"
            created_tag = card.find("span", attrs={"data-testid": "created"})
            if created_tag:
                posted_at = created_tag.get_text(strip=True)

            # 3. Work Location Type
            remote_text = ""
            remote_div = card.find("div", attrs={"data-testid": "remoteInPercent"})
            if remote_div:
                remote_text = remote_div.get_text(strip=True)

            # 4. Employment type
            emp_type = "Freelance"
            type_div = card.find("div", attrs={"data-testid": "type"})
            if type_div:
                emp_type = type_div.get_text(strip=True)

            return {
                "title": title,
                "company": "Freelancermap Client",
                "location": location,
                "link": full_link,
                "job_id": job_id,
                "provider": "freelancermap",
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "",
                "relevance_score": 0,
                "work_location_type": self._guess_location_type(f"{title} {location} {remote_text}"),
                "employment_type": emp_type,
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def _guess_location_type(self, text: str) -> str:
        """Determines location type from text."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["remote", "home office", "100%"]):
            return "Remote"
        if "hybrid" in text_lower:
            return "Hybrid"
        return "On-site"

    def fetch_full_description(self, url: str) -> str:
        """Fetches full project description from detail page."""
        if not url:
            return ""

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8",
                "Referer": self.BASE_URL,
            }
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code != self.HTTP_OK:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            content = (
                soup.find("div", class_="project-description")
                or soup.find("div", id="project-description")
                or soup.find("div", attrs={"data-testid": "description"})
            )

            if content:
                for tag in content(["script", "style", "button"]):
                    tag.decompose()
                return content.get_text(separator="\n", strip=True)

        except Exception as e:
            print(f"   [DEBUG] [FM] Detail fetch error: {e}")

        return ""


# End of src/core/providers/freelancermap.py (v. 00012)
