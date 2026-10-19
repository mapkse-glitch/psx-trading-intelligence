# System Architecture — Unified PSX Trading Intelligence Dashboard

## 1. Architectural Overview & 10-Layer Separation of Responsibilities

The application is engineered as a modular, local-first Python + FastAPI + SQLite + Interactive Web UI system organized into 10 distinct layers:

```text
psx_app/
├── main.py                         # FastAPI application entrypoint, static UI mount, CORS & localhost security
├── config.py                       # Environment & persistent data directory configuration
├── database/
│   ├── schema.py                   # Layer 7: Canonical SQLite DDL, indexes, WAL mode & migrations
│   └── repository.py               # Layer 7: Data access repositories (SQLite/PostgreSQL-ready abstraction)
├── parsers/
│   ├── detector.py                 # Layer 3: Content-based file type & schema auto-detector
│   ├── top5_parser.py              # Layer 3 & 4: Module A Price Summary TXT parser & normalizer
│   ├── tradelog_parser.py          # Layer 3 & 4: Module B TradeLog TXT/CSV/XLSX parser & normalizer
│   └── ohlcv_parser.py             # Layer 3 & 4: Module C/D Cash, Futures & Index OHLCV parser
├── services/
│   ├── import_orchestrator.py      # Layer 2: Staging, preview, atomic batch commit, rollback & idempotency
│   ├── top5_service.py             # Layer 5: Module A Top 5 Volume ranking, tie detection & register queries
│   ├── account_service.py          # Layer 5: Module B Multi-account slabs, SST, P&L & period rollups
│   ├── futures_service.py          # Layer 5: Module C Dynamic contract matching, same-date join & annualization
│   ├── technical_service.py        # Layer 6: Module D RSI, MACD, BB, EMA, VWAP proxy, ADX, Pivots & Signals
│   ├── reconciliation_service.py   # Layer 9: Automated data-quality & legacy-vs-new reconciliation engine
│   ├── migration_service.py        # Layer 9: Initial historical migration from Google Drive mirror
│   ├── export_service.py           # Layer 8: Legacy-compatible Excel (.xlsx) & CSV report generators
│   └── backup_service.py           # Layer 10: SQLite safe online backup, verification, restore & audit log
└── static/
    ├── index.html                  # Layer 1: Responsive Single-Page Application shell
    ├── styles.css                  # Layer 1: Institutional financial design system (dark/light, tabular-nums)
    └── app.js                      # Layer 1: 10-view navigation, interactive charts, filters & upload wizard
```

---

## 2. Persistent Storage Layout

By default, all persistent data is stored in a dedicated, configurable local data directory (`PSX_DATA_DIR`, defaulting to `/home/user/psx_data` in Linux workspace or `%LOCALAPPDATA%\PSXTradingDashboard` on Windows when configured):

```text
psx_data/
├── database/
│   └── app.db                      # Primary SQLite database (WAL mode, foreign keys enabled)
├── data/
│   ├── raw/                        # Immutable content-hashed archive of all uploaded & migrated files
│   ├── staging/                    # Temporary staging payloads prior to user confirmation
│   └── processed/                  # Cached normalized artifacts
├── exports/                        # Generated Excel (.xlsx) and CSV reports
├── backups/                        # Timestamped .zip / .db backups with SHA-256 manifests
├── logs/                           # Structured application & audit logs
└── config/                         # Exported settings snapshots
```

---

## 3. Database Abstraction & Future Private Server Readiness

- All SQL queries and transactions are encapsulated inside `psx_app/database/repository.py`.
- Monetary calculations use Python `Decimal` / IEEE-754 verified precision in domain services (`psx_app/services/`) rather than SQLite-specific extensions.
- Connection parameters (`PSX_DB_PATH`, `PSX_HOST`, `PSX_PORT`) are controlled via environment variables, enabling a straightforward migration to PostgreSQL (`psycopg` / `SQLAlchemy`) when deploying to a private online server later.
