# Version 1.3.6 — Turso direct persistence

Based on repository commit 8c87680849cef7dbce02e9cfd7d3323eaff43321.

The canonical database is now accessed directly over the libSQL HTTP driver. Imported schema must already exist. Initialization adds only runtime revision and bounded staging BLOB tables. Credentials stay server-side. Serverless SQLite fallback is rejected. No embedded replica or GitHub snapshot persistence is used in Turso mode.

Import previews/commits fetch only relevant dates in paged queries. Inserts use bounded batches. Account summaries and canonical writes share one transaction, along with import status and revision updates. Duplicate import protection remains. Cache writes do not create endless freshness invalidations.

Upload chunks and compressed parsed payloads are durable across worker changes. Staging expires after 24 hours and expiry cleanup occurs on subsequent chunked staging. Successful commits remove staged data transactionally. Raw source files are not a permanent remote archive.

Settings show remote connectivity accurately, rather than claiming a full SQLite integrity audit. Remote backups use Turso export. Local restore and broad heuristic date repair are blocked in remote mode. Existing typed-source date-repair safeguards remain.

Financial formulas, account separation, futures contract filters and exports are retained. No authentication system, trading rule redesign, or unrelated workflow automation was added.

Read ../START_HERE_TURSO.md for deployment, verification, limits, and security precautions. Historical docs for 1.3.5 and earlier are not current deployment instructions.
