# 🕵️‍♂️ jobLens: Complete User Manual

**jobLens** is a high-performance automation engine designed to aggregate, analyze, and rank job postings from multiple portals (LinkedIn, Solcom, Hays, etc.) simultaneously. It uses advanced stealth techniques to bypass bot detection and provides AI-ready scoring based on your professional profile.

---

## 🧭 1. Repository Architecture (Dual Branch)

For maximum transparency and privacy, the project is split into two distinct branches:

| Branch | Content | Access | Purpose |
| :--- | :--- | :--- | :--- |
| **`main`** | **Source Code** | Private/Public | Contains the Python engine, configuration templates, and helper scripts. |
| **`data`** | **Results & Logs** | Public | Stores daily updated CSVs, Excel Dashboards, and full Markdown reports. |

---

## 🚀 2. Installation & Quick Start

### Method 1: Automated Setup (Recommended)
Suitable for Linux, macOS, or Windows (via Git Bash/WSL).

```bash
# 1. Clone the repository
git clone https://github.com/OpenXFlow/jobLens.git
cd jobLens

# 2. Run the installer
bash install.sh
```
**What it does:** Checks Python 3.12+, installs dependencies via `pyproject.toml`, creates the directory structure, and initializes your profile from a template.

### Method 2: Manual Python Setup (Windows)
```cmd
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install project as editable
pip install -e .

# 3. Initialize structure
python -m src.utils.wizard
```

---

## ⚙️ 3. Configuration (Personalizing the "Brain")

The system is **Config-Driven**. All logic is controlled via files in the `configs/` directory.

### 👤 Your Profile (`configs/my_profile/my_profile.json`)
This is the most important file. The engine uses it to calculate your **Relevance Score**.
*   **`skills.roles`**: Add keywords like "Senior", "Lead", "Architect".
*   **`skills.programming`**: Your tech stack (Python, C++, etc.).
*   **`credentials`**: Add your login data for portals like `freelance.de`.

### 🔍 Search Profile (`configs/core/user_default.json`)
Defines **where** and **what** to search.
*   **`active_providers`**: Enable/disable specific portals (LinkedIn, Solcom, etc.).
*   **`locations`**: List of target countries/regions.
*   **`search_queries`**: Use "Role + Tech" combinations (e.g., `"Python Test"`, `"QA Engineer"`).

---

## 💻 4. Local Usage (CLI)

Run the agent from your terminal using various switches:

| Command | Purpose |
| :--- | :--- |
| `python jobLens.py` | Run default search (all active providers). |
| `python jobLens.py -pr solcom` | Force search only on **Solcom**. |
| `python jobLens.py -sp aggressive` | Use the **Aggressive Search** profile. |
| `python jobLens.py -b` | **Batch Mode:** Interactive menu to select multiple profiles. |

### 🧪 Simulating GitHub Actions (Headless Mode)
To test how the bot behaves in the cloud without opening a browser window:
```powershell
# PowerShell
$env:GITHUB_ACTIONS="true"; python jobLens.py -pr solcom
```

---

## 🤖 5. GitHub Actions (Automation)

The project is optimized for serverless execution via GitHub Actions.

1.  **Automation (CRON):** By default, scans run at **10:00 UTC** every 2nd day.
2.  **Manual Trigger:** Go to **Actions** -> **JobLens Optimized Scan** -> **Run workflow**.
3.  **Matrix Strategy:** Each provider runs in its own isolated virtual environment for speed and stability.
4.  **Dual Push:** Results are automatically pushed to the internal `data` branch and your public mirror repository.

---

## 🛠 6. Helper Scripts (Data Processing)

Located in the `/helper` directory, these scripts allow you to filter the raw data collected in the `/outputs` folder.

| Script | Filter Logic | Usage |
| :--- | :--- | :--- |
| `filter_jobs_for_test.py` | Filters by **Job Title** (Tester, QA, etc.). | `python helper/filter_jobs_for_test.py <path_to_outputs>` |
| `filter_jobs_for_city.py` | Filters by **City/Region** in all columns. | `python helper/filter_jobs_for_city.py <path_to_outputs>` |

---

## 📊 7. Data Lifecycle & Maintenance

The system maintains itself through `sync_results.py`, which runs after every scan:

1.  **`outputs/` (Detailed Audit):** Stores full logs and Markdown reports.
    *   **Retention:** 14-day rolling window (older folders are auto-deleted).
2.  **`results/` (Global Database):** Stores `all_found_jobs.csv`.
    *   **Rotation:** Records older than 180 days are moved to `results/history/`.
3.  **Dashboard:** Refreshes `JobLens_Dashboard.xlsx` with the latest scores and deduplicated entries.

---

## 🛡️ 8. Stealth & Troubleshooting

*   **Ultra-Stealth:** The engine uses JavaScript injection to hide Selenium footprints (`navigator.webdriver`) and spoofs languages to bypass "Access Denied" screens.
*   **WinError 6:** If you see "The handle is invalid" during shutdown on Windows, it is safely suppressed and does not affect your data.
*   **Diagnostics:** If a scan fails in the cloud, check the `logs/` artifact for **screenshots (.png)** and **HTML dumps** to see exactly what the bot saw.

---
*Maintained by the jobLens Development Team. v4.0.0*