# PSX Intelligence v1.3.30

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

## Current update: v1.3.30 — visible filter suggestions

Partial update for **v1.3.29**. Merge the included files into the existing
repository root without deleting folders; commit and deploy as usual, then
hard-refresh. No database schema, imported records, settings or credentials are
changed and no re-import is needed.

- Searchable filters show matching choices while typing, with prefix matches
  first. Click or tap a choice, or use arrow keys and Enter; Escape clears the
  search. No matching choices is explicitly shown. Typing alone does not change
  the selection or request data. The native dropdown remains available.
- Symbol and ticker filters with fewer options also get the same search, while
  other small dropdowns are left simple. Choices come from the existing filter
  options; no external service or additional data import is required.

## Previous update: v1.3.29 — alignment and chart details

Cumulative partial update for **v1.3.25 through v1.3.28**. Merge and overwrite
included files into the existing repository root; do not delete folders. Keep a
rollback commit, deploy normally and hard-refresh. No imported data, schema,
credentials or settings are changed; no re-import is needed.

- Symbol vs Index places Lock between Change % and Volume. Symbol Insights
  presents each summary in one row, with horizontal scrolling inside the card
  on narrow screens; the latest record uses a lock icon instead of cap values.
- Max and min reference closes use green and red respectively. A current close
  is red when lower than its previous imported close, green otherwise, and
  neutral if that reference is unavailable, for both symbol and index.
- Search and its selector are visually connected. Shared cards have restrained
  depth and hover effects; chart marks provide concise hover/focus information.
  Price-lock icons remain close-based estimates, not confirmed order-book locks.

### Design guidance for future pages

Reuse the shared theme, typography, yellow dividers, positive/negative colors,
connected searchable selectors and revision-scoped caching. Keep cards aligned,
responsive and readable in both themes, contain wide content within its card,
and provide labels and keyboard access. Use restrained hover effects, respect
reduced-motion preferences, and give chart marks short, accurate descriptions.
Never imply unavailable financial data is present or alter imported records.

## Previous update: v1.3.28 — Symbol Insights and horizontal charts

Cumulative partial source update for **v1.3.25, v1.3.26, or v1.3.27**.
No authentic records, database schema, credentials or settings are changed. No re-import or new environment variable
is required. Keep your current commit for rollback; extract and **merge/overwrite**
the included files into the existing repository root without deleting folders.
Those were the v1.3.28 instructions; use the current update instructions above.

- **Symbol Insights** in Market Explorer has searchable symbol and session
  controls (14 sessions by default), company identity, the latest imported row,
  and extrema for the requested sessions, all history, 1 Oct 2023 onward and
  27 Feb 2026 onward. Source averages are not calculated from high/low/close.
  Each extreme shows its latest date; tied observations are counted.
- Four symbol comparison cards and four corresponding index cards use the exact
  27 Feb 2026 row as the baseline. “After 27 Feb” means 28 Feb onward, with the
  latest stored record included. Differences are later/current value minus the
  stated reference; percentages divide by that reference. Missing baselines,
  extrema and nonpositive percentage denominators are marked unavailable.
  Index comparisons use its latest stored date on or before the symbol's latest
  date, explicitly dated. Index average and index-traded volume are not supplied.
- Symbol vs Index records have a lock icon per row using the existing tick-rounded,
  close-based estimator. Green = upper, red = lower, gray open = within range;
  unavailable inputs are distinguished. These are estimates, not confirmed
  exchange order-book locks, and exchange exceptions may differ.
- All eight Market Performance rankings use responsive horizontal bars without
  horizontal chart scrolling. For monthly, quarterly, half-year, nine-month and
  yearly charts, the sector-volume bars run horizontally with the index change
  line preserved on its separate point scale. The weekly Index change & sector
  volume combination remains unchanged. Chart data tables and exports stay intact.
- Reads are indexed per symbol, with the existing bounded, revision-scoped cache;
  no per-symbol network request loop or source data edits are introduced.

Verification: 437 tests passed, 34 skipped, and one existing dependency warning.
Local tests cover date boundaries, tied extrema, missing anchors,
percentage signs and zero denominators, the provided lock examples, SQLite and
disposable PostgreSQL, as well as all seven performance periods in Chromium at
320/390/768/1440 px, dark mode, cache reuse and stale-response protection. Live
Aiven speed and the correctness or completeness of production imports were not
verified by these tests.

## Previous update: v1.3.27 — Matching ranges, locks and searchable filters

Partial source update for **v1.3.26**. No authentic records, database schema,
credentials or settings are changed. No re-import or new environment variable
is required. Keep your current commit for rollback; extract and **merge/overwrite**
the included files into the existing v1.3.26 repository root without deleting
folders. Commit as usual, let Vercel deploy, hard-refresh, and confirm v1.3.27.

- **Price Limit Checker:** retains the existing user-requested 10% or PKR 1
  whichever is greater, but rounds the calculated limits to the nearest paisa
  before comparing the closing rate. Thus a displayed limit and equal valid
  two-decimal close cannot disagree about the lock. Genuine extra close precision
  is shown, not rounded into a false lock. PSX Regulation 19.3 states that
  calculated circuit-breaker prices are rounded to the nearest tick; the ready
  market one-paisa assumption is based on a PSX notice. This remains an estimate
  from the imported previous close, not an exchange-confirmed lock; ETF, special
  instruments, first-day and other exchange exceptions are not modeled.
- **Matching Rate 1:** initial table duplicates the original ten nearest older
  matches. Enter an inclusive starting and ending closing price and choose Find
  prices to see every matching stored record, 100 per page. Matches are ordered
  by proximity to the latest close, newest first on ties. The default range
  search includes all stored history, including the latest date; uncheck
  **Include latest month** to retain the original tab's strictly-before-one-month
  cutoff. Matching Rate itself is unchanged. The same exact-date index join and
  stored-session gaps are used, with no fabricated index values.
- **History filters:** Symbol vs Index defaults to 14 records; Small Cards
  already defaults to 14 sessions. Futures days-to-expiry and validation holding
  sessions are separate calculation parameters and remain unchanged.
- **Long dropdowns:** a search field appears beside native filters containing
  at least 12 options. Type part of a symbol or option and choose a match;
  Enter selects a sole match, and Escape clears. Existing select behavior and
  short lists are retained. No request is sent merely for typing a search.

Verification: 428 tests passed, 34 skipped, and one existing dependency warning
using local synthetic SQLite and disposable local PostgreSQL. Local Chromium tests
covered range boundaries, both date scopes, pagination, tab switching, searchable
filters, dark mode and mobile layouts. Live Aiven performance, all production
data and exchange-specific exceptions were not validated by these tests.

Sources: PSX Regulations, section 19.3, July 2025,
https://www.psx.com.pk/psx/themes/psx/uploads/PSX-Rulebook-July-14-2025.pdf ;
PSX's 7 November 2022 notice on one-paisa Ready Market tick and rounding,
https://www.psx.com.pk/psx/themes/psx/uploads/N-1100_Proposed_Amendments_-_NTS,_OO_Broker,_BMC_(November_07,_2022).pdf .

## Previous update: v1.3.26 — Technical Analysis repair

This partial update for **v1.3.25** repairs the Technical Analysis view error
`m is not defined`. It removes an accidentally copied Market Explorer loading
line from the Technical Analysis renderer. The five Technical Analysis tabs and
Market Explorer retain their existing behavior. No schema, historical records,
settings, credentials or import workflow are changed.

### Install v1.3.26

1. Keep your current commit for rollback and extract the update ZIP.
2. Merge/overwrite the included files and folders into the existing **v1.3.25**
   repository root. These are partial folders: **do not delete existing folders**.
3. Commit through your normal GitHub workflow, let Vercel deploy, then hard-refresh
   with Ctrl+Shift+R. Confirm **v1.3.26** in the sidebar or `/api/health`.
4. Open Technical Analysis and verify its tabs. No re-import, database maintenance
   or new environment variables are required.

The regression suite passed **412 tests**, with **34 skipped** and one existing
third-party deprecation warning, using a disposable local PostgreSQL database.
Local Chromium checked all five Technical Analysis tabs with synthetic data.
Read-only live checks covered dashboard pages and account, futures, Market
Explorer and Market Performance tabs. The repair itself has not been deployed
or tested on live production; destructive actions, actual imports, backups and
complete financial-data reconciliation were not tested.

