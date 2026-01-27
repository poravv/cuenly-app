"""
Redis Cache para resultados de OpenAI.

Cache distribuido que reemplaza al cache en memoria, permitiendo:
- Compartir cache entre múltiples instancias/workers
- Persistencia de cache entre reinicios
- TTL configurable para resultados

Uso:
    from app.modules.openai_processor.redis_cache import OpenAIRedisCache
    
    cache = OpenAIRedisCache()
    
    # Verificar cache
    cached = cache.get(pdf_path)
    if cached:
        return cached
    
    # Procesar y guardar
    result = process_with_openai(pdf_path)
    cache.set(pdf_path, result)
"""
import json
import hashlib
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OpenAIRedisCache:
    """
    Cache Redis para resultados de procesamiento OpenAI.
    
    El cache usa hashes MD5 de las rutas de archivo como claves,
    lo que permite:
    - Claves de longitud fija
    - Evitar caracteres especiales en paths
    - Identificación única de cada documento
    """
    
    # TTL por defecto: 7 días
    DEFAULT_TTL = 86400 * 7
    
    # Prefijo para todas las claves de cache OpenAI
    PREFIX = "cuenly:openai:cache:"
    
    def __init__(self, ttl_seconds: int = None):
        """
        Inicializa el cache Redis.
        
        Args:
            ttl_seconds: Tiempo de vida de entradas en cache (default: 7 días).
        """
        self.ttl = ttl_seconds or self.DEFAULT_TTL
        self._redis = None
        self._connected = False
        
        # Intentar conectar (lazy, no falla en init)
        self._initialize()
    
    def _initialize(self):
        """Inicializa conexión Redis de forma lazy."""
        try:
            from app.core.redis_client import get_redis_client
            self._redis = get_redis_client()
            self._connected = True
            logger.info("✅ OpenAIRedisCache inicializado correctamente")
        except Exception as e:
            logger.warning(f"⚠️ Redis cache no disponible: {e}. Cache deshabilitado.")
            self._connected = False
    
    @property
    def is_available(self) -> bool:
        """Verifica si el cache está disponible."""
        return self._connected and self._redis is not None
    
    def _make_key(self, identifier: str) -> str:
        """
        Genera clave Redis desde identificador (path o hash).
        
        Args:
            identifier: Ruta de archivo o identificador único.
            
        Returns:
            Clave Redis con prefijo.
        """
        hash_val = hashlib.md5(identifier.encode()).hexdigest()
        return f"{self.PREFIX}{hash_val}"
    
    def get(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene resultado cacheado.
        
        Args:
            identifier: Path del archivo o identificador.
            
        Returns:
            Dict con datos de factura si existe, None si no.
        """
        if not self.is_available:
            return None
        
        try:
            key = self._make_key(identifier)
            data = self._redis.get(key)
            
            if data:
                logger.info(f"🚀 Cache HIT (Redis) para {identifier[:50]}...")
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.warning(f"Error leyendo cache Redis: {e}")
            return None
    
    def set(self, identifier: str, result: Dict[str, Any], source: str = "openai") -> bool:
        """
        Guarda resultado en cache.
        
        Args:
            identifier: Path del archivo o identificador.
            result: Datos de factura a cachear.
            source: Fuente del resultado ("openai", "xml_parser", etc).
            
        Returns:
            True si se guardó exitosamente.
        """
        if not self.is_available:
            return False
        
        if not isinstance(result, dict):
            logger.warning(f"OpenAIRedisCache.set: resultado no es dict: {type(result)}")
            return False
        
        try:
            key = self._make_key(identifier)
            
            # Agregar metadata de cache
            cache_data = {
                "_cache_source": source,
                "_cache_key": key,
                **result
            }
            
            self._redis.setex(
                name=key,
                time=self.ttl,
                value=json.dumps(cache_data, default=str)
            )
            
            logger.debug(f"💾 Resultado cacheado en Redis: {key}")
            return True
            
        except Exception as e:
            logger.warning(f"Error guardando en cache Redis: {e}")
            return False
    
    def delete(self, identifier: str) -> bool:
        """
        Elimina entrada del cache.
        
        Args:
            identifier: Path del archivo o identificador.
            
        Returns:
            True si se eliminó.
        """
        if not self.is_available:
            return False
        
        try:
            key = self._make_key(identifier)
            result = self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Error eliminando de cache Redis: {e}")
            return False
    
    def clear_all(self) -> int:
        """
        Elimina todas las entradas del cache OpenAI.
        
        Returns:
            Número de entradas eliminadas.
        """
        if not self.is_available:
            return 0
        
        try:
            pattern = f"{self.PREFIX}*"
            keys = self._redis.keys(pattern)
            
            if keys:
                count = self._redis.delete(*keys)
                logger.info(f"🗑️ Cache Redis limpiado: {count} entradas eliminadas")
                return count
            
            return 0
            
        except Exception as e:
            logger.warning(f"Error limpiando cache Redis: {e}")
            return 0
    
    def stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache.
        
        Returns:
            Dict con estadísticas de uso.
        """
        if not self.is_available:
            return {"available": False}
        
        try:
            pattern = f"{self.PREFIX}*"
            keys = self._redis.keys(pattern)
            
            return {
                "available": True,
                "entries_count": len(keys),
                "prefix": self.PREFIX,
                "ttl_seconds": self.ttl
            }
            
        except Exception as e:
            return {"available": False, "error": str(e)}


# Singleton para uso global
_cache_instance: Optional[OpenAIRedisCache] = None


def get_openai_cache() -> OpenAIRedisCache:
    """
    Obtiene instancia singleton del cache OpenAI.
    
    Returns:
        OpenAIRedisCache: Instancia del cache.
    """
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = OpenAIRedisCache()
    
    return _cache_instance
