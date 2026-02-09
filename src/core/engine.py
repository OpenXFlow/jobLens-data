# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Core Engine for Job Searching with Multithreading support.

This module orchestrates the job search pipeline across multiple providers,
handles deduplication, scoring, and data persistence.
Refactored (v. 00034) - Compliance: Fixed Ruff E501 (line length) and optimized
provider-specific location handling.
"""

import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, cast

import requests

from src.core.provider_registry import ProviderRegistry


class InvalidJSONContentError(TypeError):
    """Raised when the loaded JSON content is not a dictionary."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("JSON content must be a dictionary")


class JobSearchEngine:
    """Main class managing the job search pipeline."""

    HTTP_OK: int = 200
    MAX_WORKERS_SEARCH: int = 6
    MAX_WORKERS_ENRICH: int = 5
    AUTOSAVE_INTERVAL: int = 5
    MAX_LOG_TITLE_LENGTH: int = 35
    MAX_RETRIES_PER_QUERY: int = 2

    def __init__(
        self,
        search_profile_name: str = "default",
        cv_path: str = "configs/my_profile/my_profile.json",
        global_skills_path: str = "configs/data/default_it_skills.json",
        forced_providers: Optional[List[str]] = None,
    ) -> None:
        """Initializes the engine with required configurations.

        Args:
            search_profile_name: Name of the JSON config file.
            cv_path: Path to the user CV JSON.
            global_skills_path: Path to the global skills database.
            forced_providers: Optional list of provider keys to override settings.
        """
        self.config_path: Path = self._resolve_search_profile_path(search_profile_name)
        self.cv_path: Path = Path(cv_path)
        self.global_skills_path: Path = Path(global_skills_path)

        self.profile: Dict[str, Any] = self._load_json(self.cv_path)
        self.config: Dict[str, Any] = self._load_json(self.config_path)
        self.global_skills: Set[str] = self._load_global_skills(self.global_skills_path)

        if forced_providers:
            self._override_providers(forced_providers)

        self._init_skills_sets()
        self._init_session()
        self.jobs_data: List[Dict[str, Any]] = []
        self.data_lock: Lock = Lock()
        self._setup_output_dir()

    def run(self) -> int:
        """Starts the search pipeline.

        Returns:
            int: Number of unique jobs found.
        """
        self._print_config_summary()
        skills_count = len(self.MY_SKILLS_SET)
        comp_count = len(self.profile.get("known_companies", []))
        print(f"🧠 PROFILE LOADED: {skills_count} skills, {comp_count} companies")

        start_time = time.time()
        try:
            self.search_jobs()
            self.remove_duplicates()

            # Initial enrichment on search-view data
            self._enrich_all_jobs_locally()

            self.fetch_full_descriptions()
            self.analyze_and_score()

            # Final saves
            self.save_raw_data(silent=False)
            self.autosave_filtered(silent=False)

            self.generate_report()
            print(f"\n✅ DONE! ({time.time() - start_time:.1f}s)")
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")

        return len(self.jobs_data)

    def _enrich_all_jobs_locally(self) -> None:
        """Performs scoring on partial data from search view before full enrichment."""
        with self.data_lock:
            for job in self.jobs_data:
                self._enrich_job_data(job)

    def _has_skill(self, text: str, skill: str) -> bool:
        """Robust matching tolerant to commas and brackets.

        Args:
            text: The text to search in.
            skill: The skill keyword to look for.

        Returns:
            bool: True if skill is found.
        """
        esc_skill = re.escape(skill.lower())
        if skill.lower() in ["c++", "c#", ".net"]:
            return skill.lower() in text
        pattern = rf"(?:^|[^a-zA-Z0-9]){esc_skill}(?:$|[^a-zA-Z0-9])"
        return bool(re.search(pattern, text))

    def _enrich_job_data(self, job: Dict[str, Any]) -> None:
        """Analyzes text and populates skill/score fields."""
        components = [
            job.get("title", ""),
            job.get("company", ""),
            job.get("description", ""),
            job.get("location", ""),
        ]
        text = " ".join(components).lower()

        found_mine = [s.title() for s in self.MY_SKILLS_SET if self._has_skill(text, s)]
        job["matching_skills"] = ", ".join(found_mine[:15])

        found_global = {s.lower() for s in self.global_skills if self._has_skill(text, s)}
        missing = list(found_global - self.MY_SKILLS_SET)
        job["missing_skills"] = ", ".join([s.title() for s in missing[:10]])

        langs = []
        if any(kw in text for kw in ["german", "deutsch"]):
            langs.append("German")
        if "english" in text:
            langs.append("English")
        job["detected_languages"] = ", ".join(langs)

        role_kw = self.profile.get("skills", {}).get("roles", [])
        job["matched_roles"] = ", ".join([r for r in role_kw if r.lower() in text])

        if not job.get("salary_hint"):
            pattern = r"([€$]\s?\d{2,3}[kK])|(\d{2,3}[.,]\d{3}\s?[€$]|EUR)"
            sal = re.search(pattern, job.get("description", ""))
            job["salary_hint"] = sal.group(0) if sal else ""

        self._calculate_relevance_score(job, text)

    def _calculate_relevance_score(self, job: Dict[str, Any], text: str) -> None:
        """Calculates final matching percentage."""
        score, max_score = 0, 0
        weights = self.config.get("scoring_weights", {})
        mapping = [
            ("programming_languages", 3, "programming"),
            ("testing_skills", 4, "testing"),
            ("embedded_firmware", 3, "embedded"),
            ("ai_ml_skills", 3, "ai_ml"),
        ]
        skills_data = self.profile.get("skills", {})
        for c, m, p in mapping:
            w = weights.get(c, 0)
            skills = skills_data.get(p, [])
            matches = sum(1 for s in skills if self._has_skill(text, s))
            max_score += w
            score += min(w, matches * m)

        cw, sw = weights.get("known_companies", 10), weights.get("seniority_level", 5)
        max_score += cw + sw
        if any(c.lower() in job["company"].lower() for c in self.profile.get("known_companies", [])):
            score += cw

        matches = sum(1 for r in skills_data.get("roles", []) if r.lower() in text)
        score += min(sw, matches * 3)
        job["relevance_score"] = int((score / max_score) * 100) if max_score > 0 else 0

    def _print_config_summary(self) -> None:
        """Prints configuration overview."""
        conf = self.config
        print("\n" + "=" * 75)
        print(f"⚙️  CONFIGURATION: {conf.get('profile_name', 'Unknown Profile')}")
        print("=" * 75)
        print(f"📁 Output:      {self.output_dir}")
        print("-" * 75)

    def _resolve_search_profile_path(self, name: str) -> Path:
        """Resolves config file path."""
        if name.endswith(".json"):
            name = name[:-5]
        candidates = [
            Path(f"configs/search_profiles/{name}.json"),
            Path(f"configs/core/{name}.json"),
            Path(name),
            Path(f"{name}.json"),
        ]
        for p in candidates:
            if p.exists():
                return p
        return Path("configs/core/user_default.json")

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Loads JSON data."""
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise InvalidJSONContentError()
        return cast(Dict[str, Any], data)

    def _load_global_skills(self, path: Path) -> Set[str]:
        """Loads tech DB."""
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            flat = set()
            for c in data.values():
                if isinstance(c, list):
                    flat.update(c)
            return flat

    def _init_skills_sets(self) -> None:
        """Initializes skills for matching."""
        self.CORE_SKILLS = self.profile.get("skills", {})
        self.MY_SKILLS_SET = set()
        for cat in ["programming", "testing", "embedded", "ai_ml", "ai_tools"]:
            self.MY_SKILLS_SET.update([s.lower() for s in self.CORE_SKILLS.get(cat, [])])

    def _init_session(self) -> None:
        """Inits HTTP session."""
        self.session = requests.Session()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.session.headers.update({"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})

    def _setup_output_dir(self) -> None:
        """Prepares output folder."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        base = self.config_path.stem.replace("user_", "").replace("_search", "")
        active_keys = [p[0] for p in ProviderRegistry.get_active_providers(self.config)]
        name = f"{ts}_{base}_{'_'.join(sorted(active_keys))}"
        self.output_dir = Path("outputs") / name
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _override_providers(self, providers_list: List[str]) -> None:
        """CLI overrides."""
        if "active_providers" not in self.config:
            self.config["active_providers"] = {}
        for p in self.config["active_providers"]:
            self.config["active_providers"][p]["enabled"] = False
        for p_name in providers_list:
            lower = p_name.lower()
            if lower not in self.config["active_providers"]:
                self.config["active_providers"][lower] = {"enabled": True, "max_results": 20}
            else:
                self.config["active_providers"][lower]["enabled"] = True

    def search_jobs(self) -> None:
        """Executes Phase 1: Searching."""
        print("\n" + "=" * 75 + "\n🔍 PHASE 1: SEARCHING\n" + "=" * 75)
        active_providers = ProviderRegistry.get_active_providers(self.config)
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS_SEARCH) as executor:
            for key, limit, color in active_providers:
                executor.submit(self._run_provider_search, key, limit, color)

    def _run_provider_search(self, provider_key: str, limit: int, color: str) -> None:
        """Generic provider runner with optimized individual location support."""
        provider_conf = self.config.get("active_providers", {}).get(provider_key, {})
        global_locs = self.config.get("search_parameters", {}).get("locations", ["Remote"])

        # Priority: Provider-specific list > Global fallback
        target_locs = provider_conf.get("locations", global_locs)

        queries = self.config.get("search_queries", ["Software Engineer"])
        display_name = ProviderRegistry.get_display_name(provider_key)
        provider_instance = ProviderRegistry.get_provider_instance(provider_key, self.session)

        if not provider_instance:
            return

        supports_location = getattr(provider_instance, "SUPPORTS_LOCATION_FILTER", True)
        loc_count = len(target_locs) if supports_location else 1
        print(f"{color} {display_name}: Started ({loc_count} locations)")
        delay = self.config.get("api_settings", {}).get("delay_between_requests", 2)

        for q in queries:
            current_locs = target_locs if supports_location else ["All Locations"]

            for loc in current_locs:
                success, attempts = False, 0
                max_attempts = 1 if supports_location else self.MAX_RETRIES_PER_QUERY

                while not success and attempts < max_attempts:
                    try:
                        if attempts > 0:
                            time.sleep(delay * 2)

                        search_loc = loc if supports_location else (target_locs[0] if target_locs else "Default")
                        jobs = provider_instance.search(q, search_loc, limit)

                        if jobs:
                            with self.data_lock:
                                self.jobs_data.extend(jobs)
                            print(f"   ✓ [{display_name}] +{len(jobs)} jobs (Q: {q} | L: {loc})")
                            success = True
                        elif not supports_location:
                            attempts += 1
                        else:
                            print(f"   ✓ [{display_name}] 0 jobs (Q: {q} | L: {loc})")
                            success = True

                    except Exception as e:
                        print(f"   ⚠️ [{display_name}] Error: {e}")
                        attempts += 1

                time.sleep(delay)

    def remove_duplicates(self) -> None:
        """Executes Phase 2: Deduplication."""
        seen, unique = set(), []
        with self.data_lock:
            for j in self.jobs_data:
                jid = str(j.get("job_id") or j.get("link"))
                if jid not in seen:
                    seen.add(jid)
                    unique.append(j)
            self.jobs_data = unique
        print(f"🗑️ PHASE 2: DEDUPLICATION -> {len(self.jobs_data)} unique jobs")

    def fetch_full_descriptions(self) -> None:
        """Executes Phase 3: Enrichment."""
        if not self.config.get("search_parameters", {}).get("fetch_full_description", False):
            return
        print("\n" + "=" * 75 + f"\n📥 PHASE 3: ENRICHMENT ({self.MAX_WORKERS_ENRICH} workers)\n" + "=" * 75)
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS_ENRICH) as executor:
            futures = [
                executor.submit(self._enrich_single_job, j, j.get("provider", "").lower()) for j in self.jobs_data
            ]
            for completed, f in enumerate(as_completed(futures), 1):
                f.result()
                if completed % self.AUTOSAVE_INTERVAL == 0:
                    self.save_raw_data(silent=True)
                    self.autosave_filtered(silent=True)

    def _enrich_single_job(self, job: Dict[str, Any], provider_name: str) -> Dict[str, Any]:
        """Fetches and enriches job data."""
        try:
            p_key = "freelance_de" if provider_name == "freelance_de" else provider_name
            provider = ProviderRegistry.get_provider_instance(p_key, self.session)
            if not provider:
                provider = ProviderRegistry.get_provider_instance("linkedin", self.session)
            if provider:
                desc = provider.fetch_full_description(job["link"])
                if desc and len(desc.strip()) > 0:
                    job["description"] = desc
        except Exception as e:
            print(f"   ⚠️ Enrichment error: {e}")
        self._enrich_job_data(job)
        return job

    def analyze_and_score(self) -> None:
        """Executes Phase 4: Scoring."""
        with self.data_lock:
            self.jobs_data.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    def get_csv_headers(self) -> List[str]:
        """Returns CSV headers."""
        return [
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

    def save_raw_data(self, silent: bool = True) -> None:
        """Saves all raw results.

        Args:
            silent: Suppress print if True.
        """
        with self.data_lock:
            data_copy = list(self.jobs_data)
        if not data_copy:
            return

        formats = self.config.get("output", {}).get("formats", ["csv"])

        if not silent:
            print("💾 Saving raw data...")

        if "csv" in formats:
            with (self.output_dir / "all_jobs_raw.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.get_csv_headers(), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data_copy)
        if "json" in formats:
            with (self.output_dir / "all_jobs_raw.json").open("w", encoding="utf-8") as f:
                json.dump(data_copy, f, ensure_ascii=False, indent=2)

    def autosave_filtered(self, silent: bool = True) -> None:
        """Saves filtered results.

        Args:
            silent: Suppress print if True.
        """
        with self.data_lock:
            data_copy = list(self.jobs_data)
        if not data_copy:
            return

        min_s = self.config.get("filtering", {}).get("min_relevance_score", 0)
        exclude = self.config.get("filtering", {}).get("exclude_keywords", [])
        filtered = [
            j
            for j in data_copy
            if j.get("relevance_score", 0) >= min_s and not any(k.lower() in j["title"].lower() for k in exclude)
        ]
        filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        if not silent:
            print(f"💾 Saving filtered results ({len(filtered)} jobs)...")

        base = self.config.get("output", {}).get("base_filename", "jobs")
        formats = self.config.get("output", {}).get("formats", ["csv"])
        if "csv" in formats and filtered:
            with (self.output_dir / f"{base}.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.get_csv_headers(), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(filtered)
        if "json" in formats and filtered:
            with (self.output_dir / f"{base}.json").open("w", encoding="utf-8") as f:
                json.dump(filtered, f, ensure_ascii=False, indent=2)
        if "markdown" in formats and filtered:
            self._export_markdown(base, filtered)

    def _export_markdown(self, base_name: str, data: List[Dict[str, Any]]) -> None:
        """Generates MD report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with (self.output_dir / f"{base_name}.md").open("w", encoding="utf-8") as f:
            f.write(f"# Job Search Results ({now_str})\n\nTotal processed: {len(data)}\n\n")
            for i, j in enumerate(data, 1):
                # E501 Fix: Split long string into multiple write calls
                f.write(f"### {i}. {j['title']} (**{j['relevance_score']}%**)\n")
                f.write(f"- **Provider:** {j.get('provider')} | **Location:** {j.get('location')}\n")
                f.write(f"- **Matching Skills:** {j.get('matching_skills', 'None')}\n")
                f.write(f"- **Link:** [View Posting]({j['link']})\n\n---\n")

    def generate_report(self) -> None:
        """Final summary print."""
        with self.data_lock:
            data_copy = list(self.jobs_data)
        min_s = self.config.get("filtering", {}).get("min_relevance_score", 0)
        filtered = sorted(
            [j for j in data_copy if j.get("relevance_score", 0) >= min_s],
            key=lambda x: x.get("relevance_score", 0),
            reverse=True,
        )
        if not filtered:
            return
        print("\n⭐ TOP 5 RESULTS:")
        for i, j in enumerate(filtered[:5], 1):
            # E501 Fix: Break print statement into multi-line f-string
            print(
                f"{i}. {j['title']} ({j['relevance_score']}%)\n"
                f"   Posted: {j.get('posted_at_relative')}\n"
                f"   {j['link']}\n"
            )


# End of src/core/engine.py (v. 00034)
