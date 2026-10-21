# Deployment & recovery — 1.3.1 (password-free)

## Upload checklist

1. Back up the current database independently before updating code.
2. Extract the ZIP and upload all extracted folders/root files into the **existing repository root**. Include `.gitignore` and `.vercelignore`. Do not upload the archive as a single application file or create an extra parent folder.
3. Replace matching application code, including `psx_app/security.py`, `psx_app/main.py`, `psx_app/static/index.html` and `psx_app/static/app.js`. Leaving old versions of these files can retain the old login screen.
4. **Do not delete, replace or overwrite the live `latest_cloud_sync.db.gz`.** The release ZIP contains no snapshot or database. `.gitignore` excludes new local database files but does not untrack the existing live snapshot. Do not run `git rm --cached` on that snapshot.
5. Redeploy the existing Vercel project, with its Root Directory set to the repository root. Owner password/session variables are no longer used; remove them if desired. There are no new login variables to configure.
6. Open the completed deployment URL. If an old cached login page appears, hard-refresh or open a fresh browser tab and confirm Vercel deployed the new commit.

## Existing cloud persistence

Keep `GITHUB_SYNC_REPO=owner/repository`, the correct `GITHUB_SYNC_BRANCH` (usually main), and `GITHUB_SYNC_TOKEN` if cloud sync is in use. The token is an integration credential kept only in hosting environment settings—not a dashboard password. Use a fine-grained token restricted to the selected private repository with Contents Read and Write. No token is included in this archive.

The sync repository must be private. This does not restrict access to the hosted website: this release deliberately has **no application authentication**, per the user's request. Anyone with network access to the website can view financial data, export/download it, upload files and invoke changes. Origin checks reduce ordinary cross-site browser requests but do not stop direct API clients. Password-free access is not a security boundary.

Vercel's `/tmp/psx_data` storage is temporary. Only a confirmed GitHub snapshot push counts as a cloud save. Preserve independent downloads. Stale workers reject changes rather than blindly overwriting newer remote snapshots. Use one writer at a time; GitHub snapshots are not a multi-writer transactional database.

- ACTIVE means verified remote base without known pending/error state, not that every existing worker has refreshed.
- PENDING/ERROR means cloud persistence is not confirmed. Download a current snapshot immediately where possible, resolve repository/token access and retry.
- LOCAL means no cloud configuration. Persistent local-disk use is possible; canonical writes on Vercel are blocked without configured sync.
- Reload cloud data is permitted only without pending local changes, and creates a verified local backup first. It is not an automatic conflict merge.

## After deployment

- Confirm the dashboard appears directly, with no sign-in screen or sign-out button.
- Compare both independent account totals and latest dates against your current backup. Test fixtures ended on 16 October 2026 and are **not** bundled to replace newer live data.
- Check database integrity and cloud state; download an independent snapshot.
- Review the date-normalization dry run against original source files before applying. Deployment alone does not repair dates. The scanner detects only a limited class of swaps; a clean scan is not proof that all historical dates are correct.
- Check separate futures worksheet filters in an actual Excel download.
- Test one small manual upload through stage/review/commit and confirm the cloud-save result.

## Backup and rollback limits

Backups use online SQLite snapshots and integrity verification. Restore creates a safety backup and attempts a cloud push; verify its result. Backups are not silently removed by a retention limit. A database snapshot does not include original uploaded files; backup ZIPs include raw inputs only when explicitly requested. Keep source data separately.

Temporary serverless backups, pending changes and raw archives may disappear or be on another worker. No promise of permanent local storage, automatic merge or error-free deployment is made. Restore code independently from financial-data rollback; never replace current data as an incidental code update. Windows, Docker, Render and live Vercel deployment are not executed by the local release tests.
