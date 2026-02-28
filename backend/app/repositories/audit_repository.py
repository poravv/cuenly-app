"""
Repositorio de auditoría para operaciones administrativas.

Registra en la colección `admin_audit_log` cualquier acción sensible
realizada por un administrador (cambio de rol, suspensión, reset de IA, etc.).
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AuditRepository:
    COLLECTION = "admin_audit_log"
    _indexes_ensured: bool = False

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None

    def _get_collection(self):
        if not self._client:
            self._client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        coll = self._client[settings.MONGODB_DATABASE][self.COLLECTION]
        if not AuditRepository._indexes_ensured:
            try:
                coll.create_index([("timestamp", DESCENDING)])
                coll.create_index("admin_email")
                coll.create_index("target_user")
                coll.create_index("action")
                AuditRepository._indexes_ensured = True
            except Exception:
                pass
        return coll

    def log(
        self,
        action: str,
        admin_email: str,
        target_user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Registra una acción administrativa. Fire-and-forget: nunca lanza excepciones.

        Args:
            action: Identificador del evento, p.ej. "user_role_changed", "user_suspended".
            admin_email: Email del administrador que ejecutó la acción.
            target_user: Email del usuario afectado (si aplica).
            details: Datos extra relevantes (old_role, new_role, reason, etc.).
            ip_address: IP del cliente (si disponible).
        """
        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "action": action,
                "admin_email": admin_email,
                "target_user": target_user,
                "details": details or {},
                "ip_address": ip_address,
            }
            self._get_collection().insert_one(doc)
            logger.debug(f"[AUDIT] {admin_email} → {action} (target={target_user})")
        except Exception as exc:
            # Nunca interrumpir el flujo principal por un fallo de auditoría
            logger.warning(f"[AUDIT] No se pudo registrar evento '{action}': {exc}")

    def get_logs(
        self,
        page: int = 1,
        page_size: int = 30,
        action: Optional[str] = None,
        admin_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Consulta paginada del audit log con filtros opcionales."""
        coll = self._get_collection()
        query: Dict[str, Any] = {}
        if action:
            query["action"] = action
        if admin_email:
            query["admin_email"] = admin_email

        total = coll.count_documents(query)
        skip = (page - 1) * page_size
        docs = list(
            coll.find(query)
            .sort("timestamp", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )

        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            if isinstance(doc.get("timestamp"), datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()

        return {
            "logs": docs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }


# Singleton ligero — reutiliza conexión MongoDB
_audit_repo: Optional[AuditRepository] = None


def get_audit_repo() -> AuditRepository:
    global _audit_repo
    if _audit_repo is None:
        _audit_repo = AuditRepository()
    return _audit_repo
