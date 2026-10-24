# v1.3.10 — Audited scan accounting, cross-module coverage & sector upload fix

## Deploy (no database re-import)
1. Keep a private Turso SQLite export and your original source files as backups.
2. Extract this ZIP and upload its **contents into the repository root**, replacing matching application files. Do not upload the ZIP itself or nest the application in another directory.
3. Preserve the existing Vercel server-only configuration: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, and `TURSO_AUTH_TOKEN`. Never put tokens in GitHub, screenshots or chat. Keep the existing database URL: this release does not create or reset a database.
4. Wait for the GitHub-connected Vercel production deployment to finish. Reload once with Ctrl+Shift+R. The sidebar must say **v1.3.10**. If not, inspect the latest production deployment before testing.
5. Section 07 → Trading Ideas Generator → Core36 → TRG → Long / Buy: confirm that **one matched cash symbol was examined**, with a direction-filter rejection and the structural-plan reason. The signal may change after subsequent imports; reasons and counts must stay explicit.
6. Section 07 → Data coverage & exclusions → search TRG or any ticker. Cash sessions and engine sessions should match. Inspect first/latest dates and the separate futures, Top5, account and reference sources. Download the report if investigating another discrepancy.
7. Section 02 → **normal file dropzone** → upload `SECTOR_WISE.xlsx`. Preview must identify `SECTOR_REFERENCE`, with positive accepted rows. Review warnings and commit once. Re-uploading identical rows is safely idempotent. No price records or ticker aliases are changed.
8. Recheck sector filters after commit. They use `COMP_LIST` for company/sector classification. Other recognized sheets provide named constituent lists.

## What changed
- Matched/checked symbols are counted **before** readiness, direction and structural-plan filters. Every matched symbol gets a diagnostic row; no silent early rejections or top-10-only rejection list.
- Separate counts: examined, data-ready, direction-eligible, structurally qualified and displayed. Qualified means passing fixed safeguards, **not a measured win probability**. Zero valid setups remains an honest result.
- Exact stored ticker queries are preferred; otherwise ticker/sector text matching is case-insensitive. Scope and query intersect consistently. A custom query no longer silently bypasses the selected futures/Top5/sector scope. Matching symbols outside scope are explicitly reported. Choose All imported cash symbols to remove watchlist restrictions.
- Read-only, searchable cross-module coverage, including reference-only instruments with no cash candles. Missing cash, stale history, short history and invalid trade plans are distinguished. Account futures suffixes are matched only using recognized contract-month syntax; distinct securities are not indiscriminately merged.
- A short-history analyst response now states `INSUFFICIENT_DATA` rather than printing zero-valued momentum and pseudo 20-day trends. No automatic analyst forecast is recorded for that response.
- Normal, ZIP and chunked staging now recognize company-reference workbooks by `SYMBOL`, `COMPANY NAME`, `SECTOR` headers, independent of filename. They share the existing staged, transactional commit pipeline, with source history and revision audits. Unknown schemas are still not guessed.
- Main dropzone reference imports **merge**. Existing stored rows and other bundled default members are retained; only incoming conflicting rows update when revisions are permitted. Incoming-row counters exclude preservation of bundled defaults. The separate reference replacement preview remains available for deliberately replacing/removing list members.
- Single-ticker and selected-watchlist scans calculate only relevant symbols; cache reads are bounded to selected symbols. Indicator mathematics and compatible 1.3.9 calculation caches are retained. Futures-observation changes are checked against current same-session data before reusing a cached summary (important after futures-only imports).
- False newer-build banner fixed using HTML build metadata; diagnostic explanation cells wrap and numeric columns align consistently.
- API direction and scan-limit validation; release/cache-busting updated to 1.3.10. No paid API, card registration or new external service introduced.

## Verify the imported data, not an invented universe
See `docs/LIVE_AUDIT_1_3_10.md` and the per-symbol CSV. Live audit figures describe the dashboard at audit time, not the older GitHub backup and not an independently verified active PSX universe. The dashboard should now make these distinctions itself.

## Database and privacy
- No database, credentials, uploaded workbooks or private account execution records are included in this release.
- `latest_cloud_sync.db.gz` in the existing repository is an older snapshot, **not** the current Turso database. Uploading this ZIP will not automatically delete that existing GitHub file. In confirmed Turso-only deployment it is not needed by the app. Retain a private copy first; then remove it from the current repository if you no longer need SQLite/GitHub snapshot fallback.
- Deleting a file from GitHub does not erase Git history. If real account records were committed publicly, address repository visibility/history separately. This code update cannot revoke previously downloaded data.
- This remains a password-free dashboard unless you separately configure deployment access control. Browser same-origin checks are not user authentication. Do not expose financial imports/settings writes publicly without suitable access control. Authentication/security architecture changes are not silently included in this bug-fix release.

## Limits retained honestly
Not a perfect predictor or live trading terminal. A sector workbook supplies classification and list membership, not fundamentals, verified index membership or cash OHLC history. Corporate-action adjustment, historical survivorship, broker short eligibility, live liquidity and intraday fill sequencing remain unverified. An INDEX date behind cash is missing benchmark data, not a reason to silently substitute another date. No historical signals are rewritten as forward forecasts. Existing forecast rules/versions are retained; this release repairs accounting and data routing, not a newly validated trading strategy.

## Validation
See `docs/VALIDATION_1_3_10.md`: 137 passed, 20 private-fixture skips, one test-client deprecation warning; disposable local libSQL and desktop/mobile browser checks.
