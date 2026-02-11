# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""XING Job Provider Module (Advanced Scraper).

This module handles searching and data extraction from XING.com using
the centralized SeleniumFactory.
Refactored (v. 00028) - Data Recovery: Added aggressive fallbacks (Page Title)
and relaxed return conditions to prevent 'Pending Extraction' in Manual Mode.
"""

import contextlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from bs4.element import Tag
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from src.core.selenium_factory import SeleniumFactory


class XingProvider:
    """Provider implementation for XING Jobs using Selenium and Deep Detail Extraction."""

    BASE_URL: str = "https://www.xing.com/jobs/search"
    DOMAIN: str = "https://www.xing.com"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Undetected Selenium"
    HTTP_OK: int = 200

    def __init__(self, session: requests.Session) -> None:
        """Initializes the XING provider.

        Args:
            session: Shared requests session for potential background tasks.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches for jobs on XING using Selenium.

        Args:
            keywords: Search keywords.
            location: Target location.
            limit: Maximum results to fetch.

        Returns:
            List[Dict[str, Any]]: Normalized job data.
        """
        found_jobs: List[Dict[str, Any]] = []
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            query_url = f"{self.BASE_URL}?keywords={keywords}"
            if location:
                query_url += f"&location={location}"

            print(f"   [TRACE] [XING] Navigating to: {query_url}")
            driver.get(query_url)

            self._handle_cookies(driver)
            time.sleep(random.uniform(3, 5))  # noqa: S311

            soup = BeautifulSoup(driver.page_source, "html.parser")
            job_articles = soup.find_all("article")
            print(f"   [DEBUG] [XING] Found {len(job_articles)} items.")

            for card in job_articles[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)

        except Exception as e:
            print(f"   [DEBUG] XING Search Error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates the driver to avoid WinError 6 noise."""
        with contextlib.suppress(Exception):
            time.sleep(0.5)
            driver.quit()

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Handles cookie consent banner."""
        with contextlib.suppress(Exception):
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='uc-accept-all']"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Extracts basic job data from a card."""
        try:
            link_tag = card.find("a", href=re.compile(r"/jobs/"))
            if not isinstance(link_tag, Tag):
                return None

            title_tag = card.find(["h2", "h3"]) or link_tag
            title = title_tag.get_text(strip=True)

            href = link_tag.get("href", "")
            if not isinstance(href, str):
                return None

            full_link = href if href.startswith("http") else f"{self.DOMAIN}{href}"
            job_id = href.split("/")[-1].split("?")[0]

            return {
                "title": title,
                "company": "XING Employer",
                "location": "Germany/Remote",
                "link": full_link,
                "job_id": str(job_id),
                "provider": "xing",
                "posted_at_relative": "Recent",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "",
                "relevance_score": 0,
                "work_location_type": "On-site",
                "employment_type": "Full-time",
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches description and metadata using Selenium to support Manual Mode."""
        result: Union[str, Dict[str, str]] = ""
        driver: Optional[uc.Chrome] = None

        print(f"   [DEBUG] [XING] Fetching details: {url}")

        try:
            driver = SeleniumFactory.setup_driver()
            driver.get(url)
            self._handle_cookies(driver)
            time.sleep(random.uniform(3, 5))  # noqa: S311

            soup = BeautifulSoup(driver.page_source, "html.parser")

            data = {"description": "", "title": "", "company": "XING Employer", "location": "Germany"}

            # 1. Try Extracting from JSON-LD
            self._extract_json_ld(soup, data)

            # 2. Try HTML Fallbacks
            self._extract_html_fallback(soup, data)

            # 3. Last Resort: Use Page Title for Job Title
            if not data["title"]:
                page_title = driver.title
                if page_title and "XING" not in page_title:  # Avoid "Sign In | XING"
                    data["title"] = page_title.split("|")[0].strip()

            # Return Dictionary if we found AT LEAST a title or description
            # This ensures "Pending Extraction" is overwritten even if description is protected
            if data["title"] or data["description"]:
                result = data

        except Exception as e:
            print(f"   [DEBUG] XING Detail Error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return result

    def _extract_json_ld(self, soup: BeautifulSoup, data: Dict[str, str]) -> None:
        """Parses JSON-LD script tags for job metadata."""
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld and isinstance(json_ld.string, str):
            with contextlib.suppress(json.JSONDecodeError):
                ld_data = json.loads(json_ld.string)
                data["title"] = ld_data.get("title", data["title"])

                org = ld_data.get("hiringOrganization")
                if isinstance(org, dict):
                    data["company"] = org.get("name", data["company"])

                loc_data = ld_data.get("jobLocation", [{}])
                if isinstance(loc_data, dict):
                    loc_data = [loc_data]

                if loc_data and isinstance(loc_data, list):
                    addr = loc_data[0].get("address", {})
                    city = addr.get("addressLocality")
                    if city:
                        data["location"] = city

    def _extract_html_fallback(self, soup: BeautifulSoup, data: Dict[str, str]) -> None:
        """Parses HTML elements if JSON-LD extraction was incomplete."""
        if not data["title"]:
            h1 = soup.find("h1")
            if h1:
                data["title"] = h1.get_text(strip=True)

        if not data["description"]:
            # Expanded selectors for different XING layouts
            desc_section = (
                soup.find("div", attrs={"data-testid": "html-renderer"})
                or soup.find("section", attrs={"data-testid": "job-details-content"})
                or soup.find("div", id="job-description")
                or soup.find("main")  # Aggressive fallback
            )
            if desc_section:
                # Remove scripts and styles to clean text
                for s in desc_section(["script", "style", "nav", "header", "footer"]):
                    s.decompose()
                data["description"] = desc_section.get_text(separator="\n", strip=True)


# End of src/core/providers/xing.py (v. 00028)