## Previous update: v1.3.25 — Market Performance

This **partial source update for v1.3.24** adds **10 • Market Performance** below
Market Explorer. Settings moves to menu 11; its functionality is unchanged.
No authentic records, import settings, database schema, credentials or other
modules are rewritten. No GitHub push or live deployment was performed.

### Install v1.3.25

1. Keep the current source commit for rollback. Extract the update ZIP.
2. **Merge/overwrite** the included `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` into the existing **v1.3.24 repository root**.
   These are partial folders: do not delete the original folders, create an extra
   enclosing application folder, or upload the ZIP itself as application source.
3. Commit through your normal GitHub workflow, let Vercel deploy, then hard-refresh
   with Ctrl+Shift+R. Confirm **v1.3.25** in the sidebar or `/api/health`.
4. Open **Market Performance**. No new environment variables, database maintenance
   or re-import are required when authentic cash, INDEX, COMP_LIST and KSE100
   membership data are already imported. Missing reference/data coverage is shown,
   not replaced by sample records.

### Seven periods and chart definitions

- **Daily:** date filter, index summary and eight top-10 column charts.
  A requested closed/missing date resolves to the last imported date on or before
  it, explicitly labelled. A request before all history is rejected, never moved
  forward to a later price.
- **Weekly:** ISO year/week numbers, **Monday–Friday only**. Imported weekend
  observations are excluded from weekly values and weekly baselines. The combined
  chart has five weekday slots; absent observations are gaps, not fabricated zeroes.
- **Monthly:** month/year filter. The combined chart shows **each stored session
  within that month**, not one column per month across all history (confirmed A).
- **Quarterly:** fiscal Q1 Jul–Sep, Q2 Oct–Dec, Q3 Jan–Mar, Q4 Apr–Jun.
- **Half Year:** H1 Jul–Dec; H2 Jan–Jun.
- **Nine Month Ended:** Jul–Mar, not a rolling window or Jan–Sep.
- **Yearly:** Jul–Jun. FY 2026–27 means 1 Jul 2026–30 Jun 2027.
  Quarterly, half-year, nine-month and annual combined charts use monthly buckets.

Each period has scrip-volume and sector-volume leaders, sector gainers/losers,
scrip PKR gainers/losers and scrip percentage gainers/losers. The latter six
charts use **only imported KSE100 membership**. Volume charts include all imported
cash symbols, not just KSE100 or SEL_COMP_LIST. Ties are deterministic, and fewer
than ten eligible leaders are shown without padding or invented records.

- Price change = last eligible close in the period minus the last stored close
  **before the period began**; percentage = change / baseline × 100.
- Return rankings exclude KSE100 symbols whose last quote is older than the
  period's cash as-of date, or whose endpoint/baseline is missing or nonpositive.
  Actual zero returns are valid but are neither gainers nor losers.
- **Sector returns are equal-weight averages of eligible KSE100-member percentage
  returns**, as confirmed. They are not market-cap weights or index-point
  contributions. Expand Chart data for eligible/total sector-member counts.
- KSE100 membership is the imported static list; historical reconstitutions,
  corporate-action adjustments and dividend/total-return adjustments are not modeled.
- Sector lookup uses imported COMP_LIST, then imported KSE100 sector data;
  unmapped volume is kept as **Unmapped**, never silently dropped. There is no
  bundled-company or membership fallback.
- The combined chart is **index point change** (line, left axis), not index level,
  plus imported cash volume (stacked columns, right axis). Stacks are the top five
  sectors for the selected period, Other, and Unmapped when applicable. Their sum
  equals imported bucket volume. This is **not official KSE100 trading volume**;
  the index table itself does not provide volume.
- Cash/index as-of dates and pre-period baselines remain separate and visible.
  Future observations never enter an older selected period. Current/unfinished
  imported periods are labelled; reaching the final weekday is not certification
  of full import coverage. Missing imports cannot be distinguished from exchange
  holidays. Expand Calculation & coverage for limitations and excluded-member counts.

### UI and performance safeguards

Shared red **#F63131**, green **#03D815**, yellow separator rules, human-readable
shared dates, system fonts, light/dark themes and reduced-motion preference are
retained. Eight charts form a responsive two-column grid, with internal horizontal
scrolling for dense labels and a full-width combined chart. Keyboard-focusable
columns expose exact values; Chart data tables are created only when expanded.
There is no external chart library, CDN, background training or full OHLCV download.
The top Export button downloads the selected report as CSV with coverage notes;
spreadsheet formula-leading text is neutralized. No trading or database write
is performed by the report (other than expendable PostgreSQL derived-result cache).

One report response contains filters, summary, eight rankings and the small
combined series. Date-range aggregation and indexed per-symbol baseline seeks
replace a network read per symbol. Browser caching reuses the existing bounded
30-second revision-scoped panel cache; in-flight reads deduplicate, imports/refresh
invalidate the cache scope, and late replies cannot overwrite a newer tab or view.
PostgreSQL also uses the existing revision-keyed shared compressed result cache.
Its namespace and source data are unchanged.

### Verification for v1.3.25

- **411 passed, 34 skipped, 1 dependency deprecation warning**, including guarded
  loopback PostgreSQL tests, fiscal boundaries, weekday exclusion, index baselines,
  exact stacked volumes, membership restrictions, missing prices, stale symbols,
  safe chart labels, stale-response protection and shared-cache invalidation.
- Local Chromium: all seven tabs, eight charts per tab, combined chart counts,
  light/dark themes, lazy data tables, CSV download and layouts at
  1600/1200/768/390/320 px; no document overflow or JavaScript errors. Returning
  to a cached period within the cache interval issued **zero new report requests**.
- A separate **synthetic local SQLite** benchmark used **1,000,000 rows, 1,000
  symbols and 1,000 weekday sessions**. Two calculations per period took roughly
  **68–323 ms**, with bounded chart payloads (about 16–104 KB including date options).
  Date ranges and baseline lookups used the existing indexes. These figures are
  not Aiven/Vercel network or production memory/load measurements and are not a
  live latency guarantee. No live Aiven benchmark or production data access occurred.
- Clean overlay/hash verification and a second regression run validate this patch
  against its v1.3.24 source baseline. No synthetic databases, credentials, browser
  images, package dependencies or benchmark data are included in the ZIP.

## Previous update: v1.3.24 — Futures Last Data with automatic contract Days

This partial source update is based on **v1.3.23**. It adds the requested latest-only
futures view and removes the old retention tab from the interface. **No historical
records are deleted, compressed, re-imported or rewritten.**

### Install v1.3.24

1. Keep the current GitHub source commit for rollback. Extract the ZIP.
2. Merge/overwrite its included `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` files into your existing **v1.3.23 repository root**.
   These are partial folders: **do not delete existing folders**, nest everything
   inside another parent folder, or upload the ZIP itself as application source.
3. Commit, wait for the normal GitHub/Vercel checks, then hard-refresh
   (Ctrl+Shift+R). Confirm **1.3.24** in the sidebar or `/api/health`.
4. Open **06 → Futures Comparison & Annualized Analysis → Last Data**, immediately
   beside **Date Summary**. No new dependency, configuration, schema migration,
   index, cleanup or data re-import is required. Nothing was pushed/deployed for you.

### Tab and table

- **2-Month Rolling Retention** is removed from the visible tabs. Its preview API
  remains compatible for existing integrations. Removing a tab does not delete
  data or change the rolling-window filters/settings used by the older views.
- **Last Data** always queries the **latest imported futures date**. It has no
  manual date pin, user-entered Days or rolling-window override. Newer cash data
  does not move the futures snapshot forward. Older futures rows are not mixed
  into the latest-date table, even if a symbol has no row on that latest date.
- Three aligned cards show the latest date, number of contracts, and count of
  exact same-date cash matches. No data is shown honestly as unavailable with an
  awaiting-import state, not a fabricated date or sample figures.
