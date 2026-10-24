"""Fail-closed API readiness; no remote I/O in ASGI startup, no SQLite fallback.
Diagnostics expose only fixed codes, never raw driver text, URLs, tokens or SQL.
"""
import logging
import threading
import time

LOG = logging.getLogger('psx.database')
RETRY_SECONDS = 10


class DatabaseUnavailable(RuntimeError):
    def __init__(self, code='DATABASE_UNAVAILABLE', stage='readiness', uncertain=False):
        self.code = code
        self.stage = stage
        self.uncertain = uncertain
        detail = ('Database connection unavailable (' + code + '). No local replacement database was used. '
                  'Check the connection diagnostics and Vercel server settings, then retry.')
        if uncertain:
            detail += ' The transaction was not confirmed. A write may have been sent; check its saved status before resubmitting. Do not assume rollback.'
        super().__init__(detail)

    def payload(self):
        return {'detail': str(self), 'code': self.code, 'stage': self.stage,
                'retry_after_seconds': RETRY_SECONDS, 'write_outcome_uncertain': self.uncertain}


def safe_failure(exc, stage, uncertain=False):
    if isinstance(exc, DatabaseUnavailable):
        return exc
    # Raw text is used ONLY to classify; never emitted, persisted or chained.
    text = str(exc).casefold()
    if any(x in text for x in ('auth_token is required', 'valid libsql://', 'psx_database_backend', 'local sqlite fallback')):
        code = 'SERVER_CONFIGURATION'
    elif any(x in text for x in ('unauthorized', 'unauthenticated', 'invalid token', 'token expired', 'jwt', '401')):
        code = 'AUTHENTICATION_REJECTED'
    elif any(x in text for x in ('forbidden', 'permission denied', '403', 'read-only', 'readonly')):
        code = 'PERMISSION_DENIED'
    elif 'imported psx schema is missing' in text:
        code = 'REQUIRED_SCHEMA_MISSING'
    elif any(x in text for x in ('certificate', 'tls', 'ssl')):
        code = 'TLS_CONNECTION_FAILED'
    elif any(x in text for x in ('timed out', 'timeout', 'deadline')):
        code = 'CONNECTION_TIMEOUT'
    elif any(x in text for x in ('dns', 'connection refused', 'connect error', 'network', 'resolve host')):
        code = 'NETWORK_CONNECTION_FAILED'
    elif any(x in text for x in ('429', 'rate limit', 'too many requests')):
        code = 'SERVICE_RATE_LIMITED'
    else:
        code = 'DRIVER_OPERATION_FAILED'
    # Both stage and code are application-controlled. No exception text/traceback.
    LOG.error('PSX_DATABASE_UNAVAILABLE code=%s stage=%s', code, stage)
    return DatabaseUnavailable(code, stage, uncertain)


class Readiness:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.failure = None
        self.retry_at = 0.0

    def check(self):
        from psx_app.database import turso
        try:
            if not turso.enabled():
                return
        except Exception as exc:
            raise safe_failure(exc, 'configuration') from None
        # ensure_ready retains its own lock and sets _READY only after a successful
        # schema verification/additive initialization. Never seed canonical data.
        with self.lock:
            if self.failure is not None and self.clock() < self.retry_at:
                raise self.failure from None
            try:
                turso.ensure_ready()
            except Exception as exc:
                self.failure = safe_failure(exc, 'readiness')
                self.retry_at = self.clock() + RETRY_SECONDS
                raise self.failure from None
            self.failure = None
            self.retry_at = 0.0


readiness = Readiness()


def http_read_diagnostic():
    """Optional SELECT 1 via HTTPS to distinguish credentials/service from driver.
    One bounded request; never follows redirects or returns raw response bodies.
    Only the already-configured server URL receives its existing server token.
    """
    from urllib.parse import urlsplit
    from psx_app.database.turso import credentials
    try:
        url, token = credentials()
    except Exception as exc:
        return {'code': safe_failure(exc, 'configuration').code}
    parsed = urlsplit(url)
    if parsed.scheme not in ('libsql', 'https'):
        return {'code': 'HTTPS_DIAGNOSTIC_NOT_AVAILABLE'}
    endpoint = 'https://' + parsed.netloc + '/v2/pipeline'
    import httpx
    try:
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            r = client.post(endpoint, headers={'Authorization': 'Bearer ' + token}, json={
                'requests': [{'type': 'execute', 'stmt': {'sql': 'SELECT 1', 'want_rows': True}}, {'type': 'close'}]})
        if r.status_code in (401, 403):
            return {'code': 'AUTHENTICATION_REJECTED' if r.status_code == 401 else 'PERMISSION_DENIED', 'http_status': r.status_code}
        if r.status_code != 200:
            return {'code': 'REMOTE_SERVICE_HTTP_ERROR', 'http_status': r.status_code}
        body = r.json()
        first = body.get('results', [{}])[0]
        if first.get('type') == 'ok' and first.get('response', {}).get('type') == 'execute':
            return {'code': 'HTTPS_READ_OK_NATIVE_DRIVER_OR_SCHEMA_CHECK_FAILED',
                    'note': 'The direct read succeeded. This does not verify schema initialization, write permission or commit.'}
        return {'code': 'REMOTE_QUERY_REJECTED', 'http_status': 200}
    except Exception as exc:
        return {'code': safe_failure(exc, 'https_read_diagnostic').code}
