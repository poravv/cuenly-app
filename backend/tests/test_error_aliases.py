"""
Tests unitarios para los aliases de error en app.modules.email_processor.errors.

Verifica backward compatibility: OpenAIFatalError y OpenAIRetryableError deben ser
el mismo objeto que AIFatalError y AIRetryableError (no subclases, aliases directos).

Cubre tarea 5.2 de la migración GPT-4o → Gemini 2.5 Flash.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestErrorAliases:

    def test_openai_fatal_error_is_alias_for_ai_fatal_error(self):
        """OpenAIFatalError debe ser el mismo objeto que AIFatalError (alias, no subclase)."""
        from app.modules.email_processor.errors import AIFatalError, OpenAIFatalError

        assert OpenAIFatalError is AIFatalError, (
            "OpenAIFatalError debe ser el mismo objeto que AIFatalError, "
            f"pero son: {OpenAIFatalError} vs {AIFatalError}"
        )

    def test_openai_retryable_error_is_alias_for_ai_retryable_error(self):
        """OpenAIRetryableError debe ser el mismo objeto que AIRetryableError (alias, no subclase)."""
        from app.modules.email_processor.errors import AIRetryableError, OpenAIRetryableError

        assert OpenAIRetryableError is AIRetryableError, (
            "OpenAIRetryableError debe ser el mismo objeto que AIRetryableError, "
            f"pero son: {OpenAIRetryableError} vs {AIRetryableError}"
        )

    def test_catching_ai_fatal_error_catches_openai_fatal_error(self):
        """Código que captura AIFatalError también atrapa OpenAIFatalError (backward compat)."""
        from app.modules.email_processor.errors import AIFatalError, OpenAIFatalError

        caught = False
        try:
            raise OpenAIFatalError("API key inválida")
        except AIFatalError:
            caught = True

        assert caught, "AIFatalError debe capturar OpenAIFatalError (son el mismo tipo)"

    def test_catching_ai_retryable_error_catches_openai_retryable_error(self):
        """Código que captura AIRetryableError también atrapa OpenAIRetryableError (backward compat)."""
        from app.modules.email_processor.errors import AIRetryableError, OpenAIRetryableError

        caught = False
        try:
            raise OpenAIRetryableError("Rate limit")
        except AIRetryableError:
            caught = True

        assert caught, "AIRetryableError debe capturar OpenAIRetryableError (son el mismo tipo)"

    def test_ai_fatal_error_is_exception(self):
        """AIFatalError hereda de Exception."""
        from app.modules.email_processor.errors import AIFatalError

        assert issubclass(AIFatalError, Exception)

    def test_ai_retryable_error_is_exception(self):
        """AIRetryableError hereda de Exception."""
        from app.modules.email_processor.errors import AIRetryableError

        assert issubclass(AIRetryableError, Exception)

    def test_ai_fatal_and_retryable_are_different_classes(self):
        """AIFatalError y AIRetryableError son clases distintas entre sí."""
        from app.modules.email_processor.errors import AIFatalError, AIRetryableError

        assert AIFatalError is not AIRetryableError, (
            "AIFatalError y AIRetryableError no deben ser el mismo tipo"
        )

    def test_error_message_is_preserved(self):
        """El mensaje de error se preserva correctamente al lanzar y capturar."""
        from app.modules.email_processor.errors import AIFatalError

        msg = "Error de autenticación: API key expirada"
        try:
            raise AIFatalError(msg)
        except AIFatalError as e:
            assert str(e) == msg
