# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""Core Engine for Job Searching with Bilingual and Manual support.

This module orchestrates the job search pipeline, supporting both automated
portal scraping and manual URL analysis with EN/DE language detection.
Refactored (v. 00052) - Final Scoring Parity: Enforced full re-calculation
during enrichment to eliminate discrepancies between manual and auto modes.
"""

import contextlib
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Union, cast

import requests

from src.core.provider_registry import ProviderRegistry


class InvalidJSONContentError(TypeError):
    """Raised when the loaded JSON content is not a dictionary."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("JSON content must be a dictionary")


class JobSearchEngine:
    """Main class managing the job search and analysis pipeline."""

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
        """Initializes the engine with required configurations."""
        self.config_path: Path = self._resolve_search_profile_path(search_profile_name)
        self.cv_path: Path = Path(cv_path)
        self.global_skills_path: Path = Path(global_skills_path)

        self.profile: Dict[str, Any] = self._load_json(self.cv_path)
        self.config: Dict[str, Any] = self._load_json(self.config_path)
        self.global_skills_raw: Dict[str, Any] = self._load_json(self.global_skills_path)

        if forced_providers:
            self._override_providers(forced_providers)

        self._init_skills_sets()
        self._init_session()
        self.jobs_data: List[Dict[str, Any]] = []
        self.data_lock: Lock = Lock()
        self.is_manual_mode: bool = False
        self._setup_output_dir()

    def run(self) -> int:
        """Starts the standard automated search pipeline."""
        self._print_config_summary()
        start_time = time.time()
        try:
            self.search_jobs()
            self.finalize_pipeline(start_time)
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")

        return len(self.jobs_data)

    def run_manual_mode(self, input_csv: str) -> int:
        """Starts the engine in manual injection mode using links from a CSV."""
        csv_path = Path(input_csv)
        if not csv_path.exists():
            print(f"❌ Error: Input file '{input_csv}' not found.")
            return 0

        self.is_manual_mode = True
        print(f"\n🚀 MANUAL MODE: Loading links from {csv_path.name}")
        manual_links = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                link = row.get("link")
                if not link:
                    continue

                p_key = ProviderRegistry.get_provider_key_from_url(link) or "linkedin"

                job_template = {
                    "link": link,
                    "provider": p_key,
                    "job_id": str(time.time()),
                    "title": "Pending Extraction...",
                    "company": "Pending Extraction...",
                    "location": "Remote",
                    "description": "",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "posted_at_relative": "N/A",
                    "work_location_type": "Remote",
                    "employment_type": "Freelance",
                    "search_criteria": f"Manual | {csv_path.name}",
                    "relevance_score": 0,
                }
                manual_links.append(job_template)

        with self.data_lock:
            self.jobs_data = manual_links

        start_time = time.time()
        self.finalize_pipeline(start_time)
        return len(self.jobs_data)

    def finalize_pipeline(self, start_time: float) -> None:
        """Completes the common steps of the analysis pipeline."""
        self.remove_duplicates()
        self._enrich_all_jobs_locally()
        self.fetch_full_descriptions()
        self.analyze_and_score()

        self.save_raw_data(silent=False)
        self.autosave_filtered(silent=False)
        self.generate_report()
        print(f"\n✅ DONE! ({time.time() - start_time:.1f}s)")

    def _enrich_all_jobs_locally(self) -> None:
        """Performs initial scoring on all jobs in the data list."""
        with self.data_lock:
            for job in self.jobs_data:
                self._enrich_job_data(job)

    def _detect_language(self, text: str) -> str:
        """Detects if text is primarily English or German."""
        text_lower = text.lower()
        de_words = {"der", "die", "das", "und", "mit", "von", "den", "auf", "ist"}
        en_words = {"the", "and", "with", "from", "for", "that", "this", "is", "are"}

        words = re.findall(r"\b\w{2,}\b", text_lower)
        de_score = sum(1 for w in words if w in de_words)
        en_score = sum(1 for w in words if w in en_words)

        return "de" if de_score > en_score else "en"

    def _has_skill(self, text: str, skill_entry: Union[str, Dict[str, str]]) -> bool:
        """Matches skill allowing for string or dict {en, de} structure."""
        text_lower = text.lower()

        if isinstance(skill_entry, dict):
            candidates = [str(v).lower() for v in skill_entry.values()]
        else:
            candidates = [str(skill_entry).lower()]

        for cand in candidates:
            esc_cand = re.escape(cand)
            if cand in ["c++", "c#", ".net"]:
                if cand in text_lower:
                    return True
                continue
            pattern = rf"(?:^|[^a-zA-Z0-9]){esc_cand}(?:$|[^a-zA-Z0-9])"
            if re.search(pattern, text_lower):
                return True
        return False

    def _enrich_job_data(self, job: Dict[str, Any]) -> None:
        """Analyzes text and populates skill/score fields with bilingual support."""
        desc = job.get("description", "")

        # Isolated scoring text - EXCLUDE search_criteria for consistency
        scoring_components = [job.get("title", ""), job.get("company", ""), desc, job.get("location", "")]
        text_to_score = " ".join([str(c) for c in scoring_components]).lower()

        lang = self._detect_language(text_to_score)
        job["detected_languages"] = "German" if lang == "de" else "English"

        found_mine = []
        for cat in ["programming", "testing", "embedded", "ai_ml", "ai_tools"]:
            skills = self.profile.get("skills", {}).get(cat, [])
            for s in skills:
                if self._has_skill(text_to_score, s):
                    label = s["en"] if isinstance(s, dict) else s
                    found_mine.append(label.title())

        job["matching_skills"] = ", ".join(sorted(set(found_mine))[:15])

        role_entries = self.profile.get("skills", {}).get("roles", [])
        matched_roles_list = []
        for r in role_entries:
            if self._has_skill(text_to_score, r):
                label = r["en"] if isinstance(r, dict) else r
                matched_roles_list.append(label)
        job["matched_roles"] = ", ".join(sorted(set(matched_roles_list)))

        found_global = set()
        for cat_list in self.global_skills_raw.values():
            for s in cat_list:
                if self._has_skill(text_to_score, s):
                    label = s["en"] if isinstance(s, dict) else s
                    found_global.add(label.title())

        missing = [s for s in found_global if s not in found_mine]
        job["missing_skills"] = ", ".join(missing[:10])

        if not job.get("salary_hint"):
            sal_pattern = (
                r"(?:Salary|Gehalt|Stundensatz|Vergütung):?\s*([€$]\s?\d{2,3}[kK]|\d{2,3}[.,]\d{3}\s?[€$]|EUR)"
            )
            sal = re.search(sal_pattern, desc, re.IGNORECASE)
            job["salary_hint"] = sal.group(1) if sal else ""

        # Default fallback for location type if not already extracted by provider
        rem_kws = ["remote", "home office", "homeoffice", "ortsunabhängig", "telearbeit", "mobil", "100%"]
        if any(kw in text_to_score for kw in rem_kws):
            job["work_location_type"] = "Remote"
        elif "hybrid" in text_to_score:
            job["work_location_type"] = "Hybrid"

        # ALWAYS calculate from scratch to avoid stale data from "Pending" state
        self._calculate_relevance_score(job, text_to_score)

    def _calculate_relevance_score(self, job: Dict[str, Any], text: str) -> None:
        """Calculates relevance score using dynamic category scaling."""
        score, max_score = 0, 0
        weights = self.config.get("scoring_weights", {})
        if not weights:
            weights = {
                "programming_languages": 20,
                "testing_skills": 20,
                "embedded_firmware": 15,
                "ai_ml_skills": 20,
                "known_companies": 10,
                "seniority_level": 15,
            }

        categories = [
            ("programming_languages", "programming"),
            ("testing_skills", "testing"),
            ("embedded_firmware", "embedded"),
            ("ai_ml_skills", "ai_ml"),
        ]

        skills_profile = self.profile.get("skills", {})

        for weight_key, profile_key in categories:
            weight = weights.get(weight_key, 20)
            skills = skills_profile.get(profile_key, [])

            matches = sum(1 for s in skills if self._has_skill(text, s))

            # Check if category is relevant to the job at all
            is_category_mentioned = any(
                self._has_skill(text, s) for s in self.global_skills_raw.get(f"{profile_key}_skills", [])
            ) or any(self._has_skill(text, s) for s in self.global_skills_raw.get(profile_key, []))

            if is_category_mentioned:
                max_score += weight
                score += min(weight, matches * 4)
            else:
                max_score += weight * 0.25

        cw = weights.get("known_companies", 10)
        sw = weights.get("seniority_level", 15)

        max_score += cw + sw

        # Known companies bonus
        if any(c.lower() in str(job.get("company", "")).lower() for c in self.profile.get("known_companies", [])):
            score += cw

        # Seniority / Roles bonus
        role_matches = len(job.get("matched_roles", "").split(",")) if job.get("matched_roles") else 0
        score += min(sw, role_matches * 5)

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

    def _init_skills_sets(self) -> None:
        """Initializes skills for matching."""
        self.CORE_SKILLS = self.profile.get("skills", {})
        self.MY_SKILLS_SET = set()
        for cat in ["programming", "testing", "embedded", "ai_ml", "ai_tools"]:
            skills = self.CORE_SKILLS.get(cat, [])
            for s in skills:
                val = s["en"].lower() if isinstance(s, dict) else s.lower()
                self.MY_SKILLS_SET.add(val)

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
                        search_loc = loc if supports_location else (target_locs if target_locs else "Default")
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
        """Executes Phase 3: Enrichment with session-based Selenium for Manual Mode."""
        should_fetch = self.is_manual_mode or self.config.get("search_parameters", {}).get(
            "fetch_full_description", False
        )
        if not should_fetch:
            return
        workers = 1 if self.is_manual_mode else self.MAX_WORKERS_ENRICH
        print(f"\n{'-' * 75}\n📥 PHASE 3: ENRICHMENT ({workers} workers)\n{'-' * 75}")

        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(self._enrich_single_job, j) for j in self.jobs_data]
                for f in as_completed(futures):
                    with contextlib.suppress(Exception):
                        f.result()
        else:
            for job in self.jobs_data:
                with contextlib.suppress(Exception):
                    self._enrich_single_job(job)

    def _enrich_single_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches and enriches job data with rich metadata support."""
        if self.is_manual_mode:
            print(f"   [FETCH] Processing: {job.get('link', '')[:60]}...")

        provider_name = job.get("provider", "").lower()
        provider = ProviderRegistry.get_provider_instance(provider_name, self.session)
        if not provider:
            provider = ProviderRegistry.get_provider_instance("linkedin", self.session)

        if provider:
            with contextlib.suppress(Exception):
                raw_result = provider.fetch_full_description(job["link"])
                if isinstance(raw_result, dict):
                    job.update(raw_result)
                else:
                    job["description"] = raw_result

        # RE-CALCULATE EVERYTHING AFTER METADATA UPDATE
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
        """Saves all raw results."""
        with self.data_lock:
            data_copy = list(self.jobs_data)
        if not data_copy:
            return
        if not silent:
            print("💾 Saving raw data...")
        formats = self.config.get("output", {}).get("formats", ["csv"])
        if "csv" in formats:
            with (self.output_dir / "all_jobs_raw.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.get_csv_headers(), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data_copy)
        if "json" in formats:
            with (self.output_dir / "all_jobs_raw.json").open("w", encoding="utf-8") as f:
                json.dump(data_copy, f, ensure_ascii=False, indent=2)

    def autosave_filtered(self, silent: bool = True) -> None:
        """Saves filtered results."""
        with self.data_lock:
            data_copy = list(self.jobs_data)
        if not data_copy:
            return
        min_s = 0 if self.is_manual_mode else self.config.get("filtering", {}).get("min_relevance_score", 0)
        exclude = self.config.get("filtering", {}).get("exclude_keywords", [])
        filtered = [
            j
            for j in data_copy
            if j.get("relevance_score", 0) >= min_s
            and not any(k.lower() in j.get("title", "").lower() for k in exclude)
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
                f.write(f"### {i}. {j.get('title', 'Unknown')} (**{j.get('relevance_score', 0)}%**)\n")
                f.write(f"- **Provider:** {j.get('provider')} | **Location:** {j.get('location')}\n")
                f.write(f"- **Matching Skills:** {j.get('matching_skills', 'None')}\n")
                f.write(f"- **Link:** [View Posting]({j['link']})\n\n---\n")

    def generate_report(self) -> None:
        """Final summary print."""
        with self.data_lock:
            data_copy = list(self.jobs_data)
        filtered = sorted(data_copy, key=lambda x: x.get("relevance_score", 0), reverse=True)
        if not filtered:
            return
        print("\n⭐ TOP 5 RESULTS:")
        for i, j in enumerate(filtered[:5], 1):
            msg = (
                f"{i}. {j.get('title', 'Unknown')} ({j.get('relevance_score', 0)}%)\n"
                f"   Posted: {j.get('posted_at_relative')}\n"
                f"   {j.get('link', 'N/A')}\n"
            )
            print(msg)


# End of src/core/engine.py (v. 00052)
