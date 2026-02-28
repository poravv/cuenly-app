"""
Distributed processing lock.

En producción (Kubernetes con múltiples pods) se usa un lock de Redis (SETNX + TTL)
para garantizar que solo un pod procese la misma cuenta a la vez.
Si Redis no está disponible, cae gracefully a un threading.Lock local
(comportamiento original, válido para deployments de un solo pod).

Interfaz idéntica a threading.Lock para no cambiar los callers:
    acquired = PROCESSING_LOCK.acquire(timeout=30)
    PROCESSING_LOCK.release()
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class _RedisDistributedLock:
    """
    Lock distribuido basado en Redis SETNX + EXPIRE.
    Compatible con la interfaz de threading.Lock (acquire/release).
    """

    REDIS_KEY = "cuenly:processing_lock"
    # TTL del lock en Redis: si el proceso muere sin liberar, expira automáticamente.
    LOCK_TTL_SECONDS = 120

    def __init__(self) -> None:
        self._redis = None
        self._local_lock = threading.Lock()  # fallback cuando Redis no está disponible
        self._use_redis = False
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            from app.core.redis_client import get_redis_client
            client = get_redis_client(decode_responses=True)
            client.ping()
            self._redis = client
            self._use_redis = True
            logger.info("✅ ProcessingLock: usando Redis distributed lock")
        except Exception as e:
            logger.warning(f"⚠️ ProcessingLock: Redis no disponible, usando threading.Lock local: {e}")
            self._use_redis = False

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if self._use_redis and self._redis:
            return self._acquire_redis(blocking=blocking, timeout=timeout)
        return self._acquire_local(blocking=blocking, timeout=timeout)

    def _acquire_redis(self, blocking: bool, timeout: float) -> bool:
        deadline = (time.monotonic() + timeout) if (blocking and timeout >= 0) else None
        poll_interval = 0.1

        while True:
            try:
                acquired = self._redis.set(
                    self.REDIS_KEY, "1",
                    nx=True,         # Solo si NO existe (atómico)
                    ex=self.LOCK_TTL_SECONDS
                )
                if acquired:
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Redis lock error, cayendo a lock local: {e}")
                self._use_redis = False
                return self._acquire_local(blocking=blocking, timeout=timeout)

            if not blocking:
                return False
            if deadline is not None and time.monotonic() >= deadline:
                return False

            time.sleep(poll_interval)

    def _acquire_local(self, blocking: bool, timeout: float) -> bool:
        if timeout >= 0:
            return self._local_lock.acquire(blocking=True, timeout=timeout)
        return self._local_lock.acquire(blocking=blocking)

    def release(self) -> None:
        if self._use_redis and self._redis:
            try:
                self._redis.delete(self.REDIS_KEY)
            except Exception as e:
                logger.warning(f"⚠️ Error liberando Redis lock: {e}")
        else:
            try:
                self._local_lock.release()
            except RuntimeError:
                pass  # Ya liberado


# Singleton global — mismo patrón que antes, misma interfaz
PROCESSING_LOCK = _RedisDistributedLock()
