# PSX Intelligence v1.3.11 — plain actions, calendar dates and calculated market volume

## Install this release — keep the existing Turso database
1. Keep a private database export and your original source workbooks as backups.
2. Extract the ZIP. Upload its **contents into the GitHub repository root**, replacing matching files. Do not upload the ZIP itself or create another nested application directory.
3. Keep existing Vercel server-only variables: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. **No database reset, replacement, migration or historical re-import is required.** Never put the token in GitHub or the browser.
4. Wait for the GitHub-connected Vercel production deployment to finish, then reload with Ctrl+Shift+R. The sidebar and server version must show **1.3.11**. A different version means the new build is not yet being served.
5. Section 07 → **2. Automated Technical Analyst** now puts separate Buy / Sell existing holdings / Short / Take-profit / Stop-loss / Do-not-buy explanations first. Indicators are under an expandable details section.
6. Section 09 → Symbol vs Index → **Prices through** is a calendar input. Account daily-detail and relevant futures worksheet dates are also calendar inputs; Top5 and historical-audit ranges retain their existing calendars.
7. Verify the index table’s **Market volume (calculated)** against the same date in Market volume. The formula is `SUM(equity_ohlcv.volume)` across all imported cash-stock records for the date, without adding futures, Top5 blocks or account trades again.

This source update has not itself been deployed to your live site. Installing the files and completing Vercel deployment is still required.

## Why the old N/A values appeared
| Old display | Cause | New treatment |
|---|---|---|
| Index Volume: N/A | Legacy index schema has no volume field; the view explicitly assigned `None`. | Calculate the user-requested total from cash stock volumes for that exact date. No database schema change. |
| Forecast Net return: N/A | A later price record has not arrived, the simulated trade remains open, no entry was recommended/triggered, or daily data cannot establish the order of stop/target hits. | State the reason in words. Show a percentage only for a closed simulation with a calculated return. Zero is displayed only when it is a real calculated zero. |
| ATRL SL/Target: N/A | A SELL warning is not a new short-entry plan. No executable opening trade, stop or target was validated. | “WAIT — NO NEW TRADE”, plus explanations. Rejected plan references are not drawn as active stop/target lines. |
| Other missing numeric values | The underlying field/indicator is absent or has insufficient history. | Shared formatting says “Not available”, never invents zero. Primary action and forecast views give contextual reasons. |

## What is simpler
- The analyst’s plain-English explanations are calculated from the actual current closing price, day change, completed-week change, available averages, momentum, watch levels and the existing validated execution contract. No ATRL-specific prices or fixed outcome prose are hard-coded.
- A valid conditional plan gives the next opening-price range, loss limit and profit target. A failed plan explains why to wait. **SELL existing shares is separate from opening a new short.**
- Exact personal sell/profit levels for a holding cannot be determined without its purchase price, position details and risk instructions. The dashboard does not pretend to know them.
- “Cash sessions” → daily price records; “First cash date” → history starts; “Latest cash date” → last price date. One record is one stored daily row, not a calendar day or a claim of complete coverage.
- “Rule score” is explained as positive/negative/neutral indicator votes, **not a win percentage**. It does not override price/risk checks.
- The scan’s primary table is Stock / What to do now / Why. Every matched stock remains accounted for; history/vote details and downloads remain available.
- “Horizon” → **Check after**: next imported trading record or up to ten trading records. The direction check uses the next record; the trade simulation’s time window depends on its row. A no-trade result is not credited as a profitable trade.
- Quick-select popularity continues in the backend; counts are not shown in badges or hover titles.

## Calendar behavior
A selected non-trading date resolves to the newest available date **on or before** it, with an explicit notice. The UI never substitutes a future date. Selecting a date before the available history gives a warning instead of silently jumping to the latest day. Existing All-dates modes and Reset-to-latest controls remain. Month/contract codes remain dropdowns because an expiry code is not a trading date. Native calendar appearance follows the user’s browser/locale; adjacent readouts remain DD-MM-YYYY.

The analyst still analyses the latest imported stock session. No historical date picker has been added that would accidentally use later data while pretending to be an earlier forecast. Historical testing remains the explicit past-rule test.

## Colours and data meaning
- Positive numeric data: **#03D815**.
- Negative numeric data: **#F63131**.
- Applies in both themes. Zero/missing values and dates/identifiers remain neutral. Numeric cells are aligned with numeric headers. Categories in multicolour charts remain categorical, not positive/negative claims.
- The requested bright green has limited contrast on white. Exact requested colour is retained, alongside numeric signs and text labels; it is not a claim that every light-mode value meets accessibility contrast targets.

## Material limits — not silently “fixed” by making up data
- Calculated market volume is for **all imported cash-stock rows**, not independently verified index-member or exchange-wide coverage. The imported index’s identity still needs source confirmation. Its price series is not renamed to a verified KSE-100 series without evidence.
- No live quote feed, automated order placement, broker short permission, calibrated win probability, verified fundamentals/news or corporate-action verification is introduced. A no-trade day remains legitimate.
- Daily OHLC does not reveal intraday ordering, market depth, price-lock execution or actual fills. Pending/ambiguous simulations remain explicitly unresolved.
- The existing forecast ledger remains immutable. Existing predictions, indicator mathematics, learning research, imports, financial calculations and Turso persistence are retained; no historical prediction is rewritten into a successful one.
- The existing password-free deployment is unchanged. Same-origin protections are not user authentication. Protect hosting access if private financial records or write actions must not be public. Changing your chosen access/security architecture requires a separate decision.

## Files and cleanup
No database, token, uploaded workbook, private execution data, local test runtime or cache is bundled. Tests, the bundled company/sector reference and deployment configuration are intentional and should not be deleted. Older upgrade notes are historical documentation. An existing `latest_cloud_sync.db.gz` is not removed just by uploading this ZIP: if you have confirmed Turso-only deployment, privately back it up before separately deleting an obsolete repository snapshot. Deleting it does not erase Git history.

## Validation
See `docs/VALIDATION_1_3_11.md` and `docs/LIVE_AUDIT_1_3_11.md`. **165 passed, 20 private-fixture skips, 1 dependency deprecation warning**, including disposable loopback libSQL integration and local desktop/mobile browser checks. These are software checks, not evidence of profitable trading.
