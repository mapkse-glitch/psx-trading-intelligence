# Deployment & recovery — 1.3.0

## 1. Protect the current data first

- Download the current database snapshot and a verified backup ZIP before changing code. Keep them somewhere independent of GitHub and Vercel. If the old site is public, prefer downloading over a trusted connection and restrict access promptly.
- Make `mapkse-glitch/psx-trading-intelligence` (or the actual configured repository) **private**. This release refuses cloud sync to a public repository. Audit repository access/history and remove unintended collaborators. Previously public data cannot be made retrospectively secret. Rotate a token if it was exposed; this package does not contain a token.
- The existing `latest_cloud_sync.db.gz` is the live data artifact. **Preserve it exactly while uploading this release.** Do not replace it with a snapshot from an older workspace ZIP or a test environment.

## 2. Upload source files, not the ZIP itself

Extract the release ZIP on your computer. In the existing GitHub repository, choose Add file → Upload files. Upload the extracted `api`, `docs`, `psx_app`, `tests` folders and root files into the repository root, replacing matching source files. Do not create an extra enclosing folder and do not upload the ZIP as the application. Do not delete unrelated live data artifacts. Include dotfiles `.gitignore` and `.vercelignore` if your file picker hides them.

Alternatively, with an existing Git checkout, copy over the extracted files, inspect `git diff`, and commit only the release source. `git status` must not show a deleted/replaced `latest_cloud_sync.db.gz`, a token, `.env`, or local database. `.gitignore` prevents newly added snapshots but does not untrack the existing live snapshot. **Do not run `git rm --cached` on the live snapshot as part of this update.**

The package intentionally excludes all DB/gzip/backup ZIP/raw inputs, private parity workbooks, runtime logs, caches, skills, node_modules and test credentials. Its small size is expected. Keep your original source-data archives separately.

## 3. Set production secrets in Vercel, then redeploy

| Variable | Required value |
|---|---|
| `PSX_ADMIN_PASSWORD` | Unique owner password, minimum 12 characters. Prefer a long password-manager-generated value. |
| `PSX_SESSION_SECRET` | Random signing secret, minimum 32 characters. Not the owner password. |
| `GITHUB_SYNC_REPO` | Exact private `owner/repository`, e.g. `mapkse-glitch/psx-trading-intelligence`. |
| `GITHUB_SYNC_BRANCH` | Existing branch, normally `main`. |
| `GITHUB_SYNC_TOKEN` | Fine-grained GitHub PAT, only the selected private repository, Contents Read and Write. Metadata Read is automatic. |

Generate a signing secret on your own computer with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Enter values in Vercel, not source code or chat. Enable them for the intended production deployment. Remove `PSX_AUTH_DISABLED` if present. No separate paid database or LLM key is needed for the existing snapshot architecture.

Use the existing Vercel project linked to this repository. Root Directory must be the repository root, where `main.py`, `api/index.py`, `requirements.txt` and `vercel.json` live. Framework/runtime detection uses the existing FastAPI entrypoint. Redeploy after setting secrets. Review build/runtime logs for your Vercel account's current Python/runtime/size/time limits; the live deployment was not executed during local QA.

On serverless hosts, SQLite lives under `/tmp/psx_data` and is temporary. Do not force a persistent `/home/user` path on Vercel. Successful GitHub sync, not the existence of a `/tmp` file, is the durable-save confirmation.

## 4. Post-deployment acceptance checklist

1. Open the site in a private browser window: only sign-in should be visible. An unauthenticated `/api/overview` request must return 401, not financial data.
2. Sign in with the owner password. Missing owner secrets must fail closed; there is no default password.
3. Settings: database integrity should report OK. Confirm the repository/branch and cloud state. NOT_CHECKED reference parity is expected when the private historical workbook fixtures are not installed; it is not a pass or a failure of financial calculations.
4. Compare both account totals and latest cash/futures dates with your own backup. Provided source fixtures ended on 16 October 2026; they were used only for regression tests, **not bundled as replacement live data**. Newer live rows must remain.
5. Download a current snapshot. Keep it outside the repository too.
6. If a future/suspect date is displayed, go to Settings → Date normalization → Scan. Review the proposed changes, backup availability and evidence. Apply only when correct. The plan is rejected if canonical data changes after scanning; scan again. The scanner detects a limited class of day/month swaps, not every possible date error. Do not apply a hypothesis just because a scanner suggests it.
7. Test a small daily-file upload: stage → review → commit. Confirm a successful cloud save, not just a successful local import. Reopen on another device/cold instance and verify it sees the committed data.
8. Test futures: change Monthly Comparison date, Month Filter date/contract/days, and Symbol Filter contract/symbol/days independently. Download Excel and check each sheet. Symbol Filter intentionally has no date selector.
9. Keep both account ledgers isolated; verify one account's export contains no records from the other account.

## Cloud errors, pending changes and stale instances

The app records the remote snapshot identity it started from. Before mutations and before publishing, it compares that identity with GitHub. A stale instance is rejected instead of overwriting the newer snapshot. A branch update is non-forced. There is no automatic conflict merge.

- **ACTIVE**: snapshot base is verified and there is no known pending/error state. It does not mean every other serverless worker has reloaded.
- **PENDING / ERROR**: a local change has not been confirmed saved remotely. Download the current snapshot immediately from that same active session where possible, keep an independent copy, then retry. Do not assume a successful import means a successful GitHub push.
- **LOCAL**: no remote configuration; local files are durable only on a persistent local disk. On Vercel, canonical writes are blocked without configured cloud sync.
- If remote data changed and local changes are not pending, use **Reload latest cloud data**. A verified pre-reload local backup is created. If local changes are pending, reload is refused to avoid discarding them. Save those changes externally before any manual reconciliation.
- If the repository was made private, a token expired or lost scope, resolve token/repository access first. Do not make the repository public as a workaround.

**Architecture boundary:** process locks protect one worker, not all Vercel workers or unrelated GitHub writers. Concurrent writes can produce a rejected push and local pending data. The package prevents blind stale overwrites but cannot turn GitHub snapshots into a multi-writer ACID database. Use one writer at a time. A serverless request may route to another instance; temporary pending data, local backups and raw archives are not guaranteed to survive eviction. Downloads and an independent backup policy remain necessary. There is no distributed login rate limiter, MFA or per-user role system; this is a single-owner app.

## Backups, restore and rollback

Backups use SQLite's online backup API (including committed WAL data), an integrity check and a manifest. No backup is silently deleted to meet the old retention count; manage storage deliberately after downloading copies. Restoring an existing verified backup first creates a safety backup, invalidates caches and attempts cloud sync. Confirm that sync result.

A database snapshot contains canonical SQLite data, **not the original uploaded files**. A backup ZIP includes raw files only when requested. Keep source uploads independently. On Vercel, a backup listed in one temporary worker may not exist on another.

To roll back code, restore a known code commit without replacing the current snapshot with an older one. Avoid rolling back to the unauthenticated public build. If financial data needs rollback, use a deliberately chosen verified backup and review its coverage; that is a separate data operation, never an incidental code upload.

## Local use

Python 3.12+; local QA used 3.13. Set environment secrets in your shell; `.env` is not automatically loaded. `PSX_DATA_DIR` chooses local persistent storage; default `./psx_data`. Launchers bind to loopback by default. Local/LAN exposure requires authentication and an appropriate trusted network/TLS configuration. Windows launcher and Docker/Render deployment are included but were not executed in this environment.
