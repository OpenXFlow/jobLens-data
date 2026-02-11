# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""JobLens - AI-Powered Job Searcher.

Main entry point for the JobLens application, providing a CLI for automated
job searching and manual link evaluation.
Refactored (v. 00036) - Enhancement: Added --headless (-hm) CLI argument.
"""

import argparse
import sys
from typing import List, Optional

from src.cli.batch import BatchRunner
from src.core.engine import JobSearchEngine
from src.core.selenium_factory import SeleniumFactory


def print_banner() -> None:
    """Prints the enhanced JobLens ASCII banner to the console."""
    print(r"""
     ██╗ ██████╗ ██████╗ ██╗     ███████╗███╗   ██╗███████╗
     ██║██╔═══██╗██╔══██╗██║     ██╔════╝████╗  ██║██╔════╝
     ██║██║   ██║██████╔╝██║     █████╗  ██╔██╗ ██║███████╗
██   ██║██║   ██║██╔══██╗██║     ██╔══╝  ██║╚██╗██║╚════██║
╚█████╔╝╚██████╔╝██████╔╝███████╗███████╗██║ ╚████║███████║
 ╚════╝  ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝
    Intelligent Job Search Automation
    """)


def main() -> None:
    """Main execution function for parsing arguments and starting the engine."""
    parser = argparse.ArgumentParser(
        description="JobLens - Automated job searching and analysis tool.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--search-profile", "-sp", nargs="+", help="One or more profiles (e.g., aggressive, remote_ai)."
    )

    parser.add_argument("--batch", "-b", action="store_true", help="Start interactive menu (Batch Mode).")

    parser.add_argument("--provider", "-pr", nargs="+", help="Force specific providers (e.g., linkedin solcom).")

    parser.add_argument(
        "--cv", "-cv", default="configs/my_profile/my_profile.json", help="Path to the CV/Profile JSON file."
    )

    parser.add_argument("--input", "-in", help="Path to a CSV file with links for manual evaluation.")

    parser.add_argument(
        "--headless", "-hm", action="store_true", help="Run browser in headless mode (for Selenium providers)."
    )

    args = parser.parse_args()

    # Apply headless setting to the factory before engine initialization
    if args.headless:
        SeleniumFactory.FORCE_HEADLESS = True

    print_banner()

    # 1. Manual Evaluation Mode (Highest priority)
    if args.input:
        profile_name = args.search_profile[0] if args.search_profile else "default"
        try:
            engine = JobSearchEngine(search_profile_name=profile_name, cv_path=args.cv, forced_providers=args.provider)
            engine.run_manual_mode(args.input)
        except Exception as e:
            print(f"\n❌ Manual mode error: {e}")
            sys.exit(1)

    # 2. Interactive Batch Mode
    elif args.batch:
        BatchRunner(args.cv, args.provider).run_interactive()

    # 3. Multi-profile Batch Mode (Exact list from CLI)
    elif args.search_profile and len(args.search_profile) > 1:
        print(f"🚀 Starting a batch of {len(args.search_profile)} profiles...")
        runner = BatchRunner(args.cv, args.provider)
        runner._execute_batch(args.search_profile)

    # 4. Single Profile Mode (Default or specific)
    else:
        profile_name = args.search_profile[0] if args.search_profile else "default"
        forced_providers: Optional[List[str]] = args.provider

        try:
            engine = JobSearchEngine(
                search_profile_name=profile_name, cv_path=args.cv, forced_providers=forced_providers
            )
            engine.run()
        except Exception as e:
            print(f"\n❌ Initialization error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

# End of jobLens.py (v. 00036)
