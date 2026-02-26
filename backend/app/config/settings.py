import os
import json
from typing import List, Dict, Any
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
#load_dotenv()
load_dotenv(encoding="utf-8")

class Settings(BaseSettings):
    # App
    TEMP_PDF_DIR: str = os.getenv("TEMP_PDF_DIR", "./data/temp_pdfs")
    PROCESSED_EMAILS_FILE: str = os.getenv("PROCESSED_EMAILS_FILE", "./data/processed_emails.json")
    PROCESSED_EMAIL_TTL_DAYS: int = int(os.getenv("PROCESSED_EMAIL_TTL_DAYS", 30))
    PROCESSED_EMAIL_MAX_ENTRIES: int = int(os.getenv("PROCESSED_EMAIL_MAX_ENTRIES", 20000))
    # Zona horaria para todo el backend (afecta scheduler y timestamps)
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Asuncion")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # MongoDB
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://cuenlyapp:cuenlyapp2025_seguro@mongodb:27017/cuenlyapp_warehouse?authSource=admin")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "cuenlyapp_warehouse")
    # Forzar colección v2 (headers) como única fuente de verdad
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "invoice_headers")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", 8000))

    # Job
    JOB_INTERVAL_MINUTES: int = int(os.getenv("JOB_INTERVAL_MINUTES", 60))

    # Auth / Multi-tenant
    AUTH_REQUIRE: bool = os.getenv("AUTH_REQUIRE", "true").lower() in ("1", "true", "yes")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "cuenly-app")
    MULTI_TENANT_ENFORCE: bool = os.getenv("MULTI_TENANT_ENFORCE", "true").lower() in ("1", "true", "yes")
    
    # Security - Frontend API Key
    FRONTEND_API_KEY: str = os.getenv("FRONTEND_API_KEY", "cuenly-frontend-dev-key-2025")
    # Seguridad de credenciales de correo (cifrado en reposo)
    # Recomendado: clave Fernet urlsafe base64 de 32 bytes.
    EMAIL_CONFIG_ENCRYPTION_KEY: str = os.getenv("EMAIL_CONFIG_ENCRYPTION_KEY", "")
    
    # Email Processing
    EMAIL_PROCESS_ALL_DATES: bool = os.getenv("EMAIL_PROCESS_ALL_DATES", "true").lower() in ("1", "true", "yes")
    
    # Email Processing - Multiusuario optimizado
    EMAIL_BATCH_SIZE: int = int(os.getenv("EMAIL_BATCH_SIZE", 50))  # Fallback local si fan-out no está disponible
    EMAIL_BATCH_DELAY: float = float(os.getenv("EMAIL_BATCH_DELAY", 3.0))  # Segundos entre lotes
    EMAIL_PROCESSING_DELAY: float = float(os.getenv("EMAIL_PROCESSING_DELAY", 0.5))  # Segundos entre correos
    # Si es false, no persiste placeholders ERR_* en invoice_headers/items.
    STORE_FAILED_INVOICE_HEADERS: bool = os.getenv("STORE_FAILED_INVOICE_HEADERS", "false").lower() in ("1", "true", "yes")
    
    # Email Processing - Procesamiento paralelo
    MAX_CONCURRENT_ACCOUNTS: int = int(os.getenv("MAX_CONCURRENT_ACCOUNTS", 10))  # Cuentas procesadas simultáneamente (reducido para prod)
    ENABLE_PARALLEL_PROCESSING: bool = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() in ("1", "true", "yes")
    ENABLE_EMAIL_FANOUT: bool = os.getenv("ENABLE_EMAIL_FANOUT", "true").lower() in ("1", "true", "yes")
    FANOUT_DISCOVERY_BATCH_SIZE: int = int(os.getenv("FANOUT_DISCOVERY_BATCH_SIZE", 250))  # Descubrimiento IMAP por tandas
    FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN: int = int(os.getenv("FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 200))  # Cap por cuenta/corrida
    
    # Job Processing Limits
    JOB_MAX_RUNTIME_HOURS: int = int(os.getenv("JOB_MAX_RUNTIME_HOURS", 24))  # Parar job después de 24 horas
    JOB_REST_PERIOD_HOURS: int = int(os.getenv("JOB_REST_PERIOD_HOURS", 2))  # Descansar 2 horas después de 24h
    MANUAL_PROCESS_LIMIT: int = int(os.getenv("MANUAL_PROCESS_LIMIT", 50))  # Compat legacy
    PROCESS_DIRECT_DEFAULT_LIMIT: int = int(os.getenv("PROCESS_DIRECT_DEFAULT_LIMIT", 50))
    PROCESS_DIRECT_MAX_LIMIT: int = int(os.getenv("PROCESS_DIRECT_MAX_LIMIT", 200))

    # MinIO / S3 Storage
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "minpoint.mindtechpy.net")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "bk-invoice")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "true").lower() in ("1", "true", "yes")
    MINIO_REGION: str = os.getenv("MINIO_REGION", "py-east-1")

    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_SSL: bool = os.getenv("REDIS_SSL", "0").lower() in ("1", "true", "yes")
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))

    # Pagopar Integration
    PAGOPAR_PUBLIC_KEY: str = os.getenv("PAGOPAR_PUBLIC_KEY", "")
    PAGOPAR_PRIVATE_KEY: str = os.getenv("PAGOPAR_PRIVATE_KEY", "")
    # Default to production, override with sandbox URL in dev
    PAGOPAR_BASE_URL: str = os.getenv("PAGOPAR_BASE_URL", "https://api.pagopar.com/api/pago-recurrente/3.0/")
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # Ignorar campos adicionales en lugar de lanzar un error
    }

    def model_post_init(self, __context):
        # No post-init dynamic env parsing needed; configs come from MongoDB
        pass

settings = Settings()
