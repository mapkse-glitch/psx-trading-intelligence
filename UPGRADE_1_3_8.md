# Upgrade to 1.3.8 — table alignment and newest-first dates

## Existing Turso dashboard

1. Keep an independent database backup. Pause imports during deployment.
2. Extract the ZIP and upload its **contents** into the existing GitHub repository root, replacing matching files. Include `.gitignore` and `.vercelignore`. Do not nest the application inside an extra folder.
3. Keep the existing private Vercel variables: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. No database recreation, migration, token replacement or historical re-import is needed for this update.
4. Commit and deploy. Reload the browser and confirm **v1.3.8** and **Turso: connected**. A stale-build notice means the browser and server versions differ; reload after the deployment finishes.
5. In Futures → Symbol Filter, verify that the most recent **imported trading date** is the top row. In both Account modules, verify the latest-date badge agrees with the first date in Daily Summary. Check date pins and Reset to Latest.

## What changed

- Numeric table headings and values share right alignment, tabular digits and consistent padding. Dates, ticker symbols, descriptions and status text stay left-aligned. Identifier strings keep leading zeros.
- Date-based tables display latest first: Top 5 date blocks; account daily/period/monthly/yearly tables and trade logs; Futures multi-date comparisons and symbol summaries; dated reconciliation lists; import history, backups, rule history and historical-audit yearly results.
- Trading-date selectors show newest first. Date sorting uses explicit ISO/DD-MM-YYYY parsing, not ambiguous browser month/day guessing. Invalid dates sort last rather than being silently swapped.
- Same-date rank/order is preserved, including annualized rankings, Top 5 rank, indicator rows, pivot levels and symbol-performance rankings. Totals stay at the bottom.
- Financial API arrays are copied for display sorting. Charts and indicator history stay chronological; no stored dates/prices, formulas, account totals, trade-side normalization or database schemas are rewritten. Existing workbook export layouts/order and audit JSON chronology are retained intentionally.
- Related fixes: native date inputs now refresh their adjacent DD-MM-YYYY readout when edited; account latest badges use the newest date explicitly; obsolete hard-coded rolling-window month/year captions were removed; total-row colours use theme variables so totals remain readable in light and dark modes; long backup messages and rule parameters wrap inside their cells.

## Preserved from 1.3.7

Direct Turso reads/writes, full stored-history technical calculations, stale-data/trade-plan safeguards and optional historical rule audit. The technical calculation engine remains 1.3.7 because this release does not alter its formulas. The application/UI version is 1.3.8.

Missing source history still needs importing. Latest imported date is not a live exchange feed. An OCT/NOV contract is an expiry label, not a future trading date. The dashboard does not invent missing sessions or adjust corporate actions.

## Cleanup and scope

The ZIP is source-only: no credentials, databases, workbooks, bytecode or local previews. Uploading it does **not** delete old tracked GitHub files. Follow the cleanup list in `UPGRADE_1_3_7.md`; the optional `scripts/cleanup_repository.py` defaults to a dry run. Do not delete the only copy of `latest_cloud_sync.db.gz` or any independent backup.

These changes were checked against disposable local HTTP libSQL databases and a copy of an older snapshot, not your live Turso or Vercel deployment. See `docs/QA_1_3_8.json` for exact coverage and exclusions. Production credential permissions, current source-data completeness, provider quotas, corporate-action adjustments and live deployment routing cannot be established by local table tests.

**Security remains unchanged:** the website is password-free. If it is publicly reachable without hosting access protection, visitors can potentially read or alter financial data. Keep Turso credentials server-side, and protect hosting access when private use is intended. Authentication was not silently added as part of a table-layout update.
