"""
Singleton de MongoClient compartido para todo el proceso.

PyMongo's MongoClient gestiona su propio pool de conexiones internamente.
Crear un cliente por request genera overhead innecesario de handshake TCP/TLS.
Este módulo expone un único cliente reutilizable por proceso.
"""
import logging
from pymongo import MongoClient
from app.config.settings import settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """
    Retorna el MongoClient singleton del proceso.
    Lo inicializa en el primer uso con pool de conexiones configurado.
    Nunca llamar .close() sobre el cliente retornado.
    """
    global _client
    if _client is None:
        _client = MongoClient(
            settings.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True,
        )
        logger.info("MongoClient singleton inicializado")
    return _client
