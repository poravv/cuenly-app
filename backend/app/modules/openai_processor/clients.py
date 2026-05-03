from __future__ import annotations
from typing import List, Dict, Any, Protocol, runtime_checkable
import logging
import socket
from requests.exceptions import RequestException, Timeout, ConnectionError

from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

from app.modules.email_processor.errors import AIFatalError, AIRetryableError

logger = logging.getLogger(__name__)

# Excepciones retryables
RETRYABLE_EXCEPTIONS = (
    socket.timeout, Timeout, ConnectionError,
    socket.error, OSError, RequestException
)


@runtime_checkable
class AIChatClient(Protocol):
    def chat_json(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> str: ...


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
                logger.error("Error fatal de OpenAI API: %s", e)
                raise AIFatalError(f"Error fatal de OpenAI API: {e}")

            # Rate limit - convertir a retryable
            if "rate limit" in error_msg or "too many requests" in error_msg:
                logger.warning("Rate limit en OpenAI API: %s", e)
                raise ConnectionError(f"Rate limit: {e}")

            raise


class GeminiChatClient:
    """Cliente Gemini SDK con conversión de mensajes formato OpenAI y reintentos."""

    def __init__(self, api_key: str) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
        except Exception as e:
            logger.error("No se pudo inicializar Gemini SDK: %s", e)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def chat_json(self, model: str, messages: List[Dict[str, Any]], temperature: float, max_tokens: int) -> str:
        """Llamada a Gemini con salida JSON forzada vía response_mime_type."""
        try:
            system_instruction, contents = self._openai_to_gemini_parts(messages)

            generation_config = {
                "response_mime_type": "application/json",
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }

            gemini_model = self._genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
                generation_config=generation_config,
            )

            response = gemini_model.generate_content(contents)
            return response.text or ""

        except Exception as e:
            error_msg = str(e).lower()

            if any(fatal in error_msg for fatal in [
                "api key", "authentication", "quota", "billing", "permission denied",
                "invalid api key",
            ]):
                logger.error("Error fatal de Gemini API: %s", e)
                raise AIFatalError(f"Error fatal de Gemini API: {e}")

            if any(retryable in error_msg for retryable in [
                "rate limit", "resource exhausted", "429", "timeout", "deadline exceeded",
            ]):
                logger.warning("Rate limit / timeout en Gemini API: %s", e)
                raise ConnectionError(f"Gemini rate limit / timeout: {e}")

            raise

    def _openai_to_gemini_parts(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[str | None, List[Dict[str, Any]]]:
        """Convierte mensajes formato OpenAI a system_instruction + contents de Gemini."""
        system_instruction: str | None = None
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content if isinstance(content, str) else str(content)
                continue

            gemini_role = "model" if role == "assistant" else "user"

            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append({"text": item["text"]})
                    elif item.get("type") == "image_url":
                        url: str = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            # data:image/jpeg;base64,<b64data>
                            header, b64data = url.split(",", 1)
                            mime_type = header.split(":")[1].split(";")[0]
                            parts.append({
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64data,
                                }
                            })
            else:
                parts = [{"text": str(content)}]

            contents.append({"role": gemini_role, "parts": parts})

        return system_instruction, contents


def make_ai_client(settings) -> AIChatClient:
    """Factory que instancia el cliente de IA según AI_PROVIDER."""
    if settings.AI_PROVIDER == "openai":
        return OpenAIChatClient(api_key=settings.OPENAI_API_KEY)

    if not settings.GEMINI_API_KEY:
        logger.warning(
            "AI_PROVIDER=gemini pero GEMINI_API_KEY está vacía — usando OpenAI como fallback"
        )
        return OpenAIChatClient(api_key=settings.OPENAI_API_KEY)

    return GeminiChatClient(api_key=settings.GEMINI_API_KEY)


def make_openai_client(api_key: str) -> OpenAIChatClient:
    """Deprecated — usar make_ai_client(settings). Conservado para compatibilidad."""
    return OpenAIChatClient(api_key=api_key)
