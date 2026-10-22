# 1.3.4 — complete date history and cloud freshness

## Why the old date could win

Legacy ambiguous CSV dates produced day/month-swapped records. Correct October uploads could coexist with a phantom December date; selecting MAX(trade_date) then chose that phantom date. Relabeling the date picker did not repair stored history. Version 1.3.3's source-based cleanup checked only rows outside the complete source date range, missing swapped duplicates within that range. Version 1.3.4 checks missing source keys anywhere in the history and requires an exact same-symbol, seven-measure match at the swapped source date. It never deletes a key present in the clean workbook.

Browser API results were cached indefinitely and clean warm server instances previously hydrated the cloud snapshot only at startup. An updated repository alone therefore did not guarantee that every old browser/server copy had refreshed.

## Corrections

- Each data-reading server checks cloud freshness with a shared 30-second per-worker metadata cache. A changed snapshot is validated and backed up before loading. Unchanged snapshots are not downloaded. Mutation serialization and stale-writer protection remain.
- Browser launch/Refresh/focus and a visible-tab 60-second check clear old analytics on snapshot changes. Historical manual date pins are preserved. Failed verification produces a warning.
- Shell and JS/CSS are no-store, with versioned asset URLs. This takes effect after loading the new build; a browser already running an older script should be reloaded after deployment.
- Source-verified import repair covers the full stored history; removed raw rows remain in the import-issues audit trail, transactionally.
- No computer-clock cutoff, fabricated prices or forced same-date labels across independent datasets.
- NOV/DEC identify contract expiry months, not observation dates. These legitimate contracts remain available for October trading observations.
- 08 remains for financial/data reconciliation; SQLite integrity alone cannot establish date or price accuracy. 09 is removed from navigation because downloads already exist within modules. 10 retains configuration, backup, restore and reviewed date repair. Existing section numbers are preserved.

## Verification during this audit

A reviewed live repair removed 9,872 source-certified duplicate rows: 9,396 cash and 476 futures. A safety backup preceded the mutation; cloud save was independently verified from the saved repository commit. Cash and futures then matched the supplied XLSX sources on every key and all seven measures: 97,267 cash rows and 6,539 futures rows, no missing or extra keys, and SQLite integrity OK. ATRL has 199 sessions rather than 217; its latest supplied close is 1,137.56 on 21-10-2026. Account tables were not modified.

The cloud data repair is separate from source deployment. The v1.3.4 source package has not been pushed or deployed by this audit. Preserve the existing `latest_cloud_sync.db.gz` when updating source. Do not upload an old snapshot or restore an older backup over the corrected cloud data.

## Deployment

1. Download a current independent backup.
2. Upload the extracted package contents into the existing repository root, replacing matching source files. Preserve the cloud snapshot, hosting configuration and GitHub sync credentials.
3. Redeploy the existing Vercel application. No new authentication or workflow configuration is needed.
4. Hard-reload the dashboard once. Verify v1.3.4 in the sidebar and /api/health. A browser tab already running old code cannot acquire the new cache protections until reloaded.
5. Check the module's own latest date. The supplied cash/futures end 21-10-2026; account 91269 ends 19-10-2026 and index data ends 16-10-2026. Those independent older dates are not an error or justification to invent newer data.

The live database inspected in this audit has already been repaired and cloud-saved. It does not need another full upload merely to repeat that repair. Other databases should be backed up and reimported from clean typed-date XLSX sources; deployment alone intentionally performs no automatic date-repair mutation.

## Limits

Performance measurements in the QA file are isolated local measurements, not guaranteed Vercel/GitHub network latency. Pending or unverifiable cloud states remain explicit; they are never silently overwritten. Source changes retain the existing no-login model and do not change site visibility or repository access.
