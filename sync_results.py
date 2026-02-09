# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# Job Searcher Project

"""Standalone Synchronization & Maintenance Script.

Handles the full data lifecycle:
1. Syncs latest results from outputs/ to global database.
2. Rotates/Archives old records from global database (180 days limit).
3. Refreshes the Excel Dashboard.
4. Cleans up old detail folders in outputs/ (14 days limit).
"""

from src.core.engine import JobSearchEngine
from src.utils.persistence_manager import PersistenceManager


def main() -> None:
    """Main execution function for comprehensive system maintenance."""
    print("\n" + "=" * 60)
    print("🔄 JOBLENS SYSTEM MAINTENANCE & SYNC")
    print("=" * 60)

    # Initialize Engine to retrieve standardized headers
    engine = JobSearchEngine()
    headers = engine.get_csv_headers()
    pm = PersistenceManager()

    # 1. Sync from folders
    print("   [STEP 1/4] Syncing new unique jobs to database...")
    total_new = pm.sync_all_from_outputs("outputs", headers)

    # 2. Rotate Database (Archive items older than 180 days)
    print("   [STEP 2/4] Checking database for records to archive (180d limit)...")
    archived = pm.rotate_results_database(retention_days=180)

    # 3. Generate Excel Dashboard
    print("   [STEP 3/4] Refreshing current Excel Dashboard...")
    excel_file = pm.export_to_excel()

    # 4. Cleanup old outputs (Rolling window: 14 days)
    print("   [STEP 4/4] Cleaning up old output folders (14d limit)...")
    deleted = pm.cleanup_old_outputs("outputs", retention_days=14)

    print("-" * 60)
    if excel_file:
        summary = (
            f"🏆 SUMMARY:\n"
            f"   - {total_new} new jobs synced\n"
            f"   - {archived} records moved to history\n"
            f"   - {deleted} old folders deleted\n"
            f"   - Dashboard: {excel_file}"
        )
        print(summary)
    else:
        print("⚠️  Maintenance finished. Note: Global database is empty.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

# End of sync_results.py (v. 00006)
