class OpenAIFatalError(Exception):
    """Error crítico: API key inválida, sin cuota, etc. Debe abortar procesamiento."""
    pass

class OpenAIRetryableError(Exception):
    """Error temporal: timeout, rate limit, etc. Se puede reintentar."""
    pass

class SkipEmailKeepUnread(Exception):
    """Señal especial: Omite el correo y evita marcarlo como leído (ej. límite IA alcanzado)."""
    pass