# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Provider Registry Module.

This module acts as a Factory/Registry for all available job providers.
It decouples the main Engine from specific provider implementations,
allowing for easier extensibility.
Refactored (v3.3.26) to include FERCHAU and maintain strict type-safety.
"""

from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type, Union

import requests

# Import all provider classes here
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

# Define a generic type for Provider classes constructor
ProviderClass = Type[JobProvider]


class ProviderRegistry:
    """Central registry for managing job provider classes and metadata."""

    # Configuration map: Key matches the 'active_providers' key in JSON config
    # Value contains the Class, Console Color, and Default Priority
    _REGISTRY: ClassVar[Dict[str, Dict[str, Any]]] = {
        "linkedin": {
            "class": LinkedInProvider,
            "color": "🔵",
            "default_limit": 25,
            "display_name": "LinkedIn",
        },
        "hays": {"class": HaysProvider, "color": "🔴", "default_limit": 20, "display_name": "Hays"},
        "solcom": {"class": SolcomProvider, "color": "🟠", "default_limit": 20, "display_name": "SOLCOM"},
        "freelancermap": {
            "class": FreelancermapProvider,
            "color": "🟢",
            "default_limit": 20,
            "display_name": "Freelancermap",
        },
        "xing": {"class": XingProvider, "color": "🟣", "default_limit": 15, "display_name": "XING"},
        "gulp": {"class": GulpProvider, "color": "🟡", "default_limit": 15, "display_name": "GULP"},
        "freelance_de": {
            "class": FreelanceDeProvider,
            "color": "💠",
            "default_limit": 15,
            "display_name": "Freelance.de",
        },
        "ferchau": {
            "class": FerchauProvider,
            "color": "⚙️",
            "default_limit": 10,
            "display_name": "FERCHAU",
        },
    }

    @classmethod
    def get_active_providers(cls, config: Dict[str, Any]) -> List[Tuple[str, int, str]]:
        """Parses config and returns a list of enabled providers to run.

        Args:
            config: The full configuration dictionary loaded from JSON.

        Returns:
            List of tuples: (provider_key, limit, display_color)
        """
        active_list = []
        providers_conf = config.get("active_providers", {})

        # Iterate through our known registry to preserve order or priority if needed
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
            provider_key: The string key (e.g., 'linkedin', 'solcom').
            session: The shared requests Session object.

        Returns:
            An instance of the provider class, or None if key is invalid.
        """
        # Normalize key lookup (case-insensitive)
        key = provider_key.lower()

        # Handle case where 'provider' field in CSV might be capitalized differently
        if key not in cls._REGISTRY:
            # Try to find by display name reverse lookup
            for k, v in cls._REGISTRY.items():
                if v["display_name"].lower() == key:
                    key = k
                    break

        if key in cls._REGISTRY:
            provider_cls = cls._REGISTRY[key]["class"]
            # All providers accept session in constructor
            return provider_cls(session)  # type: ignore

        return None

    @classmethod
    def get_display_name(cls, provider_key: str) -> str:
        """Returns the nice display name for a provider key."""
        return cls._REGISTRY.get(provider_key, {}).get("display_name", provider_key.title())

    @classmethod
    def get_scraping_method(cls, provider_key: str) -> str:
        """Returns the scraping method description (for config summary)."""
        entry = cls._REGISTRY.get(provider_key)
        if entry:
            return getattr(entry["class"], "SCRAPING_METHOD", "Unknown")
        return "Unknown"


# End of src/core/provider_registry.py (v. 3.3.26)
