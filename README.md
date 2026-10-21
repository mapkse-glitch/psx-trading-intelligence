# PSX Intelligence 1.3.3 — faster imports and workbook-verified futures dates

This version removes the unrequested password and sign-in system. The dashboard opens directly. No owner password, session secret, account creation or sign-out step is required. Existing PSX_ADMIN_PASSWORD / PSX_SESSION_SECRET / PSX_AUTH_DISABLED environment variables are ignored and may be removed from your hosting settings.

## Update the existing GitHub / Vercel application

1. Download an independent current-data backup first.
2. Extract this ZIP. Upload its **contents** into the existing repository root, replacing matching source files—not the ZIP itself and not an extra enclosing folder.
3. **Preserve the existing `latest_cloud_sync.db.gz` exactly. Do not delete or overwrite it.** This is a source-only release: databases, raw uploads, backups and credentials are intentionally excluded.
4. Commit and redeploy the existing Vercel project. Open the site: the dashboard should appear immediately. No new password variables are needed.
5. Keep the existing GitHub sync configuration (`GITHUB_SYNC_REPO`, `GITHUB_SYNC_BRANCH`, `GITHUB_SYNC_TOKEN`) if you use cloud persistence. Existing public or private repositories are supported. A private repository is recommended for confidential snapshots but is not required for sync. GitHub integration credentials are separate from the removed dashboard login.

Read [deployment and recovery](docs/DEPLOY_1_3.md). Password-free access means anyone who can reach the deployed site can view account data, download data and invoke data-changing actions. A private GitHub repository does **not** make the Vercel website private. Same-origin browser checks are request hygiene, not access control.

## 1.3.3 — requested corrections

- Source-verified date cleanup during re-import of typed-date OHLCV XLSX files. Original swapped rows are retained in `import_issues`; no clock-based guessing or automatic live repair on deployment.
- Seven Section 06 views verified against `Futures_Analysis (6).xlsx`, including independent filters, all-date Symbol Filter, same-date cash/futures matching and annualized calculations.
- Section 06 date dropdowns match the workbook's available-date list and display DD-MM-YYYY consistently, independent of browser locale.
- Auto → Latest badges across all modules. Futures dated sheets and account daily detail follow new imports unless explicitly pinned; Reset to Latest restores automatic tracking.
- One verified cloud preflight per import instead of two; root-only Git tree lookup, no redundant repository metadata lookup, and unchanged non-force fast-forward protection. A concurrent remote update is rejected, never overwritten.
- No technical-analysis prewarming on cold start. The overview requests only the data it displays. Daily TXT staging no longer scans unrelated cash/futures/account histories.
- Faster snapshot compression, duplicate-click prevention, no unnecessary re-push for an already committed/saved batch, and accurate completion messages.
- OHLCV updates compare all seven imported measures, so a changed volume/high/low is not skipped merely because the closing price did not change.

**For an existing database with swapped dates:** download a safety snapshot first, deploy this source-only update without replacing `latest_cloud_sync.db.gz`, then import the clean `2026_YEAR.xlsx` and `2026F.xlsx` together once. Only proven date swaps are quarantined. If unexplained future trading dates remain, review Settings → Date normalization; unverified rows are not silently removed. NOV/DEC contract codes are legitimate forward contract months and do not imply future trading dates.

See [release and recovery notes](docs/RELEASE_1_3_3.md).

## 1.3.3 — requested corrections

- Source-verified date cleanup during re-import of typed-date OHLCV XLSX files. Original swapped rows are retained in `import_issues`; no clock-based guessing or automatic live repair on deployment.
- Seven Section 06 views verified against `Futures_Analysis (6).xlsx`, including independent filters, all-date Symbol Filter, same-date cash/futures matching and annualized calculations.
- Section 06 date dropdowns match the workbook's available-date list and display DD-MM-YYYY consistently, independent of browser locale.
- Auto → Latest badges across all modules. Futures dated sheets and account daily detail follow new imports unless explicitly pinned; Reset to Latest restores automatic tracking.
- One verified cloud preflight per import instead of two; root-only Git tree lookup, no redundant repository metadata lookup, and unchanged non-force fast-forward protection. A concurrent remote update is rejected, never overwritten.
- No technical-analysis prewarming on cold start. The overview requests only the data it displays. Daily TXT staging no longer scans unrelated cash/futures/account histories.
- Faster snapshot compression, duplicate-click prevention, no unnecessary re-push for an already committed/saved batch, and accurate completion messages.
- OHLCV updates compare all seven imported measures, so a changed volume/high/low is not skipped merely because the closing price did not change.

**For an existing database with swapped dates:** download a safety snapshot first, deploy this source-only update without replacing `latest_cloud_sync.db.gz`, then import the clean `2026_YEAR.xlsx` and `2026F.xlsx` together once. Only proven date swaps are quarantined. If unexplained future trading dates remain, review Settings → Date normalization; unverified rows are not silently removed. NOV/DEC contract codes are legitimate forward contract months and do not imply future trading dates.

See [release and recovery notes](docs/RELEASE_1_3_3.md).

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
