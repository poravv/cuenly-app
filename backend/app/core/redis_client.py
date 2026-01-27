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

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Obtiene una instancia singleton del cliente Redis.
    
    Returns:
        redis.Redis: Cliente Redis conectado.
        
    Raises:
        redis.ConnectionError: Si no se puede conectar a Redis.
    """
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                ssl=settings.REDIS_SSL,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Verificar conexión
            _redis_client.ping()
            logger.info(f"✅ Conexión Redis establecida: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado en Redis: {e}")
            raise
    
    return _redis_client


def close_redis_client() -> None:
    """Cierra la conexión Redis si existe."""
    global _redis_client
    
    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("🔌 Conexión Redis cerrada")
        except Exception as e:
            logger.warning(f"Error cerrando Redis: {e}")
        finally:
            _redis_client = None


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
