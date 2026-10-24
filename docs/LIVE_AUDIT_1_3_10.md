# Live dashboard audit — 23 October 2026

Inspected https://psx-trading-intelligence.vercel.app and the public GitHub source, base commit `56266de`. Live checks used read-only data endpoints and browser inspection; browser POST actions were blocked. No live import, forecast recording, settings change, deployment or GitHub push was performed. Endpoints can maintain their existing indicator cache; canonical production data was not intentionally modified. Observations are point-in-time and may change after new imports.

## Reproduced fault: TRG, Core36, Long / Buy
- Live ticker endpoint returned **2,670 cash sessions, 2016-01-01 through 2026-10-23**, with 9 valid indicators. It did not lack data.
- Latest close 52.54; raw SHORT SELL, score −8/9.
- Long-only scan returned `candidates_scanned=0`, no rejected rows. That counter counted survivors of early filters, not examined symbols.
- All-directions scan returned one candidate and an explicit structural reward/risk rejection: reference entry 52.54, stop 55.06, T1 51.40; gross R/R ≈0.45:1, below 1.5:1.
- Correct outcome: **one symbol checked; excluded by Long-only; also no validated opening plan**. Not “missing data”, not an invented buy and not guaranteed short eligibility.

## Cross-module coverage, live API snapshot
| Check | Observed |
|---|---:|
| Stored cash symbols / technical universe symbols | 883 / 883 |
| Cash symbols missing in technical universe | 0 |
| Core36 with cash history | 36 / 36 |
| Futures base symbols with cash history | 98 / 98 |
| Top5 register symbols with cash history | 23 / 23 |
| Cash symbols matching latest imported cash date | 495 |
| Cash symbols with an older last cash date | 388 |
| Insufficient-data signals | 233 (229 stale, 4 current) |

Four current short-history examples: BAPLR1 (1 session), CHWC (1), CENIR (7), LSEFSLR (10). These are insufficient to initialize the complete signal system, not absent from the cash universe. Old symbols may be delisted, inactive, rights issues or historical instruments; the imported data alone does not establish the reason. No missing prices were fabricated.

At the observed live snapshot: cash, futures, Top5 and account 91404 reached 2026-10-23; imported INDEX reached 2026-10-22 and account 91269 reached 2026-10-19. Different source latest dates were reported rather than filled. Later imports may change these dates. The account symbol sets, including recognized contract suffixes, were compared to cash bases; see the released CSV's account-base-present flag (no private trades or balances included).

Sample live analyst checks: TRG, PRL, MLCF and legacy search alias MLF returned histories; unknown ZZZNOTREAL returned NO_DATA. BAPLR1/CENIR had data but the old analyst response failed to clearly stop narrative analysis on insufficient history; fixed in this release. MLCF remains the displayed/source ticker; MLF is only a legacy lookup alias, not a forced rewrite of imported securities.

## Sector workbook
The supplied `SECTOR_WISE.xlsx` has supported company reference sheets but the main price detector classified it as CUSTOM_XLSX. The dedicated reference import was separate. The update shares reference parsing with normal staging and atomic commit. Unsupported sheets/extra columns are disclosed; aliases are not inferred. The supplied KSE100 list has 101 entries, so it remains explicitly user-supplied/unverified rather than treated as authoritative index membership.

## Evidence and scope
`LIVE_SYMBOL_COVERAGE_2026_10_23.csv` lists all 883 cash symbols with first/latest dates, number of sessions, years present, readiness/signal, plan evidence and cross-module membership flags. These are audit observations, not future probabilities.

Patched behavior was tested separately with synthetic fixtures and a **private local copy of the older GitHub backup** (774 symbols, 654,014 cash rows). That backup differs from the live Turso dataset (883 symbols, 988,124 cash rows at observation). Local regression results must not be misrepresented as a deployment to the live 883-symbol database. The new coverage report runs against the actual configured database after the user deploys.