- The table contains the requested **12 columns**, ordered by **Symbol A–Z**, then
  by calculated contract rule date and contract label:

  | Column | Meaning |
  | --- | --- |
  | Symbol | Futures base/cash symbol |
  | Contract/Month | Original contract month, with its calculated last Friday shown beneath |
  | Current Value | Same-date cash close, PKR |
  | Volume | Same-date **cash** volume |
  | Future Value | Futures close, PKR |
  | Future Volume | Futures volume, separate from cash volume |
  | High | Futures high, always green |
  | Low | Futures low, always red |
  | Difference | Futures close − cash close, PKR |
  | Difference % | Difference ÷ cash close × 100 |
  | Days | Automatically calculated calendar days to that contract month’s last Friday |
  | Annualized % | Difference % × 365 ÷ Days |

- Cash prices and volumes use an **exact date + symbol join**. Missing cash quotes
  remain unavailable; no earlier/later price is substituted. Genuine zero volumes
  remain zero. Contracts/variants such as OCT and OCTB remain distinct rows.

### Days: explicit calculation boundaries

Days are computed from the **displayed data date**, not the computer date:

`Days = max(0, contract-month last Friday − latest futures data date)`

The data date is excluded; the ending Friday is included by date subtraction.
These are **calendar days**, including weekends, not a trading-session count.
This naturally includes the remaining current-month days, every intervening full
month, and the target month up to its last Friday.

For example, if the latest imported date is **16 Oct 2026**:

- OCT/OCTB → **30 Oct 2026** → **14 Days**.
- NOV → **27 Nov 2026** → **42 Days**.
- DEC → **25 Dec 2026** → **70 Days**.

The target is the user's requested **last-Friday rule**, not a claimed official,
holiday-adjusted exchange expiry calendar. The calculated date is visible in each
contract cell and in the Days tooltip.

- An explicit YY/YYYY in a recognizable contract month is used; YY means 2000–2099.
- For a yearless month, use its **next occurrence relative to the data month,
  current month included**. Thus JAN from a December snapshot maps to January of
  the next year. This inference is disclosed in the table footer. An expired rule
  date in the current month is not silently moved a year forward.
- A passed rule date or the ending Friday itself gives **Days = 0** and unavailable
  Annualized %, never division by zero or a made-up 1/30-day denominator.
- Unknown month/year gives unavailable Days and Annualized %. Missing/nonpositive
  cash close prevents spread/percentage calculations. A valid zero spread with
  positive Days remains a real **0.00%**, not unavailable.
- Existing futures views retain their original user-entered Days and financial
  formulas. Their service methods were checked structurally against v1.3.23 and
  remain unchanged. This new automatic rule applies only to **Last Data**.

### Consistent styling and efficient navigation

- Reuses the existing font scale, date format (**6 Sept 2019**), yellow dividers,
  **#03D815** High/positive and **#F63131** Low/negative colors, native controls,
  useful hover feedback, responsive spacing and internal sticky-header table scroll.
- Latest-date cards stretch evenly on desktop and stack cleanly on smaller widths.
  The 12-column table scrolls internally instead of widening the page.
- The new tab makes **one fresh report HTTP request** per visit/Refresh latest,
  with the existing global concurrent-GET deduplication. It bypasses futures
  metadata and historical dropdown requests; no browser TTL can pin this report.
- The report uses **one indexed latest-date SELECT with a same-date cash join**,
  not one query per symbol/contract. Local SQLite query-plan inspection confirmed
  existing `idx_fut_date_base`, the covering futures date index, and the cash
  date/symbol unique index are used. No new index is installed.
- Existing revision-keyed, compressed PostgreSQL report caching is reused. A new
  canonical import/revision invalidates an older latest-data result; no separate
  process cache is used for this endpoint. No source-data write occurs; normal
  expendable report-cache writes remain possible without advancing the revision.
- Tab selection/loading feedback is immediate. Generation guards reject late
  previous-tab responses, including metadata replies, before unnecessary follow-up
  requests or DOM replacement. Errors retain the tabs and offer Retry.
- Existing header/8-sheet futures workbook exports are unchanged. Last Data has
  not been silently inserted into or substituted for the legacy workbook sheets.

### Verification

- **372 passed, 34 skipped, 1 dependency deprecation warning** on isolated SQLite
  and disposable loopback PostgreSQL. The skipped tests need private historical
  fixtures; no production Aiven database or user workbook was accessed.
- Added tests cover current/next/further months, December–January rollover,
  leap February, explicit years, contract suffixes, ending/passed Fridays,
  unknown month/year, exact/missing cash joins, zero volume/spread, alphabetical
  ordering, freshest snapshot after a new import, API filter independence,
  per-contract 365-day annualization and shared-cache revision invalidation.
- Local synthetic Chromium checks passed in light and dark themes with 60
  contracts, three aligned summary cards, all 12 columns, A–Z ordering, separate
  source volumes, canonical High/Low colors, yellow rules, sticky headers,
  1600/1200/768/390/320 px without page-level horizontal overflow, one initial
  report request and no metadata dependency. Refresh, empty/error states and late
  metadata-response protection passed; no JavaScript page errors were observed.
- Timing on live Vercel/Aiven was not measured; network/cold-start latency still
  exists. This release removes avoidable work rather than promising instant pages.
- The minimal ZIP is verified against a clean v1.3.23 overlay and tested again.
  Unrelated application files remain byte-identical. No trading database, private
  credentials, workbook, generated test data or screenshots are packaged.

Older release sections below remain as historical reference.

## Previous update: v1.3.23 — clearer quotes, seamless gradients and lighter navigation

This is a **partial source update for v1.3.22**. Trading data, import logic,
threshold rules, date handling, colors, exports and reference membership stay intact.

### Install v1.3.23

1. Keep your current GitHub commit for rollback. Extract this ZIP.
2. Merge/overwrite its included `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` files at the existing repository root. **Do not delete
   existing folders**: this archive contains changed files only. Do not nest the
   extracted contents in another folder or upload the ZIP itself as source.
3. Commit to GitHub and wait for the normal checks and Vercel deployment.
4. Hard-refresh (Ctrl+Shift+R) and confirm **1.3.23** in the sidebar or `/api/health`.
   No dependency, environment variable, migration, new index, cleanup or re-import
   is required. This update has not been pushed or deployed on your behalf.

### Visual corrections

- Latest Close now clearly says **PKR per share**; Latest Index Close says **Index
  points**. Index levels are not labelled as rupees. Daily absolute-change labels
  carry the corresponding unit. Main figures keep their gain/loss colors.
- Quote groups are vertically balanced between the existing header and daily
  changes. All three latest cards retain equal desktop dimensions; responsive
  stacking, word wrapping and the existing Price Limit Checker remain intact.
- The six Day's Range–Year's Range bars use an opaque, continuous **green → yellow
  → red gradient**, with midpoint #D4C83F. The center no longer mixes the card's
  dark background into the colors. Headings, endpoint High/Low prices and dates
  stay in place. These six bars remain marker-free; the separate Price Limit
  Checker and its close indicator/calculation are unchanged.
- Matching Rate remains the shared dashboard sans-serif font at **13 px**. This
  was verified from computed browser styles, not just the stylesheet declaration.
- Small Cards now labels the imported source-average value simply **Average**.
  The source field, calculations, precision and values are unchanged.
- Restrained hover feedback applies only to useful controls: buttons, navigation,
  tabs, quick selectors and editable filters. No card-lift effect, looping motion,
  chart animation or new general-purpose transform was added. Keyboard focus is
  explicit; added transitions are disabled for reduced-motion preferences.
- Existing yellow dividers, #03D815 green, #F63131 red and day–month-name–year
  display conventions are retained in both themes.

### Loading investigation and changes

Two avoidable source-level costs were identified in the reported tab transition:
Matching Rate fetched metadata and then its report serially, while Symbol vs Index
used a different browser fetch path and did not populate that metadata cache. The
matching query also calculated two window functions across the full symbol history
before selecting ten eligible matches. These are verified code paths; they do not
establish that every live delay has the same cause.

- All Market Explorer tabs now share the same **30-second, refresh-scoped report
  cache**. It deduplicates in-flight requests and retains at most **48 completed
  responses** per client-cache scope. Import, manual refresh and the existing
  cloud-revision refresh replace that scope as before. Failures are not cached.
- Matching Rate starts independent metadata/history reads **in parallel** when the
  selected symbol is known. After Symbol vs Index, metadata is already reusable,
  so the first Matching Rate transition needs only the report request. An invalid
  symbol still resolves through real metadata rather than fabricated fallback data.
