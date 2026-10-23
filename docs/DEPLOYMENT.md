> Legacy reference: deployment and Section 07 behavior have changed. Current instructions: ../UPGRADE_1_3_7.md and SECTION07_RELIABILITY.md. Older fixture-specific statements are not a report of your current database.

# Deployment & Local Installation Guide (Windows 11 & Cross-Platform)

## 1. System Requirements
- **Operating System**: Windows 11 (primary target), Windows 10, Linux, or macOS.
- **Python**: Python `3.10+` (`3.11`, `3.12`, or `3.13` recommended).
- **Disk Space**: ~150 MB for the database, raw archive, and Excel exports.
- **Network**: **Zero external network access required** for runtime operation. All stylesheets, scripts, SVG charts, and fonts are bundled locally.

---

## 2. Windows 11 Installation & One-Click Startup

### Step 1: Create Virtual Environment & Install Dependencies
Open PowerShell or Command Prompt in the project root folder:
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure Local Data Directory (Optional)
By default:
- If `PSX_DATA_DIR` is not set, the application stores data in `./psx_data` inside the workspace (which already contains the pre-migrated SQLite database and backups).
- To store data in the standard Windows 11 user profile directory (`%LOCALAPPDATA%\PSXTradingDashboard\`), set:
```bat
set PSX_DATA_DIR=%LOCALAPPDATA%\PSXTradingDashboard
```
If `PSX_DATA_DIR` points to an empty directory and `drive_mirror/` is present, the application automatically runs the initial historical migration on startup.

### Step 3: Launch the Application
Double-click **`start_dashboard.bat`** (or run it from Command Prompt).
- It binds to `http://127.0.0.1:8000` by default and opens your default browser automatically.

---

## 3. Linux / Container / Server Deployment
```bash
pip install -r requirements.txt
./start_dashboard.sh
```
The server binds to `0.0.0.0:8000` and serves both the FastAPI REST API (`/api/*`) and the Single-Page Application (`/`).
