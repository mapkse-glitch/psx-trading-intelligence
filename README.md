# PSX Intelligence — corrected release 1.3.0

Private, local-first PSX analysis workspace: FastAPI, SQLite WAL, vanilla JavaScript and OpenPyXL. Imported historical/end-of-day data, not a live feed or order execution service. No external LLM subscription is required.

## Start here — existing GitHub/Vercel deployment

1. **Download an independent backup before updating. Make the GitHub repository private.** A previously public snapshot may already have been downloaded; changing visibility cannot undo that exposure.
2. Extract this ZIP and upload its **contents into the existing repository root**, replacing matching code files. **Do not delete, replace or overwrite your existing `latest_cloud_sync.db.gz`.** No database, raw inputs, credentials or snapshot are included in this ZIP. It is a complete source-code release, not a replacement for your live financial data.
3. In Vercel project Settings → Environment Variables, set `PSX_ADMIN_PASSWORD` (a unique password, 12+ characters), `PSX_SESSION_SECRET` (random, 32+ characters), `GITHUB_SYNC_REPO` (`owner/repository`), `GITHUB_SYNC_BRANCH` (`main`, unless different), and `GITHUB_SYNC_TOKEN` (fine-grained token restricted to this private repository, Contents Read and Write). Redeploy. **Never commit these secrets to GitHub. Do not enable `PSX_AUTH_DISABLED` on Vercel.**
4. Sign in. Verify Settings → database integrity and cloud state, download another snapshot, then inspect the date-normalization dry run. Apply only after reviewing its candidates. The release does **not** automatically repair your live database.

**Read [the complete deployment and recovery guide](docs/DEPLOY_1_3.md) before uploading.**

## What changed

- Owner login, signed HttpOnly/SameSite cookies, protected finance/export/backup APIs, CSRF checks and fail-closed setup.
- Private-repository requirement, known-base cloud snapshots, stale-worker rejection, pending/error status instead of false success, verified online backups and restore-to-cloud handling.
- Date-repair plan fingerprint, confirmation, pre-repair verified backup, transactional repair and cache invalidation. Future-dated data blocks generated setup candidates.
- Scoped reference reconciliation with evidence; missing references show NOT_CHECKED, not MATCH. No blanket “100% reconciled” claim.
- Independent filters carried into each of the seven visible futures worksheets; hidden source Data sheet retained. Symbol Filter keeps all retained dates. Sortable Excel dates display DD-MM-YYYY; machine-readable CSV remains ISO.
- Rule scores are not win probabilities. Static business background is labeled unverified; same-date volume/futures evidence uses the most liquid matching contract.
- Cleaner overview, separate account cards, light/dark themes, mobile navigation, keyboard-friendly scrollable tables, visible focus, labeled inputs and readable contrast. All ten modules remain.
- Safer settings validation, multi-file chunk retry, unique export response copies, no automatic backup deletion, and graceful empty-workspace exports.

## Preserved rules

Accounts 91404 and 91269 stay separate. Existing commission/SST and trading calculation semantics are retained. Missing same-date cash prices remain N/A—no forward filling. Manual import/stage/review/commit is primary. Futures filters remain worksheet-local, not universal. Original raw files are retained locally; cloud database snapshots do not include those raw files.

## Local launch (Python 3.12+; verified on 3.13)

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set `PSX_ADMIN_PASSWORD` and `PSX_SESSION_SECRET` in your shell before starting. The application does not automatically read a `.env` file. Set `PSX_DATA_DIR` to a persistent local folder if desired; otherwise the local runtime is `./psx_data`. Run `bash start_dashboard.sh` or `start_dashboard.bat`, then visit `http://127.0.0.1:8000`.

A loopback-only, explicit development bypass (`PSX_AUTH_DISABLED=1`) exists for isolated tests, not public access. Never use it for an Internet-facing deployment. A source-only checkout starts empty unless restored/imported or hydrated from the configured private repository; this is intentional.

## Verification and limits

See [testing](docs/TESTING_1_3.md), [release changes](docs/RELEASE_1_3.md) and [design rationale](docs/DESIGN_1_3.md). Historical documents are retained with a superseded notice. Local tests do not prove a live Vercel deployment or guarantee zero defects. GitHub snapshot persistence is a single-owner compromise, **not a transactional multi-writer database**. Keep independent backups and operate one import/settings/repair writer at a time.
