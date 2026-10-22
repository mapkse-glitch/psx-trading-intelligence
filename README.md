# PSX Intelligence 1.3.5 — historical workbook imports

This version removes the unrequested password and sign-in system. The dashboard opens directly. No owner password, session secret, account creation or sign-out step is required. Existing PSX_ADMIN_PASSWORD / PSX_SESSION_SECRET / PSX_AUTH_DISABLED environment variables are ignored and may be removed from your hosting settings.

## Update the existing GitHub / Vercel application

1. Download an independent current-data backup first.
2. Extract this ZIP. Upload its **contents** into the existing repository root, replacing matching source files—not the ZIP itself and not an extra enclosing folder.
3. **Preserve the existing `latest_cloud_sync.db.gz` exactly. Do not delete or overwrite it.** This is a source-only release: databases, raw uploads, backups and credentials are intentionally excluded.
4. Commit and redeploy the existing Vercel project. Open the site: the dashboard should appear immediately. No new password variables are needed.
5. Keep the existing GitHub sync configuration (`GITHUB_SYNC_REPO`, `GITHUB_SYNC_BRANCH`, `GITHUB_SYNC_TOKEN`) if you use cloud persistence. Existing public or private repositories are supported. A private repository is recommended for confidential snapshots but is not required for sync. GitHub integration credentials are separate from the removed dashboard login.

Read [deployment and recovery](docs/DEPLOY_1_3.md). Password-free access means anyone who can reach the deployed site can view account data, download data and invoke data-changing actions. A private GitHub repository does **not** make the Vercel website private. Same-origin browser checks are request hygiene, not access control.

## 1.3.5 — historical workbook import correction

Raw OHLCV XLSX files are now detected from their columns, not the hard-coded year 2026. The attached 2016 and 2022 archives were fully imported and independently validated in an isolated database: 171,431 records, preserved original dates and safe repeat-upload deduplication. Unsupported zero-row files are visibly SKIPPED rather than described as ready to import.

**After deployment, discard the old staged preview and select the original historical files again.** Existing staged manifests are not re-parsed by a code update. Do not rename old files to 2026 or alter their dates. This package does not itself add history to live data.

See [historical import and validation notes](docs/RELEASE_1_3_5.md).

## 1.3.4 — complete date-history and freshness correction

- Removes only workbook-proven swapped-date duplicates, including duplicates inside the valid overall date range. Every authoritative source key is protected; all seven measures must match before a missing-key duplicate is quarantined in the import transaction.
- Clean warm server instances check the canonical cloud snapshot before API reads, using a shared 30-second metadata cache. Changed snapshots are integrity-checked, backed up locally and loaded; pending local changes are never discarded. Unchanged snapshots are not downloaded again.
- The browser checks freshness at launch, on Refresh, when returning to the tab, and once per minute while active. A changed snapshot clears old analytics caches; manually selected historical dates stay pinned.
- Versioned, non-cached shell/assets prevent old interface files from silently surviving a deployment. Failed cloud checks display an explicit warning rather than claiming freshness.
- Futures trading dates and contract expiry months are explicitly distinguished. NOV/DEC contracts traded in October remain valid.
- Keeps 08 Data Quality & Reconciliation and 10 Settings and Backup. Removes the redundant 09 navigation page; per-module downloads and the contextual header Export remain.
- Retains 1.3.3 import-speed optimizations, all worksheet filters, account separation and existing financial calculation semantics.

**Deployment does not itself run a date-repair mutation.** For another existing database, first back up, then import the clean typed-date `2026_YEAR.xlsx` and `2026F.xlsx` together. Only source-proven duplicate swaps are quarantined. Do not force a date label to October while keeping polluted history.

See [release and verification notes](docs/RELEASE_1_3_4.md).

## Retained corrections

- Clean light/dark interface, separate account cards, responsive navigation, keyboard-friendly tables and readable financial figures.
- Independent filters in all futures worksheets, eight-sheet export, sortable DD-MM-YYYY Excel date display, and machine-readable ISO dates in CSV.
- Stale cloud-snapshot rejection, pending/error reporting, verified online backups and restore-to-cloud attempt.
- Reviewed transactional date repair with plan fingerprint and safety backup; no automatic live repair on deployment.
- Scoped reconciliation with evidence; absent private reference workbooks show NOT_CHECKED.
- Rule scores—not probability of profit—and same-date volume/most-liquid futures context.
- Settings validation, import retry handling, isolated export responses and graceful first-run/empty-account screens.

Accounts 91404 and 91269 remain separate. Existing financial calculation semantics and manual import workflow are retained. No missing cash-price backfill, live price feed, trade execution or external LLM dependency was added.

## Local launch

Python 3.12+ (tests use Python 3.13):

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. No login is needed. `PSX_DATA_DIR` chooses local runtime storage; default `./psx_data`. Local launchers are also included. A source-only checkout begins empty unless restored, imported, or hydrated from your configured GitHub repository.

See [changes](docs/RELEASE_1_3.md), [verification](docs/TESTING_1_3.md) and [design rationale](docs/DESIGN_1_3.md). No zero-defect guarantee or live Vercel deployment claim is made.
