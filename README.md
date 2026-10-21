# PSX Intelligence 1.3.1 — no login

This version removes the unrequested password and sign-in system. The dashboard opens directly. No owner password, session secret, account creation or sign-out step is required. Existing PSX_ADMIN_PASSWORD / PSX_SESSION_SECRET / PSX_AUTH_DISABLED environment variables are ignored and may be removed from your hosting settings.

## Update the existing GitHub / Vercel application

1. Download an independent current-data backup first.
2. Extract this ZIP. Upload its **contents** into the existing repository root, replacing matching source files—not the ZIP itself and not an extra enclosing folder.
3. **Preserve the existing `latest_cloud_sync.db.gz` exactly. Do not delete or overwrite it.** This is a source-only release: databases, raw uploads, backups and credentials are intentionally excluded.
4. Commit and redeploy the existing Vercel project. Open the site: the dashboard should appear immediately. No new password variables are needed.
5. Keep the existing GitHub sync configuration (`GITHUB_SYNC_REPO`, `GITHUB_SYNC_BRANCH`, `GITHUB_SYNC_TOKEN`) if you use cloud persistence. The sync repository must remain private. GitHub integration credentials are separate from the removed dashboard login.

Read [deployment and recovery](docs/DEPLOY_1_3.md). Password-free access means anyone who can reach the deployed site can view account data, download data and invoke data-changing actions. A private GitHub repository does **not** make the Vercel website private. Same-origin browser checks are request hygiene, not access control.

## Retained corrections

- Clean light/dark interface, separate account cards, responsive navigation, keyboard-friendly tables and readable financial figures.
- Independent filters in all futures worksheets, eight-sheet export, sortable DD-MM-YYYY Excel date display, and machine-readable ISO dates in CSV.
- Stale cloud-snapshot rejection, pending/error reporting, verified online backups and restore-to-cloud attempt.
- Reviewed transactional date repair with plan fingerprint and safety backup; no automatic live repair on deployment.
- Scoped reconciliation with evidence; absent private reference workbooks show NOT_CHECKED.
- Rule scores—not probability of profit—and same-date volume/most-liquid futures context.
- Settings validation, import retry handling, isolated export responses and graceful first-run/empty-account screens.

Accounts 91404 and 91269 remain separate. Existing financial calculation semantics and manual import workflow are retained. No missing cash-price backfill, live price feed, trade execution or external LLM dependency was added.

## Local launch

Python 3.12+ (tests use Python 3.13):

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. No login is needed. `PSX_DATA_DIR` chooses local runtime storage; default `./psx_data`. Local launchers are also included. A source-only checkout begins empty unless restored, imported, or hydrated from your configured private repository.

See [changes](docs/RELEASE_1_3.md), [verification](docs/TESTING_1_3.md) and [design rationale](docs/DESIGN_1_3.md). No zero-defect guarantee or live Vercel deployment claim is made.
