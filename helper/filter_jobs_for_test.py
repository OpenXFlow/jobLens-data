# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Standalone Consolidation Tool for Testing & Automation roles.

This script scans a user-provided directory for all 'all_jobs_raw.csv' files,
filters rows based on keywords found EXCLUSIVELY in the 'title' column, 
and merges them into a deduplicated CSV file in the script's directory.
Refactored (v. 00005) - Fixed missing headers and added master column synchronization.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


class JobConsolidator:
    """Handles recursive CSV traversal and keyword filtering specifically on Job Titles."""

    def __init__(self, search_dir: str) -> None:
        """Initializes the consolidator with paths and keywords.

        Args:
            search_dir: Absolute path to the directory to scan for CSV files.
        """
        self.search_path = Path(search_dir)
        
        # Determine the absolute directory where THIS script is located
        self.script_location = Path(__file__).resolve().parent
        
        # Output filename: YYYYMMDD_HHMM__filtered_jobs.csv
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        self.output_file = self.script_location / f"{timestamp}__filtered_jobs.csv"
        
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

        # Target keywords (case-insensitive) searched ONLY in 'title'
        self.keywords: List[str] = [
            "tester",
            "test",
            "verification",
            "testingenieur",
            "automation",
            "QA",
            "Assurance",
            "Quality",
            "testautomatisierung"
        ]

    def run(self) -> int:
        """Main execution loop for finding and filtering job records.

        Returns:
            int: Total number of unique matching jobs found.
        """
        print(f"🚀 Filtering titles in: {self.search_path}")
        
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
            print(f"✅ Complete. Found {len(unique_jobs)} unique jobs with target keywords in Title.")
            print(f"💾 File: {self.output_file.name}")
        else:
            print("⚠️  No jobs with matching keywords in 'title' were found.")

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
                    
                    if self._is_title_match(row):
                        matches.append(row)
                        seen_links.add(link)
        except Exception as e:
            print(f"   ⚠️ Skipping {path.name} due to error: {e}")
        
        return matches

    def _is_title_match(self, row: Dict[str, Any]) -> bool:
        """Checks if the 'title' column contains any of the target keywords.

        Args:
            row: Dictionary containing row data.

        Returns:
            bool: True if a keyword is found in the title.
        """
        # Strict search only in 'title' field
        job_title = str(row.get("title", "")).lower()
        
        return any(k.lower() in job_title for k in self.keywords)

    def _write_results(self, jobs: List[Dict[str, Any]], headers: List[str]) -> None:
        """Writes the filtered dataset to the script's directory.

        Args:
            jobs: List of job records.
            headers: Field names for the CSV.
        """
        with self.output_file.open("w", newline="", encoding="utf-8") as f:
            # Using master_headers to guarantee the presence of 'work_location_type'
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(jobs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python filter_jobs_for_test.py <search_directory_path>")
        sys.exit(1)
        
    target_dir = sys.argv[1]
    consolidator = JobConsolidator(target_dir)
    consolidator.run()

# End of helper/filter_jobs_for_test.py (v. 00005)