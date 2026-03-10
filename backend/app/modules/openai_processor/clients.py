from __future__ import annotations
from typing import List, Dict, Any
import logging
import socket
from requests.exceptions import RequestException, Timeout, ConnectionError

from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

logger = logging.getLogger(__name__)

# Excepciones retryables
RETRYABLE_EXCEPTIONS = (
    socket.timeout, Timeout, ConnectionError,
    socket.error, OSError, RequestException
)


class OpenAIFatalError(Exception):
    """Error fatal de OpenAI que no debe reintentarse (auth, quota, etc)."""
    pass


class OpenAIChatClient:
    """Cliente OpenAI SDK >=1.x con response_format JSON y reintentos."""

    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, timeout=60)
        except Exception as e:
            logger.error("No se pudo inicializar OpenAI SDK: %s", e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def chat_json(self, model: str, messages: List[Dict[str, Any]], temperature: float, max_tokens: int) -> str:
        """Llamada con response_format=json_object para garantizar JSON válido."""
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content or ""

        except Exception as e:
            error_msg = str(e).lower()

            # Errores fatales - no reintentar
            if any(fatal in error_msg for fatal in [
                "invalid api key", "api key", "authentication", "unauthorized",
                "insufficient quota", "quota exceeded", "billing"
            ]):
                logger.error(f"Error fatal de OpenAI API: {e}")
                raise OpenAIFatalError(f"Error fatal de OpenAI API: {e}")

            # Rate limit - convertir a retryable
            if "rate limit" in error_msg or "too many requests" in error_msg:
                logger.warning(f"Rate limit en OpenAI API: {e}")
                raise ConnectionError(f"Rate limit: {e}")

            raise


def make_openai_client(api_key: str) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=api_key)
