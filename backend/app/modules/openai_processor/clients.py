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
    """Interfaz simple para chat completions en modo JSON o texto."""

    def __init__(self, api_key: str, flavour: str = "legacy") -> None:
        """
        flavour:
            - "legacy": openai==0.28.x (openai.ChatCompletion.create)
            - "new": openai>=1.x (client.chat.completions.create)
        """
        self.flavour = flavour
        self.client = None

        if flavour == "new":
            try:
                from openai import OpenAI  # type: ignore
                self.client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.error("No se pudo inicializar OpenAI (nuevo SDK): %s", e)
                raise
        else:
            try:
                import openai  # type: ignore
                openai.api_key = api_key
                self.client = openai
            except Exception as e:
                logger.error("No se pudo inicializar OpenAI (legacy): %s", e)
                raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def chat_json(self, model: str, messages: List[Dict[str, Any]], temperature: float, max_tokens: int) -> str:
        """Hace una llamada y retorna el content (str). En flavour new intenta forzar JSON."""
        try:
            if self.flavour == "new":
                # Nuevo SDK con timeout
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    timeout=60,  # 60 segundos timeout
                )
                return resp.choices[0].message.content or ""
            else:
                # Legacy SDK: OpenAI 0.28.x
                resp = self.client.ChatCompletion.create(  # type: ignore[attr-defined]
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60,  # 60 segundos timeout
                )
                return resp["choices"][0]["message"]["content"]
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Errores fatales - no reintentar
            if any(fatal in error_msg for fatal in [
                "invalid api key", "api key", "authentication", "unauthorized",
                "insufficient quota", "quota exceeded", "billing"
            ]):
                logger.error(f"❌ Error fatal de OpenAI API: {e}")
                raise OpenAIFatalError(f"Error fatal de OpenAI API: {e}")
            
            # Rate limit - convertir a retryable
            if "rate limit" in error_msg or "too many requests" in error_msg:
                logger.warning(f"📊 Rate limit en OpenAI API: {e}")
                raise ConnectionError(f"Rate limit: {e}")  # Will be retried
            
            # Otros errores - propagar para que tenacity decida
            raise


def make_openai_client(api_key: str) -> OpenAIChatClient:
    """
    Si quieres migrar al nuevo SDK, cambia aquí a flavour="new".
    Por ahora se mantiene "legacy" para tu stack actual.
    """
    return OpenAIChatClient(api_key=api_key, flavour="legacy")