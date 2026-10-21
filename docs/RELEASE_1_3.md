# Release 1.3.1 — requested password removal

Removed the application owner password, login form, authentication endpoints, session cookies, CSRF token dependency, sign-in startup checks, sign-out controls, and password/session environment requirements. The site opens directly even when those variables are absent or left over from the preceding release. The API has no authentication gate.

Retained request security headers and basic same-origin browser mutation checks, without passwords or session tokens. These are not access control. Direct API clients remain able to access/change the application.

Retained the corrected UI, worksheet-local futures export state, date displays, account isolation, online backup/restore improvements, date-repair review and fingerprint, stale cloud snapshot rejection, scoped reconciliation, rule-score wording, same-date trading evidence, import retry fixes and empty-account handling.

GitHub sync still needs its existing integration token and private repository; the integration token is not a dashboard login. Live data and raw inputs are excluded from this source archive. Preserve the tracked live snapshot when updating.

No live website or repository was changed during creation of this release. Upload and redeploy the new code to remove the login from the live site.
