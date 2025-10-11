"""
Security utilities for validating frontend requests
"""
from fastapi import HTTPException, Request
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

def validate_frontend_key(request: Request) -> bool:
    """
    Valida que el request venga del frontend legítimo mediante API Key
    """
    api_key = request.headers.get("X-Frontend-Key") or request.headers.get("x-frontend-key")
    
    if not api_key:
        logger.warning(f"❌ Request sin Frontend API Key desde {request.client.host}")
        raise HTTPException(
            status_code=403, 
            detail="Frontend API Key requerida"
        )
    
    if api_key != settings.FRONTEND_API_KEY:
        logger.warning(f"❌ Frontend API Key inválida desde {request.client.host}: {api_key[:10]}...")
        raise HTTPException(
            status_code=403, 
            detail="Frontend API Key inválida"
        )
    
    logger.debug(f"✅ Frontend API Key válida desde {request.client.host}")
    return True

def get_client_info(request: Request) -> dict:
    """
    Obtiene información del cliente para logging de seguridad
    """
    return {
        "ip": request.client.host,
        "user_agent": request.headers.get("User-Agent", ""),
        "origin": request.headers.get("Origin", ""),
        "referer": request.headers.get("Referer", "")
    }