# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""LinkedIn Job Provider Module.

This module handles searching and data extraction from LinkedIn's Guest API.
Refactored (v00007) - Compliance: Fixed docstrings, exception handling, and flow control.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


class LinkedInProvider:
    """Provider implementation for LinkedIn Guest API."""

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
        """Searches for jobs on LinkedIn using the guest API.

        Args:
            keywords: Search term (e.g., "Python Developer").
            location: Geographical location.
            limit: Maximum number of results to retrieve.

        Returns:
            List[Dict[str, Any]]: A list of normalized job dictionaries.
        """
        params: Dict[str, Union[str, int]] = {
            "keywords": keywords,
            "location": location,
            "f_TPR": "r2592000",  # Posted in last month
            "f_JT": "F",  # Job Type filter (F=Full-time, C=Contract)
            "start": 0,
        }
        found_jobs: List[Dict[str, Any]] = []

        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            if response.status_code != self.HTTP_OK:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            job_cards = soup.find_all("li")

            for card in job_cards[:limit]:
                job = self._parse_card(card)
                if job:
                    job["search_criteria"] = f"{keywords} | {location}"
                    job["provider"] = "linkedin"
                    found_jobs.append(job)

        except Exception as e:
            print(f"   [DEBUG] LinkedIn Search Error: {e}")
            return []

        return found_jobs

    def _parse_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parses individual LinkedIn job card HTML.

        Args:
            card: BeautifulSoup Tag representing a single job list item.

        Returns:
            Optional[Dict[str, Any]]: Job data dictionary or None if parsing fails.
        """
        try:
            title_tag = card.find("h3", class_="base-search-card__title")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            location_tag = card.find("span", class_="job-search-card__location")
            link_tag = card.find("a", class_="base-card__full-link")

            if not (title_tag and company_tag and location_tag and link_tag):
                return None

            posted_tag = card.find("time") or card.find("span", class_="job-search-card__listdate")
            posted_at = posted_tag.get_text().strip() if posted_tag else "Unknown"

            href = link_tag.get("href")
            if not isinstance(href, str):
                return None

            # Clean link (remove tracking params)
            link = href.split("?")[0]

            title = title_tag.get_text().strip()
            company = company_tag.get_text().strip()
            location = location_tag.get_text().strip()

            job_data = {
                "title": title,
                "company": company,
                "location": location,
                "link": link,
                "job_id": link.split("/")[-1] if "jobs/view/" in link else link,
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": "",
                "relevance_score": 0,
            }
        except Exception:
            return None

        # Logic moved outside try-except block to satisfy TRY300
        job_data.update(self._detect_job_types(title, card.get_text()))
        return job_data

    def _detect_job_types(self, title: str, full_text: str) -> Dict[str, str]:
        """Detects work type and employment type from text."""
        text_lower = (title + " " + full_text).lower()
        wl = "Remote" if any(kw in text_lower for kw in ["remote", "home office", "wfh"]) else "On-site"
        if "hybrid" in text_lower:
            wl = "Hybrid"
        emp = "Contract" if any(kw in text_lower for kw in ["contract", "freelance"]) else "Full-time"
        if "intern" in text_lower:
            emp = "Internship"
        return {"work_location_type": wl, "employment_type": emp}

    def fetch_full_description(self, url: str) -> str:
        """Extracts job description from a LinkedIn detail page.

        Args:
            url: The URL of the job posting.

        Returns:
            str: The raw text description of the job.
        """
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != self.HTTP_OK:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")

            # Strategy 1: JSON-LD
            try:
                json_tag = soup.find("script", type="application/ld+json")
                if json_tag and isinstance(json_tag.string, str):
                    data = json.loads(json_tag.string)
                    raw_desc = data.get("description", "")
                    if raw_desc:
                        return BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n", strip=True)
            except (json.JSONDecodeError, TypeError):
                pass

            # Strategy 2: HTML classes
            for cls in ["show-more-less-html__markup", "description__text"]:
                box = soup.find("div", class_=cls)
                if box:
                    return box.get_text(separator="\n", strip=True)

        except Exception as e:
            # Fix S110: Log error instead of silent pass
            print(f"   [DEBUG] Description Fetch Error: {e}")

        return ""


# End of src/core/providers/linkedin.py (v. 00007)