- Active tab feedback and a lightweight loading state are immediate, instead of
  leaving the old tab selected while a new tab loads. Existing render-generation
  guards still prevent a late older response replacing the current view.
- The shared GET helper now deduplicates concurrent identical requests across all
  dashboard pages. Existing `useCache=false` calls remain uncached on sequential
  reads; they are not silently given a TTL. A response from an older cache scope
  cannot populate a refreshed scope. POST/import/export behavior is untouched.
- The matching query first ranks eligible historical closes and limits to ten,
  then counts later stored sessions for those dates using the existing symbol/date
  index. Calendar-month exclusions, nearest-price ordering, newest-date tie breaks,
  signed differences, real trading-session gaps and exact-date index joins retain
  their previous meanings. Existing valid shared backend results can be reused;
  the global backend cache namespace remains 1.3.17.

### Verification and honest performance measurements

- **Matching query:** local SQLite, selected symbol with 5,000 stored sessions
  within a 45,000-row synthetic database; median of 15 uncached service calls:
  **10.500 ms (v1.3.22) → 3.399 ms (v1.3.23)**, about **3.09×** faster. Full report
  outputs were identical to the old implementation.
- **Tab transition:** local Chromium with an artificial 100 ms delay per market
  HTTP request, three completed Symbol vs Index → Matching Rate renders per build:
  median **298 ms → 192 ms**; required requests **2 → 1**. A fully cold matching
  visit started its two independent requests 1 ms apart. Already-warm matching
  transitions were small in both builds (24 ms old / 32 ms new median); this test
  does not claim a warm-cache improvement where there was none.
- Those are **local synthetic measurements, not live Vercel/Aiven guarantees**.
  Actual first-load cold starts, database/network latency and large analysis jobs
  can still take time. Heavy pages are not speculatively fetched in the background.
- Chromium checks passed in light/dark themes and at 1600/1200/768/390/320 px:
  equal desktop latest-card dimensions, proper quote units, real opaque range
  gradients, six original range headings/endpoints, separate index cards, unchanged
  table structures/colors, computed 13 px Matching Rate font, no page overflow,
  reduced-motion opt-out and no JavaScript page errors.
- Full isolated suite: **341 passed, 34 skipped, 1 dependency deprecation warning**,
  including disposable loopback PostgreSQL tests. Skipped tests require private
  historical fixtures. Added checks cover units, gradients, label rename, parallel
  loading, cache limits, failed/concurrent reads, late-response refresh isolation
  and matching output/session-count parity.
- The minimal archive is overlay-tested against a clean v1.3.22 manifest baseline.
  Unrelated application files remain byte-identical. No live credentials, trading
  database, private workbook, generated data or screenshots are included.

Older release sections below are retained as historical reference.

## Previous update: v1.3.22 — compact cards and consistent display rules

This **partial source update for v1.3.21** makes the requested visual corrections
without changing trading data, imports, financial definitions or exports.

### Install v1.3.22

1. Keep the existing source commit for rollback. Extract this ZIP.
2. Merge/overwrite the included `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` into the **existing repository root**. These are partial
   folders: **do not delete the existing folders**, and do not upload the ZIP as
   source or nest everything inside another parent folder.
3. Commit the merged files to GitHub. Wait for the normal checks and Vercel build.
4. Hard-refresh the dashboard (Ctrl+Shift+R). Confirm version **1.3.22** in the
   sidebar or `/api/health`. No new dependency, environment setting, database
   migration, index creation, cleanup, re-import or Aiven configuration is needed.

### Requested corrections

- The six existing Symbol vs Index range headings stay in place. **High and its
  price are directly above the green/left bar end; Low and its price are directly
  above the red/right end.** Old vertical High/Low rows are gone; these bars have
  no current-price marker. The Price Limit Checker keeps its existing lock state,
  calculation, price marker and moving rate label.
- Matching Rate uses the dashboard's sans-serif UI font at a readable **13 px**,
  with tabular numerals and the existing internal table scroll.
- Small Cards now uses compact **280 px symbol cards in one horizontal rail**.
  Cards never wrap into another row, including sectors with nine or more symbols.
  Keyboard focus, native horizontal scroll and gentle scroll snapping are available.
  A sector member with no prices still has an honest placeholder card.
- The shared benchmark is no longer repeated inside every symbol card. Two
  separate index cards show current index figures and the selected-session window,
  in their own horizontal rail. Their dates, coverage and pre-window baseline
  remain explicit. Symbol and index financial definitions are unchanged.
- Shared divider lines are yellow **#D4A72C** in both themes: card-header rules,
  table-row rules, tabs, range partitions, coverage, index headings and workspace
  boundaries. Card/control outer outlines and blue status/accent indicators keep
  their existing styling; chart grids are not recolored.
- Shared semantic display rules make **High green #03D815 / Low red #F63131**,
  independent of whether the instrument gained or lost. This applies to tables,
  range extrema, KPIs and new cards, including highlighted rows and nested spans.
  Close/change figures retain their existing gain/loss direction colors.
- Full displayed dates use **6 Sept 2019**. Date-only values do not shift timezone;
  timestamps retain the existing Karachi time conversion. Native date input values,
  dropdown values, sort keys, API/database dates, raw code blocks and spreadsheet
  formats are preserved. Display-only date conversion does not rewrite stored data.

### Faster Small Cards and reusable panel-loading defaults

- Initial Small Cards rendering makes **one combined report request** for sector
  options, symbol cards and the shared index. The separate sector endpoint remains
  compatible for other clients.
- Sector aggregates now read only each symbol's **latest N stored rows before
  numbering**, using the existing symbol/date index. WTD/MTD baselines use indexed
  date seeks. Queries remain batched in groups of at most 50 members; there is no
  HTTP/database round-trip for each card. Shared index data is fetched once.
- Small Cards and Matching Rate use a bounded-lifetime **30-second panel cache**
  with concurrent-request deduplication. The cache is scoped to the existing client
  cache object, so refresh/import/cloud-revision changes invalidate it normally.
  Failed requests are not cached. New report identity prevents old cached Small
  Cards payloads being reused; the global 1.3.17 result-cache namespace stays intact.
- Compact cards and one shared index section also reduce repeated DOM construction.
  Existing unrelated report algorithms, import pipeline and data-source adapters
  remain byte-identical to v1.3.21.

### Verification and measured results

- Local SQLite benchmark: **9 synthetic symbols × 5,000 stored rows = 45,000 rows**.
  Median of seven uncached service calls per case, old versus new:

  | Selected sessions | v1.3.21 | v1.3.22 | Ratio |
  | --- | ---: | ---: | ---: |
  | 7 | 94.57 ms | 8.15 ms | 11.60× |
  | 14 | 95.08 ms | 8.23 ms | 11.55× |
  | 100 | 95.58 ms | 9.63 ms | 9.93× |
  | 6,000 requested / 5,000 available | 109.81 ms | 90.03 ms | 1.22× |

  All financial outputs matched the previous service exactly in all four cases;
  only the new sector-options field was excluded from parity comparison. These
  timings are **local synthetic query measurements, not live Aiven or full-page
  speed promises**. Large requested windows necessarily read more data.
- Local Chromium checks: both themes, nine-symbol one-row rail, separate index
  cards, shared semantic High/Low colors, yellow dividers, six endpoint labels,
  marker-free bars, universal Matching Rate font, date display with unchanged
  input/dropdown values and raw code, one initial Small Cards request and no repeat
  request on immediate rerender. Widths 1600/1200/768/390/320 px had no page-level
  horizontal overflow. No JavaScript page errors were observed.
- Full isolated regression suite: **333 passed, 34 skipped, 1 dependency warning**,
  including disposable loopback PostgreSQL query/API/cache tests. The 34 skipped
  tests require private historical fixtures; no live Aiven test was performed.
- Minimal ZIP overlay is checked against every full-release manifest hash and
  tested again from a clean v1.3.21 baseline. No credentials, trading database,
  private workbook, generated test data or browser screenshots are packaged.

The sections below describe older releases and are retained for reference.

## Previous update: v1.3.21 — range bars, Matching Rate and Small Cards

This partial update is based on **v1.3.20** and implements the confirmed choices:
search history older than one month, count stored trading sessions, use the
pre-window index close, and use your imported **SEL_COMP_LIST** membership.
The older release sections below are historical; use these current steps.

