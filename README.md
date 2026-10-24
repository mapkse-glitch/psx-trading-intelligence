# PSX Intelligence v1.3.14

A historical-data dashboard hosted on **GitHub → Vercel → Aiven PostgreSQL**.
One current README covers setup, imports, operation and verification. No Google
Drive, credentials or user trading database is included in the release archive.

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

1. Extract this ZIP. Upload its **contents** to the root of your existing GitHub
   repository. Keep `main.py`, `requirements.txt`, `vercel.json` and `psx_app/`
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
   version `1.3.14`. An empty database is expected before you import your data.

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

### If your old GitHub data is a `.db` / `.db.gz` snapshot instead

Do not upload a SQLite database into Aiven's SQL editor or the price-file importer.
It needs a one-time conversion. The optional `tools/import_sqlite_to_postgres.py`
converts a trusted PSX SQLite snapshot into an **empty** application database. It
checks source integrity, copies reviewed canonical/config/audit/forecast tables,
verifies counts, resets ID sequences and commits atomically. It refuses to merge
into a database already containing imported data. Staging, source-file binary
archives and derived indicator/result caches are not migrated.

**Hosted option; no localhost required:**
1. Use this only for a trusted snapshot **already in your repository**. Do not
   publish personal account data in a public GitHub repository just to migrate it.
2. In GitHub repository → Settings → Secrets and variables → Actions, add repository
   secrets `DATABASE_URL` and `DATABASE_CA_CERT` (same private values as Vercel).
   Vercel's variables are not automatically available to GitHub Actions.
3. Open Actions → **Import existing SQLite snapshot into empty PostgreSQL** →
   Run workflow. Enter the existing repository path, e.g. `latest_cloud_sync.db.gz`.
4. Enter `IMPORT_INTO_EMPTY_DATABASE` as the confirmation and run it. Do not use
   the dashboard importer while the workflow is running.
5. Review its count/date-range summary. Verify key reports and latest dates.
   This workflow is supplied, but was **not run against your GitHub/Aiven account**.

A snapshot may be older than your final Turso data. Reimport newer source files
through the normal importer afterward. No missing history or predictions are invented.

For a trusted snapshot on your USB, an optional one-time conversion can run from
an environment with Python and the same three variables set (this is not hosting
an app on localhost):

```bash
pip install 'psycopg[binary]==3.2.12'
python -m tools.import_sqlite_to_postgres path/to/app.db         # dry run; no DB writes
python -m tools.import_sqlite_to_postgres path/to/app.db --confirm-empty-target
```

## What changed to reduce repeated reads

- PostgreSQL persistence, double-precision prices, 64-bit volumes and IDs.
- Transactional import/staging, bulk inserts, parameterized queries and upserts.
- PostgreSQL advisory locks coordinate import commits across Vercel workers.
- A bounded persistent result cache shares analysis across cold workers. Price
  changes, corrections, settings and reference changes invalidate it by revision.
- Full ticker calculations are reused across chart/analyst/forecast consumers.
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

## Verification report

## Tested environment

- Application baseline: retained v1.3.13 Startup Recovery / Turso Diagnostics ZIP.
- Python 3.13 test environment; FastAPI/Starlette using pinned requirements.
- psycopg / psycopg-binary 3.2.12.
- Real disposable PostgreSQL 15.18 bound only to loopback, empty isolated `psx_test`.
- Remote TLS is mandatory in deployed configuration. An explicit loopback-only
  test switch permits unencrypted connections solely to the disposable test DB.
- Chromium/Playwright desktop 1440×1000 and mobile 390×844, actual running backend
  and synthetic OHLCV data. No mocked API results in these browser checks.

## Automated regression suite

Command (test database is destructive; never supply production credentials):

```
PSX_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:55432/psx_test pytest -q
```

Result: **205 passed, 34 skipped, 1 warning**.

Skipped: 20 private historical-reference fixture tests not supplied; 14 optional
legacy loopback libSQL server tests not supplied. PostgreSQL was actually exercised;
those PostgreSQL integration scenarios were not skipped. The warning is Starlette's
httpx TestClient deprecation, not a database/test failure.

Covered:
- Configuration validation and no serverless SQLite fallback.
- TLS verification selected even if URI asks for weaker SSL settings.
- Loopback test bypass cannot disable verification on a remote host.
- Sanitized configuration/authentication/TLS/network/capacity error messages.
- No automatic retry of uncertain writes.
- Actual PostgreSQL schema initialization and compatible row/index/name access.
- Transactional bulk inserts, upserts, commit/rollback and shared data revision.
- Cross-worker durable blob staging, chunk assembly, expiry and cleanup.
- Import staging/commit, repeat-commit idempotency, exact duplicates and corrections.
- Account execution rollup rollback and strict account separation.
- Sector reference preview, direct upload, batched commit and atomic rejection.
- Immutable forecast save/evaluation and learning metadata persistence.
- Cash-derived index-table volume and Market Explorer queries.
- Values above signed 32-bit volume range; JSON-friendly aggregate numeric types.
- Same full ticker calculation reused for 1/120/all-bar chart/forecast consumers.
- Revision-aware cache reuse; correction/new import invalidates changed symbols
  while preserving unchanged indicator-cache entries.
- Overview, account, volume, futures, technical, coverage, reconciliation,
  settings and status APIs against PostgreSQL; XLSX and CSV export endpoints.
- Optional SQLite snapshot conversion: source integrity check, dry run, preserved
  IDs/values, ID-sequence reset and refusal to overwrite a nonempty database.
- ASGI/static UI stays available during a failed database connection.

## Browser checks

Passed using the actual PostgreSQL-backed test server:

- Overview sidebar: `Database: connected`.
- Settings identifies PostgreSQL direct persistence.
- Market volume calendar selected a populated synthetic trading date and rendered
  the volume charts. A zero-volume latest test date correctly had no positive-volume
  chart; the test explicitly selected a populated date rather than inventing data.
- Symbol vs Index renders `Index record` and has zero date-calendar inputs.
- Automated Analyst renders the plain-language action/explanation panels.
- Mobile document width 390 px at a 390 px viewport (no whole-page overflow).
- Zero JavaScript page errors and zero HTTP 5xx API responses in the successful run.

Screenshots were generated during checks. These use synthetic data and are not
proof of your real account totals or real production performance.

## Not verified / not performed

- No live Aiven credentials were provided or used.
- No production Vercel deployment or production PostgreSQL connection test.
- No performance/load/latency benchmark against Aiven Free's real CPU/RAM/disk.
- No full user's historical dataset imported or reconciled.
- No assertion that the entire PostgreSQL footprint fits inside 1 GB until measured.
- No global connection-pool guarantee across autoscaled Vercel workers.
- No production backup restore test or Turso snapshot completeness check.
- Optional GitHub Actions workflow supplied, not executed in the user's account.
- No paid plan changes, service purchases, database deletion or production writes.

The application remains password-free as requested. Request hygiene is not
identity/access control. Provider quotas and public-access risks remain real.
