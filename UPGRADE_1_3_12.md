# PSX Intelligence v1.3.12 — clean Market Explorer layout

## Install — preserve your existing data
1. Back up your database privately and keep original source files.
2. Extract the ZIP and replace matching files in the **GitHub repository root** with its contents. Do not upload the ZIP itself or nest another application directory.
3. Retain existing Vercel server-only Turso environment variables: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. Never commit tokens.
4. Let the GitHub-connected Vercel deployment complete, then hard-refresh. The sidebar and server version should show **1.3.12**.
5. No database reset, migration, replacement or re-import is required.

**This is a source release, not a completed deployment to your live website.** These instructions supersede older upgrade notes where the Market Explorer controls differ.

## Requested changes
- **09 → Market volume:** separate year/month selectors removed. One Trading date calendar remains. Selecting a non-trading date continues to resolve backward to the latest available prior trading day, with a notice; no later data are substituted.
- **09 → Symbol vs Index:** date filter removed. Only Records and Symbol selectors remain. The view now uses the latest available N stock-price records, independent of the date selected on Market volume. Its JSON download uses the same latest-record selection; there is no invisible inherited cutoff.
- Summary maximums, including maximum average and volume, use **#03D815**. Summary minimums, including minimum average, use **#F63131**. These are max/min role colours, not the arithmetic sign of the value. Missing values stay neutral. Both light and dark themes are supported.
- Minimum date and Maximum date appear in separate prominent cards with large DD-MM-YYYY dates.
- Index table heading is **Index record**, with Date / Close / High / Low / Change / Change % / Volume columns. Removed the requested baseline and methodology paragraphs from the main view.
- Secondary scan, chart, research and storage implementation notes are under expandable details rather than filling the main workspace. Actions, errors, data-readiness reasons, missing comparison dates, conditional trade criteria and safeguards remain visible.

## Calculations and data are unchanged
This is a presentation/date-routing update, not a new trading model. Price data, financial calculations, imports, settings persistence, historical analysis, immutable forecast records and learning-research restrictions are preserved. No production writes were performed for this release.

Index-table Volume remains the sum of all imported cash-stock volumes for the exact date, excluding futures/account records to avoid double counting. It is not independently verified index-member volume or exchange-wide coverage. Source index identity/provenance and baseline fields remain in the API/export and documentation, even though the requested long UI paragraphs were removed. Missing source values are not invented. A missing-date warning remains when index records do not cover selected stock dates.

Other dashboard calendars, account date selection, futures contract selectors and historical date ranges remain unchanged. Existing trade warnings still distinguish selling owned shares from opening a short. A no-trade result remains valid; this release makes no accuracy or profitability claim.

The exact requested bright green has limited contrast on white. Text labels and signs remain; this release does not claim every light-theme value meets accessibility contrast targets.

## Validation and package
See [docs/VALIDATION_1_3_12.md](docs/VALIDATION_1_3_12.md). **169 tests passed, 20 private-reference tests skipped, 1 dependency deprecation warning.** Desktop/mobile Chromium checks passed, with no uncaught JavaScript errors.

Source, tests, deployment configuration, reference data and historical upgrade notes are intentional. No database, private workbook, credentials, logs or local runtime are bundled. Keep existing database-access controls; this update does not introduce user authentication.
