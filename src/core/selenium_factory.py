# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Selenium Factory Module.

This module provides a centralized factory for creating configured
undetected-chromedriver instances with military-grade stealth for Headless mode.
Refactored (v. 00005) - Stealth Overhaul: Added localized headers,
language spoofing, and advanced arguments to bypass "fake geo-blocks".
"""

import os
import re
import shutil
import subprocess
import sys
from typing import Optional

import undetected_chromedriver as uc  # type: ignore


class SeleniumFactory:
    """Factory class for managing Selenium WebDriver instances."""

    @staticmethod
    def get_chrome_major_version() -> Optional[int]:
        """Detects the installed Chrome major version on the system.

        Returns:
            Optional[int]: Major version number or None if detection fails.
        """
        try:
            chrome_candidates = ["google-chrome", "google-chrome-stable", "chrome", "chromium"]
            chrome_path = None

            for candidate in chrome_candidates:
                found = shutil.which(candidate)
                if found:
                    chrome_path = found
                    break

            if chrome_path:
                # S603: Trusted input from shutil.which logic.
                cmd = [chrome_path, "--version"]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
                output = res.stdout.strip()
            elif sys.platform == "win32":
                cmd = [
                    "reg",
                    "query",
                    r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon",
                    "/v",
                    "version",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
                output = res.stdout.strip()
            else:
                return None

            match = re.search(r"(\d+)\.", output)
            if match:
                return int(match.group(1))

        except Exception as e:
            print(f"   [DEBUG] Chrome version detection error: {e}")

        return None

    @classmethod
    def setup_driver(cls) -> uc.Chrome:
        """Configures and initializes an undetected Chrome driver.

        Handles environment-specific settings with maximum stealth.

        Returns:
            uc.Chrome: Initialized driver instance.
        """
        options = uc.ChromeOptions()

        env_gha = str(os.environ.get("GITHUB_ACTIONS", "")).strip().lower()
        is_ci = env_gha == "true"

        # 1. Advanced Anti-Detection Arguments
        # We use a real-looking user agent and language
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"  # noqa: E501
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--lang=de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7")

        if is_ci:
            print("   [FACTORY] CI/Headless mode activated with Ultra-Stealth.")
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
            # Bypass specific bot checks
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument("--no-first-run")
            options.add_argument("--no-service-autorun")
            options.add_argument("--password-store=basic")
        else:
            print("   [FACTORY] Local/GUI mode activated.")

        # Standard stability flags
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.page_load_strategy = "eager"

        # Version handling
        detected_version = cls.get_chrome_major_version()
        target_version = detected_version if detected_version else (None if is_ci else 143)

        # Initialize the driver
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=target_version)

        # 2. In-browser JS Stealth Patches
        # Inject scripts to hide Selenium footprints
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """
            },
        )

        return driver


# End of src/core/selenium_factory.py (v. 00005)
