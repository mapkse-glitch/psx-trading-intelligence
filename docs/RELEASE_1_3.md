# Release 1.3.0 — scope and compatibility

## Corrected

Security: private owner workspace, signed expiring session cookies, CSRF/same-origin mutation checks, protected financial APIs and exports, security headers and no-store API responses. Missing secrets fail closed. Local development bypass is explicit, loopback-only and disabled on serverless hosts.

Persistence: private GitHub repository required, verified remote-base identity, stale snapshot refusal, non-forced branch update, pending/error states, transactional online snapshot handling, local reload safety backup, restore-to-cloud attempt. Network failure is not reported as a successful save. Does not add multi-writer merge or persistent Vercel local storage.

Maintenance: date-plan fingerprint prevents applying a stale scan, confirmation, online verified pre-repair backup, transaction/quarantine/audit and indicator cache invalidation. The server does not auto-repair live records on deployment. Future-date checks block setup-generation on suspect canonical input.

Reconciliation: real workbook comparisons for historical Top 5 scope, separate account historical totals, populated futures comparison rows and ATRL indicators. Missing reference fixtures show NOT_CHECKED. Same-date cash mismatches are counted over full history; rows displayed are capped. Integrity, historical parity, sufficiency and freshness are different checks.

Exports: each futures worksheet receives its own selected filters. Eight sheets remain: seven visible and hidden source Data. Symbol Filter remains all retained dates. Dates display DD-MM-YYYY in Excel with sortable date cells. Downloads use unique response copies. Empty workspaces produce valid workbooks, not a server error. CSV keeps machine-readable ISO dates.

Intelligence: `setup_score` replaces `probability_score` in the ideas API. This is an intentional compatibility change for external callers: update any client that expected the old probability field. Scores rank deterministic rules, not probability of profit. Business background is explicitly unverified. Volume and active-contract context is date-matched, and the most liquid matching futures contract wins deterministic selection.

UI: calmer overview, light/dark themes, responsive sidebar drawer, simplified mobile utilities, table-local scroll, labeled settings fields and accessible focus. Fixed light-theme invisible KPI figures, narrow Top 5 overflow, ambiguous display dates, settings field-name errors, stale asynchronous renders, and duplicate chunk retry handling. All ten core modules are retained; trading ideas remain in Technical Analysis rather than occupying the first screen.

## Deliberately unchanged

Accounts 91404/91269 isolation; existing commission/SST and execution accounting semantics; existing indicator implementations and warm-up rules; manual file workflow; no cash backfill; worksheet-local futures filters; original uploaded files and historical assets. No external AI service, trading execution or live price feed was added. No live repository/deployment mutation was performed during release QA.

## Known limitations

Read DEPLOY_1_3.md before use. Snapshot sync is single-owner/single-writer oriented. Authentication is a single owner password, not a multi-user identity platform; the in-memory limiter is not distributed. CSP still permits inline script/style because the inherited interface uses inline handlers. This release does not claim an independent penetration test. Date-swap detection is heuristic and narrowly scoped. Historical parity references are excluded from the deployment archive. Serverless temporary files, source upload archives and backup ZIPs need independent preservation. A clean local checkout begins empty. Hosting quotas and runtime support remain subject to the provider.
