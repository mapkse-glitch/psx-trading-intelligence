# Live read-only investigation — v1.3.11

The existing production v1.3.10 site was opened in the shared browser before implementing these fixes:
https://psx-trading-intelligence.vercel.app

Mutation requests were blocked in the audit tab before analysis navigation, because the existing analyst automatically records forecasts. No live mutation request was sent: no imports, settings edits, forecast saves or forecast evaluations were performed. GET endpoints can maintain their normal analytical caches; no canonical price/account records were edited. Source changes and mutation/browser tests used isolated local databases only.

## Observed causes
1. Market Explorer / Symbol vs Index rendered N/A index volumes. Source `market_explorer.py` explicitly set each index row’s volume to `None`. The legacy `index_ohlcv` schema has no volume column. The fix derives the requested per-date cash-market total rather than inventing an index volume field.
2. The live volume endpoint reported **398,942,840** shares for imported cash symbols on **2026-10-23**. This is an observed dataset total, not a hard-coded application value, verified index-member total or certified exchange-wide total.
3. ATRL’s observed latest price was **1,090.75** on **2026-10-23**. Its raw SELL warning had no valid new opening trade: the contract had no active stop/target. The fix distinguishes existing-holding sell warnings from new short entries, hides rejected execution-level lines and explains absent levels instead of manufacturing them.
4. The inspected saved forecasts were PENDING and waiting for later imported sessions. Reporting a win, loss, or 0% profit at that point would be false. The new view explains what data/result is still missing.
5. The As-of control was an imported-date dropdown. The replacement is a native calendar input, with explicit backward-only date resolution. Exact-date index price joins and earlier-session baselines are retained.

Counts, signals and prices above describe the audit snapshot only. The deployed application derives subsequent values from its database and existing rule engine. This investigation did not establish index identity, broker eligibility, fundamental evidence or trading profitability.
