"""
FirestoreAdminRepository — Gestión de administradores en Firestore.

Colección: `admins` (doc ID = email en minúsculas).
Cache: Redis con TTL de 60s para lookups frecuentes (is_admin).
Soft-delete: revoke_admin marca revoked=True; preserva historial completo.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.firebase_admin_client import get_firestore_client
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

ADMIN_CACHE_TTL = 60  # segundos
ADMIN_CACHE_PREFIX = "admin:lookup:"
ADMINS_COLLECTION = "admins"


def _cache_key(email: str) -> str:
    return f"{ADMIN_CACHE_PREFIX}{email.lower()}"


class FirestoreAdminRepository:
    """Repositorio de admins respaldado por Firestore con cache Redis."""

    def is_admin(self, email: str) -> bool:
        """
        Verifica si el email corresponde a un admin activo.

        Primero consulta Redis (TTL 60s); si hay cache miss, consulta Firestore
        y escribe el resultado en cache.

        Args:
            email: Email del usuario a verificar.

        Returns:
            True si el usuario es admin activo, False en cualquier otro caso.
            Si Firestore falla, retorna False (denegar acceso es más seguro).
        """
        email = email.lower()
        try:
            redis = get_redis_client()
            cached = redis.get(_cache_key(email))
            if cached is not None:
                return cached == "1"
        except Exception as e:
            logger.debug("Redis no disponible para lookup admin: %s", e)

        # Cache miss — consultar Firestore
        try:
            db = get_firestore_client()
            doc = db.collection(ADMINS_COLLECTION).document(email).get()
            result = doc.exists and not doc.to_dict().get("revoked", False)
            try:
                redis = get_redis_client()
                redis.setex(_cache_key(email), ADMIN_CACHE_TTL, "1" if result else "0")
            except Exception:
                pass
            return result
        except Exception as e:
            logger.error("Error verificando admin en Firestore para %s: %s", email, e)
            return False  # Denegar acceso si Firestore falla — más seguro

    def grant_admin(
        self,
        email: str,
        granted_by: str,
        uid: str = "",
        notes: str = "",
    ) -> bool:
        """
        Promueve un email a admin. Crea o sobreescribe el documento en Firestore.

        Args:
            email: Email a promover.
            granted_by: Email o identificador de quien otorga el permiso.
            uid: UID de Firebase del usuario (opcional, informativo).
            notes: Nota libre sobre el motivo de la concesión.

        Returns:
            True si la operación fue exitosa, False si hubo error.
        """
        email = email.lower()
        try:
            db = get_firestore_client()
            db.collection(ADMINS_COLLECTION).document(email).set({
                "email": email,
                "granted_by": granted_by,
                "granted_at": datetime.now(timezone.utc),
                "revoked": False,
                "revoked_by": None,
                "revoked_at": None,
                "notes": notes,
                "uid": uid,
            })
            self._invalidate_cache(email)
            logger.info("Admin otorgado: %s por %s", email, granted_by)
            return True
        except Exception as e:
            logger.error("Error otorgando admin a %s: %s", email, e)
            return False

    def revoke_admin(self, email: str, revoked_by: str) -> bool:
        """
        Revoca un admin (soft-delete). Preserva historial completo.

        Args:
            email: Email del admin a revocar.
            revoked_by: Email o identificador de quien revoca.

        Returns:
            True si la operación fue exitosa, False si hubo error.
        """
        email = email.lower()
        try:
            db = get_firestore_client()
            db.collection(ADMINS_COLLECTION).document(email).update({
                "revoked": True,
                "revoked_by": revoked_by,
                "revoked_at": datetime.now(timezone.utc),
            })
            self._invalidate_cache(email)
            logger.info("Admin revocado: %s por %s", email, revoked_by)
            return True
        except Exception as e:
            logger.error("Error revocando admin %s: %s", email, e)
            return False

    def list_admins(self) -> List[Dict]:
        """
        Lista todos los admins activos (revoked=False).

        Returns:
            Lista de dicts con los datos de cada admin activo.
        """
        try:
            db = get_firestore_client()
            docs = db.collection(ADMINS_COLLECTION).where("revoked", "==", False).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error("Error listando admins: %s", e)
            return []

    def get_active_admin_count(self) -> int:
        """
        Cuenta admins activos. Usado para protección anti-lockout.

        Returns:
            Número de admins con revoked=False.
        """
        return len(self.list_admins())

    def has_any_admin(self) -> bool:
        """
        Verifica si existe al menos un admin activo en Firestore.

        Returns:
            True si existe al menos un admin activo.
            En caso de error de Firestore retorna True (conservador: evita re-bootstrap).
        """
        try:
            db = get_firestore_client()
            docs = list(
                db.collection(ADMINS_COLLECTION)
                .where("revoked", "==", False)
                .limit(1)
                .stream()
            )
            return len(docs) > 0
        except Exception as e:
            logger.error("Error verificando existencia de admins: %s", e)
            return True  # Conservador: asumir que existe para no re-bootstrappear

    def _invalidate_cache(self, email: str) -> None:
        """Elimina el registro Redis para forzar re-consulta a Firestore."""
        try:
            redis = get_redis_client()
            redis.delete(_cache_key(email))
        except Exception:
            pass
