# v1.3.11 validation

## Automated tests
- **165 passed, 20 skipped, 1 warning.**
- Skips are the existing opt-in private historical-reference fixtures, not hidden test failures.
- Warning: Starlette TestClient/httpx dependency deprecation. Application behavior and all executed assertions passed; dependency upgrades are not mixed into this display/data-routing release.
- Includes a real disposable libSQL HTTP server on loopback, never the production Turso database.

Run with an isolated virtual environment (Node.js is also needed for the frontend-helper assertions; without it those assertions are explicitly skipped):
```
pip install -r requirements.txt
pytest -q
# Optional: start a disposable libSQL server first, then include remote tests:
PSX_TEST_LIBSQL_SERVER=http://127.0.0.1:8176 pytest -q
```
Remote fixtures drop/recreate application tables and refuse non-loopback hosts. Never point tests at production.

## Added regressions
- Calculated index-table volume equals the cash-symbol sum for the exact date; zero is retained as zero; futures volume is not double-counted. Verified with SQLite and libSQL HTTP.
- Conditional buy and short timing, directional loss limits and profit targets; unvalidated plans never display invented active levels.
- Plain-language explanations change when input prices, daily/weekly change and trend data change. The actual analyst API returns the guide.
- Pending, open, no-trade, not-triggered, ambiguous and missing-data outcomes never acquire synthetic profit. Closed positive/negative/zero returns retain their actual sign/value.
- Invalid dates, weekends and dates before history never silently resolve to future data or latest data.
- Exact colour variables, matching server/interface build versions, date controls and runtime execution of diagnostic HTML generation.

## Local browser validation
Headless Chromium/Playwright against an isolated copy, with no production credentials:
- Overview, Import, Top5, both accounts, Futures, Reconciliation and Settings rendered successfully.
- Every Section07 tab rendered: ideas, data coverage, Core36, charts/past tests, all stocks, analyst, saved forecasts.
- Unknown ticker produces an honest unavailable-analysis message, not a fabricated trade.
- Analyst primary view has all six explicit action sections and no unexplained N/A. A conditional rendering test verifies actual supplied entry/stop/target lines and exact semantic colours.
- Saved forecasts explain the time window and pending returns.
- Market, account daily detail and futures worksheet calendars tested in the rendered DOM. Selecting Sunday 2026-10-18 resolved to Friday 2026-10-16 with a visible notice.
- Calculated market volume **396,904,989** on the local copy’s 2026-10-16 matched the volume view. This is test-copy evidence, not a hard-coded value or a claim about production today.
- Positive colour computed as `rgb(3, 216, 21)` and negative as `rgb(246, 49, 49)` in **both** light and dark themes.
- Mobile viewport 390px; document width 390px; no page-level horizontal overflow. Wide tables retain their own scroll regions.
- Account/futures Reset-to-latest and futures All-dates modes clear obsolete date notices. Calendar notices remain stable without repeated DOM redraws.
- No uncaught JavaScript errors in the successful runs.

## What these checks do not prove
No forecast accuracy, live trade execution, verified fundamental analysis, survivorship-free universe or guaranteed completeness of every source year is claimed. The live production site was inspected read-only; the modified source still requires deployment. Historical financial private-reference assertions remain opt-in when their original files are available.
