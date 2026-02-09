# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Batch Runner CLI Module.

This module contains the logic for interactively running multiple search profiles.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.engine import JobSearchEngine


class BatchRunner:
    """Class for bulk execution of search profiles."""

    def __init__(self, cv_path: str, forced_providers: Optional[List[str]] = None) -> None:
        """Initializes the BatchRunner.

        Args:
            cv_path: Path to the CV/Profile JSON file.
            forced_providers: Optional list of providers to force.
        """
        self.cv_path: str = cv_path
        self.forced_providers: Optional[List[str]] = forced_providers
        self.configs_dir: Path = Path("configs/search_profiles")

    def run_interactive(self) -> None:
        """Main interactive loop for profile selection."""
        if not self.configs_dir.exists():
            print(f"❌ Directory {self.configs_dir} does not exist!")
            return

        all_configs = list(self.configs_dir.glob("*.json"))
        if not all_configs:
            print(f"⚠️  No profiles found in {self.configs_dir}")
            return

        print("\n╔════════════════════════════════════════════════╗")
        print("║    BATCH MODE - Profile Selection              ║")
        print("╚════════════════════════════════════════════════╝")
        for i, config in enumerate(all_configs, 1):
            print(f"  {i}. {config.name}")

        print("\n[ENTER] = All  |  [1,3] = Selected  |  [q] = Quit")
        choice = input("Choice: ").lower().strip()

        if choice == "q":
            return

        profiles_to_run: List[str] = []
        if choice == "":
            profiles_to_run = [c.name for c in all_configs]
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                profiles_to_run = [all_configs[i].name for i in indices if 0 <= i < len(all_configs)]
            except (ValueError, IndexError):
                print("❌ Invalid input")
                return

        self._execute_batch(profiles_to_run)

    def _execute_batch(self, profiles: List[str]) -> None:
        """Executes a list of profiles sequentially.

        Args:
            profiles: List of profile filenames to run.
        """
        print(f"\n🚀 Running {len(profiles)} profiles...\n")
        stats: Dict[str, Any] = {}
        total_start = time.time()

        for profile in profiles:
            print(f"\n{'=' * 50}")
            print(f"▶️  PROFILE: {profile}")
            print(f"{'=' * 50}")

            try:
                engine = JobSearchEngine(
                    search_profile_name=profile, cv_path=self.cv_path, forced_providers=self.forced_providers
                )
                count = engine.run()
                stats[profile] = {"count": count, "output": str(engine.output_dir)}
            except Exception as e:
                print(f"❌ Error in profile {profile}: {e}")
                stats[profile] = {"count": 0, "error": str(e)}

        self._print_summary(stats, total_start)

    def _print_summary(self, stats: Dict[str, Any], start_time: float) -> None:
        """Prints the final summary report for the batch run.

        Args:
            stats: Dictionary containing results for each profile.
            start_time: Epoch time when the batch started.
        """
        print("\n" + "=" * 60)
        print("📊 SUMMARY REPORT (BATCH)")
        print("=" * 60)
        print(f"⏱️  Total time: {time.time() - start_time:.1f}s\n")

        total_jobs = 0
        for name, data in stats.items():
            status = f"✅ {data['count']} jobs" if "error" not in data else "❌ Error"
            print(f"🔹 {name}: {status}")
            if "output" in data:
                print(f"   📁 {data['output']}")
            total_jobs += data.get("count", 0)
            print()

        print(f"🏆 TOTAL FOUND: {total_jobs}")


# End of src/cli/batch.py (v. 00002)
