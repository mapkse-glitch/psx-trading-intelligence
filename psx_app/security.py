"""Password-free request hygiene. This is not authentication or access control."""
import asyncio
from urllib.parse import urlsplit
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MUTATION_LOCK = asyncio.Lock()

def same_origin(request):
    origin = request.headers.get('origin')
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.netloc == request.headers.get('host') and parsed.scheme in ('http', 'https')

def install_request_safety(app):
    app.add_middleware(RequestSafetyMiddleware)

class RequestSafetyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not same_origin(request):
            return JSONResponse({'detail': 'Cross-origin changes refused.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith('/api/') or request.url.path in ('/openapi.json', '/docs', '/redoc'):
            response.headers['Cache-Control'] = 'no-store'
        return response
