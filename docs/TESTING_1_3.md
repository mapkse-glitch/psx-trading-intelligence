# Verification — corrected release 1.3.0

## Executed locally

Environment: Linux, Python 3.13, Chromium through Playwright, Node 24. Runtime dependencies are pinned in requirements.txt. `pip check` found no broken requirements.

- **Historical fixture regression run: 73 passed, 0 failed.** This includes the inherited regression suite and new safety tests, using isolated copies of the supplied historical DB/workbooks. The supplied database was never mutated.
- **Clean-checkout run: 53 passed, 20 skipped, 0 failed.** The 20 skipped tests need private historical fixtures deliberately excluded from the release ZIP. These are explicit skips, not silently passing tests.
- Both pytest runs emit one Starlette TestClient/httpx deprecation warning. It did not fail tests; this release does not claim a warning-free test environment.
- JavaScript syntax check (`node --check`) and Python bytecode compilation passed.
- Browser: all ten navigation modules on desktop and mobile, eight futures tabs, four technical tabs, and eight report tabs per populated account. No JavaScript exceptions or failing responses in these paths.
- Reflow: ten modules at widths 320, 390, 768, 1280 and 1440 pixels; no page-level horizontal overflow. Essential tables scroll inside their own containers. Drawer closes with Escape.
- axe-core 4.10.3: zero reported WCAG A/AA tagged violations in the eight main views checked in both light and dark themes after fixes. An additional light-theme run included Top 5. These checks are not a certification of complete accessibility; charts, all hidden states and assistive technology combinations were not exhaustively audited.
- Separate authenticated browser session: anonymous financial API 401; wrong-password rejection; successful login 200; missing-CSRF mutation 403; valid-CSRF backup 200; logout restores 401. Cookie HttpOnly and SameSite Strict verified. Production Secure cookie behavior is covered by the HTTPS/serverless code path and unit tests, not a live Vercel sign-in.
- Empty first run: all ten main views tested without existing financial records; valid empty exports verified. Account pages explain missing imports instead of dereferencing missing daily summaries.
- Actual futures download from the browser: eight sheets, hidden Data, Monthly Comparison date 12 October, independent Month Filter date 13 October/20 days, Symbol Filter OCT/OGDC/40 days across all retained dates, separate Date Summary date 12 October. Structural checks and targeted LibreOffice render of Monthly Comparison/Symbol Filter showed no package issues or visible spreadsheet error values. Excel date cells remain sortable and use DD-MM-YYYY display.
- Final archive extracted to an independent folder, clean tests and syntax checks rerun; content allowlist and exclusion scan performed. No runtime databases, snapshots, credentials, uploads, backup archives or private fixture workbooks packaged.

## What the safety tests cover

Fail-closed authentication, expiring signed sessions and logout, CSRF/same-origin checks, serverless bypass rejection, private repo enforcement, stale two-worker snapshot rejection with mocked GitHub, unknown-baseline rejection, failed-push pending state, online WAL backups, backup retention without deletion, restore cloud push, independent futures filters, invalid filter/settings validation, future-date guard, missing-reference NOT_CHECKED, changed ATRL reference detection, synthetic import idempotency, repair plan fingerprint and verified backup, multi-file chunk retry, empty-workspace APIs/exports, same-date most-liquid futures evidence and absence of unrelated-date Top 5 claims.

GitHub tests use a deterministic fake remote, not your live credentials or repository. Actual live deployment, private-repo token scope, concurrent Vercel routing and provider build/runtime quotas require the post-deployment checklist in DEPLOY_1_3.md.

## Reproduce

```sh
pip install -r requirements.txt
pytest -q
node --check psx_app/static/app.js
python -m compileall -q psx_app api main.py
```

For the optional historical regression tests, point to your independently preserved original fixtures (never the live runtime DB):

```sh
PSX_TEST_SEED_DB=/absolute/path/to/original/app.db \
PSX_TEST_REFERENCE_DIR=/absolute/path/to/original/drive_mirror \
pytest -q
```

The test harness always creates an isolated temporary database and removes live cloud credentials from the test process. The test-only development bypass must not be copied into production environment settings.

## Not executed / no guarantee

No live GitHub write, Vercel deploy, real PAT validation, real cloud conflict merge, Windows launcher execution, Docker build, Render deployment, penetration test, financial strategy backtest or exhaustive import fuzz test was performed. No software package can honestly be guaranteed to have zero defects. This release corrects the identified issues and records the validation scope, rather than hiding these limits.
