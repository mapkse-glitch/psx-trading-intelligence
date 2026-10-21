"""Single-owner authentication. No passwords or signing keys are shipped in source."""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict
from urllib.parse import urlsplit
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

COOKIE = 'psx_owner_session'
_ATTEMPTS = defaultdict(list)
MUTATION_LOCK = asyncio.Lock()


def configured():
    return len(os.environ.get('PSX_ADMIN_PASSWORD', '')) >= 12 and len(os.environ.get('PSX_SESSION_SECRET', '')) >= 32


def local_bypass(request):
    return (os.environ.get('PSX_AUTH_DISABLED') == '1' and not os.environ.get('VERCEL')
            and not os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
            and request.client and request.client.host in ('127.0.0.1', '::1', 'testclient'))


def sign(data):
    return hmac.new(os.environ.get('PSX_SESSION_SECRET', '').encode(), data.encode(), hashlib.sha256).hexdigest()


def issue_session(remember=True):
    payload = base64.urlsafe_b64encode(json.dumps({'exp': int(time.time()) + (604800 if remember else 28800),
                                                 'csrf': secrets.token_urlsafe(32)}).encode()).decode()
    return payload + '.' + sign(payload)


def session(request):
    if local_bypass(request):
        return {'csrf': 'local-development-only'}
    if not configured():
        return None
    try:
        payload, signature = request.cookies.get(COOKIE, '').rsplit('.', 1)
        if not hmac.compare_digest(signature, sign(payload)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data if data['exp'] > time.time() else None
    except Exception:
        return None


def same_origin(request):
    origin = request.headers.get('origin')
    if not origin:
        return True  # non-browser clients must still present session and CSRF
    parsed = urlsplit(origin)
    return parsed.netloc == request.headers.get('host') and parsed.scheme in ('http', 'https')


def install_auth(app):
    @app.get('/api/auth/status')
    def auth_status(request: Request):
        s = session(request)
        return {'configured': configured() or bool(local_bypass(request)), 'authenticated': bool(s),
                'csrf': s['csrf'] if s else None, 'version': '1.3.0'}

    @app.post('/api/auth/login')
    async def login(request: Request):
        if not same_origin(request):
            return JSONResponse({'detail': 'Cross-origin login refused.'}, status_code=403)
        if not configured():
            return JSONResponse({'detail': 'Owner login is not configured. Set PSX_ADMIN_PASSWORD (12+ characters) and PSX_SESSION_SECRET (32+ characters), then restart.'}, status_code=503)
        key = request.client.host if request.client else 'unknown'
        now = time.time()
        _ATTEMPTS[key] = [t for t in _ATTEMPTS[key] if t > now - 300]
        if len(_ATTEMPTS[key]) >= 10:
            return JSONResponse({'detail': 'Too many attempts. Wait five minutes.'}, status_code=429)
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({'detail': 'Invalid login request.'}, status_code=400)
        if not isinstance(data, dict):
            return JSONResponse({'detail': 'Invalid login request.'}, status_code=400)
        supplied = data.get('password', '')
        if not isinstance(supplied, str) or not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(), hashlib.sha256(os.environ['PSX_ADMIN_PASSWORD'].encode()).digest()):
            _ATTEMPTS[key].append(now)
            return JSONResponse({'detail': 'Incorrect password.'}, status_code=401)
        _ATTEMPTS.pop(key, None)
        remember = data.get('remember') is True
        response = JSONResponse({'authenticated': True})
        response.set_cookie(COOKIE, issue_session(remember), httponly=True,
                            secure=bool(os.environ.get('VERCEL')) or request.url.scheme == 'https',
                            samesite='strict', max_age=604800 if remember else None, path='/')
        return response

    @app.post('/api/auth/logout')
    def logout():
        response = JSONResponse({'authenticated': False})
        response.delete_cookie(COOKIE, path='/')
        return response

    app.add_middleware(OwnerSecurityMiddleware)


class OwnerSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        public = path in ('/', '/styles.css', '/app.js', '/favicon.ico', '/api/auth/status', '/api/auth/login')
        if not public:
            auth = session(request)
            if not auth:
                return JSONResponse({'detail': 'Owner sign-in required.'}, status_code=401)
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and not local_bypass(request):
                token = request.headers.get('x-psx-csrf', '')
                if not same_origin(request) or not hmac.compare_digest(token, auth['csrf']):
                    return JSONResponse({'detail': 'Invalid CSRF token. Refresh and sign in again.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if path.startswith('/api/') or path in ('/openapi.json', '/docs', '/redoc'):
            response.headers['Cache-Control'] = 'no-store'
        return response
