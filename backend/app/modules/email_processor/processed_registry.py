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
            coll.create_index("message_id")
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
            
            # Si fue omitido por límite de IA o está pendiente, NO lo consideramos "procesado" 
            # para que el loop principal intente procesarlo de nuevo.
            if doc.get("status") in ("skipped_ai_limit", "skipped_ai_limit_unread", "pending"):
                return False
                
            self._local_cache[key] = True
            return True
        except Exception as e:
            logger.error(f"Error consultando processed_emails en Mongo: {e}")
            return False

    def was_processed_by_message_id(self, message_id: str, owner_email: str) -> bool:
        """
        Verifica si un correo ya fue procesado globalmente por su Message-ID.
        """
        if not message_id:
            return False
            
        try:
            # Buscamos si existe algú procesado exitoso con este Message-ID para este owner
            doc = self._get_collection().find_one({
                "message_id": message_id,
                "owner_email": owner_email,
                "status": {"$nin": ["skipped_ai_limit", "skipped_ai_limit_unread", "pending"]} # Ignoramos los skip y pending
            })
            return doc is not None
        except Exception as e:
            logger.error(f"Error consultando por message_id en Mongo: {e}")
            return False

    def mark_processed(self, key: str, status: str = "success", reason: str = None, 
                       owner_email: str = None, account_email: str = None, 
                       message_id: str = None, subject: str = None,
                       sender: str = None, email_date: datetime = None) -> None:
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

            # Usamos update_one con $set para no sobrescribir metadatos existentes (como el subject) si no se pasan
            update_data = {
                "status": status,
                "reason": reason,
                "processed_at": datetime.utcnow()
            }
            if message_id:
                update_data["message_id"] = message_id
            if subject:
                update_data["subject"] = subject
            if sender:
                update_data["sender"] = sender
            if email_date:
                update_data["email_date"] = email_date

            set_on_insert = {
                "owner_email": owner,
                "account_email": account,
                "email_uid": uid
            }

            self._get_collection().update_one(
                {"_id": key},
                {
                    "$set": update_data,
                    "$setOnInsert": set_on_insert
                },
                upsert=True
            )
            
            if status != "skipped_ai_limit" and status != "pending":
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

def was_processed_by_message_id(message_id: str, owner_email: str) -> bool:
    return _repo.was_processed_by_message_id(message_id, owner_email)

def mark_processed(key: str, status: str = "done", message_id: str = None, reason: str = None, subject: str = None) -> None:
    # Intenta extraer owner y account del key si es posible
    _repo.mark_processed(key, status, message_id=message_id, reason=reason, subject=subject)