### Install v1.3.21

1. Keep the current source commit for rollback. Extract the ZIP.
2. Merge/overwrite its `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` files at your existing repository root. **Do not delete
   the full existing `psx_app/` or `tests/` folders**: this ZIP contains partial
   folders with changed files only. Preserve paths, including the new
   `psx_app/services/market_panels.py` and `psx_app/static/market1321.js` files.
3. GitHub → **Add file → Upload files**: upload the extracted contents and commit
   to `main`. Do not upload the ZIP itself as application source or nest the files
   inside another parent folder.
4. Wait for GitHub checks and Vercel. Confirm `/api/health` reports **1.3.21**, then
   hard-refresh (**Ctrl+Shift+R**). All browser scripts, including the new one, have
   matching versioned asset URLs. No dependency, environment variable, migration,
   new index, new database table or data re-import is needed.
5. Open **09 → Market Explorer**. The tabs are **Market volume → Symbol vs Index →
   Matching Rate → Small Cards**. Your existing Aiven data and imported reference
   lists stay in place. If SEL_COMP_LIST is absent, Small Cards explicitly asks
   for the existing reference import; it never substitutes COMP_LIST/bundled data.

### Six marker-free range bars

In Symbol vs Index, Day's / 30 / 60 / 90 / 180 Days / Year's Range retain their
headings, High/Low values, dates, record counts and calculation windows. A small
horizontal bar is added beneath those values, green at the High/left side and red
at the Low/right side, fading toward the center. **No current-price marker** is
added to these six bars. Missing bounds give a neutral unavailable bar.

These are visual range summaries, not additional lock checks or a new high/low
calculation. The existing Price Limit Checker, its status icon, descending scale,
tracking closing-rate label and thresholds remain unchanged. Existing Year means
YTD and 30–180 means calendar-day windows; those definitions are not altered.

### Keyboard navigation in dashboard dropdown filters

- Focus a single-choice dropdown and type a letter: **C** jumps to its first
  C-item; repeated C cycles through available C-items and wraps to the first.
- Type multiple letters within one second to select a longer prefix, including
  words separated by spaces. Matching is case-insensitive and accent-normalized;
  disabled/hidden options are skipped. A nonmatching longer prefix can restart
  from its latest letter. This jumps the selection; it does not hide other options.
- **Press Enter or move focus away to apply the choice. Escape cancels a staged
  keyboard selection.** Staging prevents a network refresh on every letter and
  lets you cycle smoothly without losing focus. A tooltip on the dropdown explains
  these controls. Pointer/arrow selection keeps the native select behavior.
- Applies to ordinary single-choice native dropdowns across modules, including
  dynamically rendered filters. It does not intercept text/date/number inputs,
  multi-selects, composition input or Ctrl/Alt/Meta shortcuts. No new filter
  controls, extra tab stops, external widget, font or package is introduced.

### Matching Rate: exact definitions

1. Choose a symbol. Its latest imported close and date anchor the comparison.
2. Exclude the most recent **one calendar month**: eligible dates are strictly
   before `latest symbol date minus one calendar month`. Month subtraction clamps
   to a valid day in the shorter month (e.g. March 31 → February 28/29). This is
   neither a 30-trading-session cutoff nor a search confined to one previous month.
3. Search **all older available symbol records**, rank by the absolute difference
   from the latest close, and return the closest ten. Equal distances use newest
   historical date first. Fewer than ten eligible records means fewer rows, not
   duplicates or fabricated matches. Source prices are not split-adjusted here.
4. The nine table columns are **Latest close, Latest index close, Nearby close,
   Match date, Close difference, Sessions ago, Index date, Index close on match,
   Index difference**. Differences are signed `latest minus historical` values;
   matching/ranking itself uses absolute symbol-price distance.
5. **Sessions ago** counts stored records for this symbol after the matched date
   through its latest date. It is not calendar-day distance, futures/account rows,
   or a reconstructed exchange calendar. Missing imported sessions cannot be
   guessed, so the count describes the available history only.
6. Latest index = newest stored index on or before the latest symbol date, shown
   with its own date. A match's index uses the **exact match date only**, never a
   nearby-date substitute. Missing same-day index is clearly unavailable; a future
   index is not used. Index difference = latest index close minus exact-date index
   close. The table retains the dashboard's internal scrolling/sticky-header style.

This is a historical-price lookup, not a prediction, valuation or trade signal.

### Small Cards: membership, sessions and all seven sections

- Sector options come exclusively from the imported SEL_COMP_LIST sheet. Exactly
  one card is created per listed symbol in that sector, sorted by ticker—no padding
  cards, unlisted companies or bundled-list substitutes. A member without prices
  still gets one clearly labelled no-price card, rather than disappearing.
- Session count defaults to **14**, accepts integers **1–6000**, and is independent
  of the Symbol vs Index Records filter. Cards use a responsive equal-width grid:
  columns wrap with the viewport; a partially filled final row is not stretched
  into a misleading full-width comparison chart. Both themes use the existing
  borders, fonts, spacing and canonical **#03D815 / #F63131** gain/loss colors.
- Card heading: ticker and authentic imported company name, dated quote and stale
  coverage label when applicable. The ticker and first row's closing/change values
  are green for a positive daily change, red for negative and neutral if unchanged
  or unavailable. "Negative closing" means a daily decline, not a negative price.
- **1:** Latest close, daily change and daily percentage, using the existing
  imported `pr_close` convention. **2:** Latest High/Low. **3:** Source average and
  volume; an absent source average is unavailable, not recomputed. Zero volume
  remains a real zero. **4:** Week-to-date and month-to-date change plus percentage.
- **5:** Centered **Based on Selected Sessions (N)** heading, then maximum High
  and minimum Low over the symbol's last N stored records. Actual coverage count
  and first/last dates are shown; short histories are not zero-filled.
- **6:** Current index close, high, low, daily change and percentage. All values in
  this section use the current index change's sign color, independently of the
  symbol's color. The index record date is shown explicitly.
- **7:** Selected-session index maximum High, minimum Low, change and percentage;
  this section's sign color follows the index's **selected-window** change, not
  its daily change. The window dates, available count and baseline date are shown.
- WTD/MTD baseline = last available symbol close before Monday/month start of the
  latest imported cash-market date. A missing/zero/nonpositive baseline, or no
  symbol record in the current period, makes that period unavailable. Partial
  imported coverage is never represented as a complete exchange calendar.
- The anchor is the latest imported cash-market date. Each symbol and the index
  independently use their own last N stored sessions through that date; their
  quote/window dates can differ and remain visible. Index selected-window change
  = latest index close minus the stored index close **immediately before** that
  N-session window; percentage uses that baseline. Without that preceding record
  the change is unavailable, not calculated from the first included session.

### Performance, storage and verification

- New read endpoints: `/api/v139/market/matching/{symbol}`, `/market/selected-sectors`
  and `/market/small-cards?sector=...&sessions=...` under `/api/v139`. Session bounds
  are API-validated; all SQL values, including sector/symbol names, are bound.
- Matching ranks one symbol's history inside SQL and returns at most ten records;
  exact matching index dates are fetched in one bounded query. It does not transfer
  all historical rows to the browser or perform a query for every matching row.
- Sector calculations are batched in groups of at most 50 reference members. SQL
  returns compact aggregates per symbol; WTD/MTD baselines are fetched in batches
  of at most 100 exact symbol/date pairs. One shared index window of at most N+1
  records is read and reused across all cards. No per-card history/API request loop.
- These new functions reuse the existing bounded compressed shared-result cache,
  keyed by canonical data revision and Karachi day. Reference/price imports invalidate
  results through that revision. New function identities give new cache keys;
  the existing **1.3.17 cache namespace** deliberately stays unchanged, preserving
  valid older reports rather than forcing all modules to rebuild.
- Source tables, financial calculations in existing modules, database adapters,
  imports, existing exports, Price Limit Checker and base UI helpers are unchanged.
  No new source-data write, cleanup, schema migration or reference import was run.
  Normal expendable result-cache writes may occur when reading these new reports;
  they never advance the canonical revision and retain the existing 200-entry cap.
- **326 passed, 34 skipped, one dependency deprecation warning** on isolated SQLite
  and disposable loopback PostgreSQL. Tests cover month-end/leap cutoffs, signed
  differences/ties, trading-session gaps, exact/missing/future index data, real
  zeros, missing membership, 105-member batching, partial/stale coverage, daily
  versus N-session index baselines, API validation and cache invalidation.
