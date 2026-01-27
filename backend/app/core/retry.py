"""
Decoradores de retry con backoff exponencial usando tenacity.

Uso:
    from app.core.retry import openai_retry, imap_retry

    class MyService:
        @openai_retry
        def call_openai(self, prompt: str):
            # Esta llamada se reintentará automáticamente
            return openai.ChatCompletion.create(...)

        @imap_retry  
        def connect_imap(self):
            # Esta conexión se reintentará con backoff
            return imaplib.IMAP4_SSL(...)
"""
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

from app.core.exceptions import AIRetryableError, AITimeoutError, EmailConnectionError

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


# ============ OpenAI Retry ============

openai_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((
        TimeoutError,
        ConnectionError,
        AIRetryableError,
        AITimeoutError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
"""
Decorador para llamadas a OpenAI.
- 3 intentos máximo
- Backoff exponencial aleatorio: 2s → 30s
- Reintenta en: TimeoutError, ConnectionError, AIRetryableError
"""


# ============ IMAP Retry ============

imap_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
        TimeoutError,
        OSError,
        ConnectionResetError,
        EmailConnectionError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
"""
Decorador para conexiones IMAP.
- 3 intentos máximo
- Backoff exponencial: 1s → 10s
- Reintenta en: TimeoutError, OSError, ConnectionResetError
"""


# ============ Generic Retry ============

def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 30,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Factory para crear decoradores de retry personalizados.
    
    Args:
        max_attempts: Número máximo de intentos.
        min_wait: Tiempo mínimo de espera entre intentos (segundos).
        max_wait: Tiempo máximo de espera entre intentos (segundos).
        exceptions: Tupla de excepciones que disparan retry.
    
    Usage:
        @with_retry(max_attempts=5, exceptions=(TimeoutError,))
        def my_function():
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# ============ Storage Retry ============

storage_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type((
        TimeoutError,
        ConnectionError,
        OSError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
"""
Decorador para operaciones de storage (MongoDB, MinIO).
- 3 intentos máximo
- Backoff exponencial rápido: 0.5s → 5s
"""


# ============ Redis Retry ============

redis_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
    retry=retry_if_exception_type((
        TimeoutError,
        ConnectionError,
        OSError
    )),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=True
)
"""
Decorador para operaciones Redis (cache).
- 2 intentos máximo (cache no es crítico)
- Backoff rápido: 0.5s → 3s
"""
