# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Freelance.de Job Provider Module (Authenticated Scraper).

This module handles searching and data extraction from Freelance.de using
the centralized SeleniumFactory. Based on the stable v36 architecture.
Refactored (v. 00055) - Precision: Added skill badge scraping to Detail Fetch
to ensure parity in scoring between Manual and Auto modes.
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
from bs4.element import Tag
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

            # Capture full card text for initial skill matching
            full_text_description = self.card.get_text(separator=" | ", strip=True)

            # Clean the title
            clean_title = link_data["title"].split("Firmenname")[0].strip()

            return {
                "title": clean_title,
                "company": self.company,
                "location": self.location,
                "link": link_data["full_link"],
                "job_id": link_data["job_id"],
                "provider": "freelance_de",
                "posted_at_relative": self._extract_posted_date(),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": full_text_description,
                "relevance_score": 0,
                "work_location_type": (
                    "Remote" if self.remote_possible or "remote" in self.location.lower() else "On-site"
                ),
                "employment_type": "Freelance",
                "search_criteria": f"{self.query} | {self.req_loc}",
            }
        except Exception as e:
            print(f"   [DEBUG] Freelance.de parse error: {e}")
            return None

    def _extract_link_info(self) -> Optional[Dict[str, str]]:
        """Safely extracts title and link from the card header."""
        link_tag = self.card.find("a", href=re.compile(r"project\.php|projekte/"))
        if not isinstance(link_tag, Tag):
            return None

        title = link_tag.get_text(strip=True)
        href = link_tag.get("href")
        if not isinstance(href, str):
            return None

        return {
            "title": title,
            "full_link": href if href.startswith("http") else f"{self.domain}{href}",
            "job_id": href.split("/")[-1].replace("projekt-", "").split("-")[0],
        }

    def _extract_metadata(self) -> None:
        """Parses the icon-based metadata list."""
        info_list = self.card.find("ul", class_=re.compile(r"fa-ul|icon-list"))
        if not isinstance(info_list, Tag):
            return

        for li in info_list.find_all("li"):
            text = li.get_text(strip=True)
            li_str = str(li)
            if any(icon in li_str for icon in ["fa-map-marker", "fa-location"]):
                self.location = text.split("Premiumaccount")[0].strip()
            elif "fa-calendar" in li_str:
                self.start_date = text
            elif any(kw in text.lower() for kw in ["remote", "home office"]):
                self.remote_possible = True
            elif "Project Provider:" in text:
                self.company = text.replace("Project Provider:", "").strip()

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

            if not self._load_session(driver) and not self._login_attempted:
                self._login_attempted = True
                self._perform_login(driver)

            print(f"   [TRACE] [Freelance.de] Searching for {keywords} in {location}...")

            self._perform_ui_search(driver, keywords, localized_loc)
            time.sleep(random.uniform(5, 7))  # noqa: S311

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.find_all("search-project-card") or soup.find_all("div", class_="project-item")

            if not cards:
                self._dump_diagnostics(driver, f"fde_empty_{keywords[:5]}")

            print(f"   [DEBUG] [Freelance.de] Found {len(cards)} items.")

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

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches details including badges/tags to ensure scoring parity."""
        # Initialize result
        result: Union[str, Dict[str, str]] = ""

        # Stagger start
        time.sleep(random.uniform(1, 5))  # noqa: S311

        driver: Optional[uc.Chrome] = None
        try:
            driver = SeleniumFactory.setup_driver()
            if not self._load_session(driver):
                self._perform_login(driver)

            driver.get(url)
            self._handle_cookies(driver)
            time.sleep(random.uniform(3, 5))  # noqa: S311

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # 1. Description
            desc = ""
            container = (
                soup.find("div", id="project-description")
                or soup.find("div", class_="panel-body")
                or soup.find("div", class_="project-detail-content")
            )
            if container:
                desc = container.get_text(separator="\n", strip=True)

            # FIX: Scrape Skill Tags/Badges from detail page to enrich context
            skills = []
            for badge in soup.find_all(class_=re.compile(r"badge|tag|skill")):
                skills.append(badge.get_text(strip=True))
            if skills:
                desc += "\n\nSkills & Keywords: " + ", ".join(skills)

            # 2. Title
            title = ""
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True).replace(" - freelance.de", "").split("Firmenname")[0].strip()

            # 3. Metadata
            location = "Germany/Remote"
            company = "Freelance.de Client"

            meta_ul = soup.find("ul", class_=re.compile(r"fa-ul|icon-list|overview"))
            if meta_ul:
                for li in meta_ul.find_all("li"):
                    txt = li.get_text(strip=True)
                    if any(x in str(li) for x in ["fa-map-marker", "fa-location"]):
                        location = txt
                    elif "fa-building" in str(li):
                        company = txt

            result = {"description": desc, "title": title, "company": company, "location": location}

        except Exception as e:
            print(f"   [DEBUG] [Freelance.de] Detail fetch error: {e}")
        finally:
            if driver:
                self._safe_quit(driver)

        return result

    def _perform_ui_search(self, driver: uc.Chrome, keywords: str, location: str) -> None:
        """Executes search via UI with fallback."""
        wait = WebDriverWait(driver, 15)

        if "freelance.de" not in driver.current_url.lower() or "login" in driver.current_url:
            driver.get(self.BASE_URL)
            time.sleep(2)

        self._handle_cookies(driver)
        time.sleep(1)

        try:
            input_sel = "input[placeholder*='UX Design'], input[placeholder*='Java'], input[id*='search']"
            search_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, input_sel)))

            combined_query = f"{keywords} {location}"
            driver.execute_script("arguments[0].value = arguments[1];", search_input, combined_query)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
            time.sleep(0.5)

            submit_sel = "#ga4-hp-projekt-suchen, button[type='submit'], .btn-search"
            submit_btn = driver.find_element(By.CSS_SELECTOR, submit_sel)
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception:
            direct_url = (
                f"{self.BASE_URL}/search/project.php?ad_search[keywords]={keywords}&ad_search[location]={location}"
            )
            driver.get(direct_url)

    def _safe_quit(self, driver: uc.Chrome) -> None:
        """Safely terminates driver service."""
        with contextlib.suppress(Exception):
            time.sleep(0.5)
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
            return "logout" in driver.page_source.lower() or "abmelden" in driver.page_source.lower()
        except Exception:
            return False

    def _perform_login(self, driver: uc.Chrome) -> bool:
        """Performs robust login procedure."""
        with contextlib.suppress(Exception):
            profile = json.loads(Path("configs/my_profile/my_profile.json").read_text(encoding="utf-8"))
            creds = profile.get("credentials", {})
            user, pw = creds.get("freelance_de_user"), creds.get("freelance_de_pass")

            if not user or not pw:
                return False

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
            if any(kw in driver.page_source.lower() for kw in ["logout", "abmelden"]):
                with Path(self.COOKIE_FILE).open("w", encoding="utf-8") as f:
                    json.dump(driver.get_cookies(), f)
                return True
        return False

    def _handle_cookies(self, driver: uc.Chrome) -> None:
        """Removes cookie banners."""
        with contextlib.suppress(Exception):
            sel = "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, button.acceptall"
            for btn in driver.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)

    def _dump_diagnostics(self, driver: uc.Chrome, name: str) -> None:
        """Dumps debug info."""
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        with contextlib.suppress(Exception):
            Path(f"logs/debug_{ts}_{name}.html").write_text(driver.page_source, encoding="utf-8")
            driver.save_screenshot(str(Path(f"logs/debug_{ts}_{name}.png")))


# End of src/core/providers/freelance_de.py (v. 00055)
