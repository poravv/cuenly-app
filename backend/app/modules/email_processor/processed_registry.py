import logging
from datetime import datetime

from pymongo import MongoClient
try:
    from pymongo.errors import DuplicateKeyError
except Exception:  # pragma: no cover - fallback para tests con stubs de pymongo
    class DuplicateKeyError(Exception):
        pass

from app.config.settings import settings

logger = logging.getLogger(__name__)


class MongoProcessedEmailRepository:
    RETRYABLE_STATUSES = {
        "skipped_ai_limit",
        "skipped_ai_limit_unread",
        "pending_ai_unread",
        "retry_requested",
    }
    _indexes_ensured: bool = False

    def __init__(self):
        self._client = None
        self._db_name = settings.MONGODB_DATABASE
        self._conn_str = settings.MONGODB_URL

        # Cache local simple para evitar hits excesivos a Mongo en la misma ejecución
        # Key: _id, Value: reservado/procesado
        self._local_cache = {}

    def _get_collection(self):
        if not self._client:
            self._client = MongoClient(self._conn_str)
        coll = self._client[self._db_name].processed_emails
        if not MongoProcessedEmailRepository._indexes_ensured:
            try:
                coll.create_index("status")
                coll.create_index("owner_email")
                coll.create_index("message_id", unique=True, sparse=True)
                coll.create_index([("owner_email", 1), ("status", 1)])
                coll.create_index([("owner_email", 1), ("processed_at", -1)])
                MongoProcessedEmailRepository._indexes_ensured = True
            except Exception:
                pass
        return coll

    def is_retryable_status(self, status: str) -> bool:
        return str(status or "").lower() in self.RETRYABLE_STATUSES

    def _extract_parts(self, key: str, owner_email: str = None, account_email: str = None):
        parts = key.split("::")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        return owner_email or "unknown", account_email or "unknown", key

    def was_processed(self, key: str) -> bool:
        """
        Verifica si un correo ya fue procesado o reservado.
        Solo estados retryables (skipped_ai_limit*) permiten reintento.
        """
        if key in self._local_cache:
            return True

        try:
            doc = self._get_collection().find_one({"_id": key}, {"status": 1})
            if not doc:
                return False

            if self.is_retryable_status(doc.get("status")):
                return False

            self._local_cache[key] = True
            return True
        except Exception as e:
            logger.error(f"Error consultando processed_emails en Mongo: {e}")
            return False

    def was_processed_by_message_id(self, message_id: str, owner_email: str, exclude_key: str = None) -> bool:
        """
        Verifica si un correo ya fue procesado/reservado por su Message-ID.
        """
        if not message_id:
            return False

        try:
            query = {
                "message_id": message_id,
                "owner_email": owner_email,
                "status": {"$nin": list(self.RETRYABLE_STATUSES)},
            }
            if exclude_key:
                query["_id"] = {"$ne": exclude_key}

            doc = self._get_collection().find_one(query, {"_id": 1})
            return doc is not None
        except Exception as e:
            logger.error(f"Error consultando por message_id en Mongo: {e}")
            return False

    def claim_for_processing(
        self,
        key: str,
        owner_email: str = None,
        account_email: str = None,
        message_id: str = None,
        subject: str = None,
        sender: str = None,
        email_date: datetime = None,
        reason: str = None,
    ) -> bool:
        """
        Reserva un correo para procesamiento de forma segura ante concurrencia.
        Solo permite reclamar si no existe o si está en estado retryable.
        """
        owner, account, uid = self._extract_parts(key, owner_email, account_email)
        update_data = {
            "status": "processing",
            "reason": reason or "Reservado para procesamiento",
            "processed_at": datetime.utcnow(),
        }
        if message_id:
            update_data["message_id"] = message_id
        if subject:
            update_data["subject"] = subject
        if sender:
            update_data["sender"] = sender
        if email_date:
            update_data["email_date"] = email_date

        base_data = {
            "owner_email": owner,
            "account_email": account,
            "email_uid": uid,
        }

        coll = self._get_collection()

        # 1) Intento optimista: crear registro nuevo
        try:
            coll.insert_one({"_id": key, **base_data, **update_data})
            self._local_cache[key] = True
            return True
        except DuplicateKeyError:
            pass
        except Exception as e:
            logger.error(f"Error insertando claim de procesamiento: {e}")
            return False

        # 2) Si ya existe, solo reclamamos si su estado permite reintento
        try:
            res = coll.update_one(
                {"_id": key, "status": {"$in": list(self.RETRYABLE_STATUSES)}},
                {"$set": update_data, "$setOnInsert": base_data},
                upsert=False,
            )
            if res.modified_count > 0:
                self._local_cache[key] = True
                return True
            return False
        except Exception as e:
            logger.error(f"Error reclamando correo existente para procesamiento: {e}")
            return False

    def set_message_id(self, key: str, message_id: str) -> None:
        if not message_id:
            return
        try:
            self._get_collection().update_one({"_id": key}, {"$set": {"message_id": message_id}})
        except Exception as e:
            logger.error(f"Error actualizando message_id para key {key}: {e}")

    def mark_processed(
        self,
        key: str,
        status: str = "success",
        reason: str = None,
        owner_email: str = None,
        account_email: str = None,
        message_id: str = None,
        subject: str = None,
        sender: str = None,
        email_date: datetime = None,
    ) -> None:
        """
        Marca un correo como procesado (o skipeado).
        """
        try:
            owner, account, uid = self._extract_parts(key, owner_email, account_email)

            update_data = {
                "status": status,
                "reason": reason,
                "processed_at": datetime.utcnow(),
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
                "email_uid": uid,
            }

            self._get_collection().update_one(
                {"_id": key},
                {
                    "$set": update_data,
                    "$setOnInsert": set_on_insert,
                },
                upsert=True,
            )

            if self.is_retryable_status(status):
                self._local_cache.pop(key, None)
            else:
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


def was_processed_by_message_id(message_id: str, owner_email: str, exclude_key: str = None) -> bool:
    return _repo.was_processed_by_message_id(message_id, owner_email, exclude_key=exclude_key)


def claim_for_processing(
    key: str,
    owner_email: str = None,
    account_email: str = None,
    message_id: str = None,
    subject: str = None,
    sender: str = None,
    email_date: datetime = None,
    reason: str = None,
) -> bool:
    return _repo.claim_for_processing(
        key=key,
        owner_email=owner_email,
        account_email=account_email,
        message_id=message_id,
        subject=subject,
        sender=sender,
        email_date=email_date,
        reason=reason,
    )


def set_message_id(key: str, message_id: str) -> None:
    _repo.set_message_id(key, message_id)


def mark_processed(key: str, status: str = "done", message_id: str = None, reason: str = None, subject: str = None) -> None:
    # Intenta extraer owner y account del key si es posible
    _repo.mark_processed(key, status, message_id=message_id, reason=reason, subject=subject)
