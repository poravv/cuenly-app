class AIFatalError(Exception):
    """Error crítico: API key inválida, sin cuota, etc. Debe abortar procesamiento."""
    pass

class AIRetryableError(Exception):
    """Error temporal: timeout, rate limit, etc. Se puede reintentar."""
    pass

class SkipEmailKeepUnread(Exception):
    """Señal especial: Omite el correo y evita marcarlo como leído (ej. límite IA alcanzado)."""
    pass

# deprecated aliases — eliminar próximo sprint
OpenAIFatalError = AIFatalError
OpenAIRetryableError = AIRetryableError
