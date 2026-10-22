# 1.3.5 — recognise historical price workbooks

## Cause and scoped correction

The XLSX detector previously recognised raw prices only when a filename or sheet included 2026. Valid historical workbooks were consequently labelled CUSTOM_XLSX with zero rows read. This was not a duplicate-data rejection: those files were never parsed.

Raw price workbooks are now recognised using the active sheet's DATE, SYMBOL, VOLUME/VOL, PR-CLOSE aliases, OPEN, HIGH, LOW and CLOSE columns in the first five rows, independently of filename or year. Contract suffixes distinguish futures from cash; mixed samples are not silently assigned to one table. Existing legacy report and index detection retains precedence. No CSV date-parsing policy or financial formula was changed.

The upload preview highlights zero-accepted-row files as SKIPPED, shows an explicit warning, and disables Import when the entire batch has no importable rows. The backend also rejects a zero-accepted-row commit rather than reporting it as imported. Recognised exact duplicates remain safe to re-upload.

## Evidence

Both attached original files were tested in full against an isolated copy of the previously corrected database:

- 2016.xlsx: 87,393 rows, 01-01-2016 through 30-12-2016.
- 2022.xlsx: 84,038 rows, 03-01-2022 through 30-12-2022.
- Combined: 171,431 new historical cash records; repeating both imports produced zero new records and 171,431 exact duplicates.
- Every key and all seven measures were independently checked using the existing blank-as-zero parsing policy. The 2016 source contains one blank OPEN and one blank VOLUME; these retain the existing zero-default behavior. No CLOSE fields were blank. The 2022 measures were all populated. Numeric ticker 786 remains the string symbol 786.
- Existing current cash, futures and account data remained intact; the isolated starting database's latest cash date stayed 21-10-2026. Older history must not move the latest badge backwards.
- These tests did not import historical data into the live dashboard or deploy source. Other historical files in the screenshot were not attached and were not individually validated.

## Deployment and one-time backfill

1. Download an independent current backup.
2. Upload the extracted package contents to the existing repository root and redeploy Vercel. Preserve latest_cloud_sync.db.gz, hosting environment variables and credentials.
3. Hard-refresh once and confirm v1.3.5.
4. Discard the old STAGED batch that shows CUSTOM_XLSX/zero rows. It contains the old parser result; deploying code does not re-parse an existing manifest.
5. Select the original historical XLSX files again. Check each file shows OHLCV_CASH, its historical dates and nonzero accepted rows before committing. Do not rename the files to 2026 or alter their source dates.
6. Commit, wait for verified cloud-save confirmation, then download an independent backup. Unrecognised files are visibly skipped and must be resolved rather than assumed imported.

History is additive and retained in the canonical database. It does not need to be re-uploaded each day. For a large initial backfill, import one or two years per batch so validation and retry are manageable; local test timings do not guarantee hosting or network times. The files already present in the database are safely deduplicated by their original date/symbol keys and values.

This source-only package includes the earlier 1.3.4 safeguards. It does not include financial databases, raw workbooks or credentials, and does not configure new workflows or authentication.