- Local synthetic Chromium checks passed in both themes: unchanged six headings
  with marker-free bars; four ordered tabs; 9-column matching table; 4-refinery /
  9-cement card counts and equal widths; requested session changes; missing-price
  membership; 1200/768/390/320px layouts without page-width overflow; horizontal
  table scrolling; no JavaScript page errors. Keyboard checks cover repeated-letter
  cycling, longer prefixes/spaces, disabled options, Escape, Enter/blur single
  commit and unaffected text inputs, including a dropdown outside the new tabs.
- The delivered ZIP is overlaid onto a verified v1.3.20 source tree, checked against
  its complete release manifest and regression suite. These are local/synthetic
  checks, not live Aiven/deployment verification or an overall speed guarantee.
- No production Aiven access or automatic GitHub push/deployment. No trading
  database, credentials, logs or generated caches in the ZIP. Revert your source
  commit and redeploy to roll back; no data migration is involved.

## Previous update: v1.3.20 — close colors, original lock and moving rate

This partial-file update is based on **v1.3.19**. It changes only the requested
Market Explorer close/checker presentation plus the explicitly requested basic
animations; other components' content, design and calculations are not changed.
Previous version sections below are historical; use these current instructions.

### Install v1.3.20

1. Keep your existing source commit for rollback. Extract the ZIP.
2. Merge/overwrite the extracted `psx_app/`, `tests/`, `README.md` and
   `RELEASE_MANIFEST.json` paths at the existing repository root. **Do not delete
   the complete existing `psx_app/` or `tests/` directories**: these are partial
   folders containing changed files only.
3. GitHub → **Add file → Upload files**: upload the extracted contents preserving
   paths, then commit to `main`. Do not upload the ZIP as application source or
   put the files inside another parent folder.
4. Wait for GitHub checks and Vercel. Confirm `/api/health` reports **1.3.20**,
   then hard-refresh (**Ctrl+Shift+R**). No migration, re-import, environment
   variable, dependency or paid service is needed.

### Exact visible changes

- **Latest Close** and **Latest Index Close**: the main closing values now use
  the same daily-change sign colors as their existing DoD figures. Positive is
  canonical green **#03D815**, negative red **#F63131**, zero/missing neutral.
  DoD amounts/percentages, headings and dates remain in place.
- **Price Limit Checker**: restores the original large closed/open status-lock
  SVG and status text above the bar. Reached upper = green closed lock; reached
  lower = red closed lock; within range/unavailable = neutral open lock. Small
  endpoint lock icons, the upper-left/lower-right orientation and gradient remain.
- Removes the **Previous close** footer, and removes the duplicate closing-rate
  block above the bar. **Closing rate** with the actual PKR value is now beneath
  the indicator bar, positioned from the same percentage as the marker. It follows
  the marker and is green above the previous close, red below, neutral unchanged
  or without a valid baseline. The previous close remains an internal baseline;
  hiding its footer does not remove data or alter the threshold calculations.
- The rate label is centered under the marker where space permits, clamped inside
  the track's available width near either endpoint so text cannot be cut off.
  Out-of-range closes retain the real displayed value while marker/label stop at
  the corresponding endpoint. Missing baselines retain an unavailable check, no
  marker and a centered neutral label; no prior value is invented.
- The record date remains visible; an old imported close is never relabelled as
  today's live market rate. Removed calculation-details panel, disclaimer sentence
  and row badges remain removed. Existing high/low row highlights are unchanged.

### Authorized basic animation

- One 180ms view-entry fade with a 4px rise, returning to `transform:none` so no
  persistent transformed containing block is left behind.
- Short 140ms background/border/text transitions on existing buttons and tabs;
  180ms left-position transitions on the price marker/rate when updated in place.
- No flashing, looping, per-row animation, new runtime library, timer or request.
  Full content re-renders use the view entry, not a claim that every refresh
  interpolates marker positions across replaced DOM nodes.
- Operating-system **prefers-reduced-motion** disables these effects. There is
  no animation of table dimensions, financial values or surrounding layout.

### Rules, data safety and verification

- Existing requested calculations remain unchanged: upper is
  `max(previous × 1.10, previous + 1)`; lower is
  `min(previous × 0.90, previous − 1)`, PKR. Exact boundaries count. These are
  close-based requested thresholds, not an official exchange-halt feed or a
  tick-rounded instrument-specific rules engine. Sub-PKR-1 baselines can yield
  a negative lower threshold under this formula; the requested rule is not altered.
- No source-data edits, database cleanup, new query, API shape, import/export
  behavior, reference data, account calculation or schema change. API cache
  namespace remains **1.3.17** because payloads are unchanged; app/assets are
  **1.3.20**. The prior row-highlight palettes, filters, six ranges, nine/eight
  record columns, internal table scroll and sticky headers are preserved.
- **303 passed, 34 skipped, one dependency deprecation warning** on isolated
  SQLite and disposable loopback PostgreSQL. Skipped private-reference tests are
  not claimed as passed. New tests cover both close cards, positive/negative/zero
  states, original open/closed icons, tracking positions, endpoints/overshoots,
  missing baselines and reduced-motion CSS.
- Local synthetic Chromium checks passed: light/dark sign colors, equal-sized
  desktop cards, moving labels contained at endpoints and intermediate positions,
  restored status icons, unchanged tied row highlights/9-and-8 columns/six ranges,
  sticky internal-scroll headers, widths 1200/1050/768/390/320 without page-width
  overflow, reduced-motion disabling effects, and no JavaScript page errors.
- The delivered partial ZIP is overlaid onto the verified v1.3.19 source, checked
  against the complete release manifest and regression suite. This is local
  verification, not live Aiven/deployment testing or a promise of faster queries.
- No production Aiven access or automatic GitHub push/deployment. No trading
  database, credentials, logs or generated cache is included. Revert your source
  commit and redeploy to roll back; no database migration is involved.

## Previous update: v1.3.19 — horizontal price range

This partial update is based on **v1.3.18**. It changes the existing third card in
**09 → Symbol vs Index**, not the database, import path or other modules.
Earlier version sections below document previous releases; follow these steps now.

### Install this update

1. Keep the current source commit for rollback. Extract the ZIP.
2. Merge its `psx_app/`, `tests/`, `README.md` and `RELEASE_MANIFEST.json` files
   into the existing repository root, preserving paths. **Do not delete the whole
   existing `psx_app/` or `tests/` folder**: the ZIP contains changed files only.
3. On GitHub use **Add file → Upload files**, upload those extracted paths and
   commit to `main`. Do not upload the ZIP as source or nest another parent folder.
4. Wait for GitHub checks and Vercel. Verify `/api/health` shows **1.3.19**,
   then hard-refresh (**Ctrl+Shift+R**). No new environment variable, migration,
   data import, dependency or paid service is needed.

### Price Limit Checker display

- Three equally sized desktop cards remain; narrower layouts stack them.
  The third shows a dated **Closing rate**, threshold status and horizontal bar.
- **Upper Lock is at the left; Lower Lock is at the right.** This is a descending
  price scale, intentionally opposite a normal low-to-high number line.
- Endpoint labels show both lock prices. Green uses **#03D815** and red
  **#F63131**, the dashboard's existing universal gain/loss tokens in both themes.
  Gradient and row-fill tints are derived from these tokens, not new hues.
- A distinct theme-contrasting tick/dot marks the actual close. Its position is
  `100 × (upper − close) / (upper − lower)` percent from the left. It is clamped
  to the nearest end for an out-of-range close, while the displayed closing rate
  retains its actual value and status reports the threshold as reached.
- Green-side proximity is `clamp((close − previous)/(upper − previous),0,1)`;
  red-side proximity is `clamp((previous − close)/(previous − lower),0,1)`.
  Endpoint intensity varies from 18% to 100% of its base color as proximity rises;
  each side fades toward a soft center. Previous close corresponds to the center.
- The source record date is shown explicitly. Old imported data is never relabelled
  as today's live market rate. Missing/invalid baselines produce an unavailable
  neutral track with no fabricated price marker. The graphic is read-only, with
  an accessible description, not an interactive slider.

### Preserved rules and requested removals

