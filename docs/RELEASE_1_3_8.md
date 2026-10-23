# 1.3.8 — dashboard table presentation

Complete source package based on 1.3.7. Direct Turso persistence retained.

The fix addresses a CSS specificity conflict: `table.data-table th` forced left alignment over `.num`. Numeric headers and cells now share explicit table-scoped alignment. Missing numeric header/cell classes were corrected in rank, import IDs, trade identifiers, technical values and audit summaries. Total-row background/text now use matching theme variables instead of a dark background with light-theme dark text.

`table_display.js` provides stable, non-mutating newest-first ordering with explicit date validation. Every date-list renderer uses it without changing finance-service array ordering. Tables retain within-date ranking and bottom totals. UI date selectors and latest badges follow the same newest-first convention. Native date-input readouts refresh on edits. Hard-coded 2026 rolling-window captions were removed.

Existing financial calculation/persistence services, technical rules, chart chronology, workbook exports, filters and manual pins are retained. The app version is 1.3.8; the technical calculation engine remains 1.3.7. No database migration or data rewrite is part of the release.

Read `UPGRADE_1_3_8.md` before deployment and `docs/QA_1_3_8.json` for local test scope. No guarantee is made about untested production conditions or investment performance.
