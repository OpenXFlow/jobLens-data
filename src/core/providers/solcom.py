# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""SOLCOM Job Provider Module (Undetected Selenium).

This module handles searching and data extraction from SOLCOM.de.
Refactored (v. 00050) - Deep Extraction Strategy: Shifted focus to Detail Page 
scraping. Now extracts all text relative to the H1 header to capture hidden skills.
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
from selenium.webdriver.common.keys import Keys  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from src.core.selenium_factory import SeleniumFactory


class SolcomProvider:
    """Provider implementation for SOLCOM using Deep Detail Extraction."""

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
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the Solcom provider.

        Args:
            session: Shared requests session.
        """
        self.session = session
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for jobs using direct URL parameters (Phase 1: Link Collection)."""
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Deutschland")
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            
            # Construct URL with parameters
            base_p = "--contenance_solcom-portal_project_index"
            query_url = (
                f"{self.BASE_URL}?"
                f"{base_p}[searchArguments][searchParameter]={keywords}&"
                f"{base_p}[searchArguments][location]={localized_loc}&"
                f"{base_p}[itemsPerPage]={limit}"
            )
            
            print(f"   [TRACE] [SOLCOM] Navigating directly to: {query_url}")
            driver.get(query_url)

            # 1. Handle Cookie Consent
            time.sleep(3)
            self._handle_cookies(driver)

            # 2. Check for Geo-Block
            time.sleep(1)
            if self._is_geo_blocked(driver):
                print(f"   [ERROR] [SOLCOM] Geo-blocked! Access from {localized_loc} is restricted.")
                self._dump_diagnostics(driver, f"solcom_geoblock_{keywords}")
                return []

            # Wait for results to render
            time.sleep(random.uniform(5, 7))  # noqa: S311
            self._nuke_overlays(driver)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            item_class = "contenance-solcom-portal-project-item"
            items = soup.find_all("div", class_=item_class)

            if not items:
                self._dump_diagnostics(driver, f"solcom_zero_{keywords}")
            else:
                print(f"   [DEBUG] [SOLCOM] Found {len(items)} items. Collecting links for deep enrichment...")
                for card in items[:limit]:
                    job = self._parse_card(card, keywords, location)
                    if job:
                        found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] [SOLCOM] Global search failed: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _is_geo_blocked(self, driver: uc.Chrome) -> bool:
        """Detects if the access is blocked based on country/IP."""
        block_keywords = ["Kundeninformation", "Customer Information", "Ihrem Land aktuell nicht"]
        page_text = driver.page_source
        return any(kw in page_text or kw in driver.title for kw in block_keywords)

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Attempts to accept cookie consent banner."""
        with contextlib.suppress(Exception):
            selectors = ["button#uc-btn-accept-banner", "button.uc-btn-accept", "button[id*='accept']"]
            for sel in selectors:
                btns = driver.find_elements(By.CSS_SELECTOR, sel)
                for b in btns:
                    if b.is_displayed():
                        driver.execute_script("arguments[0].click();", b)
                        time.sleep(1)
                        return

    def _nuke_overlays(self, driver: uc.Chrome) -> None:
        """Removes blocking dialogs and banners via JS injection."""
        script = """
        const selectors = [
            '#uc-center-container', '.modal-backdrop',
            '#onetrust-banner-sdk', '.cookie-banner',
            '#uc-btn-accept-banner'
        ];
        selectors.forEach(s => {
            const el = document.querySelector(s);
            if (el) el.remove();
        });
        document.body.style.overflow = 'auto';
        """
        with contextlib.suppress(Exception):
            driver.execute_script(script)

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Parses a project card from list view."""
        try:
            h_div = card.find("div", class_="project-header")
            link_tag = h_div.find("a") if h_div else None
            if not isinstance(link_tag, Tag): return None

            title_tag = link_tag.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            href = link_tag.get("href", "")
            full_link = f"{self.DOMAIN}{href}" if href.startswith("/") else str(href)

            # Note: List view description is empty/weak. We rely on fetch_full_description.
            location = "Germany"
            info_list = card.find("div", class_="project-infos")
            if info_list:
                pin = info_list.find("li", class_="pin-icon")
                if pin: location = pin.get_text(strip=True)

            return {
                "title": title,
                "company": "SOLCOM Client",
                "location": location,
                "link": full_link,
                "job_id": str(href.split("/")[-1]),
                "provider": "solcom",
                "posted_at_relative": "Recent",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "", # Will be filled in Phase 3
                "relevance_score": 0,
                "work_location_type": "Remote" if "remote" in title.lower() else "On-site",
                "employment_type": "Freelance",
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches full description by extracting ALL text relative to the main H1 header."""
        result_data: Dict[str, str] = {}
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()
            driver.get(url)
            # Give it time to load dynamic content
            time.sleep(5) 
            self._nuke_overlays(driver)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Strategy: Find the main Title (H1) and grab the parent container's text
            h1 = soup.find("h1")
            
            if h1:
                # Find the main content area (usually 2 or 3 levels up from H1)
                container = h1.find_parent("div", class_=re.compile(r"content|main|project"))
                
                # Fallback: specific Solcom detail classes
                if not container:
                    container = soup.find("div", class_="project-details") or \
                                soup.find("div", class_="description-content")

                if container:
                    # Extract list items specifically (where skills are hidden)
                    skills_list = [li.get_text(strip=True) for li in container.find_all("li")]
                    
                    full_text = container.get_text(separator="\n", strip=True)
                    enriched_text = f"{full_text}\n\nSKILLS EXTRACT:\n" + "\n".join(skills_list)

                    result_data = {
                        "description": enriched_text,
                        "company": "SOLCOM Client",
                        "title": h1.get_text(strip=True)
                    }
        except Exception as e:
            print(f"   [DEBUG] [SOLCOM] Detail fetch error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return result_data if result_data else ""

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Terminates the driver instance safely."""
        with contextlib.suppress(Exception):
            time.sleep(0.5)
            driver.quit()

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Captures troubleshoot data."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        with contextlib.suppress(Exception):
            log_path = Path(f"logs/debug_{ts}_{name}.html")
            log_path.write_text(driver.page_source, encoding="utf-8")
            driver.save_screenshot(str(Path(f"logs/debug_{ts}_{name}.png")))


# End of src/core/providers/solcom.py (v. 00050)