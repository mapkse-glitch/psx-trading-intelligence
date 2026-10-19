# Skills Research & Security Verification Report

**Date**: 2026-10-18  
**Project**: Unified PSX Trading Intelligence Dashboard  
**Scope**: Evaluation of `https://www.skills.sh/`, `https://mcpmarket.com/tools/skills`, and open-source GitHub repositories across 15 engineering and financial domains.

---

## 1. Sources Investigated

### 1.1 `https://www.skills.sh/` (The Open Agent Skills Directory)
- **Status**: Accessible and inspected directly via HTTP fetch.
- **Findings**: Maintained by Vercel Labs (`vercel-labs/skills`), indexing open-source `SKILL.md` specifications across `anthropics/skills`, `vercel-labs/agent-skills`, `mattpocock/skills`, and `product-on-purpose/pm-skills`.
- **Selected Artifacts**:
  - `anthropics/skills/xlsx` (`SKILL.md` — 8,598 bytes)
  - `anthropics/skills/frontend-design` (`SKILL.md` — 9,390 bytes)
  - `anthropics/skills/webapp-testing` (`SKILL.md` — 3,913 bytes)
  - `vercel-labs/agent-skills/react-best-practices` (`SKILL.md` — 7,251 bytes)
  - `vercel-labs/agent-skills/web-design-guidelines` (`SKILL.md` — 1,231 bytes)
  - `product-on-purpose/pm-skills/deliver-prd` (`SKILL.md` — 8,975 bytes)
  - `product-on-purpose/pm-skills/develop-adr` (`SKILL.md` — 4,797 bytes)
  - `product-on-purpose/pm-skills/deliver-edge-cases` (`SKILL.md` — 4,342 bytes)

### 1.2 `https://mcpmarket.com/tools/skills` (MCP Market Skills Directory)
- **Status**: Accessible and inspected directly via HTTP fetch.
- **Findings**: Lists over 360,000 community and commercial skills across 20 categories (`Security & Testing`, `Data Science & ML`, `Developer Tools`, `API Development`, `Database Management`, etc.), alongside official vendor packs (`Anthropic`, `Microsoft`, `Supabase`, `Stripe`).
- **Filtering Decision**: Many featured skills on MCP Market are commercial/paid (`$19` "Premium" listings) or marketing-oriented (`Ad Creative Engine`, `ATS Resume Tailor`). Per project requirements (Section 4), paid/proprietary skills and irrelevant marketing tools were rejected in favor of free, open-source skills with verifiable MIT/Apache-2.0 licenses on GitHub.

### 1.3 Public GitHub Repositories
- **Status**: Queried via GitHub Contents API and raw content fetch.
- **Selected Repositories**:
  - `howard-lynn-ye/fin-skills` (MIT License): Quantitative finance skill library covering market-data validation, lookahead-bias prevention, signal construction, and execution-cost modeling.
  - `mehmetmuejde/agent-skills` (MIT License): Layered FastAPI backend architecture and repository patterns.
  - `aks-builds/quality-skills` (MIT License): Comprehensive `pytest`, `pytest-api`, and `security-testing` procedural guides.

---

## 2. Coverage Across Required Engineering Domains

| Required Domain | Verified Skill(s) Selected | Application to PSX Dashboard |
|---|---|---|
| 1. Requirements analysis | `deliver-prd` | Decomposed all 4 legacy workflows (`Top 5`, `Accounts 91404/91269`, `Futures`, `36-Ticker Technicals`) into canonical requirements (`docs/REQUIREMENTS.md`). |
| 2. Structured brainstorming | `deliver-prd`, `deliver-edge-cases` | Mapped edge cases (missing same-date spot/futures, `<5` rows in TXT, short sell = sell, mixed commission slabs). |
| 3. Architecture planning | `develop-adr`, `fastapi-backend` | Designed the 10-layer separation of concerns (`docs/ARCHITECTURE.md`, `docs/ASSUMPTIONS_AND_DECISIONS.md`). |
| 4. Task decomposition | `develop-adr` | Structured the 10-phase implementation workflow from discovery and migration through E2E testing. |
| 5. Python engineering | `fastapi-backend` | Type-annotated Python 3.11+ services, `Decimal` monetary arithmetic, and clean repository abstractions. |
| 6. Financial-data processing | `execution-cost-analysis`, `research-integrity-guards` | Implemented exact PSX commission slabs, 13% SST, weighted averages, and lookahead-free indicator series. |
| 7. Excel import/export | `xlsx` | Two-pass workbook inspection (`data_only=True/False`) and legacy-compatible `.xlsx` exports with precalculated values + formulas. |
| 8. Database design & migrations | `fastapi-backend` | Normalized SQLite schema with WAL mode, foreign keys, content-hash idempotency, and PostgreSQL-ready repository layer. |
| 9. Data validation & reconciliation | `data-quality-validation`, `deliver-edge-cases` | Built automated reconciliation comparing legacy workbook totals against recalculated database totals. |
| 10. Dashboard UI/UX | `frontend-design`, `web-design-guidelines` | Restrained dark/light institutional financial interface with clear hierarchy, green/red P&L semantics, and `tabular-nums`. |
| 11. Data visualization | `frontend-design`, `react-best-practices` | Interactive SVG/Canvas price/volume candlesticks, Bollinger/EMA overlays, RSI/MACD subcharts, and futures basis curves. |
| 12. Security & dependency auditing | `security-testing` | Enforced localhost binding, path-traversal guards, ZIP-slip/bomb limits, non-execution of uploaded files, and safe SQLite backups. |
| 13. Automated testing | `pytest`, `pytest-api`, `webapp-testing` | Built unit, hand-calculated commission, futures matching, indicator sufficiency, migration, and E2E API tests. |
| 14. Performance optimization | `react-best-practices`, `fastapi-backend` | Indexed SQLite tables, batch transaction commits, SHA-256 skip-on-unchanged-file, and cached indicator series. |
| 15. Deployment & documentation | `develop-adr`, `deliver-prd` | Created Windows double-click launcher (`start_dashboard.bat`), PowerShell helper, and 15 comprehensive documentation files. |

---

## 3. Security Audit & Rejection Log

1. **Static Inspection**: Every downloaded `SKILL.md` file was inspected in Python prior to saving. None of the 16 retained files contain shell-execution payloads (`curl | bash`), credential-harvesting instructions, or external webhook calls.
2. **Rejected Resources**:
   - **Commercial MCP Market Skills** (`mp-ad-creative-engine`, `mp-ats-resume-tailor`): Rejected due to paid licensing ($19) and lack of domain relevance.
   - **External Market-Scraping Skills** (`gauss314/skills`, `miladaghdak/pytse-client-skill`): Inspected for structure only; not installed because the PSX dashboard must operate strictly on local uploaded files without unverified web scraping.
   - **Unverified CLI Installers (`npx skills add`)**: Rather than executing third-party `npx` postinstall scripts inside the workspace, raw `SKILL.md` markdown documents were fetched over HTTPS, inspected in memory, hashed with SHA-256, and written as inert documentation files.
