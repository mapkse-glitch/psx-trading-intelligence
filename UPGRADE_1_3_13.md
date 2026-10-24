# PSX Intelligence v1.3.13 — startup recovery and safe Turso diagnostics

## Why the production site failed
The supplied Vercel traceback shows `lifespan → init_db → ensure_ready → initialize → SELECT name FROM sqlite_master` failing on its first table-list read. That exception escaped ASGI startup and Vercel could not start the application. The previous error wrapper discarded the original driver text, so this log alone does NOT prove an expired token, wrong URL, TLS/network failure or native-driver fault. The later `vc_handler` ImportError occurs after the startup failure; it is not independently established as the cause.

This release fixes the application-wide startup failure mode and diagnostic blind spot. It cannot make invalid credentials valid or guarantee the remote service is available.

## Deployment — no reset
1. Keep a private database backup and original source files.
2. Extract and upload the ZIP contents into the GitHub repository root, replacing matching files. Keep the existing Vercel/Turso environment variables. Do not commit private tokens.
3. Wait for the Vercel deployment and hard-refresh. Confirm **1.3.13**.
4. Open `/api/health`. Healthy JSON has `status: ok` and `db_integrity.ok: true`. An unavailable connection returns **503 JSON**, not fake success.
5. If data are still unavailable, click **Connection diagnostics** or open `/api/health?diagnose=true`. Share only its safe `code` and `read_only_diagnostic` result. These responses do not contain the configured token, database hostname or raw driver message.
6. When the actual connection problem is corrected, wait at least ten seconds and click **Retry connection**. Environment-variable changes in Vercel generally require a new deployment to reach the function.

**No database deletion, replacement, seeding, reset, migration or re-import is needed.** The patch does not deploy itself. Never replace your database with an empty SQLite fallback. Do not edit Vercel-generated runtime files.

## What changed
- Remote database I/O no longer runs inside ASGI lifespan startup. The static application can start independently of Turso availability.
- A worker-thread readiness gate runs before API freshness checks, financial reads or mutations. Required-schema checks and the pre-existing additive initialization still must succeed before a database API is allowed. No bypass or empty replacement data.
- Failed readiness is cached for ten seconds per worker, limiting repeated failed connection attempts during a page load. It is retried only on a later request; mutations are never automatically replayed.
- Safe failure codes replace the generic masked query error. Logs contain application-controlled category/stage fields only, never raw exception text, SQL parameters, tokens, connection URLs or response bodies.
- `/api/health` reports database unavailability as HTTP503. Optional `diagnose=true` makes one bounded, read-only HTTPS `SELECT 1` request using the existing private server credentials to the already-configured host. Redirects and insecure transport fallback are disabled; the token is never sent to the browser.
- Static shell/assets remain reachable. The UI explains that records were not loaded and provides Retry/diagnostics controls. Status indicators cannot claim a healthy connection during failure.
- Existing trade, financial, import, sector, forecast, volume and layout behavior is retained. No changes to Vercel dependencies or the native driver were made without evidence that they caused the incident.

## How to interpret diagnostics
| Safe code | Next step |
|---|---|
| SERVER_CONFIGURATION | Check Production-scoped server environment variables: `PSX_DATABASE_BACKEND=turso`, a valid `TURSO_DATABASE_URL`, and a nonempty `TURSO_AUTH_TOKEN`. Do not post their values. |
| AUTHENTICATION_REJECTED | Verify the configured token belongs to this database and is valid. A direct HTTP401 is evidence of rejected authentication, not proof of why it was rejected. |
| PERMISSION_DENIED | Verify database/token permissions. Do not weaken security or switch to local fallback. |
| NETWORK_CONNECTION_FAILED / TLS_CONNECTION_FAILED / CONNECTION_TIMEOUT | Check database service availability, hostname configuration and connectivity. Do not disable TLS verification. |
| REQUIRED_SCHEMA_MISSING | Verify the URL points to the existing imported PSX database. Do not seed an empty replacement. |
| SERVICE_RATE_LIMITED / REMOTE_SERVICE_HTTP_ERROR | Review Turso service status/limits and the returned HTTP status. |
| HTTPS_READ_OK_NATIVE_DRIVER_OR_SCHEMA_CHECK_FAILED | Direct credentialed HTTPS read worked, but the native connection/schema path failed. This does not prove write permission or commit. Inspect the main diagnostic stage/code next; do not change tokens blindly. |
| DRIVER_OPERATION_FAILED / REMOTE_QUERY_REJECTED | Still unclassified. Share the safe JSON result. Do not assume data loss or successful rollback. |

If Vercel still returns its platform-level500 rather than the JSON health response, send the new runtime traceback: a separate platform/runtime failure may remain. Hosting and private account configuration cannot be verified from this source ZIP alone.

## Write safety
No write is retried automatically. A lost acknowledgement may mean the outcome is uncertain: verify saved batch/status before manually resubmitting. The existing transaction/rollback protections and immutable forecast history remain. Loading the shell is not evidence that all records are available or healthy.

## Verification
**191 tests passed, 20 optional private-reference tests skipped, 1 dependency deprecation warning.** Includes real disposable libSQL HTTP cold-start integration, mocked first-query failures, credential-safe diagnostics, cooldown/recovery and write-safety checks. Local healthy and outage desktop/mobile browser checks passed. See `docs/VALIDATION_1_3_13.md`.

No production credentials or database writes were used. No database, tokens, private uploads, logs or local runtime are packaged. Production recovery remains to be verified after deployment.
