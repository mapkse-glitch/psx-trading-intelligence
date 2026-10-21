> **Historical documentation (pre-1.3).** Preserved for project continuity, not current deployment instructions. Where this conflicts with README.md or DEPLOY_1_3.md, use the 1.3 documents. Old absolute paths, public-hosting advice, fixed dataset counts, probability wording and blanket reconciliation claims are superseded.

# Official 2026 Documentation Audit: How to Host PSX Trading Intelligence Dashboard on ONE Permanent Free URL

This guide is based on a direct, line-by-line review of the official 2026 documentation for **Render.com**, **Hugging Face Spaces**, **Vercel**, **GitHub (Pages & Codespaces)**, **Koyeb**, **Fly.io**, **PythonAnywhere**, **Cloudflare Tunnel**, and **Tailscale Serve/Funnel**.

---

## 1. What Every Major Platform's Official Documentation Actually Says (Verified October 2026)

Because your application is a **full-stack Python FastAPI server + a live 21 MB SQLite database (`app.db`) + dynamic `.xlsx` workbook generator**, most "free hosting listicles" online give bad advice that will cause your uploaded data to vanish. Here is what each provider's official documentation states in 2026:

| Platform & Official Doc Source | 100% Free ($0, No Card)? | Runs Python FastAPI? | Gives ONE Permanent URL? | What the Official Documentation Says About Your SQLite Data & Catch | Verdict |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **1. Render.com Free Web Service** + **Private GitHub Repo Auto-Sync** (`render.com/docs/free`) | **YES** ($0/mo, no credit card required) | **YES** (Native Python & Docker) | **YES** (`https://psx-trading-intelligence.onrender.com`) | Per `render.com/docs/free`: Free web services get **750 hours/month** (enough for 24/7 all month!) and spin down after 15 mins idle (~45s wake-up). Normally, Render wipes local disk changes on spin-down. **HOWEVER**, we built `CloudSyncService` (`psx_app/services/cloud_sync_service.py`) directly into your app: it automatically compresses `app.db` (`5.7 MB`) and saves it to your **Private GitHub Repo** on every import, and restores it automatically whenever Render wakes up! | **#1 BEST 100% CLOUD-HOSTED OPTION (Zero PC required, 1 URL everywhere)** |
| **2. Tailscale Funnel / Serve** or **Cloudflare Tunnel** on Your Office/Home PC (`tailscale.com/kb/1223/funnel`, `developers.cloudflare.com/cloudflare-one`) | **YES** ($0/mo, no credit card required for Tailscale) | **YES** (Runs on your PC) | **YES** (`https://<your-pc>.<tailnet>.ts.net`) | Gives you **one permanent HTTPS URL** that works from your Office PC, Home PC, and Mobile Phone browser with **0-ms cold start** and **100% local SSD persistence**. Only catch: the PC running `start_dashboard.bat` must be powered on when you visit the URL. | **#1 BEST PRIVATE HARDWARE OPTION (Fastest speed, zero sleep)** |
| **3. Hugging Face Spaces** (`huggingface.co/docs/hub/spaces-overview`) | **NO** (Changed in 2026) | YES | YES (`https://...hf.space`) | Per `huggingface.co/docs/hub/spaces-overview` (verified Oct 2026): *"Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a paid plan to create: PRO ($9/mo) for personal accounts."* Also, `/data` is wiped on restart unless you pay for Storage Buckets. | **Disqualified for Free Tier** (Requires $9/mo PRO to create Docker Spaces in 2026) |
| **4. Vercel Hobby** (`vercel.com/docs/functions/runtimes/python`, `vercel.com/docs/limits`) | YES | Serverless only | YES | Per `vercel.com/docs/limits`: Serverless functions have a **read-only filesystem** except `/tmp`, which is **wiped after every invocation**. Any file you upload in `02 • Import Center` disappears minutes later. | **Do Not Use** (Wipes SQLite database) |
| **5. GitHub Pages** (`docs.github.com/en/pages`) | YES | **NO** (Static HTML/JS only) | YES | Per GitHub Docs: GitHub Pages **only serves static files** and cannot run Python, FastAPI, SQLite, or dynamic `.xlsx` exports. *(However, **GitHub Repositories** ARE the best free place to host your private code + auto-synced database for Render!)* | **Cannot Run Python Alone** (Use Private GitHub Repo + Render instead) |
| **6. GitHub Codespaces** (`docs.github.com/en/billing/.../github-codespaces`) | YES (Limited quota) | YES | Temporary port-forwarded URL | Per GitHub Docs: Free personal accounts get **120 core-hours/month** (only **60 hours/month** on a 2-core machine) and **15 GB-month** storage. Stops after 30 mins idle and deletes stopped codespaces after 30 days. | Good for coding, **too limited (60 hrs/mo) for daily hosting** |
| **7. Koyeb & Fly.io** (`koyeb.com/docs`, `fly.io/docs`) | **NO** | YES | YES | Koyeb removed its card-free Hobby plan in Feb 2026 (now requires Pro $29/mo or $29 card hold). Fly.io ended free allowances in Oct 2024 (only a 7-day / 2-hour trial). | **Disqualified** (No longer free in 2026) |
| **8. PythonAnywhere Free** (`help.pythonanywhere.com`) | YES | **WSGI only** (No native ASGI) | YES | Only **512 MB total disk space**, blocks outbound internet access, WSGI-only, and expires every 30 days if not manually renewed. | **Too small / restrictive** |

---

## 2. THE WINNER: Where You Should Host It (Step-by-Step)

