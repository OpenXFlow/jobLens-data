# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Provider Registry Module.

This module acts as a Factory/Registry for all available job providers.
It decouples the main Engine from specific provider implementations and
provides logic to identify providers based on URL patterns.
Refactored (v. 00027) - Enhancement: Added URL-to-Provider mapping logic.
"""

from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type, Union

import requests

# Import all provider classes
from src.core.providers.ferchau import FerchauProvider
from src.core.providers.freelance_de import FreelanceDeProvider
from src.core.providers.freelancermap import FreelancermapProvider
from src.core.providers.gulp import GulpProvider
from src.core.providers.hays import HaysProvider
from src.core.providers.linkedin import LinkedInProvider
from src.core.providers.solcom import SolcomProvider
from src.core.providers.xing import XingProvider

# Define a Union type for all supported provider instances
JobProvider = Union[
    LinkedInProvider,
    HaysProvider,
    SolcomProvider,
    FreelancermapProvider,
    XingProvider,
    GulpProvider,
    FreelanceDeProvider,
    FerchauProvider,
]


class ProviderRegistry:
    """Central registry for managing job provider classes and metadata."""

    # Configuration map: Key matches the 'active_providers' key in JSON config
    _REGISTRY: ClassVar[Dict[str, Dict[str, Any]]] = {
        "linkedin": {
            "class": LinkedInProvider,
            "color": "🔵",
            "default_limit": 25,
            "display_name": "LinkedIn",
            "domain_pattern": "linkedin.com",
        },
        "hays": {
            "class": HaysProvider,
            "color": "🔴",
            "default_limit": 20,
            "display_name": "Hays",
            "domain_pattern": "hays.de",
        },
        "solcom": {
            "class": SolcomProvider,
            "color": "🟠",
            "default_limit": 20,
            "display_name": "SOLCOM",
            "domain_pattern": "solcom.de",
        },
        "freelancermap": {
            "class": FreelancermapProvider,
            "color": "🟢",
            "default_limit": 20,
            "display_name": "Freelancermap",
            "domain_pattern": "freelancermap.de",
        },
        "xing": {
            "class": XingProvider,
            "color": "🟣",
            "default_limit": 15,
            "display_name": "XING",
            "domain_pattern": "xing.com",
        },
        "gulp": {
            "class": GulpProvider,
            "color": "🟡",
            "default_limit": 15,
            "display_name": "GULP",
            "domain_pattern": "gulp.de",
        },
        "freelance_de": {
            "class": FreelanceDeProvider,
            "color": "💠",
            "default_limit": 15,
            "display_name": "Freelance.de",
            "domain_pattern": "freelance.de",
        },
        "ferchau": {
            "class": FerchauProvider,
            "color": "⚙️",
            "default_limit": 10,
            "display_name": "FERCHAU",
            "domain_pattern": "ferchau.com",
        },
    }

    @classmethod
    def get_active_providers(cls, config: Dict[str, Any]) -> List[Tuple[str, int, str]]:
        """Parses config and returns a list of enabled providers to run.

        Args:
            config: The full configuration dictionary.

        Returns:
            List of tuples: (provider_key, limit, display_color)
        """
        active_list = []
        providers_conf = config.get("active_providers", {})

        for key, meta in cls._REGISTRY.items():
            conf_entry = providers_conf.get(key, {})
            if conf_entry.get("enabled", False):
                limit = conf_entry.get("max_results", meta["default_limit"])
                active_list.append((key, limit, meta["color"]))

        return active_list

    @classmethod
    def get_provider_instance(cls, provider_key: str, session: requests.Session) -> Optional[JobProvider]:
        """Factory method to instantiate a specific provider.

        Args:
            provider_key: The string key (e.g., 'linkedin').
            session: The shared requests Session object.

        Returns:
            An instance of the provider class, or None if key is invalid.
        """
        key = provider_key.lower()

        # Reverse lookup by display name if key not found
        if key not in cls._REGISTRY:
            for k, v in cls._REGISTRY.items():
                if v["display_name"].lower() == key:
                    key = k
                    break

        if key in cls._REGISTRY:
            provider_cls: Type[JobProvider] = cls._REGISTRY[key]["class"]
            return provider_cls(session)

        return None

    @classmethod
    def get_provider_key_from_url(cls, url: str) -> Optional[str]:
        """Identifies the provider key based on the URL domain.

        Args:
            url: The job posting URL.

        Returns:
            The provider key (e.g., 'gulp') or None if no match is found.
        """
        url_lower = url.lower()
        for key, meta in cls._REGISTRY.items():
            if meta["domain_pattern"] in url_lower:
                return key
        return None

    @classmethod
    def get_display_name(cls, provider_key: str) -> str:
        """Returns the nice display name for a provider key."""
        return cls._REGISTRY.get(provider_key, {}).get("display_name", provider_key.title())

    @classmethod
    def get_scraping_method(cls, provider_key: str) -> str:
        """Returns the scraping method description."""
        entry = cls._REGISTRY.get(provider_key)
        if entry:
            return getattr(entry["class"], "SCRAPING_METHOD", "Unknown")
        return "Unknown"


# End of src/core/provider_registry.py (v. 00027)
