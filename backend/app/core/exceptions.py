"""
Excepciones base estandarizadas para CuenlyApp.

Jerarquía:
    CuenlyError (base)
    ├── AIError
    │   ├── AILimitReachedError
    │   ├── AIProcessingError  
    │   └── AITimeoutError
    ├── EmailError
    │   ├── EmailConnectionError
    │   └── EmailAuthError
    ├── StorageError
    ├── ValidationError
    └── ProcessingError
"""
from typing import Optional, Dict, Any


class CuenlyError(Exception):
    """
    Base exception para todos los errores de CuenlyApp.
    
    Attributes:
        message: Mensaje descriptivo del error.
        code: Código único para identificar el tipo de error.
        details: Información adicional para debugging.
    """
    code: str = "CUENLY_ERROR"
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.details = details or {}
        self.cause = cause
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa el error a diccionario para respuestas API."""
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details
        }


# ============ AI Errors ============

class AIError(CuenlyError):
    """Errores relacionados con procesamiento de IA."""
    code = "AI_ERROR"


class AILimitReachedError(AIError):
    """Usuario alcanzó su límite de procesamiento con IA."""
    code = "AI_LIMIT_REACHED"


class AIProcessingError(AIError):
    """Error durante el procesamiento con OpenAI."""
    code = "AI_PROCESSING_ERROR"


class AITimeoutError(AIError):
    """Timeout en llamada a OpenAI."""
    code = "AI_TIMEOUT"


class AIFatalError(AIError):
    """Error fatal de OpenAI (API key inválida, sin crédito, etc.)."""
    code = "AI_FATAL"


class AIRetryableError(AIError):
    """Error transitorio de OpenAI que puede reintentarse."""
    code = "AI_RETRYABLE"


# ============ Email Errors ============

class EmailError(CuenlyError):
    """Errores relacionados con procesamiento de correos."""
    code = "EMAIL_ERROR"


class EmailConnectionError(EmailError):
    """Error de conexión IMAP."""
    code = "EMAIL_CONNECTION_ERROR"


class EmailAuthError(EmailError):
    """Error de autenticación IMAP/OAuth."""
    code = "EMAIL_AUTH_ERROR"


class EmailParseError(EmailError):
    """Error parseando contenido del correo."""
    code = "EMAIL_PARSE_ERROR"


# ============ Storage Errors ============

class StorageError(CuenlyError):
    """Errores de almacenamiento (MongoDB, MinIO)."""
    code = "STORAGE_ERROR"


class FileNotFoundError(StorageError):
    """Archivo no encontrado en storage."""
    code = "FILE_NOT_FOUND"


# ============ Validation Errors ============

class ValidationError(CuenlyError):
    """Errores de validación de datos."""
    code = "VALIDATION_ERROR"


# ============ Processing Errors ============

class ProcessingError(CuenlyError):
    """Errores generales de procesamiento."""
    code = "PROCESSING_ERROR"


class InvoiceParseError(ProcessingError):
    """Error parseando datos de factura."""
    code = "INVOICE_PARSE_ERROR"


class DuplicateInvoiceError(ProcessingError):
    """Factura duplicada detectada."""
    code = "INVOICE_DUPLICATE"