- The existing requested upper/lower calculations are unchanged:
  `upper = max(previous × 1.10, previous + 1)` and
  `lower = min(previous × 0.90, previous − 1)` in PKR. Exact boundaries count.
  This remains a calculation from imported close/previous close, not an official
  exchange halt feed or instrument-specific rule engine; no tick rounding or
  exchange validation is added. A sub-PKR-1 previous price can yield a negative
  lower threshold under this requested formula, which is not silently altered.
- The long close-based explanatory sentence is removed from the visible card.
- The entire **Range and volume calculation details** panel is removed from
  the view, not merely collapsed. Its underlying range/volume calculations remain.
- **Max high / Min low** badges beneath table dates and the repeated helper lines
  are removed. All tied maximum-High/minimum-Low row and exact-cell highlights
  remain in both tables; a row can still qualify for both. Highlight backgrounds
  now derive from the canonical gain/loss colors, with readable theme-colored
  table text. The shared blue accent distinguishes a dual-extrema row.
- Filters, record counts, company name, six range partitions, 9/8 table columns,
  financial calculations, exports, internal scrolling and sticky headers remain.
  Other dashboard component layouts are unchanged. Existing global positive and
  negative tokens already match the specified colors; this update removes the
  checker/highlight palette exceptions rather than recoloring unrelated controls.

### Verification and safety

- **288 passed, 34 skipped, one dependency deprecation warning** with isolated
  SQLite and disposable loopback PostgreSQL. Skipped private-data tests are not
  claimed as passed. Tests cover marker direction/positions, boundaries,
  proximity/intensity inputs, overshoots, low prices and missing baselines.
- Local synthetic Chromium tests passed in light/dark modes: equal-size desktop
  cards, exact base icon colors, changing gradient intensities, all tied highlights,
  no badges/details/disclaimer, unchanged 9/8 columns, no JavaScript page errors,
  and no page-width overflow at 1200/1050/768/390/320px. Sticky headers remain fixed
  after internal table scrolling. The complete delivered file overlay is checked
  against its manifest and regression suite before handoff.
- No new database request, write, schema change, source-data edit or cache rebuild
  is introduced. Existing API cache namespace stays **1.3.17** because its payload
  is unchanged; app/assets are versioned **1.3.19** to refresh browser files.
  No overall performance increase is claimed; the graphic is a small client-only
  calculation using existing response fields.
- No live Aiven access or automatic GitHub push/deployment was performed. No
  database, secrets, logs or generated cache files are in the ZIP. To roll back,
  revert your source commit and redeploy; no database migration is involved.

## Previous update: v1.3.18 — price-limit card and table highlights

This partial-file ZIP updates published **v1.3.17**, GitHub base commit
`31a647d45499996827d5dbecd65d8c6778e652f5`. The v1.3.17 section later in this
README is historical; use these installation steps for the current ZIP.

### Install v1.3.18 yourself

1. Keep your current source commit for rollback. Extract the ZIP.
2. **Merge/overwrite the extracted files at your existing repository root. Do
   not delete the whole existing `psx_app/` or `tests/` folder:** the ZIP contains
   partial folders, not a replacement for the repository.
3. Use GitHub **Add file → Upload files**. Upload the extracted `psx_app/`,
   `tests/`, `README.md` and `RELEASE_MANIFEST.json` together, preserving paths
   such as `psx_app/main.py`. Do not upload the ZIP as application source or nest
   its contents inside another parent folder. Commit to `main` when ready.
4. Wait for GitHub checks and Vercel deployment. Confirm `/api/health` reports
   **1.3.18**, hard-refresh (**Ctrl+Shift+R**), then open **09 → Symbol vs Index**.
5. No new environment variable, dependency, migration or data re-import is needed.
   Existing reference names, six ranges, weekly reports and exports remain.

### Third card: requested close-based price check

Three equally sized desktop cards show Latest Close, Latest Index Close and
**Price-limit check**. Narrow screens stack them.

- Uses latest imported **symbol close** and that row's imported `pr_close`,
  not its high/low or the index price.
- Upper price = `max(previous close × 1.10, previous close + PKR 1)`.
- Lower price = `min(previous close × 0.90, previous close − PKR 1)`.
- **Green closed lock** at or above the upper price; **red closed lock** at or
  below the lower price. Exact boundary prices count as reached. An unlocked
  neutral state appears within those prices. Missing/invalid close or a
  nonpositive previous close gives an unavailable check, not an invented value.
- Previous PKR 100 → upper PKR 110 / lower PKR 90. Previous PKR 5 → upper PKR 6 /
  lower PKR 4. The card displays the previous close, both prices and source date.
- This implements your requested arithmetic, **not exchange-confirmed circuit
  breaker or halt status**. No live exchange feed, instrument exemption or
  tick-size rounding is added. For a previous close below PKR 1 the requested
  lower-price formula can be negative: it is shown as calculated, not silently
  clamped or advertised as an official trading limit.

### Maximum High / minimum Low highlighting in both tables

- Each table independently highlights **every row tied for maximum High** and
  **every row tied for minimum Low** within its displayed Records selection.
  These are not the six range cards' independent calendar windows.
- High rows have muted green fill; low rows muted rose. Rows meeting both use
  violet fill, with their exact High/Low cells emphasized separately. Visible
  **Max high / Min low** badges avoid relying on color alone.
- Null/nonfinite values are excluded. Actual numeric zero stays as imported.
  A single row can qualify for both. Empty tables retain the no-data state.
- Separate light/dark palettes remain visible under alternating-row/hover styles.
  Symbol/index keep nine/eight columns, internal scrolling and sticky headers.
  Export values are unchanged; this is browser styling, not spreadsheet formatting.

### Safety, performance and verification

- No source-data writes, financial calculation changes, extra database queries,
  schema changes, cleanup, credentials or trading database in this patch. Live
  Aiven was not accessed; nothing was pushed or deployed automatically.
- Thresholds use existing API fields; highlighting is linear in displayed rows,
  with no per-row request. App/static versions move to **1.3.18**; API cache
  namespace deliberately stays **1.3.17** because its payload is unchanged,
  avoiding unnecessary report-cache rebuilds. No overall speed increase is claimed.
- **273 passed, 34 skipped, one dependency deprecation warning** using isolated
  SQLite and disposable loopback PostgreSQL. Skips are not claimed as passes.
  Tests cover exact boundaries, low prices, missing baselines, all ties,
  simultaneous extrema and unaffected ordinary tables.
- Local synthetic Chromium checks passed: three equal desktop cards; green/red
  states; independent tied extrema in both tables; 9/8 columns; minimum tested
  highlighted-row text contrast **5.61:1 light / 7.29:1 dark**; hover persistence;
  sticky header after internal scrolling; stacked 390px mobile layout without
  page-width overflow; no JavaScript page errors. Not live deployment verification.
- The ZIP is overlaid on a clean published v1.3.17 tree and checked against the
  complete release manifest and regression suite. To roll back, revert your
  source commit and redeploy; no data migration is involved. Keep authentic
  workbook and database backups independently.

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
   version `1.3.24`. An empty database is expected before you import your data.

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

Current regression suite: **372 passed, 34 skipped, 1 deprecation warning**.
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


## v1.3.16 — weekly accounts, readable tables and bounded import work

### Account performance (04 and 05)

- Both accounts have a **Weekly Summary** tab and a **Weekly Summary** sheet in their account Excel export. Account headings no longer include the terminal suffix; source terminal identifiers remain in the raw trade/audit data.
- Weeks follow ISO **Monday–Sunday**, including weeks that cross a month or calendar-year boundary. The table shows the ISO week, calendar range, actual first/last imported dates and number of stored trading days. Partial weeks are not padded with invented trades or zero-filled days.
- Weekly quantities, values, commissions and SST are summed from the same account-isolated symbol/day rows as the existing monthly/yearly summaries. Average prices are quantity-weighted; Return on Buy is Net P&L divided by Buy Value, never an average of daily percentages. No financial calculation policy changed.
- All-history weekly totals reconcile with the all-history monthly/yearly totals. Existing MTD/QTD/YTD periods still use that account's latest stored trading date. The weekly tab defaults to the latest week first; Excel exports retain chronological order.

### Tables, readability and Technical Analysis (06 and 07)

