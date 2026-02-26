"""
Redis Client Singleton

Proporciona una conexión compartida a Redis para toda la aplicación.
Usado para:
- Cache distribuido (OpenAI results)
- Cola de trabajo (RQ jobs)
- Bloqueos distribuidos (si se necesitan)
"""
import logging
from typing import Optional
import redis

from app.config.settings import settings

logger = logging.getLogger(__name__)

_redis_client_decoded: Optional[redis.Redis] = None
_redis_client_raw: Optional[redis.Redis] = None


def get_redis_client(decode_responses: bool = True) -> redis.Redis:
    """
    Obtiene una instancia singleton del cliente Redis.
    
    Args:
        decode_responses: Si es True, las respuestas se decodifican como strings (UTF-8).
                         Si es False, se devuelven como bytes (necesario para RQ/pickle).
    
    Returns:
        redis.Redis: Cliente Redis conectado.
    """
    global _redis_client_decoded, _redis_client_raw
    
    # Seleccionar el singleton adecuado
    if decode_responses:
        client = _redis_client_decoded
    else:
        client = _redis_client_raw
        
    if client is None:
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                ssl=settings.REDIS_SSL,
                db=settings.REDIS_DB,
                decode_responses=decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Verificar conexión
            client.ping()
            mode = "DECODED" if decode_responses else "RAW"
            logger.info(f"✅ Conexión Redis ({mode}) establecida: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
            # Guardar en el singleton correspondiente
            if decode_responses:
                _redis_client_decoded = client
            else:
                _redis_client_raw = client
                
        except redis.ConnectionError as e:
            logger.error(f"❌ Error conectando a Redis ({'decoded' if decode_responses else 'raw'}): {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado en Redis: {e}")
            raise
    
    return client


def close_redis_client() -> None:
    """Cierra la conexión Redis si existe."""
    global _redis_client_decoded, _redis_client_raw

    for mode, client in (("DECODED", _redis_client_decoded), ("RAW", _redis_client_raw)):
        if client is None:
            continue
        try:
            client.close()
            logger.info(f"🔌 Conexión Redis ({mode}) cerrada")
        except Exception as e:
            logger.warning(f"Error cerrando Redis ({mode}): {e}")

    _redis_client_decoded = None
    _redis_client_raw = None


def redis_health_check() -> dict:
    """
    Verifica el estado de la conexión Redis.
    
    Returns:
        dict: Estado de salud con campos 'healthy' y 'message'.
    """
    try:
        client = get_redis_client()
        info = client.info()
        return {
            "healthy": True,
            "message": "Redis conectado",
            "version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown")
        }
    except redis.ConnectionError as e:
        return {
            "healthy": False,
            "message": f"Error de conexión: {str(e)}"
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Error: {str(e)}"
        }
