### 🏗️ Architectural Highlights for `structure.md`:

1.  **Modular Scraper Layer:** The `src/core/providers/` directory demonstrates a strict **Provider Pattern**, making the system easily extensible for new job portals.
2.  **Configuration as Code:** The `configs/` ecosystem separates the **Identity** (what you know) from the **Strategy** (where you look), allowing for rapid pivots in your job search without changing a single line of code.
3.  **Data Lifecycle Management:** `sync_results.py` combined with the `results/` and `outputs/` folders proves that this is not just a scraper, but a complete **ETL (Extract, Transform, Load)** pipeline.
4.  **Stealth Dominance:** The inclusion of `selenium_factory.py` indicates a specialized focus on bypassing enterprise-grade bot protections in the cloud.



jobLens/
├── .github/
│   └── workflows/
│       └── job_scan_daily.yml        # CI/CD: Automated Dual-Push Matrix workflow
├── configs/
│   ├── core/
│   │   ├── providers_settings.json   # Technical metadata: URLs, limits, and methods
│   │   └── user_default.json         # Fallback search parameters and global defaults
│   │   └── user_default.example      # Sanitized template for public/new users
│   ├── data/
│   │   └── default_it_skills.json    # Knowledge Base: Global IT skills for Gap Analysis
│   ├── my_profile/
│   │   ├── my_profile.json           # User Identity: Personal CV, Skills, and Credentials
│   │   └── my_profile.json.example   # Sanitized template for public/new users
│   └── search_profiles/              # Business Logic: Specialized search strategies
│       ├── aggressive_search.json    # Strategy: High-volume, wide-net discovery
│       ├── quality_focused.json      # Strategy: Strict filtering for premium roles
│       ├── remote_ai_only.json       # Strategy: Focused on AI/ML and Remote work
│       └── debug_*.json              # Tech-Validation: Targeted provider test configs
├── logs/
│   └── cookies_freelance_de.json     # Auth: Persistent session data for scrapers
├── outputs/                          # Short-term artifacts: Latest run logs and reports
│   └── .gitkeep
├── results/                          # Master DB: Long-term cumulative CSV and Dashboards
│   └── .gitkeep
├── src/                              # Source Code Directory
│   ├── cli/
│   │   └── batch.py                  # CLI: Interactive multi-profile runner
│   ├── core/
│   │   ├── providers/                # Scraper Layer: Individual portal implementations
│   │   │   ├── linkedin.py           # API-based: High-speed guest portal scraper
│   │   │   ├── solcom.py             # UI-driven: Specialized freelance portal agent
│   │   │   ├── xing.py               # Deep-extraction: Meta-data and salary scraper
│   │   │   └── ...                   # (Ferchau, Gulp, Hays, Freelancermap, etc.)
│   │   ├── engine.py                 # Orchestration: Multithreaded search & scoring brain
│   │   ├── selenium_factory.py       # Stealth: Centralized Ultra-Stealth browser factory
│   │   └── provider_registry.py      # Registry: Factory pattern for dynamic provider loading
│   └── utils/
│       ├── persistence_manager.py    # ETL: Data consolidation, rotation, and Excel logic
│       └── wizard.py                 # Setup: Interactive project initializer
├── .gitignore                        # Git Rules: Separation of private code and data
├── install.sh                        # Installer: Modern Bash script for automated setup
├── jobLens.py                        # Entry Point: Main CLI search engine interface
├── LICENSE                           # Legal: MIT License documentation
├── pyproject.toml                    # Build: Dependency and project metadata (PEP 517)
├── README.md                         # Documentation: Main project guide 
├── setup.py                          # Build: Compatibility shim for pip installation
└── sync_results.py                   # Maintenance: Standalone data lifecycle manager