- Tables have bounded internal vertical/horizontal scrolling, keyboard-focusable containers and sticky headings. Normal page scrolling remains available between cards and on mobile; it is not disabled, because that would make content inaccessible. Printing removes the table height cap, and downloads retain all rows.
- Futures table cells are 13.5px and headings 12.5px, scoped to module 06. Table heading colors follow the light/dark theme.
- Primary technical navigation is now **Trading Ideas Generator**, **Automated Technical Analyst**, **Saved predictions & results**, **Stock screener**, and **Charts & past rule tests**.
- The **Stock screener** contains a universe selector for **Core 36 watchlist / All stocks**, replacing two overlapping tabs without removing either scope.
- “Which stocks have data?” was a data-coverage diagnostic, not a trading signal. It remains accessible from the scan's **Check where this stock has data** action as **Data diagnostics**; it no longer occupies a primary tab. It helps explain missing/stale/short price history. Saved forecast outcomes, historical rule tests and trading safeguards remain available.
- Optional learning research is fetched only when its disclosure is opened, not on every initial analyst render. It remains separate from production trading rules; failures can be retried by closing and reopening it.

### Performance changes and measured limits

- Index imports prefetch only incoming dates and batch inserts instead of one existence query and one insert per new row. The existing first-record/existing-date policy, transaction, source references, duplicate handling and repeat-commit protection are retained.
- Indicator invalidation uses bounded sets of at most 500 affected symbols per DELETE instead of one remote DELETE per symbol. Unchanged symbols retain their caches; a corrected symbol still invalidates its entire history.
- A synthetic **100-date INDEX** import on a disposable local PostgreSQL server used **200 → 4 index SELECT/INSERT statements**, with both versions inserting exactly 100 records. One observed loopback commit was **0.0342s → 0.0162s**. This is a controlled synthetic comparison, not a guarantee of production or upload speed.
- A separate synthetic 120-symbol cash import used **one** indicator invalidation statement and preserved the untouched symbol's cache. The analyst's initial production-analysis request group is **three → two APIs**; research loads separately only if requested.
- The result-cache namespace is bumped with the release, so old cached account responses cannot hide the new weekly fields. Cache contents are expendable derived data; canonical prices and trades are not rewritten by viewing reports.
- Large spreadsheet parsing, network speed, Vercel cold starts and the free Aiven plan's CPU/RAM/storage remain limiting factors. No unlimited-capacity or fixed-speed claim is made. No historical 2016 file is imported by this update; the owner controls those uploads.

### Verification of this release

- **231 passed, 34 skipped, one dependency deprecation warning** using synthetic SQLite tests and an explicitly configured disposable loopback PostgreSQL server. Skipped private-reference tests are not claimed as passed.
- New tests cover ISO-year boundary/partial weeks, account isolation, weighted totals, empty accounts, Excel values/frozen headings, consolidated navigation, bounded index inserts, duplicate/existing-date preservation, and selective multi-symbol cache invalidation.
- Local Chromium desktop/mobile checks verify sticky table headings while the table scrolls, horizontal scrolling without page-width overflow at 390px, both account tabs, screener scope changes, diagnostics access, Futures typography and unclipped print tables.
- Existing financial calculations, provenance/revision handling and import transaction safeguards remain covered by the regression suite. Source changes are deployed through GitHub main → Vercel as before; no new provider or paid service is introduced.


## v1.3.17 — Symbol vs Index identity, daily figures and price ranges

This is a file-only update over v1.3.16 (base GitHub commit `0232f36f504cd4fcc10ad47ba779ae0e61a708bd`). It requires **no new environment variable, database migration, data re-import, paid service, or dependency**. No production data has been edited or imported to prepare this patch.

### Install this ZIP yourself

1. Extract the ZIP. It contains only the changed `psx_app/` application files, matching `tests/` files, and the existing `README.md` / `RELEASE_MANIFEST.json`—no database, secrets, backups, generated caches, or extra documentation folders.
2. **Merge/overwrite these paths in your existing repository root. Do not delete or replace the entire existing `psx_app` or `tests` directory with the partial directories in this patch.** Keep all unchanged repository files.
3. On GitHub, use **Add file → Upload files** at the repository root and drag the extracted folders/files together so `psx_app/main.py` remains at that exact path. Do not upload the ZIP itself as application source and do not add an extra parent directory.
4. Commit to your chosen deployment branch (normally `main`). Let the existing GitHub checks and Vercel deployment finish. This patch has not been pushed automatically.
5. Verify `/api/health` reports version **1.3.17**, then use **Ctrl+Shift+R** and open **09 → Symbol vs Index**. Your current Aiven connection settings and stored data stay in place.
6. If a company name is absent, upload/preview/commit your authentic **Sector Wise** workbook through the existing reference import workflow. Its company-name columns remain `SYMBOL`, `COMPANY NAME`, `SECTOR`. Refresh the dashboard after committing the reference; do not invent a company name.

### What appears in Symbol vs Index

- A prominent full company-name card beside the Records/Symbol filters. Imported references are preferred: a Sector Wise-named list first, then the imported `COMP_LIST`, then other imported lists. With no imported match, the existing bundled Sector Wise company directory is used. No match displays **Full company name unavailable**. Names and sectors are HTML-escaped.
- Two separate cards for **Latest Close** and **Latest Index Close**, each showing DoD change and DoD percentage. Changes follow the existing imported prior-close (`pr_close`) convention. Missing/nonpositive prior close leaves the change unavailable. Each card shows its own stored date; an older index is not labelled as today's index. No future index date is substituted.
- Six partitions: **Day's Range**, **30 Days Range**, **60 Days Range**, **90 Days Range**, **180 Days Range**, **Year's Range**. Highs are maxima of imported highs; lows are minima of imported lows. Day means the latest stored symbol date, 30–180 mean calendar-day windows including that date, and Year means January 1 through that date (YTD), not trailing 365 days. There is no fabricated weekend/holiday data. Available session counts and window dates are shown. These ranges are calculated independently of the Records filter.
- The symbol table has **nine columns** and the index table **eight**, adding **Volume (% Change)** to each. Existing comparisons, date bounds, extrema, exports and internal table scrolling remain available.

### Volume percentage definition and limitations

`(current volume / previous stored volume - 1) × 100`.

- Symbol volume compares with the preceding stored record for that symbol, including a baseline outside the displayed Records limit.
- Index volume remains the sum of imported cash-symbol volume on the index date; futures/account trade logs are excluded. Its baseline is the previous stored index date, even if that date is absent from the displayed symbol rows. This is not a verified index-member or exchange-wide volume total; changing imported cash coverage can also change the aggregate.
- A missing or nonpositive prior volume is **Not available**, never 0% or infinity. A real current volume of zero following a positive volume is correctly **−100%**. No missing prices or volumes are zero-filled.
- The symbol/index record tables retain exact-date matching. The separate latest-index card can show an older, explicitly dated index record when a same-date benchmark is unavailable.

### Performance, safety and verification

- One extra bounded symbol row supplies the oldest displayed row's previous volume; there is no per-row volume lookup.
- Index-volume aggregation reads only the required dates in bounded groups of 200, avoiding scans over unrelated years when index coverage is stale. Range history is bounded to the larger of YTD and 180 days and does not grow with the displayed history beyond that bound.
- Shared result-cache keys and versioned assets move to v1.3.17 so old payloads cannot hide the new fields. Only expendable derived cache writes occur during report reads; source prices, volumes, accounts and financial calculations are not rewritten by this update.
- **244 tests passed, 34 skipped, one dependency deprecation warning** on isolated SQLite and explicitly configured disposable loopback PostgreSQL. Private-reference tests that were skipped are not claimed as passed. Tests cover source-name precedence, date boundaries, untruncated ranges, preceding volumes outside the display, missing/zero volume, stale/future index dates, cash-only aggregation and PostgreSQL shared-cache behavior.
- Local Chromium checks passed for light/dark desktop and 390px mobile layouts: prominent name beside filters, six desktop range partitions/two per mobile row, exactly 9/8 table columns, dated older-index card, range independence from Records, sticky table headers and no page-width overflow or JavaScript errors.
- The ZIP was overlaid onto a clean copy of the published v1.3.16 tree and checked against the complete release manifest. These are local/synthetic checks, not a claim that this unpushed patch has already been deployed or tested against live Aiven.
