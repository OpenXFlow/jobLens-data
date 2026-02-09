# 📊 jobLens Public Data Release

This repository contains daily updated, analyzed, and scored job listings for **Senior Firmware, Testing, and AI/ML Engineering roles**. 
The data is aggregated from multiple European job portals (LinkedIn, Solcom, Hays, etc.) by the private **jobLens Intelligence Engine**.

---

## 🧭 Repository Navigation (Dual Branch Architecture)

This repository uses two separate branches for maximum transparency:

| Branch | Primary Content | Purpose |
| :--- | :--- | :--- |
| [main](https://github.com/OpenXFlow/jobLens-data/tree/main)  | **Open-Source Code** (`.github`, `configs`, `src`,`docs`, ...)  | Provides a view of the code structure and tools for local data processing. |
| [data](https://github.com/OpenXFlow/jobLens-data/tree/data)  | **Data Backup** (`outputs/`, `results/`) | **CI/CD Target.** Stores the complete history and backup of all scraped data. |

***Recommendation: To view the latest job results / sources, switch the branch to **`data / main `** in the top-left menu.***

---

## ✨ Data Structure

This repository is maintained by an automated Continuous Integration (CI) process. It contains two main directories for data persistence:

### 1. `results/` (The Final Database)
This is the long-term, cumulative database of all unique job findings.

| File Name | Format | Purpose |
| :--- | :--- | :--- |
| `all_found_jobs.csv` | CSV | **Master Database.** All unique jobs found since the start of the project. Used for historical analysis. |
| `JobLens_Dashboard.xlsx` | Excel | **Primary Dashboard.** Multi-tab report (one sheet per provider), with all jobs sorted by Relevance Score. |
| `history/` | CSV/XLSX | Archived job records older than 180 days. |

### 2. `outputs/` (Latest Scan Artifacts)
This directory contains the full, unfiltered output and logs from the automated market scans.

***Note:*** *The output directories are subject to a **14-day rolling window** cleanup, meaning folders older than 14 days are automatically deleted.*

| File Name | Format | Purpose |
| :--- | :--- | :--- |
| `job_search_results.csv` | CSV | Filtered, scored results from the *latest run*. Contains only jobs passing the minimum relevance score threshold. |
| `all_jobs_raw.json` | JSON | Unfiltered list of all jobs found in the latest scan (used internally for data synchronization). |
| `job_search_results.md` | Markdown | Console-ready report summarizing the top N jobs found, including direct links. |
| `debug_*.png/html` | PNG/HTML | Diagnostic screenshots/HTML dumps from Selenium providers (only if a scraping error occurred). |

---

## 🛠 Helper Scripts (for Manual Filtering)

The `/helper` directory contains Python scripts for users who want to run custom, deep-dive filtering on the raw output data from the `/outputs` folder.

***Note:*** *Both scripts are **recursive**—they scan the specified directory and **all its subdirectories** to find `all_jobs_raw.csv` files.*

### 1. Filter by Testing/QA Role (`filter_jobs_for_test.py`)
This script isolates jobs based on keywords found exclusively in the job title (e.g., Tester, QA, Automation).

*   **Action:** Scans all `all_jobs_raw.csv` files recursively and filters by job title.
*   **Usage (Command Line):**
    ```bash
    python helper/filter_jobs_for_test.py C:/path/to/jobLens-data/outputs/
    ```
    *Example:* `python helper/filter_jobs_for_test.py C:\Users\YourName\jobLens-data\outputs\`

### 2. Filter by City/Region (`filter_jobs_for_city.py`)
This script isolates jobs based on specific city keywords found anywhere in the job record.

*   **Action:** Scans all `all_jobs_raw.csv` files recursively and filters by full row content (e.g., searches for "Vienna" or "Munich").
*   **Usage (Command Line):**
    ```bash
    python helper/filter_jobs_for_city.py C:/path/to/jobLens-data/outputs/
    ```
    *Example:* `python helper/filter_jobs_for_city.py C:\Users\YourName\jobLens-data\outputs\`

***Note:*** *Both scripts generate a new, deduplicated CSV file in the `/helper` directory.*

---

## ⚙️ How It Works
The jobLens Engine runs on a daily schedule, executing the following steps:
1.  **Scraping:** Fetches data from all configured job portals (LinkedIn, Solcom, etc.).
2.  **Scoring:** Compares job descriptions against a detailed personal profile (skills, experience).
3.  **Consolidation:** Runs `sync_results.py` to deduplicate, archive old records, and update the master database.
4.  **Publishing:** Pushes the updated data to this public repository.

## 🔗 Repository Links
- **Source Code (Engine View):**  switch to Branch 'main'
- **Data Branch URL:** [View Raw Data](https://github.com/OpenXFlow/jobLens-data/tree/data/results)

## 🌍 Region Coverage
- Germany (DE)
- Austria (AT)
- Switzerland (CH)
- Remote / International Markets (USA, UK, CEE)

---
*Maintained by the private jobLens Engine, Copyright (c) 2025 Jozef Darida. Last updated: Automated Daily.*

