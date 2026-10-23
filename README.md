# PSX Intelligence 1.3.6 — direct Turso database

**Read [START_HERE_TURSO.md](START_HERE_TURSO.md) before deploying.**

Source-only upgrade of the existing PSX dashboard: direct remote database reads/writes, transactional imports/account rollups, durable staged uploads, batched inserts, and revision-aware view refresh. No GitHub snapshot sync or local replica is used in Turso mode.

Production requires private Vercel variables `PSX_DATABASE_BACKEND=turso`, `TURSO_DATABASE_URL`, and `TURSO_AUTH_TOKEN`. Credentials and data are intentionally excluded. Serverless startup fails closed if remote configuration is missing; local SQLite remains available only for non-serverless development/tests.

This package does not deploy itself or import missing history. Your existing imported Turso database is retained. Keep original uploads and independent backups. The dashboard remains password-free as requested; a private database token does not restrict public website access.

Current instructions: [deployment and verification](START_HERE_TURSO.md), [release notes](docs/RELEASE_1_3_6.md), [test report](docs/QA_1_3_6.json). Earlier version documents describe historical behavior and are not the Turso deployment instructions.

## Local development

Use a Python virtual environment, install requirements.txt, then run `uvicorn main:app`. With no serverless flags and no backend setting, local SQLite is the development default. Never point tests at a production database. Optional HTTP libSQL integration tests require the explicitly configured disposable loopback test server described in tests/test_turso_remote.py.
