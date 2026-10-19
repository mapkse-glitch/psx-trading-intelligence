# Verified Agent & Engineering Skills Toolkit

This directory contains the curated, security-audited, and license-verified engineering skills researched for the **Unified PSX Trading Intelligence Dashboard** project.

## Directory Structure

```text
skills/
├── README.md                 # Overview, usage guide, and offline guarantee
├── catalog.json              # Machine-readable catalog with URLs, SHA-256 hashes, and licenses
├── research_report.md        # Evaluation of skills.sh, mcpmarket.com, and GitHub repositories
└── verified/                 # Local offline copies of verified SKILL.md specifications
    ├── data-quality-validation/SKILL.md
    ├── deliver-edge-cases/SKILL.md
    ├── deliver-prd/SKILL.md
    ├── develop-adr/SKILL.md
    ├── execution-cost-analysis/SKILL.md
    ├── fastapi-backend/SKILL.md
    ├── frontend-design/SKILL.md
    ├── pytest/SKILL.md
    ├── pytest-api/SKILL.md
    ├── react-best-practices/SKILL.md
    ├── research-integrity-guards/SKILL.md
    ├── security-testing/SKILL.md
    ├── signal-construction/SKILL.md
    ├── web-design-guidelines/SKILL.md
    ├── webapp-testing/SKILL.md
    └── xlsx/SKILL.md
```

## Offline Operation Guarantee

- **Zero Runtime Dependency**: The PSX Trading Intelligence Dashboard does **not** connect to `skills.sh`, `mcpmarket.com`, or GitHub during normal daily operation.
- **Static Procedural Reference**: All 16 verified skills are stored locally as static Markdown (`SKILL.md`) artifacts under `skills/verified/`. No third-party executable scripts or untrusted hooks are invoked by the application.
- **Privacy Preservation**: No personal files, PSX TradeLogs, account identifiers (`91404`, `91269`), or workbook contents were transmitted to any external skill service during research or acquisition.

## Verified Skills Summary

| Skill ID | Category | Source Repository | License | Verification |
|---|---|---|---|---|
| `deliver-prd` | Requirements analysis & Brainstorming | `product-on-purpose/pm-skills` | Apache-2.0 | `verified_safe` |
| `develop-adr` | Architecture planning & Task decomposition | `product-on-purpose/pm-skills` | Apache-2.0 | `verified_safe` |
| `deliver-edge-cases` | Data validation & Edge-case analysis | `product-on-purpose/pm-skills` | Apache-2.0 | `verified_safe` |
| `fastapi-backend` | Python engineering & Database design | `mehmetmuejde/agent-skills` | MIT | `verified_safe` |
| `xlsx` | Excel import/export & Formula auditing | `anthropics/skills` | Apache-2.0 / Source-Available | `verified_safe` |
| `data-quality-validation` | Financial data validation & Reconciliation | `howard-lynn-ye/fin-skills` | MIT | `verified_safe` |
| `research-integrity-guards` | Quantitative integrity & Lookahead guards | `howard-lynn-ye/fin-skills` | MIT | `verified_safe` |
| `signal-construction` | Technical indicators & Signal modeling | `howard-lynn-ye/fin-skills` | MIT | `verified_safe` |
| `execution-cost-analysis` | Brokerage slabs, SST & P&L attribution | `howard-lynn-ye/fin-skills` | MIT | `verified_safe` |
| `frontend-design` | Dashboard UI/UX & Visual hierarchy | `anthropics/skills` | Apache-2.0 / Source-Available | `verified_safe` |
| `react-best-practices` | Frontend performance & Component design | `vercel-labs/agent-skills` | MIT | `verified_safe` |
| `web-design-guidelines` | Accessibility & Financial table layout | `vercel-labs/agent-skills` | MIT | `verified_safe` |
| `pytest` | Unit & parametrized testing | `aks-builds/quality-skills` | MIT | `verified_safe` |
| `pytest-api` | FastAPI & integration testing | `aks-builds/quality-skills` | MIT | `verified_safe` |
| `webapp-testing` | End-to-end web application verification | `anthropics/skills` | Apache-2.0 / Source-Available | `verified_safe` |
| `security-testing` | Upload security & Dependency auditing | `aks-builds/quality-skills` | MIT | `verified_safe` |

## How These Skills Were Applied

1. **Discovery & Reconciliation (`xlsx`, `data-quality-validation`, `deliver-prd`, `develop-adr`)**:
   - Used two-pass `openpyxl` loading (`data_only=True` and `data_only=False`) to inspect both cached values and underlying formulas across all 9 Excel workbooks in the Google Drive `Input folder` and `Output folder`.
   - Documented discrepancies between legacy specifications and actual workbooks in `docs/ASSUMPTIONS_AND_DECISIONS.md` and `docs/MIGRATION_REPORT.md`.
2. **Financial & Quantitative Engine (`execution-cost-analysis`, `research-integrity-guards`, `signal-construction`)**:
   - Enforced exact PSX commission slabs (`< 54 PKR` = `0.0175 paisa/share`, `>= 54 PKR` = `0.0325% of sell value`) per execution prior to aggregation, plus `13%` SST.
   - Enforced zero lookahead bias, explicit `N/A` on missing same-date futures/spot comparisons, and honest labeling of daily typical-price VWAP proxies versus intraday VWAP.
3. **Architecture, UI & Testing (`fastapi-backend`, `frontend-design`, `react-best-practices`, `web-design-guidelines`, `pytest`, `pytest-api`, `security-testing`)**:
   - Designed a 10-layer modular backend in FastAPI + SQLite with atomic batch staging, content-hash idempotency, and safe SQLite backup APIs.
   - Built a clean, high-contrast financial UI with `tabular-nums`, explicit PKR/percentage formatting, and comprehensive automated `pytest` suites.
