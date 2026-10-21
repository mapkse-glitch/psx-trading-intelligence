# Verification — 1.3.1 no-login release

The authentication tests from 1.3.0 were removed because that feature was explicitly removed, not silently bypassed. New regressions check direct access without password/session variables, serverless read access without login, absence of the login form and session cookies, password-free local mutation, retained rejection of ordinary cross-origin browser mutations, and retained settings validation.

Run portable tests from a clean checkout:

```sh
pip install -r requirements.txt
python -m pytest -q
node --check psx_app/static/app.js
python -m compileall -q psx_app api main.py
```

Twenty historical-fixture tests explicitly skip unless both private fixture variables are supplied. To execute them, use an isolated original fixture copy—not the live runtime DB:

```sh
PSX_TEST_SEED_DB=/path/to/original/app.db \
PSX_TEST_REFERENCE_DIR=/path/to/original/drive_mirror \
python -m pytest -q
```

See QA_SUMMARY_1_3.json for the actual revised-release results. Historical fixtures are deliberately excluded from the ZIP. Browser tests check direct startup without cookies or login environment variables, module navigation on desktop/mobile and a real export download. The archive is verified after extraction; runtime data and credentials are excluded.

The earlier 1.3.0 UI/export checks are background evidence, not a claim that all old authentication behavior is retained. Live GitHub/Vercel deployment, real token scope, Windows launchers, Docker and exhaustive security/financial-strategy testing are not executed here. Password-free access intentionally removes data confidentiality/access control at the application layer. No zero-defect guarantee is made.

## Executed revised-release results

71 passed with historical fixtures. Clean checkout: 51 passed, 20 explicit private-fixture skips. Both emitted one Starlette TestClient/httpx deprecation warning, not a failure. Twenty populated-module browser checks across desktop/mobile completed without JavaScript errors or failed responses; direct account API and password-free backup returned 200. Actual futures download remained an eight-sheet workbook with hidden Data.
