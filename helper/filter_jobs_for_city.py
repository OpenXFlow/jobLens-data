# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Standalone Consolidation Tool for City-based job filtering.

This script scans a user-provided directory for all 'all_jobs_raw.csv' files,
filters rows based on city keywords found in ANY column, 
and merges them into a deduplicated CSV file in the script's directory.
Refactored (v. 00002) - Fixed missing headers and added master column synchronization.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


class CityJobFilter:
    """Handles recursive CSV traversal and keyword filtering across all columns."""

    def __init__(self, search_dir: str) -> None:
        """Initializes the filter with paths and city keywords.

        Args:
            search_dir: Absolute path to the directory to scan for CSV files.
        """
        self.search_path = Path(search_dir)
        
        # Determine the absolute directory where THIS script is located
        self.script_location = Path(__file__).resolve().parent
        
        # Output filename: YYYYMMDD_HHMM__filtered_jobs_city.csv
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        self.output_file = self.script_location / f"{timestamp}__filtered_jobs_city.csv"
        
        # Master headers to ensure consistency with engine.py v3.3.7
        self.master_headers: List[str] = [
            "relevance_score",
            "search_criteria",
            "provider",
            "title",
            "company",
            "location",
            "work_location_type",
            "employment_type",
            "matching_skills",
            "missing_skills",
            "detected_languages",
            "matched_roles",
            "salary_hint",
            "posted_at_relative",
            "link",
            "scraped_at",
        ]

        # Target cities (case-insensitive) searched in ALL columns
        self.cities: List[str] = [
            "vienna",
            "graz",
            "linz",
            "munchen"
        ]

    def run(self) -> int:
        """Main execution loop for finding and filtering job records by city.

        Returns:
            int: Total number of unique matching jobs found.
        """
        print(f"🚀 Filtering cities in: {self.search_path}")
        print(f"📂 Output will be saved to: {self.script_location}")
        
        if not self.search_path.exists() or not self.search_path.is_dir():
            print(f"❌ Error: Target directory '{self.search_path}' not found.")
            return 0

        # Find all raw CSV files recursively
        raw_files = list(self.search_path.glob("**/all_jobs_raw.csv"))
        print(f"📂 Found {len(raw_files)} 'all_jobs_raw.csv' files.")

        unique_jobs: List[Dict[str, Any]] = []
        seen_links: Set[str] = set()

        for csv_path in raw_files:
            matches = self._process_file(csv_path, seen_links)
            if matches:
                unique_jobs.extend(matches)

        if unique_jobs:
            self._write_results(unique_jobs, self.master_headers)
            print(f"✅ Filter complete. Found {len(unique_jobs)} unique jobs in target cities.")
            print(f"💾 File created: {self.output_file.name}")
        else:
            print("⚠️  No jobs matching the city criteria were found.")

        return len(unique_jobs)

    def _process_file(self, path: Path, seen_links: Set[str]) -> List[Dict[str, Any]]:
        """Reads a CSV and returns matching rows, skipping existing URLs.

        Args:
            path: Path to a specific all_jobs_raw.csv.
            seen_links: Set for URL deduplication.

        Returns:
            List[Dict[str, Any]]: List of matching records.
        """
        matches = []
        try:
            with path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    link = row.get("link", "")
                    if not link or link in seen_links:
                        continue
                    
                    if self._is_city_match(row):
                        matches.append(row)
                        seen_links.add(link)
        except Exception as e:
            print(f"   ⚠️ Skipping {path.name} due to error: {e}")
        
        return matches

    def _is_city_match(self, row: Dict[str, Any]) -> bool:
        """Checks if ANY column in the row contains any of the target city keywords.

        Args:
            row: Dictionary containing row data.

        Returns:
            bool: True if a city keyword is found anywhere in the row.
        """
        # Join all values into one string and search
        row_content = " ".join(str(val) for val in row.values()).lower()
        
        return any(city.lower() in row_content for city in self.cities)

    def _write_results(self, jobs: List[Dict[str, Any]], headers: List[str]) -> None:
        """Writes the filtered dataset to the script's directory.

        Args:
            jobs: List of job records.
            headers: Field names for the CSV.
        """
        with self.output_file.open("w", newline="", encoding="utf-8") as f:
            # extrasaction="ignore" ensures that if a row is missing a column, it won't crash
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(jobs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python filter_jobs_for_city.py <search_directory_path>")
        sys.exit(1)
        
    target_dir = sys.argv[1]
    consolidator = CityJobFilter(target_dir)
    consolidator.run()

# End of helper/filter_jobs_for_city.py (v. 00002)