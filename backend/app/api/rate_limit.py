"""
Rate limiter compartido para los routers de la API.
Inicializado una vez y reutilizado por todos los routers.
"""
import os
import logging

logger = logging.getLogger(__name__)

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from fastapi import Request

    def _get_user_or_ip(request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.utils.firebase_auth import verify_firebase_token
                token = auth.split(" ", 1)[1]
                payload = verify_firebase_token(token)
                return payload.get("email") or get_remote_address(request)
            except Exception:
                pass
        return get_remote_address(request)

    _limiter_storage = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}"
    limiter = Limiter(key_func=_get_user_or_ip, storage_uri=_limiter_storage)
    _ENABLED = True
    logger.info("✅ Rate limiting habilitado (slowapi + Redis)")
except Exception as _err:
    limiter = None
    _ENABLED = False
    logger.warning(f"⚠️ Rate limiting deshabilitado: {_err}")


def rate_limit(limit_string: str):
    """Decorador de rate limit seguro — no-op si slowapi no está disponible."""
    def decorator(func):
        if _ENABLED and limiter:
            return limiter.limit(limit_string)(func)
        return func
    return decorator
