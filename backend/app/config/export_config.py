"""
Configuración para los nuevos exportadores - MongoDB como almacenamiento primario
"""
import os
from typing import Optional
from pymongo import MongoClient

# Configuración MongoDB - PRIMARIO
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_URL", "mongodb://cuenlyapp:cuenlyapp2025@mongodb:27017/cuenlyapp_warehouse?authSource=admin")
MONGODB_DATABASE_NAME = os.getenv("MONGODB_DATABASE", "cuenlyapp_warehouse")
# Colección v2 (headers) como fuente única
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION", "invoice_headers")

# MongoDB como almacenamiento primario
MONGODB_AS_PRIMARY = os.getenv("MONGODB_AS_PRIMARY", "true").lower() == "true"
AUTO_EXPORT_TO_MONGODB = os.getenv("AUTO_EXPORT_TO_MONGODB", "true").lower() == "true"

# Configuración de funcionalidades (solo MongoDB)
ENABLE_MONGODB_EXPORT = os.getenv("ENABLE_MONGODB_EXPORT", "true").lower() == "true"

# Configuración de performance
MONGO_BULK_SIZE = int(os.getenv("MONGO_BULK_SIZE", "100"))

# Configuración de retención
MONGO_DATA_RETENTION_DAYS = int(os.getenv("MONGO_DATA_RETENTION_DAYS", "365"))

def get_mongodb_config() -> dict:
    """Obtiene configuración completa de MongoDB con cliente conectado"""
    client = MongoClient(MONGODB_CONNECTION_STRING)
    return {
        "client": client,
        "database": MONGODB_DATABASE_NAME,
        "connection_string": MONGODB_CONNECTION_STRING,
        "collection_name": MONGODB_COLLECTION_NAME,
        "bulk_size": MONGO_BULK_SIZE,
        "retention_days": MONGO_DATA_RETENTION_DAYS,
        "enabled": ENABLE_MONGODB_EXPORT,
        "as_primary": MONGODB_AS_PRIMARY,
        "auto_export": AUTO_EXPORT_TO_MONGODB
    }
