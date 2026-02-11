# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""LinkedIn Job Provider Module.

This module handles searching and data extraction from LinkedIn's Guest API.
Refactored (v. 00011) - Compliance: Fixed missing 'random' import (F821)
and optimized try-except control flow (TRY300) after Ruff validation.
"""

import contextlib
import json
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


class LinkedInProvider:
    """Provider implementation for LinkedIn Guest API with regional constraints."""

    SEARCH_URL: str = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    HTTP_OK: int = 200
    SCRAPING_METHOD: str = "API (Requests)"

    def __init__(self, session: requests.Session) -> None:
        """Initializes the LinkedIn provider.

        Args:
            session: Shared requests session for connection pooling.
        """
        self.session = session

    def search(self, keywords: str, location: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Searches for jobs on LinkedIn using regional and remote filters.

        Args:
            keywords: Search term (e.g., "Python Developer").
            location: Geographical location key.
            limit: Maximum number of results to retrieve.

        Returns:
            List[Dict[str, Any]]: A list of normalized job dictionaries.
        """
        # Determine strict work-type filters
        # f_WT: 1=On-site, 2=Remote, 3=Hybrid
        is_remote_search = location.lower() == "remote"
        target_loc = "Germany" if is_remote_search else location

        params: Dict[str, Union[str, int]] = {
            "keywords": keywords,
            "location": target_loc,
            "f_TPR": "r2592000",
            "start": 0,
        }

        if is_remote_search:
            params["f_WT"] = "2"

        found_jobs: List[Dict[str, Any]] = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # noqa: E501
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.session.get(self.SEARCH_URL, params=params, headers=headers, timeout=30)
            if response.status_code != self.HTTP_OK:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            job_cards = soup.find_all("li")

            for card in job_cards[:limit]:
                job = self._parse_card(card)
                if job:
                    job["search_criteria"] = f"{keywords} | {location}"
                    job["provider"] = "linkedin"
                    if is_remote_search:
                        job["work_location_type"] = "Remote"
                    found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] LinkedIn Search Error: {e}")
            return []

        return found_jobs

    def _parse_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parses individual LinkedIn job card HTML with enhanced type detection.

        Args:
            card: BS4 Tag representing a single job entry.

        Returns:
            Optional[Dict[str, Any]]: Normalized job data or None if parsing fails.
        """
        job_data: Dict[str, Any] = {}
        try:
            title_tag = card.find("h3", class_="base-search-card__title")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            location_tag = card.find("span", class_="job-search-card__location")
            link_tag = card.find("a", class_="base-card__full-link")

            if not (title_tag and company_tag and location_tag and link_tag):
                return None

            href = link_tag.get("href")
            if not isinstance(href, str):
                return None

            title = title_tag.get_text(strip=True)

            # Extract additional text from badges (often contains 'Contract' or 'Remote')
            badge_text = ""
            badges = card.find_all("span", class_=re.compile(r"badge|metadata"))
            if badges:
                badge_text = " ".join([b.get_text(strip=True) for b in badges])

            job_data = {
                "title": title,
                "company": company_tag.get_text(strip=True),
                "location": location_tag.get_text(strip=True),
                "link": href.split("?")[0],
                "job_id": href.split("/")[-1].split("?")[0] if "jobs/view/" in href else href,
                "posted_at_relative": "Recent",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "",
                "relevance_score": 0,
            }

            combined_text = f"{title} {badge_text} {card.get_text()}"
        except Exception:
            return None
        else:
            # TRY300 Fix: Logic moved to else block
            job_data.update(self._detect_job_types(combined_text))
            return job_data

    def _detect_job_types(self, text: str) -> Dict[str, str]:
        """Detects work type and employment type with bilingual support.

        Args:
            text: Input string for keyword scanning.

        Returns:
            Dict[str, str]: Map containing work_location_type and employment_type.
        """
        text_lower = text.lower()

        wl = "On-site"
        remote_kws = ["remote", "home office", "home-office", "wfh", "telecommute", "mobil", "ortsunabhängig"]
        hybrid_kws = ["hybrid", "mischform", "flexibel"]

        if any(kw in text_lower for kw in remote_kws):
            wl = "Remote"
        elif any(kw in text_lower for kw in hybrid_kws):
            wl = "Hybrid"

        emp = "Full-time"
        contract_kws = ["contract", "freelance", "freiberuflich", "project", "befristet", "projektbasiert"]
        intern_kws = ["intern", "praktikant", "student", "thesis", "werkstudent"]

        if any(kw in text_lower for kw in contract_kws):
            emp = "Contract"
        elif any(kw in text_lower for kw in intern_kws):
            emp = "Internship"

        return {"work_location_type": wl, "employment_type": emp}

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Extracts job description and validates types from a detail page.

        Args:
            url: Job posting detail URL.

        Returns:
            Union[str, Dict[str, str]]: Full text or metadata dictionary.
        """
        try:
            # F821 Fix: Now random is imported
            time.sleep(random.uniform(1, 2))  # noqa: S311
            resp = self.session.get(url, timeout=15)
            if resp.status_code != self.HTTP_OK:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            description = ""

            # Strategy 1: JSON-LD
            json_tag = soup.find("script", type="application/ld+json")
            if json_tag and isinstance(json_tag.string, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    data = json.loads(json_tag.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("description"):
                            description = BeautifulSoup(item["description"], "html.parser").get_text(
                                separator="\n", strip=True
                            )
                            break

            # Strategy 2: HTML Containers
            if not description:
                selectors = ["div.show-more-less-html__markup", "section.description", "article.jobs-description"]
                for sel in selectors:
                    box = soup.select_one(sel)
                    if box:
                        description = box.get_text(separator="\n", strip=True)
                        break

            if description:
                types = self._detect_job_types(description)
                return {
                    "description": description,
                    "work_location_type": types["work_location_type"],
                    "employment_type": types["employment_type"],
                }

        except Exception as e:
            print(f"   [DEBUG] LinkedIn Description Fetch Error: {e}")

        return ""


# End of src/core/providers/linkedin.py (v. 00011)
