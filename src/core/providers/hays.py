# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Hays.de Job Provider Module.

This module handles searching and data extraction from Hays.de using
standard requests and BeautifulSoup for HTML parsing.
Refactored (v00011) - Compliance: Added missing docstrings and fixed error handling.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


class HaysProvider:
    """Provider implementation for Hays.de using BeautifulSoup HTML scraping."""

    BASE_URL: str = "https://www.hays.de/jobsuche/stellenangebote-jobs"
    DOMAIN: str = "https://www.hays.de"
    HTTP_OK: int = 200
    SCRAPING_METHOD: str = "HTML Scraper (BeautifulSoup)"

    def __init__(self, session: requests.Session) -> None:
        """Initializes the Hays provider.

        Args:
            session: Shared requests session for connection pooling.
        """
        self.session = session

    def search(self, keywords: str, location: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for jobs on Hays.de.

        Args:
            keywords: Search query (e.g. "Python").
            location: Location filter.
            limit: Maximum number of results to fetch.

        Returns:
            List[Dict[str, Any]]: List of normalized job dictionaries.
        """
        params: Dict[str, Any] = {"q": keywords, "r": location if location else "", "page": 1}
        found_jobs: List[Dict[str, Any]] = []
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            if response.status_code != self.HTTP_OK:
                return []
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", class_="search__result")
            for card in cards[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)
        except Exception:
            return []
        return found_jobs

    def _parse_card(self, card: Tag, query: str, req_loc: str) -> Optional[Dict[str, Any]]:
        """Extracts summary data from an HTML card."""
        try:
            t_tag = card.find("h4", class_="search__result__header__title")
            if not t_tag:
                return None
            title = t_tag.get_text(strip=True)
            link_tag = card.find("a", class_="search__result__link")
            if not isinstance(link_tag, Tag):
                return None
            href = link_tag.get("href")
            if not isinstance(href, str):
                return None
            link = href if href.startswith("http") else f"{self.DOMAIN}{href}"
            job_id = link.split("-")[-1].replace("/", "")
            location = "Germany"
            loc_container = card.find("div", class_="search__result__job__attribute__location")
            if isinstance(loc_container, Tag):
                info = loc_container.find("div", class_="info-text")
                if info:
                    location = info.get_text(strip=True)
            posted_at = "Recent"
            for r in card.find_all("div", class_="row"):
                if "Online seit" in r.get_text():
                    posted_at = r.get_text().replace("Online seit:", "").strip()
                    break
            return {
                "title": title,
                "company": "Hays Client",
                "location": location,
                "link": link,
                "job_id": job_id,
                "provider": "hays",
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "",
                "relevance_score": 0,
                "work_location_type": "Remote"
                if any(kw in (title + location).lower() for kw in ["remote", "home office", "mobil"])
                else "On-site",
                "employment_type": "Contract",
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> str:
        """Fetches and cleans the full description from the Hays detail page.

        Args:
            url: The URL of the job details.

        Returns:
            str: Cleaned description text.
        """
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != self.HTTP_OK:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            container = (
                soup.find("div", class_="job-description__content")
                or soup.find("div", class_="h-text")
                or soup.find("section", class_="job-description")
                or soup.find("article")
            )
            if container:
                for s in container(["script", "style"]):
                    s.decompose()
                return container.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"   [DEBUG] Hays Fetch Error: {e}")
        return ""


# End of src/core/providers/hays.py (v. 00011)
