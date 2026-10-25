# PSX Intelligence v1.3.15

A historical-data dashboard hosted on **GitHub → Vercel → Aiven PostgreSQL**.
One current README covers setup, imports, operation and verification. No Google
Drive, credentials or user trading database is included in the release archive.

## Contents

- [Setup and deployment](#your-setup-three-variables-then-deploy)
- [Imports and private snapshot migration](#add-old-data-now-new-usb-files-later)
- [Performance design](#what-changed-to-reduce-repeated-reads)
- [Limits and security](#limits-and-security--important)
- [USB backup and restore](#usb-backup--restore)
- [Troubleshooting](#troubleshooting)
- [Daily workflow and modules](#daily-workflow-and-modules)
- [Calculation boundaries](#calculation-and-data-boundaries)
- [Verification and performance](#verification-and-performance)
- [Rollback](#deployment-rollback-versus-data-restore)

## Repository layout

| Path | Purpose |
|---|---|
| `psx_app/` | Application, database adapters, parsers, calculations and browser UI |
| `main.py`, `api/`, `vercel.json` | Vercel entry points and deployment configuration |
| `requirements.txt` | Pinned Python dependencies |
| `tests/`, `pytest.ini` | Regression and integration tests; retain these |
| `tools/` | Optional SQLite conversion and learning-research utilities |
| `.github/workflows/` | Optional manually triggered snapshot conversion |
| `RELEASE_MANIFEST.json` | Release file hashes and verification summary |

Obsolete `docs/`, `START_HERE_*` and `UPGRADE_*` documents were consolidated here.
Older version numbers in source/test filenames do **not** mean those files are
obsolete: active UI scripts, database adapters and regression tests are retained.
Existing data snapshots in your repository are not deleted by this cleanup.


## Your setup: three variables, then deploy

Your application stays password-free, as before. No Google Drive is required.
Your own USB remains your backup. No credentials or user database are in this ZIP.

1. Keep the current source on the GitHub `main` branch. If using a release ZIP,
   extract it and upload its **contents** to the repository root. Keep `main.py`, `requirements.txt`, `vercel.json` and `psx_app/`
   together at that root. Do not put them inside an extra nested folder.
2. In Vercel → Project → Settings → Environment Variables, use:

   | Name | Value |
   |---|---|
   | `PSX_DATABASE_BACKEND` | `postgres` (change the existing value; do not add a duplicate) |
   | `DATABASE_URL` | Your complete private Aiven PostgreSQL connection URI |
   | `DATABASE_CA_CERT` | Complete CA certificate text, including BEGIN/END lines |

   Select **Production**. Also select **Preview** if testing a preview branch.
   `DATABASE_URL` is a secret; never commit it or send it in screenshots/chat.
   The certificate is text, not `ca.pem` as a filename. Multiline PEM and literal
   `\n` separators are accepted. Certificate/hostname validation is mandatory
   for remote PostgreSQL, even if the URI contains `sslmode=require` or `disable`.
3. Leave `PSX_DATA_DIR` unchanged; Vercel uses /tmp only for temporary files.
   Existing `TURSO_*` and `GITHUB_SYNC_*` variables are **ignored in postgres mode**.
   Keep them until the migration is verified. Do not select sqlite on Vercel.
4. Deploy the new GitHub commit (or Redeploy after changing variables).
   Do **not** just redeploy the old 1.3.13 code.
5. Open the dashboard. Sidebar should say **Database: connected**. Settings should
   say **PostgreSQL — direct remote database**. `/api/health` should return 200 and
   version `1.3.15`. An empty database is expected before you import your data.

The first API request creates the application tables and default configuration in
**your deliberately configured PostgreSQL database**. It does not manufacture
prices, accounts' trading history, or predictions. It never silently falls back
to SQLite or downloads an old GitHub snapshot in PostgreSQL mode.

## Add old data now, new USB files later

Use **02 → Import and Update Center**:
1. Select your original TXT/CSV/XLSX files (or a supported ZIP of them).
2. Review the staged counts, dates, account IDs, rejected rows and revisions.
3. Click **Import and Update Canonical Database**.
4. Check reports and latest dates. Repeat later with new files from your USB.

Exact duplicates are skipped. Reviewed corrections use the import revision rules.
Sector workbooks are supported through the normal upload or reference preview.
Do not import everything in one giant request: start with a small representative
file, then manageable yearly/monthly batches. Serverless time/memory limits still
apply. Split a batch if parsing or commit reaches the function time limit. A lost
write response is not proof of rollback: inspect import history before retrying.

### Initial SQLite snapshot migration — private, hosted, empty target only

A `.db.gz` snapshot is not an OHLCV workbook. Do **not** send it to Aiven's SQL
editor or the ordinary price-file parser. Use the one-time migration below.
Keep the original snapshot and source files on your USB.

1. Configure GitHub repository → Settings → Secrets and variables → Actions:
   add encrypted repository secrets `DATABASE_URL` and `DATABASE_CA_CERT` with
   the same private values as Vercel. Vercel variables do not transfer automatically.
2. Stage the trusted snapshot through the dashboard's existing chunk-upload API.
   The helper uploads 1 MiB requests into PostgreSQL temporary staging; the data
   is **not committed to GitHub or attached to a release**:

   ```bash
   python tools/stage_sqlite_snapshot.py /path/to/latest_cloud_sync.db.gz \
     --dashboard https://your-dashboard.vercel.app
   ```

   This is a one-time file-transfer client, **not** hosting an app on localhost.
   It returns `upload_id`, `total_chunks`, and `expected_sha256`. Preserve those
   identifiers. Staging expires after 24 hours; run the migration before expiry.
3. GitHub → Actions → **Import existing SQLite snapshot into empty PostgreSQL**
   → Run workflow on `main`. Fill those three fields; leave `snapshot_path` empty.
   Enter `IMPORT_INTO_EMPTY_DATABASE` in `confirm`.
4. Do not import files or change settings while it runs. The runner retrieves the
   private staged pieces with TLS-verified database credentials, verifies SHA256,
   checks SQLite integrity, and refuses a target already containing imported data.
5. It copies reviewed canonical/config/audit/forecast tables atomically, verifies
   row counts, compares volume and financial aggregates, resets ID sequences,
   updates the shared revision, and runs ANALYZE for useful query-planner statistics.
   Financial comparisons allow at most 0.01 PKR absolute / 1e-12 relative rounding
   tolerance; no trade values or financial formulas are recalculated during copy.
6. Review the workflow's `COMMITTED`, table counts, aggregate `matched` flags and
   date ranges. Check dashboard totals and a representative ticker/index date.
   Successful runs remove **only that upload's temporary chunks**. The original
   USB snapshot and copied canonical data are never deleted as cleanup.
7. Add newer TXT/CSV/XLSX source files through the normal importer afterward.
   No missing history or saved forecasts are invented. A failed/uncertain response
   is not proof of rollback: inspect target counts before any retry.

The optional `snapshot_path` workflow input is only for a trusted snapshot **already**
in the repository. Do not publish private account data just to use it. The workflow
uses read-only repository permissions and does not push code or publish releases.
GitHub Actions logs must never print connection URIs, certificate/private key
material, source-file contents or individual financial rows.

The migration preserves IDs, account separation, recorded totals, source metadata
and available audit/forecast history. It skips derived caches, pending upload
staging and raw source-file binary archives. Old local file paths are metadata,
not proof that original files are archived online. Keep your USB originals.

For an already-populated PostgreSQL database use the normal source-file importer;
this is not a merge/overwrite/rollback utility. For a trusted local snapshot a
one-time operator can also run `python -m tools.import_sqlite_to_postgres file.db`
for a read-only dry run, followed by `--confirm-empty-target` only after review.

## What changed to reduce repeated reads

- PostgreSQL persistence, double-precision prices, 64-bit volumes and IDs.
- Transactional import/staging, bulk inserts, parameterized queries and upserts.
- PostgreSQL advisory locks coordinate import commits across Vercel workers.
- A bounded persistent result cache shares analysis across cold workers. Price
  changes, corrections, settings and reference changes invalidate it by revision.
- Full ticker calculations are reused across chart/analyst/forecast consumers when
  they fit the bounded cache. Oversized results are computed, not silently truncated.
- Overview, account, Top5 and futures read-only reports now share revision-keyed
  PostgreSQL caches across Vercel workers, not just one worker's memory.
- Cold universe scans fetch missing histories in batches of at most 100 tickers
  instead of one remote history query per ticker. Indicator mathematics are unchanged.
- Price imports invalidate only affected symbols' indicator caches; historical
  corrections invalidate the whole affected symbol, not just one date.
- Unchanged indicator calculations are reused. Calculations remain on demand;
  this is **not** an incremental-math rewrite or a claim of zero full-history reads.
- No full-database GitHub downloads/pushes in PostgreSQL mode.
- Remote outages return safe API errors while the static page remains available.

## Limits and security — important

Aiven Free currently has 1 CPU, 1 GB RAM, 1 GB disk and 20 connections, no managed
connection pooling and no availability SLA. It can be stopped for inactivity.
This release does not make the service unlimited or change any provider quota.

The adapter opens short-lived connections, permits at most two concurrently per
Python process and never automatically retries uncertain writes. **That is not a
global connection pool**: multiple Vercel workers/admin sessions can still reach
Aiven's 20-connection limit. The app reports `CONNECTION_CAPACITY` rather than
silently using another database. Avoid overlapping large imports/maintenance jobs.
A small-instance capacity/concurrency pilot is still required for your real workload.

Database, indexes, cache, WAL and temporary staging all need disk headroom. The
SQLite file size is not the PostgreSQL disk requirement. The result cache is
bounded to 200 entries, at most 512 KiB compressed text each; it can be recomputed.
Watch Aiven storage metrics and Vercel CPU/invocations. This ZIP creates no paid
resource and does not upgrade your plan.

As requested, the dashboard remains **password-free**. Same-origin request hygiene
is NOT authentication. Anyone able to access the public URL/API may read data or
submit imports/settings changes, including clients that omit Origin headers. Do
not assume this is a secure private financial dashboard. Keep the URL restricted
through your hosting access controls where available, and do not expose sensitive
account data publicly. No new password gate was introduced by this migration.

## USB backup / restore

Google Drive is not used. Keep original source files and periodic PostgreSQL
exports on your USB. A data-file collection alone does not preserve saved forecasts,
manual settings or audit history. A PostgreSQL-native export preserves those too.
The application does not create a pretend SQLite backup of the remote database.

With compatible PostgreSQL client tools and `PGSSLROOTCERT` pointing to your CA
certificate, a shell can use a private `DATABASE_URL` environment variable:

```bash
pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-acl --file=psx-backup.dump
```

Set `PGSSLMODE=verify-full`; remove conflicting `sslmode` URI parameters so the
certificate setting is not weakened. Never put the actual URI/password into a
shared script, repository or screenshot. Use a client version compatible with
your Aiven PostgreSQL server. Test restore into a **separate empty service/database**
with `pg_restore`, verify counts and reports, then switch credentials if needed.
Do not restore over the active service. Aiven's own managed backups do not replace
your independent USB copy.

## Troubleshooting

- **Old version still appears:** ensure GitHub has the new root files and Vercel
  deployed that commit; reload. Environment changes need a new deployment.
- **Still says Turso:** change `PSX_DATABASE_BACKEND` to `postgres`, then redeploy.
- **SERVER_CONFIGURATION:** check URI format and complete certificate text.
- **AUTHENTICATION_REJECTED:** check Aiven user/password; URL-encode special
  password characters or copy Aiven's complete connection URI.
- **TLS_CONNECTION_FAILED:** use the CA from this service and its exact hostname;
  do not disable verification.
- **NETWORK_CONNECTION_FAILED / CONNECTION_TIMEOUT:** confirm the service is
  Running and network access permits the Vercel deployment. Do not weaken access
  rules blindly; check Aiven's networking settings.
- **CONNECTION_CAPACITY:** reduce concurrent jobs/requests and check connection metrics.
- **STORAGE_CAPACITY:** stop new imports, inspect disk/staging/cache headroom. Do not
  delete original data to hide the warning.
- **Blank reports on a connected DB:** import data. Empty is not a connection failure.

### Verification boundary

See the verification report below. Real disposable PostgreSQL and browser tests are
not a live Aiven/Vercel benchmark. Your live credentials remain private; production
connectivity, full-data size, concurrency, quotas and restore must be checked there.

## Official provider references

- Aiven Free limits: https://aiven.io/docs/products/postgresql/concepts/pg-free-tier
- Aiven connections: https://aiven.io/docs/products/postgresql/get-started
- Python / certificate verification: https://aiven.io/docs/products/postgresql/howto/connect-python
- Vercel variables / deployment scope: https://vercel.com/docs/environment-variables

Provider plan details can change; the package does not remove these limits.

## Learning research (optional)

Run `python tools/refresh_learning.py --help` for the supported research refresh options. Research does not automatically replace the production trading rules.

## Daily workflow and modules

| Module | What it does / what to check |
|---|---|
| 01 Overview | Latest imported dates, separate account summaries, source counts and shortcuts |
| 02 Import and Update Center | Upload → inspect staged counts/rejections/revisions → commit; review import history |
| 03 Top 5 Volume & Rate Register | Ranked source trades/volume and ticker trends; not a full exchange feed |
| 04 Account 91404 | Isolated ledger, daily/monthly/yearly reports, commissions, tax, audit and exports |
| 05 Account 91269 | Same reporting, strictly separate account; never combine its positions with 91404 |
| 06 Futures Comparison | Same-date cash/futures basis, days-to-expiry and annualized comparison; worksheet filters retained |
| 07 Technical Analysis | Trading ideas, plain-language stock analysis, saved predictions/results, data coverage, charts and screener |
| 08 Data Quality | Coverage, duplicate/revision and reconciliation checks; date repair requires dry-run evidence and confirmation |
| 09 Market Explorer | Calendar + Top N volume charts; last N stored symbol records versus exact-date imported index records |
| 10 Settings and Backup | Rule parameters/version history, database diagnostics and independent USB export/restore guidance |

**Every import:** keep originals → stage manageable batches → inspect warnings and
source dates → commit once → compare counts/latest dates/account totals. Exact
duplicates are skipped. Source corrections are visible revisions, not an excuse
to silently replace unrelated records. If a request times out, inspect its saved
status before retrying. Old snapshots can end earlier than the files on your USB.

**Every trading session:** import completed-session data, verify the displayed
as-of date and ticker's coverage, then review the action/entry/exit explanation.
A data filter rejection is not missing data. Fewer than five setups, or WAIT / no
new trade, is a legitimate result; safeguards are not loosened to fill five cards.
Short signals are not broker approval to short. Existing-holding sell warnings
are distinct from opening a short. No order is placed by this dashboard.

**Saved predictions:** the prediction period means the next stored session or up
to ten subsequent stored sessions, not calendar days. Original snapshots remain
immutable. Evaluate after importing new records. Pending results are not wins;
ambiguous daily stop/target order gets no unjustified profit credit. Rule scores
are indicator votes, **not** calibrated win probabilities or fundamental evidence.

**Sector/company files:** normal reference preview detects supported workbooks;
inspect detected sheet/columns/membership before commit. Unknown schemas require
custom mapping rather than fabricated rows. Use exact stored symbols; the legacy
`MLF` alias resolves to `MLCF` only for compatibility, not as a new instrument.

**Market Explorer:** Top N (1–10) is ranked by the selected date's positive cash
volume; Others contains the remainder. Index-table volume is the sum of imported
cash-symbol volumes for that date, not an index-member-verified exchange total.
One requested record means one stored symbol observation. Missing benchmark dates
are reported, not forward-filled. Maxima are green `#03D815`, minima red `#F63131`.
The Symbol vs Index tab uses the latest available imported records, without a
separate calendar; date-range cards show the actual minimum and maximum dates.

## Calculation and data boundaries

- Price change = close minus stored previous close; percent = change / previous
  close × 100 where a valid positive baseline exists. One-record period change
  uses the preceding stored observation, not close minus itself.
- Account net P&L = recorded gross P&L minus recorded charges. Aggregated prices
  are quantity-weighted from totals. Settings determine commission slabs and SST;
  source snapshot migration preserves recorded totals rather than repricing them.
- Futures basis = futures minus same-date cash; basis percent uses cash as base.
  Annualized simple basis uses 365 / configured positive days to expiry, not a
  guaranteed realized return. Calendar-date resolution and each worksheet's
  retained filters must be checked before comparison.
- Indicators use stored cash OHLCV only. Top5 trades, futures and account fills
  do not manufacture missing cash candles. EMA/SMA, Wilder RSI/ADX, MACD,
  Bollinger bands, pivots and trend fits retain the existing engine mathematics.
- Full history feeds indicators; chart trimming only trims presentation. Completed
  weeks exclude unfinished weeks conservatively; no verified exchange-holiday
  calendar or corporate-action adjustment assurance is supplied.
- Risk/reward uses a valid structural target and loss limit. Invalid or too-small
  reward-versus-risk plans are rejected. Fees/slippage are assumptions unless
  verified with your broker. OHLCV alone cannot identify intraday execution order.
- No verified fundamental statements, live news feed or broker execution data are
  bundled. Optional learning research is an experiment and never silently replaces
  production rules. There is no promise of perfect forecasts or profitability.

## Verification and performance

Current regression suite: **224 passed, 34 skipped, 1 deprecation warning**.
Tests use a real isolated PostgreSQL 15 server. They explicitly isolate synthetic
tests from retained repository snapshots. Twenty private historical-fixture tests
and fourteen optional legacy libSQL-server tests are skipped, not passed.
Run only against an expendable loopback database named with `_test` suffix:

```bash
pip install -r requirements.txt
PSX_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:55432/psx_test pytest -q
```

The fixture drops/recreates the test schema. **Never use production credentials.**
These are developer tests; running them does not require local hosting for users.

Full-snapshot isolated pilot: 731,806 cash rows, 6,668 futures rows and 2,425 index
rows migrated and reconciled, with roughly 259 MB PostgreSQL database size in the
pilot. This is not a prediction of total Aiven disk usage including WAL/staging.
The inspected source's cash history starts 2019-01-01 and ends 2026-10-22; index
history starts 2017-01-03. This describes that source file, not a hardcoded runtime
date range. New imports change the dashboard's dates dynamically.

Illustrative isolated service timings (seconds, cold / repeated call):

| Operation | Before this optimization | After |
|---|---:|---:|
| Overview summary | 0.245 / 0.236 | 0.246 / 0.003 |
| Market date/symbol metadata | 0.139 / 0.003 | 0.135 / 0.003 |
| Latest-date volume | 0.011 / 0.003 | 0.010 / 0.002 |
| Core 36 summary | 2.121 / 0.006 | 2.086 / 0.006 |

These are single-process loopback PostgreSQL measurements, **not live Aiven or
browser latency guarantees**. CPU-heavy cold indicator work still costs time.
Remote batching reduces network round trips; caches accelerate unchanged reads.
A first request, cache eviction, midnight cache-key change or new import may be
slower. Compare the same data, endpoint, filters and cold/warm state when measuring.
Do not claim a speedup merely because an empty database loads quickly.

Production acceptance after each deployment/migration:
1. Verify GitHub `main` commit and Vercel Production Ready refer to the same release.
2. Check `/api/health` HTTP 200 and current version, Settings backend PostgreSQL ACTIVE,
   and `/api/system/freshness` HTTP 200; read connectivity is not a full integrity scan.
3. Compare imported row counts/date ranges, both isolated account totals and a
   representative symbol/index date with the trusted source.
4. Open Overview, Import Center, both accounts, futures, Technical Analysis,
   Data Quality and Market Explorer. Inspect console/API failures and exports.
5. Measure cold and repeated calls sequentially before testing modest concurrency.
   Do not saturate Aiven's 20-connection limit or treat the per-process limit as global.
6. Check Aiven disk/CPU/memory and a tested USB-native export/restore process.

Prior live v1.3.14 checks verified Vercel deployment and PostgreSQL connectivity
with an empty application database. A later migration is successful only when its
workflow reports COMMITTED and the full-data acceptance checks pass. This README
is an operating guide, not an assertion that every future environment is verified.
No payment/plan upgrade, blanket overwrite, global pool or profit guarantee is made.

## Deployment rollback versus data restore

Code and data are separate. Revert an identified code commit (or use Vercel's
previous deployment) only if it is compatible with the current schema and PostgreSQL
backend. Do not blindly roll back to Turso-only v1.3.13 or set backend=sqlite on Vercel.
A code rollback does **not** undo database writes. For data recovery, restore a verified
PostgreSQL dump into a separate empty target, reconcile, then deliberately switch
credentials. Keep original data intact until the replacement is independently checked.

## Repository maintenance

Keep one current README rather than generating another upgrade-note/docs tree.
Retain active source, tests, `.github/workflows`, `requirements.txt`, `vercel.json`
and the release manifest. Versioned UI filenames still contain active code.
Do not commit `.env`, connection URIs, passwords, private keys, raw financial
snapshots, temporary uploads, caches, virtual environments or database journals.
An already tracked legacy snapshot is not made private merely by adding `.gitignore`;
repository history may retain it. Review your repository visibility/access if it
contains account records; do not assume a public repository is a private backup.

Normal pushes to `main` can automatically deploy Vercel. Review tests and saved
Production variables first; Preview needs its own configured variable scopes.
The one-time migration workflow never runs automatically on push.

The migration workflow first performs a verified-TLS `SELECT 1` using the separate Actions secrets. If `CA_OR_URI_CONFIGURATION_INVALID` is reported, save the complete CA PEM (including BEGIN/END lines), not a download filename. `TLS_CA_NOT_TRUSTED` means the supplied CA did not validate this server; copy the CA and URI from the same Aiven service. Never fix this by disabling certificate verification. A preflight failure occurs before the canonical import.

## Restoring the complete snapshot when live imports already exist

Do **not** run the empty-target workflow against a database that already contains imports. Use **Actions → Verify connection and prepare isolated restore** instead:

1. Save `DATABASE_URL` and the complete `DATABASE_CA_CERT` PEM as **Actions repository secrets**. These are separate from Vercel variables. Run with mode `check_connection` first; it only performs SELECT queries. Never disable certificate verification.
2. Stage the trusted `.db.gz` using `python -m tools.stage_sqlite_snapshot FILE.db.gz --dashboard https://YOUR-DASHBOARD` (a one-time upload client, not localhost hosting). Keep its upload ID, chunk count and SHA256. The compressed file is stored temporarily in the private PostgreSQL staging tables, not GitHub. Do not commit it or attach it to a public release. Staging expires after 24 hours.
3. Pause ordinary imports during restoration. Run the same workflow with mode `restore_candidate`, the three upload values, and confirmation `RESTORE_SEPARATE_DATABASE`.
4. The runner checks SHA256 and SQLite integrity, checks estimated free-plan storage headroom, and creates a separate database named `psx_restore_` plus the first 12 SHA256 characters. It never creates a new paid service. It refuses an existing candidate and never drops or overwrites the original live database.
5. All snapshot canonical tables are copied and reconciled first. It then copies the live database's canonical rows into the candidate. Existing live business keys take precedence over snapshot overlaps; missing older history remains. Source-file and import-batch numeric IDs are remapped, related references are checked, and every live row's resulting values and table counts are verified. Monetary amounts are copied, not recomputed. Original JSON audit payloads are retained verbatim. Derived caches and temporary uploads are not canonical history.
6. A successful result is `CANDIDATE_VERIFIED_NOT_ACTIVATED`. Check snapshot counts, aggregate checks, live reconciliation results and candidate size. The runner intentionally does **not** activate the database. The reconciliation reflects the live revision recorded in its result; if new imports occurred afterwards, stop and reconcile again before activation.
7. Only after verification, set **Vercel Production** variable `PSX_POSTGRES_DATABASE` to the reported candidate name and redeploy. This optional validated database-name override reuses the existing secret URI, password and CA certificate; it does not change the host or weaken TLS. Never set it to an unverified database. Check health, account reports, dates and market/technical views after deployment.
8. Retain the previous database until independently satisfied. To roll back the selection, remove `PSX_POSTGRES_DATABASE` and redeploy; this returns to the database named in `DATABASE_URL`, without deleting either database. Future Actions jobs use their own secrets: align their URI with the intended active database before other maintenance, and never blindly rerun a one-time restore.

The storage check is a conservative estimate, not a guarantee of provider disk capacity or WAL headroom. PostgreSQL may reject database creation because of permissions or storage; the workflow then stops without activation. If any run fails after candidate creation, inspect it before proceeding; an existing candidate is deliberately not overwritten on retry. No automatic paid upgrade, no background retry of ambiguous writes, no financial-row values in public workflow output.

Restore maintenance validation: **215 tests passed, 34 skipped, one dependency deprecation warning**. A complete 731,806-row cash-price snapshot was also restored into a disposable PostgreSQL candidate alongside a synthetic newer live record; final cash count was 731,807 and the source database remained unchanged. These are isolated test results, not a claim that production restoration has completed.

Bulk restore maintenance: live rows are reconciled through temporary-table COPY and set-based upserts, with bounded SQL statements per table instead of network requests per row. A 5,000-row test checks the target uses fewer than 20 statements. After an operator-confirmed cancelled run, `resume_candidate` may be selected with the same explicit confirmation: it refuses if existing candidate counts or available volume/financial sums differ from the original snapshot. An entirely empty candidate can use the original empty-target copy. A previously merged candidate is not blindly merged again. Both fresh and interrupted full-snapshot paths were tested on disposable PostgreSQL; the source remains read-only.


### Completed production restoration and acceptance

The supplied compressed SQLite snapshot was restored into a separate database in the existing Aiven service, then reconciled with newer live imports. Original `defaultdb` was retained unchanged for rollback. No financial snapshot was uploaded to a GitHub release, artifact or source commit during this restore.

- Successful restore job: https://github.com/mapkse-glitch/psx-trading-intelligence/actions/runs/40165536178
- Active Vercel Production selection: `PSX_POSTGRES_DATABASE=psx_restore_64b36a85534e`, using the existing `DATABASE_URL` and `DATABASE_CA_CERT`. No additional paid service was created. The existing free-plan storage and resource limits still apply.
- Verified live counts: 731,806 cash-price rows across 766 symbols; 6,668 futures rows; 2,425 index rows; 5,380 Top 5 rows; 506 raw executions and 331 account daily-symbol summaries.
- Price snapshot coverage ends **22 October 2026**; newer Top 5 and account 91404 imports through **23 October 2026** were preserved. Account 91269 history ends 19 October. Import later files normally to extend coverage; missing dates were not invented.
- Every restored account summary was checked against the old-snapshot/newer-live business-key union: 264 rows for 91404 and 67 for 91269. Buy/sell quantities and values, gross/net P&L, commission, SST and charges matched. Live rows take precedence on matching keys.
- Live API checks passed for health, overview, both accounts, ATRL symbol/index records, all 36 watchlist symbols and ATRL automated analysis. Browser smoke checks passed for overview, technical analysis and market explorer without reported JavaScript errors. These are targeted acceptance checks, not a claim every possible user interaction was exhaustively tested.

Observed live HTTPS request durations from one verification client (seconds, first/repeat): overview 0.359/0.257; account 91404 0.681/0.679; account 91269 0.595/0.441; ATRL market comparison 0.931/0.390; Core 36 5.977/0.424; ATRL automated analyst 2.237/0.218. These are point-in-time measurements, not latency guarantees or a controlled before/after speed comparison.

**What to do next:** reload the dashboard and inspect both accounts. Continue importing later daily files through Import and Update Center; preview and commit normally. Keep your USB originals. Do not rerun the completed one-time restore. Keep the previous database until satisfied with the restored history. GitHub Actions credentials still select their own database independently; before future maintenance, point Actions at the intended database (the existing Actions URI still names the previous database). To roll back production selection, remove `PSX_POSTGRES_DATABASE` in Vercel Production and redeploy. Removing that variable does not delete either database.


### Volume-chart presentation and storage planning

Market volume now uses one blue scale for ranked stocks and neutral slate for Others in both charts. The donut has stock/share/volume labels connected directly to slices; the detached legend is removed. Labels and headline percentages remain calculated from the selected date and Top N, not a fixed screenshot value. Charts stack where needed to keep labels readable; on small phones a chart can be scrolled horizontally rather than shrinking its labels to illegible text.

For a **read-only storage audit**, open Actions → Verify connection and prepare isolated restore → Run workflow → choose `inspect_storage` on main. Other inputs are not needed. The audit reports database, table and index sizes, estimated dead rows, temporary-upload byte totals and the latest ten cash sessions' record/logical-byte counts. It uses database-enforced read-only connections and never removes records, changes compression, vacuums or switches production. It logs no account values, filenames, URIs or credentials. Database totals exclude shared PostgreSQL/WAL/system overhead; do not equate them directly with Aiven's service-level disk gauge.

Do not forecast retention using raw TXT/XLSX upload sizes. Parsed canonical rows, indexes, staging, repeated revisions and WAL have different storage costs. PostgreSQL already compresses eligible large values through TOAST, but ordinary narrow OHLCV rows are not transparently compressed as a whole table. Zipping queryable prices into opaque blobs would require a separate archival/query design and can slow or break existing views. Do not trade away exact financial values or historical daily resolution to claim compression.

Before importing 2016–2018, measure actual daily growth and inspect temporary staging, duplicate indexes and the retained rollback database. **Do not delete the rollback database without explicit approval and a verified recovery path.** Cleanup of deleted rows normally makes space reusable within tables; it does not guarantee that Aiven's disk gauge falls immediately. Avoid a blind `VACUUM FULL`: it locks/rebuilds the table and needs additional free disk. Keep headroom for imports and PostgreSQL maintenance. The free plan remains finite; no compression promise makes 1 GB unlimited.

Official references: [PostgreSQL TOAST](https://www.postgresql.org/docs/current/storage-toast.html), [vacuuming and disk reclamation](https://www.postgresql.org/docs/current/routine-vacuuming.html), [Aiven free-tier limits](https://aiven.io/docs/products/postgresql/concepts/pg-free-tier).


### Guarded cleanup and one-month historical capacity test

The maintenance action is deliberately scoped to the completed snapshot restoration, not general deletion. It preserves both the active price/account history and the original rollback database.

1. Pause imports while measuring. In GitHub Actions open **Guarded migration storage cleanup**, choose **main**, select **preview** and run. Review the result before proceeding.
2. The tool reconnects to the restored candidate using the same existing secret host/CA credentials. It refuses an unexpected source selection or insufficient restored history. In the original staging database it considers only `chunk:migration-...` uploads older than 15 minutes, requires contiguous pieces and verifies the complete bytes against the restored snapshot SHA-256 and byte count. Unrelated, incomplete, recent or nonmatching uploads are preserved.
3. To apply, run the same action with **cleanup** and confirmation `CLEAN_MIGRATION_UPLOADS_AND_DUPLICATE_INDEX`. No account values or credentials are logged. Only hash-verified upload pieces are deleted. A normal `VACUUM (ANALYZE)` targets the old staging table; `VACUUM FULL`, database deletion and history truncation are not used.
4. The only index eligible for removal is `public.idx_eq_date_sym`. The action first validates that it is a valid nonunique, nonconstraint, non-replica-identity, nonclustered exact catalog match for the healthy retained unique B-tree `equity_ohlcv_trade_date_symbol_key` on `(trade_date,symbol)`, including ordering, operator classes, collations, predicate and expressions. It uses `DROP INDEX CONCURRENTLY`, outside a transaction. The unique constraint and reverse-order `(symbol,trade_date)` index remain. The PostgreSQL schema generator no longer recreates this redundant index.
5. The result compares canonical table counts and account financial aggregates before/after, verifies the retained unique constraint, reports database sizes and confirms the rollback database remains. On failure, inspect the result before retrying: staging cleanup and concurrent index removal are separate committed steps, not one cross-database transaction. A rerun safely handles already-removed matching pieces and an absent duplicate index.
6. Run **Verify connection and prepare isolated restore → inspect_storage** for a fresh read-only report. Aiven's service gauge may lag and includes WAL/shared overhead; reclaimed database bytes are not a promise of an identical immediate gauge change.

**One-month test, before a bulk 2016–2018 import:**

1. Provide one real calendar month of historical cash OHLCV for all available symbols, for example January 2016, with the original headers/symbols/dates and no invented records. If the workbook contains multiple years, extract only that month into a separate import file without changing values. Do not upload it to public GitHub; use the dashboard import center.
2. Keep the post-cleanup `inspect_storage` result as the baseline. Record active database bytes and equity heap/index/total bytes. Do not use raw upload-file size as database growth.
3. Stage the month through **Import and Update Center**. Verify detected cash schema, date range, accepted/new/revised/duplicate counts, then commit only that month. Stop on unexpected revisions or other months/modules.
4. Verify prices for several symbols and account isolation. Re-run `inspect_storage` once the import has completed. Record the new canonical-row count from the committed import report and the number of distinct trading dates actually added.
5. Calculate `additional_database_MB = (after_bytes - before_bytes) / 1,000,000`. Also compare equity table and index bytes; unrelated ongoing writes can affect whole-database growth. Divide the comparable increase by newly added trading sessions to obtain an observed per-session increment. Existing reusable pages can make an initial delta unusually small; treat one month as a pilot, not a guaranteed linear forecast.
6. Extrapolate to the actual remaining historical sessions, reserve at least 25–30% service-disk headroom for staging/WAL/maintenance and daily additions, then decide whether to proceed in small yearly/monthly batches. Keep USB originals; do not sacrifice exact prices or daily resolution to fit a guessed compression ratio.

Maintenance regression suite: **224 passed, 34 skipped**; synthetic tests exercise preview/no-write behavior, exact-index mismatch refusal, preservation of unrelated staging and financial rows, unique-key enforcement after index removal, confirmation gating and repeat safety.


#### Completed cleanup baseline

The guarded production cleanup completed successfully: [workflow run 40168863586](https://github.com/mapkse-glitch/psx-trading-intelligence/actions/runs/40168863586). Two full-SHA-verified migration-upload copies (85,919,596 payload bytes across 492 staging pieces) and the exact redundant price index were removed. A normal staging vacuum reclaimed additional table/TOAST overhead. Combined database size fell by **147,857,408 bytes (147.86 MB)**: active database **330,274,495 → 270,980,799 bytes**; retained rollback database **101,643,967 → 13,080,255 bytes**. This is database-size reduction, not a measurement of Aiven service-level WAL/shared-disk usage.

The unique price constraint and reverse-order lookup index were preserved. Canonical counts and account totals matched before/after; independent live API checks also matched complete account-summary-row digests for both accounts. Health, ten-row symbol/index comparison and all 36 watchlist stocks passed after cleanup. No historical prices or account records were deleted and the rollback database remains available. **The one-month 2016–2018 capacity pilot has not been performed: it requires a supplied historical month.** Use the baseline above only while no unrelated imports have intervened; otherwise obtain a fresh audit immediately before the pilot.
