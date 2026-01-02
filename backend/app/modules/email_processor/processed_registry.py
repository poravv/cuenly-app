import logging
from datetime import datetime
from typing import Optional
from pymongo import MongoClient, UpdateOne
from app.config.settings import settings
from app.models.processed_email import ProcessedEmail

logger = logging.getLogger(__name__)

class MongoProcessedEmailRepository:
    def __init__(self):
        self._client = None
        self._db_name = settings.MONGODB_DATABASE
        self._conn_str = settings.MONGODB_URL
        
        # Cache local simple para evitar hits excesivos a Mongo en la misma ejecución
        # Key: _id, Value: timestamp check
        self._local_cache = {} 

    def _get_collection(self):
        if not self._client:
            self._client = MongoClient(self._conn_str)
        coll = self._client[self._db_name].processed_emails
        try:
            coll.create_index("status")
            coll.create_index("owner_email")
        except:
            pass
        return coll

    def was_processed(self, key: str) -> bool:
        """
        Verifica si un correo ya fue procesado exitosamente.
        Si está en estado 'skipped_ai_limit', devuelve False para permitir reintento (si el límite se renovó).
        """
        if key in self._local_cache:
            return True

        try:
            doc = self._get_collection().find_one({"_id": key})
            if not doc:
                return False
            
            # Si fue omitido por límite de IA, NO lo consideramos "procesado" 
            # para que el loop principal intente procesarlo de nuevo.
            # (El loop principal hará el chequeo de cuota nuevamente)
            if doc.get("status") == "skipped_ai_limit":
                return False
                
            self._local_cache[key] = True
            return True
        except Exception as e:
            logger.error(f"Error consultando processed_emails en Mongo: {e}")
            return False

    def mark_processed(self, key: str, status: str = "success", reason: str = None, owner_email: str = None, account_email: str = None) -> None:
        """
        Marca un correo como procesado (o skipeado).
        """
        try:
            parts = key.split("::")
            if len(parts) >= 3:
                owner = parts[0]
                account = parts[1]
                uid = parts[2]
            else:
                owner = owner_email or "unknown"
                account = account_email or "unknown"
                uid = key

            doc = ProcessedEmail(
                _id=key,
                owner_email=owner,
                account_email=account,
                email_uid=uid,
                status=status,
                reason=reason,
                processed_at=datetime.utcnow()
            )
            
            self._get_collection().replace_one(
                {"_id": key},
                doc.model_dump(by_alias=True),
                upsert=True
            )
            
            if status != "skipped_ai_limit":
                self._local_cache[key] = True
                
        except Exception as e:
            logger.error(f"Error guardando processed_email en Mongo: {e}")

# Instancia global para mantener compatibilidad
_repo = MongoProcessedEmailRepository()

def build_key(email_uid: str, username: str, owner_email: str | None = None) -> str:
    owner = (owner_email or "").lower()
    return f"{owner}::{username or ''}::{email_uid}"

def was_processed(key: str) -> bool:
    return _repo.was_processed(key)

def mark_processed(key: str, status: str = "done") -> None:
    # Intenta extraer owner y account del key si es posible
    _repo.mark_processed(key, status)