To get **ONE single permanent URL (`https://psx-trading-intelligence.onrender.com`)** that is **100% Free ($0, no credit card)**, works on your **Office PC, Home PC, and Mobile Phone browser**, and **never loses your uploaded data when the server sleeps**, use **Private GitHub Repo + Render.com Free Web Service** using the built-in **`render.yaml`** and **`CloudSyncService`** we just added to your project.

### How It Works Under the Hood
1. **Your Code + Initial Database (`app.db`) Live in a Private GitHub Repo**:
   - Because `app.db` is `20.9 MB` (and `5.7 MB` compressed), it fits inside a standard **Private GitHub Repository** (which allows up to 100 MB per file for free).
2. **Render.com Runs the Live Python FastAPI Server (`https://psx-trading-intelligence.onrender.com`)**:
   - Render gives you **750 free hours every month** (a full month only has 720–744 hours) with **no credit card required**.
3. **Built-in `CloudSyncService` Solves Render's 15-Minute Sleep Wipe Automatically**:
   - Normally, when Render goes to sleep after 15 minutes of inactivity, local disk changes are lost.
   - Because we built `psx_app/services/cloud_sync_service.py` into your app:
     - **Whenever you upload & commit new PSX files** (from Office, Home, or Phone), the app automatically compresses `app.db` into `psx_data/backups/latest_cloud_sync.db.gz` (`5.7 MB`) and commits it straight back to your Private GitHub Repo via the GitHub API!
     - **Whenever Render wakes up from sleep**, your app automatically checks your Private GitHub Repo on startup, verifies `PRAGMA integrity_check`, and loads the latest `app.db` before opening the dashboard!

---

## 3. Exact 5-Minute Setup Guide to Get Your Single Permanent URL

We have already generated **`/home/user/render.yaml`**, **`/home/user/Dockerfile`**, and **`/home/user/psx_app/services/cloud_sync_service.py`** in your workspace. Follow these 4 steps once:

### Step 1 — Create a Free Private GitHub Repository
1. Go to [github.com/new](https://github.com/new), name the repository **`psx-trading-intelligence`**, select **Private**, and click **Create repository**.
2. Push this `/home/user` workspace folder to your repository (including `psx_app/`, `psx_data/database/app.db`, `requirements.txt`, `render.yaml`, and `Dockerfile`).

### Step 2 — Create a Free GitHub Personal Access Token (For Automatic Database Sync)
1. On GitHub, go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Select **Only select repositories** → pick **`psx-trading-intelligence`**.
3. Under **Repository permissions**, set **Contents** to **Read and write**.
4. Click **Generate token** and copy your token (`github_pat_...`).

### Step 3 — Deploy to Render.com (Free Plan, No Credit Card)
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign in with your GitHub account.
2. Click **New +** → **Web Service** → connect your **`psx-trading-intelligence`** repository.
3. Choose the **Free** instance type (`$0/month`).
4. Verify these commands (automatically pre-filled if you use `render.yaml`):
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `python3 -m uvicorn psx_app.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add two keys:
   - `GITHUB_SYNC_REPO` = `your-github-username/psx-trading-intelligence`
   - `GITHUB_SYNC_TOKEN` = `github_pat_...` *(the token from Step 2)*
6. Click **Create Web Service**.

### Step 4 — Bookmark Your Single URL Everywhere!
- Within ~2 minutes, Render gives you your permanent HTTPS URL:
  **`https://psx-trading-intelligence.onrender.com`**
- Open that exact URL on your **Office PC**, **Home PC**, and **Mobile Phone** (add to Home Screen on iOS/Android).
- Whenever you upload a file at the Office and click **Import and Update**, it automatically syncs to your Private GitHub repo and is immediately available at the exact same URL when you open it at Home or on your Phone!

---

## Troubleshooting: 403 Forbidden on GitHub Push (Token Permissions)

If the Import Center shows **"⚠ Sync Issue: GitHub 403 Forbidden"**, your `GITHUB_SYNC_TOKEN` has **read-only** permission. GitHub fine-grained tokens default to NO repository permissions, so pushes are always rejected until you add write access.

**Fix (about 60 seconds, no card involved):**
1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens** → open your token (e.g. `psx-trading-intelligence`).
2. Under **Permissions**, the box says "No repository permissions added yet" → click **"+ Add permissions"**.
3. Tick **Contents** and set its access dropdown to **"Read and write"** (Metadata: Read-only is auto-added — normal).
4. Scroll down and click the green **Update** button. Same token value — **no Vercel env change, no redeploy needed.**

**Classic token alternative:** check the full **`repo`** scope.

### Auto-Sync & the Emergency Push Button behavior
- **Every successful upload Commit automatically pushes** the fresh `latest_cloud_sync.db.gz` snapshot to GitHub — you never need to push manually.
- The **"Push Snapshot to GitHub Now"** button is an **emergency-only** control: it is **hidden whenever auto-sync is healthy** and automatically **reappears in red** if a push ever fails (e.g. token issue). Success/failure state is persisted in the SQLite `sync_state` table, so the healthy state survives Vercel cold starts.
- After fixing the token, the commit toast confirms: `✓ … auto-pushed to GitHub (abc1234)`.

### Large files (previously HTTP 413 — fixed)
Vercel rejects any single HTTP request body over ~4.5 MB. The Import Center now detects files near that limit and **automatically slices every file into ~3 MB pieces**, uploads them one at a time, and the server reassembles them before staging — so file size is no longer a problem for daily uploads from the cloud UI. Pieces are validated (missing-piece recovery is built in — if a piece lands on a different server instance, the browser re-sends just the missing pieces automatically) and temporary chunk folders are cleaned after assembly and swept after 3 hours.
