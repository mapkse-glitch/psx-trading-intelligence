# Current release: v1.3.10

Start with [UPGRADE_1_3_10.md](UPGRADE_1_3_10.md) for deployment, audit findings and verification. No database re-import is required for existing Turso deployments.

# Current release: PSX Intelligence 1.3.9

**Start with [UPGRADE_1_3_9.md](UPGRADE_1_3_9.md)** for deployment, new forecast/sector/Market Explorer features, optional external research learning, and material limitations. Keep the existing Vercel Turso credentials private. No database is bundled.

The learning baseline is research-only and does not silently replace production trading rules. INDEX identity/volume and fundamentals are not invented.

---

# PSX Intelligence 1.3.8 — aligned tables and newest-first dates

**Existing Turso users: read [UPGRADE_1_3_8.md](UPGRADE_1_3_8.md).**

**First Turso setup: read [START_HERE_TURSO.md](START_HERE_TURSO.md).**

This update aligns numeric headings with values, displays date-based tables/selectors latest first, fixes edited-date readouts and light-mode total-row contrast, and removes stale rolling-window labels. Sorting is display-only; charts, calculations, storage and workbook export layouts are preserved.

This source-only update preserves direct remote Turso reads/writes, durable uploads and transactional financial records. It improves technical-analysis transparency and trade-plan safeguards; no credentials or database files are included.

Section 07 calculates daily indicators from each symbol's full stored history before trimming its chart. It now shows coverage and imported-session freshness, excludes unavailable strict-mode indicator votes, distinguishes YTD from full-history RSI, labels completed-week context, and uses one consistent structural execution plan. Technical safeguards from 1.3.7 are retained; this UI release leaves the calculation engine at 1.3.7. The ideas generator may correctly return no trade rather than force five suggestions.

The optional Historical Rule Audit in Ticker Deep-Dive is a bounded, read-only, long-only chronological simulation with configurable fee/slippage assumptions and downloadable JSON. It is **not** a trained predictor, independent out-of-sample result, or a guarantee of profit. Corporate-action adjustment and real-world execution remain unverified.

Production requires private Vercel variables `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. Existing working values can be retained. Serverless local fallback remains disabled. The password-free website remains password-free; protect hosting access if financial data must be private.

Current guidance: [upgrade/cleanup](UPGRADE_1_3_8.md), [technical methodology](docs/SECTION07_RELIABILITY.md), [release notes](docs/RELEASE_1_3_8.md), [test report](docs/QA_1_3_8.json). Older documents describe earlier versions and are not current deployment instructions.

## Local development and tests

Use a Python virtual environment and install `requirements.txt`, then run `uvicorn main:app`. Local SQLite is available outside serverless environments. Tests are retained intentionally; never point them at a production database. Optional real HTTP libSQL tests require an explicitly supplied disposable loopback server as documented in `tests/test_turso_remote.py`.
