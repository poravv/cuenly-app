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
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # MongoDB
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://cuenlyapp:cuenlyapp2025@mongodb:27017/cuenlyapp_warehouse?authSource=admin")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "cuenlyapp_warehouse")
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "facturas_completas")

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
    
    # Email Processing
    EMAIL_PROCESS_ALL_DATES: bool = os.getenv("EMAIL_PROCESS_ALL_DATES", "true").lower() in ("1", "true", "yes")
    
    # Email Processing - Multiusuario optimizado
    EMAIL_BATCH_SIZE: int = int(os.getenv("EMAIL_BATCH_SIZE", 5))  # Correos por lote (reducido para multiusuario)
    EMAIL_BATCH_DELAY: float = float(os.getenv("EMAIL_BATCH_DELAY", 3.0))  # Segundos entre lotes
    EMAIL_PROCESSING_DELAY: float = float(os.getenv("EMAIL_PROCESSING_DELAY", 0.5))  # Segundos entre correos
    
    # Email Processing - Procesamiento paralelo
    MAX_CONCURRENT_ACCOUNTS: int = int(os.getenv("MAX_CONCURRENT_ACCOUNTS", 10))  # Cuentas procesadas simultáneamente
    ENABLE_PARALLEL_PROCESSING: bool = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() in ("1", "true", "yes")
    
    # Job Processing Limits
    JOB_MAX_RUNTIME_HOURS: int = int(os.getenv("JOB_MAX_RUNTIME_HOURS", 24))  # Parar job después de 24 horas
    JOB_REST_PERIOD_HOURS: int = int(os.getenv("JOB_REST_PERIOD_HOURS", 2))  # Descansar 2 horas después de 24h
    MANUAL_PROCESS_LIMIT: int = int(os.getenv("MANUAL_PROCESS_LIMIT", 10))  # Límite de facturas por proceso manual
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # Ignorar campos adicionales en lugar de lanzar un error
    }

    def model_post_init(self, __context):
        # No post-init dynamic env parsing needed; configs come from MongoDB
        pass

settings = Settings()
