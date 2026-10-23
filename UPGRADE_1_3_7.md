> Historical 1.3.7 guide. For the current release start with `UPGRADE_1_3_8.md`; the cleanup list below still applies.

# Upgrade to 1.3.7 — Section 07 reliability and historical rule audit

## Existing Turso installation

1. Keep an independent Turso SQLite export and your original source files. Pause imports during deployment. Do not switch back to writing through the old GitHub-snapshot application.
2. Extract the ZIP and upload its **contents** to the existing repository root, replacing matching source files. Include `.gitignore`, `.vercelignore`, and the non-secret `.env.example`.
3. Keep your existing private Vercel variables: `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, and `TURSO_AUTH_TOKEN`. No new database or token is required if the current read/write token works. Never upload a real `.env` or token to GitHub.
4. Commit and deploy through the existing Vercel project. Confirm **v1.3.7**, **Turso: connected**, and the correct imported trading dates. Refresh the browser once if the prior JavaScript is cached.
5. Open Section 07 → Ticker Deep-Dive. Check **History used**, latest symbol/market session, valid-indicator count and the opening-trade decision. Scroll to **Historical Rule Audit**, choose a period and realistic fee/slippage assumptions, then click **Run historical audit**. The audit is optional, read-only and long-only; it does not place trades.

Existing database records and financial account calculations are retained. Technical scores can change because invalid warm-up votes are now excluded and boundaries reconcile with the explanations. Old technical caches are recognized by engine version and rebuilt; this does not re-import history or delete financial data. Corporate actions are not automatically adjusted. Missing years still require original source imports.

## First Turso installation

Read `START_HERE_TURSO.md` for full credential, deployment, verification and backup instructions. This ZIP does not deploy or connect itself without valid server-side variables.

## Clean old files already tracked in GitHub

The new ZIP omits bytecode, database snapshots, duplicate archived documentation, and obsolete QA reports. Uploading new files does NOT remove old tracked files. Delete these paths from GitHub if present:

```text
psx_app/__pycache__/
psx_app/database/__pycache__/
psx_app/parsers/__pycache__/
psx_app/services/__pycache__/
docs/historical/
docs/QA_1_3_3.json
docs/QA_1_3_4.json
docs/QA_1_3_5.json
```

If using a local repository checkout, `python scripts/cleanup_repository.py` previews safe non-data removals; `python scripts/cleanup_repository.py --apply` applies them. Commit the deletions yourself. This script never removes financial data or credentials.

`latest_cloud_sync.db.gz` is no longer needed by direct Turso mode. Remove its GitHub copy only after confirming Turso reads/writes and preserving an independent backup. The cleanup script deliberately leaves it alone. Deleting a file does not erase its Git history. Do not delete your only backup.

Keep `tests/`, `pytest.ini`, the active source, current guides, and deployment files. Other historical release notes remain as useful records. Docker/Render/local launchers are retained for portability; they do not run on Vercel.

## Understand the new decisions

- Raw indicator signals are shown separately from an **opening-trade decision**. A bearish raw signal is not automatic permission to open a short; a SELL may mean reducing an existing holding.
- The same structural entry/stop/target plan is used by the deep-dive, analyst and ideas generator. Gross target-1 reward/risk must reach 1.5; targets are not extended merely to manufacture a good ratio. Actual fills, costs, liquidity and contract permissions still need checking.
- Trading ideas exclude stale symbol dates and nonpositive latest volume. Fewer than five, including zero, is a legitimate result.
- Completed-week context can differ from today's daily trend. An unfinished current week is excluded conservatively; no exchange holiday calendar is assumed.
- Rule strength is not a profit probability. Daily TP/20-session VWAP proxies remain labelled, not represented as true intraday VWAP.

## Audit limitations — read before relying on results

The audit replays fixed, causal long-only BUY rules, enters at the next eligible session's open with adverse slippage, and applies per-side fee assumptions. Stop/target levels are fixed from the signal day; invalid opening gaps are rejected. Stop is assumed first if both levels occur in one daily candle; gap stops use the opening price. No leverage or overlapping positions in one symbol. Unresolved end-of-sample positions are excluded and reported.

It supports up to 6,000 daily sessions per symbol, with earlier history used for warm-up even when evaluation starts later. Costs default to an illustrative 10 bps fees and 10 bps slippage on each side, NOT a verified broker/tax schedule. Drawdown is trade-close only, not mark-to-market. Price locks, depth, actual fills, and corporate-action adjustments are not verified. Small samples are explicitly flagged. The JSON download records rules, assumptions, trades and limitations.

This is an initial historical rule audit, **not** walk-forward parameter training, independent model validation, calibrated prediction, or a promise of improved returns. Market-regime models, learned indicator weights and broker-verified short eligibility are not implemented by this release.

## Security and test scope

Turso remains direct remote read/write; no local-replica or GitHub snapshot sync is used in production. The dashboard remains password-free as previously requested. Anyone able to access the website may read or change data; protect hosting access for private use. No credentials or data are included in the ZIP.

Tests and browser checks use disposable local databases, including a copy of your older snapshot. They do not access or change live Turso and are not a live Vercel deployment test. See `docs/QA_1_3_7.json`.
