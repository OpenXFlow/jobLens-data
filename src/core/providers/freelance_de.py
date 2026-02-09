# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Freelance.de Job Provider Module (Authenticated Scraper).

This module handles searching and data extraction from Freelance.de using
the centralized SeleniumFactory. It supports persistent sessions via cookies
and implements a robust UI-driven search to bypass Headless redirects.
Refactored (v. 00036) - Stability: Added aggressive overlay removal and
refined UI interaction timing to ensure the first search attempt succeeds.
"""

import contextlib
import json
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


class FreelanceDeJobParser:
    """Helper class to parse a single search-project-card from Freelance.de."""

    def __init__(self, card: Tag, domain: str, query: str, req_loc: str) -> None:
        """Initializes the parser."""
        self.card = card
        self.domain = domain
        self.query = query
        self.req_loc = req_loc
        self.location = "Germany/Remote"
        self.start_date = "ASAP"
        self.company = "Freelance.de Client"
        self.remote_possible = False

    def parse(self) -> Optional[Dict[str, Any]]:
        """Parses the job card into a standardized dictionary."""
        try:
            link_data = self._extract_link_info()
            if not link_data:
                return None

            self._extract_metadata()
            description = self._build_description()
            posted_at = self._extract_posted_date()

            return {
                "title": link_data["title"],
                "company": self.company,
                "location": self.location,
                "link": link_data["full_link"],
                "job_id": link_data["job_id"],
                "provider": "freelance_de",
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": description,
                "relevance_score": 0,
                "work_location_type": "Remote"
                if self.remote_possible or "remote" in self.location.lower()
                else "On-site",
                "employment_type": "Freelance",
                "search_criteria": f"{self.query} | {self.req_loc}",
            }
        except Exception as e:
            print(f"   [DEBUG] Freelance.de parse error: {e}")
            return None

    def _extract_link_info(self) -> Optional[Dict[str, str]]:
        """Safely extracts title and link from the card header."""
        h1_tag = self.card.find("h1")
        link_tag = h1_tag.find("a") if isinstance(h1_tag, Tag) else None

        if not isinstance(link_tag, Tag):
            link_tag = self.card.find("a", href=re.compile(r"project\.php|projekte/"))

        if not isinstance(link_tag, Tag):
            return None

        title = link_tag.get_text(strip=True)
        href = link_tag.get("href")
        if not isinstance(href, str) or not href:
            return None

        return {
            "title": title,
            "full_link": href if href.startswith("http") else f"{self.domain}{href}",
            "job_id": href.split("/")[-1].replace("projekt-", ""),
        }

    def _extract_metadata(self) -> None:
        """Parses the icon-based metadata list."""
        info_list = self.card.find("ul", class_="fa-ul")
        if not isinstance(info_list, Tag):
            return

        for li in info_list.find_all("li"):
            text = li.get_text(strip=True)
            if any(icon in str(li) for icon in ["fa-map-marker-alt", "fa-location-dot"]):
                self.location = text
            elif "fa-calendar-star" in str(li):
                self.start_date = text
            elif any(kw in text.lower() for kw in ["remote", "home office", "homeoffice"]):
                self.remote_possible = True
            elif "Project Provider:" in text:
                self.company = text.replace("Project Provider:", "").strip()

    def _build_description(self) -> str:
        """Combines skill labels and preview text."""
        parts = [f"Start: {self.start_date}", f"Location: {self.location}"]
        badges = self.card.find_all("a", class_="badge")
        if badges:
            parts.append("Skills: " + ", ".join([b.get_text(strip=True) for b in badges]))

        desc_tag = self.card.find("p", class_="description")
        if isinstance(desc_tag, Tag):
            parts.append(desc_tag.get_text(separator=" ", strip=True))

        return " \n ".join(parts)

    def _extract_posted_date(self) -> str:
        """Retrieves the relative posting date."""
        time_tag = self.card.find("small", class_="time-ago")
        return time_tag.get_text(strip=True) if isinstance(time_tag, Tag) else "Recent"


class FreelanceDeProvider:
    """Provider for Freelance.de with authenticated search."""

    BASE_URL: str = "https://www.freelance.de"
    LOGIN_URL: str = "https://www.freelance.de/login.php"
    COOKIE_FILE: str = "logs/cookies_freelance_de.json"
    SCRAPING_METHOD: str = SeleniumFactory.__doc__ or "Authenticated Selenium"
    HTTP_OK: int = 200

    SUPPORTS_LOCATION_FILTER: bool = True

    # Mapping for localized search parameters
    LOCATION_MAP: ClassVar[Dict[str, str]] = {
        "Germany": "Deutschland",
        "Austria": "Österreich",
        "Switzerland": "Schweiz",
        "Remote": "Remote",
    }

    def __init__(self, session: requests.Session) -> None:
        """Initializes the provider instance."""
        self.session = session
        self._login_attempted = False
        Path("logs").mkdir(parents=True, exist_ok=True)

    def search(self, keywords: str, location: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Main search method executing authenticated flow."""
        found_jobs: List[Dict[str, Any]] = []
        localized_loc = self.LOCATION_MAP.get(location, "Deutschland")
        driver: Optional[uc.Chrome] = None

        try:
            driver = SeleniumFactory.setup_driver()

            # 1. Ensure Login / Session
            if not self._load_session(driver) and not self._login_attempted:
                self._login_attempted = True
                self._perform_login(driver)

            # 2. UI-Driven Search
            print(f"   [TRACE] [Freelance.de] Searching for {keywords} in {location}...")
            self._perform_ui_search(driver, keywords, localized_loc)

            # 3. Wait and Parse
            # S311: Standard random (noqa)
            time.sleep(random.uniform(5, 7))  # noqa: S311

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.find_all("search-project-card") or soup.find_all("div", class_="project-item")

            if not cards:
                self._dump_diagnostics(driver, f"fde_empty_{keywords[:5]}_{location[:5]}")

            print(f"   [DEBUG] [Freelance.de] Found {len(cards)} items for {location}.")

            for card in cards[:limit]:
                if isinstance(card, Tag):
                    job = FreelanceDeJobParser(card, self.BASE_URL, keywords, location).parse()
                    if job:
                        found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] [Freelance.de] Global error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return found_jobs

    def _perform_ui_search(self, driver: uc.Chrome, keywords: str, location: str) -> None:
        """Executes search via the main UI elements with aggressive overlay handling."""
        wait = WebDriverWait(driver, 15)

        # Ensure we are on home/dashboard
        if "freelance.de" not in driver.current_url.lower() or "login" in driver.current_url:
            driver.get(self.BASE_URL)
            time.sleep(2)

        self._handle_cookies(driver)
        # Extra wait for any animations to finish
        time.sleep(1)

        try:
            # 1. Fill Keywords (using JS and dispatching events)
            input_sel = "input[placeholder*='UX Design'], input[placeholder*='Java'], input[id*='search']"
            search_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, input_sel)))

            combined_query = f"{keywords} {location}"
            driver.execute_script("arguments[0].value = arguments[1];", search_input, combined_query)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
            time.sleep(0.5)

            # 2. Click Search Button
            submit_sel = "#ga4-hp-projekt-suchen, button[type='submit'], .btn-search"
            submit_btn = driver.find_element(By.CSS_SELECTOR, submit_sel)
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception as e:
            print(f"   [ERROR] UI Search failed: {e}")
            # Diagnostic screenshot to see what blocked us
            self._dump_diagnostics(driver, "search_interaction_error")
            # Fallback to direct URL
            direct_url = (
                f"{self.BASE_URL}/search/project.php?ad_search[keywords]={keywords}&ad_search[location]={location}"
            )
            driver.get(direct_url)

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates driver service."""
        with contextlib.suppress(Exception):
            driver.close()
            driver.quit()

    def _load_session(self, driver: uc.Chrome) -> bool:
        """Tries to restore session via cookies."""
        cookie_path = Path(self.COOKIE_FILE)
        if not cookie_path.exists():
            return False
        try:
            driver.get(self.BASE_URL)
            time.sleep(1)
            with cookie_path.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
                for c in cookies:
                    driver.add_cookie(c)
            driver.refresh()
            time.sleep(2)
            return "logout" in driver.page_source.lower()
        except Exception:
            return False

    def _perform_login(self, driver: uc.Chrome) -> bool:
        """Performs robust login procedure using JS clicks."""
        try:
            profile_path = Path("configs/my_profile/my_profile.json")
            if not profile_path.exists():
                return False

            profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
            creds = profile_data.get("credentials", {})
            user, pw = creds.get("freelance_de_user"), creds.get("freelance_de_pass")

            if not user or not pw:
                return False

            print("   [AUTH] [Freelance.de] Attempting login...")
            driver.get(self.LOGIN_URL)
            wait = WebDriverWait(driver, 20)

            self._handle_cookies(driver)

            u_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            p_field = driver.find_element(By.ID, "password")
            login_btn = driver.find_element(By.ID, "login")

            driver.execute_script("arguments[0].value = arguments[1];", u_field, user)
            driver.execute_script("arguments[0].value = arguments[1];", p_field, pw)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", login_btn)

            time.sleep(7)
            if "logout" in driver.page_source.lower():
                print("   [AUTH] [Freelance.de] Success.")
                with Path(self.COOKIE_FILE).open("w", encoding="utf-8") as f:
                    json.dump(driver.get_cookies(), f)
                return True
        except Exception as e:
            print(f"   [AUTH] Login failed: {e}")

        return False

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Removes cookie banners and overlays via JS."""
        with contextlib.suppress(Exception):
            selectors = [
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                "button.acceptall",
                ".cookie-accept-all",
                ".modal-backdrop",
                ".modal-close",
            ]
            for selector in selectors:
                btns = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in btns:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Dumps page source and screenshot for debugging."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        log_path = Path(f"logs/debug_{ts}_{name}.html")
        log_path.write_text(driver.page_source, encoding="utf-8")
        img_path = Path(f"logs/debug_{ts}_{name}.png")
        with contextlib.suppress(Exception):
            driver.save_screenshot(str(img_path))

    def fetch_full_description(self, _url: str) -> str:
        """Stub for future enrichment."""
        return ""


# End of src/core/providers/freelance_de.py (v. 00036)
