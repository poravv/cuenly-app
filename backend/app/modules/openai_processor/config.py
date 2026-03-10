from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OpenAIConfig:
    """Configuración para el procesador de facturas vía OpenAI."""
    api_key: str
    model: str = "gpt-4o"           # gpt-4o-mini no tiene precisión suficiente para facturas
    temperature: float = 0.3       # más conservador para extracción
    max_tokens: int = 4000         # suficiente para facturas con muchos items