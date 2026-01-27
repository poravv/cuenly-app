"""
Patrón Result para manejo estandarizado de resultados y errores.

Uso:
    from app.core.result import success, failure, Result

    def process_invoice(data: dict) -> Result[InvoiceData]:
        if not data:
            return failure("Datos vacíos", code="EMPTY_DATA")
        
        try:
            invoice = InvoiceData.from_dict(data)
            return success(invoice)
        except Exception as e:
            return failure(str(e), code="PARSE_ERROR")
    
    # Consumir resultado
    result = process_invoice(data)
    if result.is_success():
        invoice = result.value
    else:
        logger.error(f"Error: {result.error} (code={result.code})")
"""
from dataclasses import dataclass, field
from typing import Generic, TypeVar, Union, Optional, Any

T = TypeVar('T')


@dataclass
class Success(Generic[T]):
    """Representa un resultado exitoso con un valor."""
    value: T
    
    def is_success(self) -> bool:
        return True
    
    def is_failure(self) -> bool:
        return False
    
    def unwrap(self) -> T:
        """Obtiene el valor. Siempre seguro para Success."""
        return self.value
    
    def unwrap_or(self, default: T) -> T:
        """Obtiene el valor o un default (ignora default para Success)."""
        return self.value


@dataclass
class Failure:
    """Representa un resultado fallido con información de error."""
    error: str
    code: str = "UNKNOWN"
    details: Optional[dict] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        return False
    
    def is_failure(self) -> bool:
        return True
    
    def unwrap(self) -> Any:
        """Lanza excepción porque no hay valor."""
        raise ValueError(f"Cannot unwrap Failure: {self.error} (code={self.code})")
    
    def unwrap_or(self, default: T) -> T:
        """Retorna el valor default porque es Failure."""
        return default


# Tipo unión para tipado estático
Result = Union[Success[T], Failure]


# ============ Helper Functions ============

def success(value: T) -> Success[T]:
    """Crea un resultado exitoso."""
    return Success(value)


def failure(error: str, code: str = "UNKNOWN", details: dict = None) -> Failure:
    """Crea un resultado fallido."""
    return Failure(error=error, code=code, details=details or {})


# ============ Common Error Codes ============

class ErrorCodes:
    """Códigos de error estandarizados."""
    # General
    UNKNOWN = "UNKNOWN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    
    # AI/Processing
    AI_LIMIT_REACHED = "AI_LIMIT_REACHED"
    AI_PROCESSING_ERROR = "AI_PROCESSING_ERROR"
    AI_TIMEOUT = "AI_TIMEOUT"
    
    # Email
    EMAIL_CONNECTION_ERROR = "EMAIL_CONNECTION_ERROR"
    EMAIL_AUTH_ERROR = "EMAIL_AUTH_ERROR"
    EMAIL_PARSE_ERROR = "EMAIL_PARSE_ERROR"
    
    # Storage
    STORAGE_ERROR = "STORAGE_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    
    # Invoice
    INVOICE_PARSE_ERROR = "INVOICE_PARSE_ERROR"
    INVOICE_DUPLICATE = "INVOICE_DUPLICATE"
    INVOICE_INVALID = "INVOICE_INVALID"
