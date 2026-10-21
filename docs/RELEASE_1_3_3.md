# 1.3.3 — import speed, date integrity and Futures_Analysis (6) parity

## Deployment / data safety

1. Download an independent current snapshot before redeploying. If the existing page reports PENDING, preserve that snapshot especially carefully: those local changes may not be in GitHub.
2. Upload the ZIP contents to the existing repository root, replacing only source files. Preserve the live `latest_cloud_sync.db.gz`; this package has no database, workbook data, token or credentials.
3. Redeploy the existing Vercel project; keep existing GitHub environment variables. No dashboard login or new GitHub Actions workflow is required.
4. Open a fresh page against the current cloud baseline. Import the clean `2026_YEAR.xlsx` and `2026F.xlsx` together once to certify dates and update all source values.
5. Wait for **Cloud save confirmed**, not merely a local SQLite commit. On an error, download the pending snapshot; never force-overwrite a newer remote snapshot. Unsynced local data blocks reload deliberately. Reconcile missing daily inputs from their original files rather than discarding the only pending copy.

## Why November/December appeared

Both supplied source workbooks end on 21-10-2026. A stored trading date such as 2026-12-10 can be a day/month-swapped 12-10-2026 (12 October). Updating date display alone does not repair persisted records. This release uses a newly imported typed-date workbook to certify corrections: an out-of-source-coverage row is quarantined only when its swapped date, symbol and seven OHLCV measures match the clean source exactly. The full original row remains in import_issues in the same transaction. Unverified later rows remain for review. No deployment-time heuristic repair is run.

November/December **contract codes** are a different matter: NOV, NOVB and DEC are present in the supplied October futures data. They are not fabricated future trading dates and are retained.

## Section 06 workbook contract

Seven visible worksheet views retain independent state:

- Monthly Comparison: trading date and Days, annualized ascending.
- Month Filter: trading date, Days and Month/Contract, annualized ascending.
- Symbol Filter: Month/Contract, Days and Symbol across all retained dates, date ascending.
- Annualized Comparison: trading date and Days, all symbols/contracts, annualized ascending.
- Date Filter: trading date and Days, full-day comparison, annualized ascending.
- Future Symbol Summary: full contract symbol, all retained dates, date ascending.
- Date Summary: trading date, all symbols, symbol ascending.

The existing 2-Month Rolling Retention policy tab remains an application control, not an additional workbook worksheet. Eight-sheet export retains seven visible sheets plus hidden Data. Export filters exclude UI-only pin state. The dashboard recreates the worksheet behavior; it is not an embedded Excel editor.

Cash prices match only on the same symbol and trading date. Missing cash prices remain N/A, never forward-filled. Difference = Future − Current. Difference % = Difference / Current × 100. Annualized % = Difference % × 365 / Days. Dates remain ISO internally and are shown DD-MM-YYYY.

## Performance and honest save status

An import previously performed two four-request cloud checks before the four-request Git write. It now performs one three-request preflight and four write requests (12 → 7). Reusing the checked parent is safe because PATCH uses force=false and fast-forward failure retains the pending local snapshot. Network work runs off the async event loop. No background "fire-and-forget" cloud save is used on ephemeral hosting.

Snapshot compression uses gzip level 1 rather than 6, trading a modestly larger file for less CPU time. Actual live upload speed depends on GitHub and Vercel. Staging loads only the modules present in the upload. Startup no longer computes unused overview/technical/intelligence analysis; overview uses a lightweight compatible route.

Auto → Latest is dataset-based, never hardcoded to 21 October or the computer clock. Manual historical worksheet/account selections stay pinned until Reset to Latest. Summary, import, settings, export and quality pages show data freshness, not an invented date filter.

## Verification

See QA_1_3_3.json. Tests use isolated databases and fake GitHub responses. User files were validated separately against all seven worksheet caches and all 4,248 retained hidden Data comparison rows. No live GitHub write or Vercel deployment was performed by this build.
