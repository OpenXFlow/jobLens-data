# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""XING Job Provider Module (Advanced Scraper).

This module handles searching and data extraction from XING.com using
the centralized SeleniumFactory.
Refactored (v. 00025) - Stability: Improved process cleanup to prevent
'WinError 6' noise in Windows console during driver termination.
"""

import contextlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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

            print(f"   [DEBUG] Opening XING: {query_url}")
            driver.get(query_url)

            # 1. Handle Cookie Consent
            with contextlib.suppress(Exception):
                time.sleep(2)
                cookie_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='uc-accept-all']"))
                )
                driver.execute_script("arguments[0].click();", cookie_btn)
                time.sleep(1)

            # 2. Wait for content
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            job_articles = soup.find_all("article")
            print(f"   [DEBUG] Items found via XING Selenium: {len(job_articles)}")

            for card in job_articles[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)

        except Exception as e:
            print(f"   [DEBUG] XING Selenium Error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates the driver to avoid WinError 6 noise.

        Args:
            driver: The active Chrome driver instance.
        """
        with contextlib.suppress(Exception):
            driver.close()
            driver.quit()

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Extracts basic job data from a card.

        Args:
            card: BeautifulSoup Tag of the job card.
            query: Current query string.
            req_loc: Requested location string.

        Returns:
            Optional[Dict[str, Any]]: Partial job data.
        """
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

    def fetch_full_description(self, url: str) -> str:
        """Fetches description and extracts accurate metadata including large salary ranges.

        Args:
            url: Job detail URL.

        Returns:
            str: Description with embedded metadata tags.
        """
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != self.HTTP_OK:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            page_text = soup.get_text()

            # 1. Metadata Extraction via JSON-LD
            meta_prefix = ""
            json_ld = soup.find("script", type="application/ld+json")
            if json_ld and isinstance(json_ld.string, str):
                with contextlib.suppress(json.JSONDecodeError):
                    data = json.loads(json_ld.string)
                    org = data.get("hiringOrganization")
                    company = org.get("name") if isinstance(org, dict) else None
                    if company:
                        meta_prefix += f"[COMPANY]{company}[/COMPANY]"

                    loc_data = data.get("jobLocation", [{}])
                    if isinstance(loc_data, list) and loc_data:
                        city = loc_data[0].get("address", {}).get("addressLocality")
                        if city:
                            meta_prefix += f"[LOCATION]{city}[/LOCATION]"

            # 2. Advanced Salary Extraction (Improved regex for thousands)
            salary_text = ""
            num_pattern = r"\d{1,3}(?:[.,]\d{3})*"
            salary_range_pattern = rf"(?:€|EUR)\s?({num_pattern}).*?(?:to|bis|-)\s?(?:€|EUR)\s?({num_pattern})"

            s_match = re.search(salary_range_pattern, page_text, re.IGNORECASE)
            if s_match:
                low, high = s_match.groups()
                salary_text = f"[SALARY]{low} - {high} EUR[/SALARY]"
            else:
                forecast_match = re.search(rf"Salary forecast:.*?({num_pattern}).*?({num_pattern})", page_text)
                if forecast_match:
                    low, high = forecast_match.groups()
                    salary_text = f"[SALARY]{low} - {high} EUR[/SALARY]"

            # 3. Extract Job Description text
            desc_section = (
                soup.find("section", attrs={"data-testid": "job-details-content"})
                or soup.find("div", id="job-description")
                or soup.find("div", class_="job-description")
            )

            main_text = desc_section.get_text(separator="\n", strip=True) if desc_section else ""

        except Exception:
            return ""
        else:
            return f"{meta_prefix}{salary_text}\n{main_text}"


# End of src/core/providers/xing.py (v. 00025)
