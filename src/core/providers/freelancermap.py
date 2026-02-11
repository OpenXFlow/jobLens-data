# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Freelancermap Job Provider Module.

This module handles searching and data extraction from Freelancermap.de using
the centralized SeleniumFactory and advanced React-state JSON parsing.
Refactored (v. 00023) - Clean Code: Split _extract_deep_data into sub-methods
to resolve Ruff PLR0912 (Too many branches) and improved SRP.
"""

import contextlib
import json
import os
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
            url = f"{self.BASE_URL}?query={keywords}&sort=2"
            if localized_loc:
                url += f"&location={localized_loc}"

            print(f"   [TRACE] [FM] Navigating to: {url}")
            driver.get(url)

            # S311: Standard random is safe for human-like delays (noqa)
            time.sleep(random.uniform(3, 5))  # noqa: S311
            self._handle_cookies(driver)

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
            time.sleep(0.5)
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
            link_tag = card.find("a", attrs={"data-testid": "title"})
            if not isinstance(link_tag, Tag):
                return None

            title = link_tag.get_text(strip=True)
            href = link_tag.get("href", "")
            if not isinstance(href, str):
                return None
            full_link = f"{self.DOMAIN}{href}" if href.startswith("/") else href
            job_id = href.split("/")[-1]

            city_div = card.find("div", attrs={"data-testid": "city"})
            location = city_div.get_text(" ", strip=True).replace(",", "").strip() if city_div else "Germany"

            created_tag = card.find("span", attrs={"data-testid": "created"})
            posted_at = created_tag.get_text(strip=True) if created_tag else "Recent"

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
                "work_location_type": "On-site",
                "employment_type": "Freelance",
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches full project description and company metadata."""
        if not url:
            return ""

        print(f"   [DEBUG] [FM] Fetching details: {url}")
        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()
            driver.get(url)
            time.sleep(random.uniform(3, 5))  # noqa: S311
            return self._extract_deep_data(driver.page_source)
        except Exception as e:
            print(f"   [DEBUG] [FM] Detail fetch failed: {e}")
            return ""
        finally:
            if driver:
                self._safe_quit(driver)

    def _extract_deep_data(self, html: str) -> Dict[str, str]:
        """Orchestrates parsing from multiple sources to ensure high fidelity."""
        soup = BeautifulSoup(html, "html.parser")
        result = {"description": "", "company": "", "title": "", "location": ""}

        # Priority 1: Modern React State
        self._extract_from_react_state(soup, result)

        # Priority 2: JSON-LD (Search for missing fields)
        if not result["company"] or not result["location"]:
            self._extract_from_json_ld(soup, result)

        # Priority 3: Final HTML fallbacks
        self._apply_html_fallbacks(soup, result)

        return result

    def _extract_from_react_state(self, soup: BeautifulSoup, result: Dict[str, str]) -> None:
        """Parses the 'js-react-on-rails-component' JSON script tag."""
        with contextlib.suppress(Exception):
            selector = {"class_": "js-react-on-rails-component", "data-component-name": "ProjectShow"}
            tag = soup.find("script", **selector)
            if isinstance(tag, Tag) and tag.string:
                data = json.loads(tag.string)
                project = data.get("project", {})

                result["title"] = project.get("title", "").strip()

                # Handle polymorphic company
                comp = project.get("company")
                result["company"] = comp.get("name", "").strip() if isinstance(comp, dict) else str(comp or "").strip()

                # Handle polymorphic country
                city = project.get("city", "")
                country_raw = project.get("country")
                country = country_raw.get("localizedName", "") if isinstance(country_raw, dict) else ""
                result["location"] = f"{city} {country}".strip()

                # Handle description and skills
                desc_html = project.get("description", "")
                if desc_html:
                    result["description"] = BeautifulSoup(desc_html, "html.parser").get_text(separator="\n", strip=True)

                skills = [s.get("localizedName") for s in project.get("skills", {}).get("enabled", [])]
                if skills:
                    result["description"] += "\n\nSkills: " + ", ".join(skills)

    def _extract_from_json_ld(self, soup: BeautifulSoup, result: Dict[str, str]) -> None:
        """Parses all 'application/ld+json' tags for metadata recovery."""
        with contextlib.suppress(Exception):
            for tag in soup.find_all("script", type="application/ld+json"):
                if not tag.string:
                    continue
                data = json.loads(tag.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        self._parse_job_posting_ld(item, result)

    def _parse_job_posting_ld(self, item: Dict[str, Any], result: Dict[str, str]) -> None:
        """Helper to extract specific fields from a JobPosting JSON-LD object."""
        org = item.get("hiringOrganization")
        if isinstance(org, dict) and not result["company"]:
            result["company"] = org.get("name", "").strip()

        loc = item.get("jobLocation")
        if isinstance(loc, dict) and not result["location"]:
            addr = loc.get("address", {})
            if isinstance(addr, dict):
                result["location"] = addr.get("addressLocality", "").strip()

    def _apply_html_fallbacks(self, soup: BeautifulSoup, result: Dict[str, str]) -> None:
        """Applies manual HTML parsing as a last resort."""
        if not result["company"]:
            selector = re.compile(r"/profil/firma/")
            node = soup.find("div", class_="company-name") or soup.find("a", href=selector)
            if node:
                result["company"] = node.get_text(strip=True)

        if not result["description"]:
            cont = (
                soup.find("div", class_="ql-editor")
                or soup.find("div", class_="project-body-description")
                or soup.find("div", id="project-description")
            )
            if cont:
                result["description"] = cont.get_text(separator="\n", strip=True)


# End of src/core/providers/freelancermap.py (v. 00023)
