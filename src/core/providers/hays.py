# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Hays.de Job Provider Module.

This module handles searching and data extraction from Hays.de using
standard requests and BeautifulSoup for HTML parsing.
Refactored (v. 00013) - Bugfix: Fixed location overwriting issue in enrichment.
Now extracts detailed location or preserves existing one if not found.
"""

import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

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

        # Random sleep to be polite
        time.sleep(random.uniform(1, 2))  # noqa: S311

        try:
            # Use specific headers to avoid generic bot blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # noqa: E501
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            response = self.session.get(self.BASE_URL, params=params, headers=headers, timeout=30)

            if response.status_code != self.HTTP_OK:
                print(f"   [DEBUG] Hays search failed with status: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", class_="search__result")

            print(f"   [DEBUG] [Hays] Found {len(cards)} items.")

            for card in cards[:limit]:
                if isinstance(card, Tag):
                    job_data = self._parse_card(card, keywords, location)
                    if job_data:
                        found_jobs.append(job_data)
        except Exception as e:
            print(f"   [DEBUG] Hays search error: {e}")
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
            job_id = link.split("/")[-2] if "/job/" in link else link.split("-")[-1].replace("/", "")

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

            # Extract teaser text for initial scoring
            description = ""
            teaser = card.find("div", class_="search__result__teaser")
            if teaser:
                description = teaser.get_text(separator=" ", strip=True)

            return {
                "title": title,
                "company": "Hays Client",
                "location": location,
                "link": link,
                "job_id": job_id,
                "provider": "hays",
                "posted_at_relative": posted_at,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "description": description,  # Populated for Phase 1 scoring
                "relevance_score": 0,
                "work_location_type": "Remote"
                if any(kw in (title + location).lower() for kw in ["remote", "home office", "mobil"])
                else "On-site",
                "employment_type": "Contract",
                "search_criteria": f"{query} | {req_loc}",
            }
        except Exception:
            return None

    def fetch_full_description(self, url: str) -> Union[str, Dict[str, str]]:
        """Fetches and cleans the full description from the Hays detail page."""
        # Initialize result
        result: Dict[str, str] = {}

        # Random sleep to avoid WAF blocking
        time.sleep(random.uniform(0.5, 2.0))  # noqa: S311

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # noqa: E501
                "Referer": self.BASE_URL,
            }
            resp = self.session.get(url, headers=headers, timeout=15)

            if resp.status_code != self.HTTP_OK:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")

            # Try multiple selectors for description
            container = (
                soup.find("div", class_="job-description__content")
                or soup.find("div", class_="h-text")
                or soup.find("section", class_="job-description")
                or soup.find("div", class_="job-details-content")
                or soup.find("article")
            )

            if container:
                # Cleanup scripts/styles
                for s in container(["script", "style", "iframe", "noscript"]):
                    s.decompose()
                result["description"] = container.get_text(separator="\n", strip=True)

            # Only if description was found, proceed to extract metadata
            if result.get("description"):
                # 1. Title
                h1 = soup.find("h1")
                if h1:
                    result["title"] = h1.get_text(strip=True)

                result["company"] = "Hays Client"

                # 2. Location (Try to find it, otherwise do NOT add key to result)
                # Strategy: Search for header location or specific text in labels
                loc_node = soup.find("div", class_="job-details__header-location")
                if loc_node:
                    result["location"] = loc_node.get_text(strip=True)
                else:
                    # Fallback to searching text
                    for span in soup.find_all("span"):
                        if "Einsatzort" in span.get_text():
                            parent = span.parent
                            if parent:
                                result["location"] = parent.get_text(strip=True).replace("Einsatzort", "").strip()
                                break

        except Exception as e:
            print(f"   [DEBUG] Hays Fetch Error: {e}")

        # Return dict only if we have data, otherwise empty string
        return result if result else ""


# End of src/core/providers/hays.py (v. 00013)
