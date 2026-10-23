# Section 07 methodology — engine 1.3.7

## Data and evidence

All stored cash OHLCV rows for a symbol are queried chronologically, with no year restriction, for daily indicators. The chart tail is trimmed after calculation. Recursive EMA/MACD and Wilder smoothing retain history with decaying weight; rolling windows retain their defined session lengths. Old years are not averaged equally or used as trained forecast labels. The analyst now builds weekly context from full available history, excluding an unfinished latest week. Four-/ten-week averages require their full lookbacks. Exchange-holiday and missing-session completeness is not verified.

Coverage exposes first/last dates, sessions, years, and simple quality flags (zero volume, absent reported high/low and close changes above 30%). Flags do not prove bad data or a corporate action. No rows are silently dropped or adjusted. Current freshness means matching the newest imported cash session, not a live exchange clock. A symbol with an older date is labelled stale and excluded from new ideas.

## Indicator score

Existing nine factors and configurable BUY/SELL thresholds remain; learned weights and regime-dependent scoring are not added. In strict mode EMA9/21/50/200 votes require their actual session counts. Unavailable factors contribute zero. EMA200 warm-up values are not strict votes. Existing permissive mode remains explicitly optional. Boundary comparisons and explanatory votes reconcile. Valid-indicator count is displayed alongside the fixed nine-factor maximum. HIGH/MODERATE/LOW is rule agreement, not calibrated confidence. YTD RSI uses the latest imported bar's calendar year; full-history RSI is separate.

## Opening-trade plan

Raw signals and trade eligibility are separate. The shared plan uses the current close as an analytical entry reference, a directional stop from daily pivot/EMA21 structure, and the next structural pivot targets in the relevant direction. Targets are never stretched to force an attractive reward multiple. Gross target-1 R/R must be at least 1.5. No positive reported latest volume, stale data, insufficient data, invalid geometry, no opening signal, or inadequate R/R leads to NO TRADE. SELL is not a new short position.

Same-date futures records establish data presence only, not broker/contract eligibility or short-sale permission. Real fills, costs, margin and liquidity remain external checks. Candidates with a valid gross structural plan can still be unprofitable after costs. Rule strength /100 is a bounded deterministic ranking, with no arbitrary minimum score or win-probability claim.

## Historical audit

The new read-only API `/api/technical/validation/{symbol}` powers the opt-in Deep-Dive audit. It evaluates fixed long-only BUY rules after sufficient observations, using only causal values on the signal date. It warms up on earlier bars, filters end dates before calculation, enters at next-session open with adverse slippage, and rejects entries beyond the fixed stop/target or below required gross R/R. One hypothetical unleveraged fully allocated position per symbol at a time. STOP first for an ambiguous stop-and-target candle; stop gaps use the opening price; positive target gaps do not receive a windfall above the limit target. Horizon is counted in stored sessions; zero-volume exit bars cannot fill. Unresolved end positions are excluded and counted.

Fees and slippage are user-supplied basis points on each side. Net return is `(exit_after_slippage * (1-fee))/(entry_after_slippage * (1+fee)) - 1`. Reported compound return reinvests across closed hypothetical trades. Drawdown uses closed-trade equity only. Yearly rows group by entry year. Full JSON includes assumptions, settings and trade records. Results are descriptive, not a probability for today's setup. Small samples are flagged.

No parameter search, learned model, walk-forward optimization, probability calibration, survivorship-free historical universe, intraday sequence reconstruction, or real execution certification is claimed. These require separate research and testing. Raw corporate actions and inconsistent prices can distort all historical findings. Use realistic total cost assumptions and independently verify data before financial decisions.
