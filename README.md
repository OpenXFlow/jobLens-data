# jobLens: Intelligent Job Search Automation Engine


<p align="center">
  <img src="docs/assets/image/jobLens.gif" alt="jobLens Logo" width="600">
</p>

<p align="left">
  <strong>Aggregate, analyze, and rank job postings from multiple providers simultaneously.</strong>
  <br>
  jobLens is a high-performance automation tool designed to give you a unified edge in the job market.
  <br>
  jobLens is Your Personal Career Intelligence Engine.
</p>

This repository is a powerful framework for automated recruitment research. Use it to scan major job portals (LinkedIn, Solcom, Gulp, etc.) in parallel, bypass advanced bot protections, and receive a curated, scored list of opportunities that perfectly match your professional profile.

---

## 🧭 Repository Navigation (Dual Branch Architecture)

**This repository stores the source code and configuration for the jobLens Agent.** Its results are published to a separate repository for public access.

| Branch | Primary Content | Purpose |
| :--- | :--- | :--- |
| [main](https://github.com/OpenXFlow/jobLens-data/tree/main)  | **Open-Source Code** (`.github`, `configs`, `src`, `docs`, ...)  | Provides a view of the code structure and tools for local data processing. |
| [data](https://github.com/OpenXFlow/jobLens-data/tree/data)  | **Data Backup** (`outputs/`, `results/`) | **CI/CD Target.** Stores the complete history and backup of all scraped data. |

***Note: All public-facing data (CSV, Excel) is pushed from here to the [jobLens Public Data Repo](https://github.com/OpenXFlow/jobLens-data/tree/data).***

---

### ✨ Key Features

-   🚀 **Multi-Provider Architecture:** Built on a modular **Provider Pattern**, supporting LinkedIn (API), SOLCOM, GULP, and others (Selenium).
-   ⚡ **Parallel Execution:** High-speed multithreaded engine for simultaneous searching and data enrichment across all platforms.
-   🛡️ **Advanced Bot Protection:** Integrated **Ultra-Stealth** patches and `undetected-chromedriver` to bypass WAF and Headless detections.
-   🧠 **Relevance Scoring:** Automated skill matching, gap analysis (Missing Skills), and ranking based on your personalized CV profile.
-   📊 **Professional Dashboards:** Global deduplication with exports to cumulative CSV databases and multi-tab **Excel Dashboards**.
-   🤖 **CI/CD Ready:** Optimized for serverless execution via **GitHub Actions** for periodic, fully automated market scans.

### 🛠️ Tech Stack & Powered By

**Core Logic:**
-   **Python 3.12+:** High-performance core with full type-hinting.
-   **Concurrent Futures:** ThreadPool implementation for parallel I/O.
-   **Pandas / OpenPyXL:** Data processing, consolidation, and Excel dashboard generation.

**Stealth & Scraping:**
-   **Selenium / Undetected-ChromeDriver:** Automated browser for protected portals.
-   **BeautifulSoup4 / Requests:** Fast data extraction for APIs and static HTML.

**Quality & DevTools:**
-   **Ruff / MyPy:** Cutting-edge linting and static type checking for code quality enforcement.

---

### 🚀 Quick Start for Developers

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/OpenXFlow/jobLens.git
    cd jobLens
    ```

2.  **Set up the Environment:**
    *   Create a virtual environment: `python -m venv .venv`
    *   Activate it: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux)
    *   Install dependencies: `pip install .`

3.  **Initialize the "Brain":**
    *   Run the wizard to create directories and local configs:
        ```bash
        python -m src.utils.wizard
        ```
    *   **Configure Your Profile:** Edit `configs/my_profile/my_profile.json` with your specific skills and target roles.

4.  **Run Your First Search:**
    *   Standard search (all active providers):
        ```bash
        python jobLens.py
        ```
    *   Targeted search on a specific portal:
        ```bash
        python jobLens.py -pr solcom -sp remote_ai_only
        ```

5.  **Global Sync & Dashboard:**
    *   Merge results from all runs into your global database:
        ```bash
        python sync_results.py
        ```

---

## 🔗 Public Data & Helper Tools

The publicly available results and helper scripts are located in the separate repository:

| Content | Location |
| :--- | :--- |
| **Live Data / Results** | [jobLens Public Data Repo](https://github.com/OpenXFlow/jobLens-data/tree/data) |
| **Example CI Workflow** | **job_scan_daily.yml.example** (in this repo) |

## license

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
