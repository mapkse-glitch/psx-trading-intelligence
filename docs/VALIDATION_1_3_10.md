# v1.3.10 validation

## Automated regression
Final isolated run: **137 passed, 20 skipped, 1 deprecation warning**, 8.81 seconds.

The 20 skips require older private historical reference fixtures that were not provided to the portable suite. They are not represented as passing tests. The warning is Starlette's test-client/httpx deprecation, not a failing runtime check.

Command used: `PSX_TEST_LIBSQL_SERVER=http://127.0.0.1:8176 pytest -q` against a disposable **loopback-only** official libSQL server v0.24.32. Never run disposable-database tests against a real Turso database.

Includes: bearish symbol rejected by Long-only but counted as examined; all early exclusions accounted for; scope intersections and exact ticker preference; current/stale/short-history/zero-volume cases; missing reference-only cash; normal/ZIP reference imports; duplicate/idempotent commit; audited revisions; defaults preserved; cross-worker Turso staging; atomic rollback; full 903-row reference import using bounded bulk writes; futures-only context cache invalidation; build-metadata consistency; unavailable weekly/momentum values not replaced by zero. Existing financial, date, display, import, forecast and research regressions were also run.

## Browser checks (exact patched local application)
Using a private copy of the older GitHub SQLite backup, not the production Turso database:
- TRG + Long-only shows one examined symbol, direction rejection and structural R/R rejection.
- Full-history TRG analyst, execution conditions and no-opening decision render.
- AAL's short stored history displays the explicit insufficient-history state.
- Cross-module coverage tab filters TRG and exposes data provenance.
- The actual attached `SECTOR_WISE.xlsx` is recognized in the normal file uploader with **903 accepted rows** in preview (not a production commit).
- All sidebar modules opened: Overview, Import, Top5, both accounts, Futures, Technical, Reconciliation, Market Explorer and Settings.
- Desktop 1440px and mobile 390px checked; no page-level mobile overflow; explanations wrap inside scrollable tables.
- No JavaScript page errors; no false build-upgrade banner on a fresh v1.3.10 load.
- Both changed JavaScript files pass `node --check`.

Production was inspected read-only, not redeployed. The tests do not prove predictive profitability, complete historical source accuracy or production deployment success. Follow the deployment acceptance checks in UPGRADE_1_3_10.md.
