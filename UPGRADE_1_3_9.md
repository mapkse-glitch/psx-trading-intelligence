# PSX Intelligence 1.3.9 — accountable analysis & Market Explorer

## Deploy (existing Vercel + Turso)
1. Download an independent SQLite backup from Turso before updating code.
2. Extract this ZIP. Upload its **contents** to the existing GitHub repository root (main.py, psx_app/, requirements.txt, etc.). Do not upload the ZIP itself as the application. Include the hidden `.github` directory if you want optional research automation.
3. Keep existing Vercel server environment variables: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. Never put tokens in source, chat, frontend code or a public screenshot. The token needs schema/write permission for additive tables.
4. Redeploy from the updated commit. Startup adds the new reference/forecast/research tables. It does not drop canonical tables, reimport prices, replace the Turso database, or require a new database URL.
5. Reload the dashboard and verify UI/API version **1.3.9**. Open Section 07 → Automated Technical Analyst. Confirm the forecast-save acknowledgement. Open Forecasts & Results. Test one small known import and verify its commit acknowledgement and forecast-reconciliation status.
6. Section 09 is Market Explorer. Company/sector defaults from your workbook are included. The separate reference uploader at the top of Section 02 previews and commits replacements; prices/account records are not changed by reference imports.

## Implemented
- Section 07 starts with ideas, then an independent auto-loading analyst tab. Refresh remains optional. Visible search counts removed; existing browser-local ranking continues (not misrepresented as central tracking).
- Conditional next-session OPEN entry band ±0.25% around the structural reference, stop/T1/T2 where available; no chasing, actual-fill gross R/R >=1.5 and positive reward after illustrative costs. Entry valid only on next imported market session. Separate 1- and 10-session horizons.
- Up to five structurally qualified setups. Rejection reasons for ranked invalid-plan candidates; zero is legitimate. No invented probability or invented fundamental research. Daily close/level chart and completed-week close chart.
- Forecasts saved automatically for displayed candidates and selected analyst ticker, via explicit POST. Idempotent per ticker/as-of/horizon/rule version; original payload never replaced. They are **not forecasts for every symbol in the background**, nor live orders. No backfilled simulation is labelled a forward forecast.
- Import commit performs bounded reconciliation (100 snapshots). Failures leave the import committed with RETRY_REQUIRED. Evaluate saved forecasts retries/continues. Optional external job handles up to 1,000 snapshots per run. List/download endpoint currently returns newest 200 snapshots; older records remain in Turso.
- Next-session direction compared with next close versus as-of close separately from hypothetical trade results. Missing next-session bars are not substituted. Both stop and target inside one daily candle => AMBIGUOUS, no profit credited. Open-gap stop priced adversely at open, target gaps capped at T1. Fees and slippage each 10 bps per side are assumptions.
- Outcome observations retained when imports change evaluated evidence. Recorded forecasts must be created before importing the target session for a meaningful prospective evaluation; timestamps remain visible.
- Sector workbook defaults: COMP_LIST 671, SEL_COMP_LIST 101, KSE100 101, KSE30 30. KSE100 is explicitly an unverified user list, not verified official membership. Extra unlabelled values are not aliases. MLCF display uses source ticker.
- Native Market Explorer: date hierarchy, Top1–10/Others donut + separate columns, total/share labels; N-record symbol/Index comparison, extrema with all tied dates, source AVG, exact-date benchmark joins and newest-first tables.

## Learning: functional research baseline, NOT a proven self-improving trading model
The release includes a deterministic logistic baseline trained from stored historical close/volume features. It uses training-only standardisation, 60/20/20 chronological partitions, a one-sample boundary purge, validation-selected regularisation and a final test against a training-frequency baseline. A training run is cached by the complete source data hash and model version. Changing historical data creates a new run. It is a next-session **direction research model**, not a learned stop/target or 10-day profitability model.

This is a single chronological holdout, **not** a full rolling walk-forward study. Its raw output is uncalibrated, not a win probability. Repeated research on the same holdout can overfit. Production trading rules are never silently replaced. There is no claimed perfect analysis, demonstrated alpha, profitability, survivorship-free universe or corporate-action-adjusted history.

### One command after dependencies/auth environment are already configured
Run from the extracted application root, in your existing Ubuntu terminal:

```bash
python3 -m tools.refresh_learning --symbols ATRL PRL MLCF OGDC PPL
```

Use `python3 -m tools.refresh_learning` without `--symbols` to process all stored symbols, after reviewing Turso quotas and runtime. It also reconciles saved forecasts. Results appear under Automated Technical Analyst → Learning research. This operates directly against whatever database backend your environment selects; set the three Turso environment variables privately first. Without them a local run uses local SQLite and does NOT train your production database. No credentials are included in this ZIP.

### Optional automatic refresh using your existing GitHub account
1. Repository Settings → Secrets and variables → Actions: add **secrets** TURSO_DATABASE_URL and TURSO_AUTH_TOKEN. Vercel secrets do not automatically transfer to GitHub Actions.
2. Actions → Refresh research models (opt-in) → Run workflow, initially with a few symbols.
3. Verify results and quota usage. To enable the weekly Friday schedule, add repository **variable** PSX_ENABLE_RESEARCH=`true`. Optional PSX_RESEARCH_SYMBOLS changes the ticker list.
4. Scheduled learning is OFF unless you enable it. It runs separately from page requests and never auto-promotes models. It is not automatically run after every file import; forecast evaluation is.
No new paid API/provider or card entry is implemented. GitHub Actions and Turso free allowances are finite; inspect your plan's current quotas before enabling scheduled jobs. Local execution avoids GitHub Actions minutes but still consumes Turso usage.

## Known limitations that cannot honestly be fixed from the supplied files alone
- INDEX legacy table does not identify the benchmark or contain volume. Display says **Imported INDEX — identity unverified**, and volume N/A rather than zero. Confirm the source really is KSE-100 before relying on the comparison.
- Source AVG is displayed; absent source averages remain N/A. N-session return baseline is the previous available symbol close before the first included row. Weekly baseline is prior week's last available symbol close; Index uses that exact date, not a substitute.
- Sector lists are current classifications, not point-in-time historical constituents. Do not use them as proof of survivorship-free historical performance.
- No financial statements, timestamped news, short-borrow inventory, broker permission, intraday fills/order-book data or verified corporate-action adjustment inputs were supplied.
- There is no background always-on process on Vercel. Displayed forecasts are recorded on page use; research automation requires enabling the external workflow or running the command.
- Password-free existing app access is retained. Same-origin checks are not authentication. Anyone who can access the public app can use its write routes. Add access control before treating it as a private production trading system.
- New workbook formats are not arbitrarily guessed. Reference import requires SYMBOL/COMPANY NAME/SECTOR mapping; unsupported sheets stay custom and do not change canonical prices. General interactive arbitrary-schema mapping is not included.

## Source-only packaging & rollback
No database, gzip snapshot, original workbook, token, Git history, virtual environment or cache is packaged. The sector JSON is derived from the workbook you supplied. A ZIP upload does not remove old tracked repository files: preserve independent backups before separately removing obsolete generated artifacts. Do not delete Turso data or overwrite it with a repository snapshot.
Rollback: restore the previous code deployment and preserve the new tables; do not restore an older database merely to roll back UI code. New forecast/reference tables are additive.

## Evidence
See docs/QA_1_3_9.json for actual local test results and limitations. Local tests/preview are not verification of your live Turso deployment, real market performance, or future fills.
