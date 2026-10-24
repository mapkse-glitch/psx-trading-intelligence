> **Existing deployment upgrade:** use [UPGRADE_1_3_10.md](UPGRADE_1_3_10.md). Preserve your current Turso database and credentials; do not repeat the initial database import.

> Already using Turso? Follow UPGRADE_1_3_8.md. Keep your working credentials; do not re-import the snapshot.

# Turso setup — PSX Intelligence 1.3.8

This is a source-only update for your existing GitHub/Vercel dashboard. It connects directly to the database you already imported into Turso. It does not import the backup again, include credentials, or deploy itself.

## 1. Preserve data before switching

Keep your downloaded latest_cloud_sync.db.gz and original Excel/TXT files safely on your computer or independent backup storage. Pause imports and settings changes in the old dashboard during cutover. Do not keep writing through both the old and new versions.

Your imported database is `psx-import-64b36a85534e` in organization `map-kse`. The original `psx-pilot` is not used.

## 2. Create a private read/write database token

In your existing Ubuntu/WSL terminal, paste this entire block. It copies a new token to the Windows clipboard without displaying it. This is a database token, not your Turso account-login token.

```bash
(
  set -euo pipefail
  export PATH="$HOME/.turso:$HOME/.local/bin:$PATH"
  turso org switch map-kse
  token="$(turso db tokens create psx-import-64b36a85534e --expiration 365d)"
  printf '%s' "$token" | clip.exe
  unset token
  echo "Database token copied. Paste it only into Vercel TURSO_AUTH_TOKEN."
)
```

Do not choose a read-only token. The application needs writes and permission to create its small runtime/staging tables. The token expires after 365 days: renew it before expiry. Do not send it in chat, screenshots, GitHub files, or browser JavaScript. Clear the clipboard after saving it. If clipboard copying fails, use Turso's Create Token interface and copy the token privately.

## 3. Configure Vercel before deploying the new code

Open your existing project → Settings → Environment Variables. Add these for **Production**:

| Name | Value |
|---|---|
| PSX_DATABASE_BACKEND | turso |
| TURSO_DATABASE_URL | libsql://psx-import-64b36a85534e-map-kse.aws-ap-south-1.turso.io |
| TURSO_AUTH_TOKEN | Paste the private database token |

Save them. Do not redeploy the old code as the migration step. Use a separate database/token for preview deployments if needed; do not expose production credentials to untrusted pull requests.

## 4. Upload and deploy

Extract this ZIP. Upload its **contents** into the existing repository root, replacing matching source files. Do not upload the ZIP itself or an extra containing folder. Include the dotfiles (.gitignore and .vercelignore). Commit the changes and let the existing Vercel project deploy the new commit.

Keep the existing downloaded database backup. No database is included in this package. Existing tracked snapshots are not needed in the deployed build and are excluded by .vercelignore. Do not delete your only backup. After verifying Turso, remove unnecessary financial snapshots from a public repository; deleting a file does not erase Git history.

The Vercel project must deploy from the repository root. Existing root main.py is the FastAPI entry point. This release requests the Mumbai region and a 300-second function duration; actual platform allowances still apply.

## 5. Verify before resuming normal imports

1. Confirm the dashboard says v1.3.8.
2. Open Settings: status must say **Turso — direct remote database (reads and writes)** and ACTIVE. Sidebar must say Turso: connected. A missing/invalid credential must fail, not silently create an empty local database.
3. Check cash/futures latest dates against your imported data. Your verified snapshot had latest trading data of 22-10-2026; a particular account or symbol may legitimately have an earlier last activity date. NOV is a futures contract month, not a November trading date.
4. Open the imported database in Turso → Edit Data. Confirm historical cash records are visible. The imported snapshot had cash history from 2019 onward; missing 2016–2018 files still need importing through the new dashboard if you want them.
5. Test one small, known import. Confirm the audit result, then verify the corresponding rows in Turso. Reload the dashboard and confirm the data persists. A repeated identical upload should be deduplicated.
6. Only then resume larger historical imports. Preserve original uploads separately. Do not re-import the entire backup into this same database.

If startup fails, check the deployment logs and environment values privately. Do not paste secrets into logs or screenshots. Do not resume imports in the old GitHub-snapshot application as a workaround: that would create two divergent databases. Stop writes and diagnose first.

## What changed

- All application database reads and writes go directly to Turso when configured, not a temporary SQLite replica or GitHub snapshot.
- Imports, account rollups, audit status, and database revision are committed together. Failed transactions roll back; uncertain network acknowledgements are not automatically retried.
- Upload chunks and parsed staging payloads survive between serverless workers in Turso, with expiry cleanup. Successful commit removes its staged payload.
- Import lookups are limited to incoming dates and inserts are batched, reducing full-history scans and per-row network requests.
- Views refresh when the remote revision changes. No repeated whole-database GitHub download/upload is required.
- Existing financial formulas, source-verified date protection, account separation, and futures worksheets remain.

## Limits and backups

Turso is persistent storage, not unlimited storage. Monitor its storage/read/write quotas in the dashboard. Upload staging also consumes database capacity until committed, discarded, or expired and cleaned up. The application caps a staged upload batch at 150 MB; large historical workbooks can still take time and are subject to Vercel request/function limits. Browser uploads use chunked transport.

Raw original files are not permanently archived in Turso: source metadata and canonical records are retained. Keep originals on your PC/Drive. Expired temporary staging is cleaned during subsequent chunked staging, not by a continuously running cleanup daemon.

Use Turso → database → **Download SQLite File** for independent backups. In-app local ZIP backup/restore and the broad heuristic swapped-date scanner are deliberately disabled in remote mode. Restore into a new database, verify it, then change the server URL/token. Existing source-verified import-date safeguards remain active.

After a successful cutover, old GITHUB_SYNC_* credentials are unused in Turso mode and can be removed from Vercel. GitHub remains the source-code host, not the live financial database.

## Important security notice

This release preserves your requested password-free dashboard. Anyone who can reach the website can potentially read financial data and invoke write actions. Keeping the Turso token private protects the token, **not access to the website**. Restrict site access using appropriate hosting protection before treating it as a private financial application. No new sign-in system has been added.

## Validation scope

See docs/QA_1_3_6.json. Tests used isolated local HTTP libSQL servers, including a copy of your snapshot. They did not modify your live Turso database and do not constitute a live Vercel deployment test. No card or paid plan is required by this code; service signup/plan terms are controlled by the providers.
