# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# Job Searcher Project

"""Persistence Manager Module.

This module handles cumulative storage, multi-portal synchronization,
rolling directory cleanup, and automated database rotation/archiving.
"""

import contextlib
import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd  # type: ignore


class PersistenceManager:
    """Manages global result storage, deduplication, and automated data lifecycle."""

    def __init__(self, results_dir: str = "results", filename: str = "all_found_jobs.csv") -> None:
        """Initializes the manager and ensures directories exist.

        Args:
            results_dir: Path to the results directory.
            filename: Name of the cumulative CSV file.
        """
        self.results_path = Path(results_dir)
        self.history_path = self.results_path / "history"
        self.global_file = self.results_path / filename

        self.results_path.mkdir(parents=True, exist_ok=True)
        self.history_path.mkdir(parents=True, exist_ok=True)

    def _get_existing_links(self) -> Set[str]:
        """Reads the global CSV and returns a set of all unique job links."""
        links: Set[str] = set()
        if not self.global_file.exists():
            return links

        with contextlib.suppress(FileNotFoundError, StopIteration, KeyError, csv.Error), self.global_file.open(
            "r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            for row in reader:
                link = row.get("link")
                if link:
                    links.add(str(link))
        return links

    def update_cumulative_results(self, new_jobs: List[Dict[str, Any]], headers: List[str]) -> int:
        """Appends new unique jobs to the global CSV file."""
        if not new_jobs:
            return 0

        existing_links = self._get_existing_links()
        to_append = []

        for job in new_jobs:
            link = str(job.get("link", ""))
            if link and link not in existing_links:
                to_append.append(job)
                existing_links.add(link)

        if not to_append:
            return 0

        file_exists = self.global_file.exists()
        with self.global_file.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerows(to_append)

        return len(to_append)

    def sync_all_from_outputs(self, outputs_dir: str, headers: List[str]) -> int:
        """Scans the outputs directory and syncs all found jobs to CSV."""
        out_path = Path(outputs_dir)
        if not out_path.exists():
            return 0

        total_new = 0
        for folder in out_path.iterdir():
            if not folder.is_dir():
                continue

            json_file = folder / "jobs.json"
            if not json_file.exists():
                json_file = folder / "all_jobs_raw.json"

            if json_file.exists():
                try:
                    with json_file.open("r", encoding="utf-8") as f:
                        jobs = json.load(f)
                        if isinstance(jobs, list):
                            count = self.update_cumulative_results(jobs, headers)
                            if count > 0:
                                print(f"   [SYNC] Found {count} new jobs in {folder.name}")
                            total_new += count
                except Exception as e:
                    print(f"   [SYNC] Error processing {json_file}: {e}")

        return total_new

    def rotate_results_database(self, retention_days: int = 180) -> int:
        """Archives records older than the retention period to the history folder.

        Args:
            retention_days: Number of days to keep in the active CSV.

        Returns:
            int: Number of archived records.
        """
        if not self.global_file.exists():
            return 0

        df = pd.read_csv(self.global_file)
        if "scraped_at" not in df.columns:
            return 0

        # Convert to datetime and calculate threshold
        df["scraped_at_dt"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=retention_days)

        # Split data
        archived_df = df[df["scraped_at_dt"] < cutoff].copy()
        active_df = df[df["scraped_at_dt"] >= cutoff].copy()

        if archived_df.empty:
            return 0

        # Prepare archive filenames based on date range
        min_date = archived_df["scraped_at_dt"].min().strftime("%Y%m")
        max_date = archived_df["scraped_at_dt"].max().strftime("%Y%m")
        base_name = f"{min_date}_{max_date}_archived_jobs"

        # Drop temporary datetime column before saving
        archived_df = archived_df.drop(columns=["scraped_at_dt"])
        active_df = active_df.drop(columns=["scraped_at_dt"])

        # Save to cold storage (History)
        archived_df.to_csv(self.history_path / f"{base_name}.csv", index=False)
        with pd.ExcelWriter(self.history_path / f"{base_name}.xlsx", engine="openpyxl") as writer:
            archived_df.to_excel(writer, sheet_name="ARCHIVE", index=False)

        # Overwrite global file with remaining active records
        active_df.to_csv(self.global_file, index=False)

        print(f"   [ROTATION] Archived {len(archived_df)} records to {base_name}")
        return len(archived_df)

    def cleanup_old_outputs(self, outputs_dir: str, retention_days: int = 14) -> int:
        """Deletes directories in the outputs folder older than the retention period."""
        out_path = Path(outputs_dir)
        if not out_path.exists():
            return 0

        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=retention_days)
        deleted_count = 0

        for folder in out_path.iterdir():
            if not folder.is_dir():
                continue

            try:
                date_str = folder.name.split("_")[0]
                folder_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)

                if folder_date < cutoff_date:
                    shutil.rmtree(folder)
                    print(f"   [CLEANUP] Deleted folder: {folder.name}")
                    deleted_count += 1
            except (ValueError, IndexError):
                continue
            except Exception as e:
                print(f"   [CLEANUP] Failed to delete {folder.name}: {e}")

        return deleted_count

    def export_to_excel(self, excel_filename: str = "JobLens_Dashboard.xlsx") -> str:
        """Exports the current global CSV to a multi-tab Excel dashboard."""
        if not self.global_file.exists():
            return ""

        excel_path = self.results_path / excel_filename
        df = pd.read_csv(self.global_file)

        if "relevance_score" in df.columns:
            df = df.sort_values(by="relevance_score", ascending=False)

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="ALL_JOBS", index=False)
            if "provider" in df.columns:
                providers = df["provider"].unique()
                for provider in providers:
                    sheet_name = str(provider).upper()[:30]
                    provider_df = df[df["provider"] == provider]
                    provider_df.to_excel(writer, sheet_name=sheet_name, index=False)

        return str(excel_path)


# End of src/utils/persistence_manager.py (v. 00010)
