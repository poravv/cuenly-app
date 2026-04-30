"""
Payment mixin: métodos de pago (CRUD), billing recurrente y resolución de pagopar_user_id.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class _PaymentMixin:

    # ─── Resolución de pagopar_user_id ───────────────────────────────────────

    def resolve_pagopar_user_id(self, user_email: str) -> Optional[str]:
        """
        Resolver pagopar_user_id buscando en todas las fuentes disponibles.
        Orden: payment_methods → auth_users → suscripción activa.
        Sincroniza automáticamente a payment_methods si falta.
        """
        user_email = (user_email or "").lower()
        pagopar_id = None

        pm = self.get_user_payment_method(user_email)
        if pm:
            pagopar_id = pm.get("pagopar_user_id")

        if not pagopar_id:
            user = self.users_collection.find_one({"email": user_email}, {"pagopar_user_id": 1})
            if user:
                pagopar_id = user.get("pagopar_user_id")

        if not pagopar_id:
            sub = self.subscriptions_collection.find_one(
                {"user_email": user_email, "status": "active"},
                {"pagopar_user_id": 1}
            )
            if sub:
                pagopar_id = sub.get("pagopar_user_id")

        if pagopar_id and (not pm or not pm.get("pagopar_user_id")):
            self.save_payment_method(user_email, pagopar_id, "Bancard")
            logger.info(f"📎 Sincronizado pagopar_user_id a payment_methods para {user_email}")

        return pagopar_id

    # ─── CRUD métodos de pago ────────────────────────────────────────────────

    def get_user_payment_method(self, user_email: str) -> Optional[Dict[str, Any]]:
        try:
            return self.payment_methods_collection.find_one({"user_email": (user_email or "").lower()})
        except Exception as e:
            logger.error(f"Error obteniendo método de pago de {user_email}: {e}")
            return None

    def save_payment_method(self, user_email: str, pagopar_user_id: str, provider: str = "Bancard") -> bool:
        try:
            user_email = (user_email or "").lower()
            now = datetime.utcnow()
            self.payment_methods_collection.update_one(
                {"user_email": user_email},
                {
                    "$set": {
                        "user_email": user_email,
                        "pagopar_user_id": pagopar_user_id,
                        "provider": provider,
                        "confirmed_at": now,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            logger.info(f"💳 Método de pago guardado para {user_email}")
            return True
        except Exception as e:
            logger.error(f"Error guardando método de pago para {user_email}: {e}")
            return False

    def delete_payment_method(self, user_email: str) -> bool:
        try:
            result = self.payment_methods_collection.delete_one({"user_email": (user_email or "").lower()})
            logger.info(f"Método de pago eliminado para {user_email}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error eliminando método de pago de {user_email}: {e}")
            return False

    # ─── Billing recurrente ──────────────────────────────────────────────────

    def get_subscriptions_due_for_billing(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Suscripciones ACTIVE y PAST_DUE cuyo next_billing_date ya venció.
        PAST_DUE son reintentos tras un fallo anterior.
        """
        try:
            if target_date is None:
                target_date = datetime.utcnow()
            query = {
                "status": {"$in": ["active", "past_due"]},
                "next_billing_date": {"$lte": target_date, "$ne": None},
            }
            subs = list(self.subscriptions_collection.find(query).sort("next_billing_date", 1))
            logger.info(f"📅 Encontradas {len(subs)} suscripciones para cobrar")
            return subs
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones para cobrar: {e}")
            return []

    def update_billing_date(self, sub_id: str, next_billing_date: datetime) -> bool:
        """Actualizar fecha de próximo cobro y restaurar status a active."""
        try:
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "active",
                        "next_billing_date": next_billing_date,
                        "last_billing_date": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "retry_count": 0,
                    }
                },
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error actualizando fecha de cobro: {e}")
            return False

    def mark_subscription_past_due(self, sub_id: str, reason: str, retry_count: int = 0) -> bool:
        """Marcar suscripción como morosa."""
        try:
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "past_due",
                        "updated_at": datetime.utcnow(),
                        "last_retry_date": datetime.utcnow(),
                        "retry_count": retry_count,
                        "last_error": reason,
                    }
                },
            )
            logger.warning(f"⚠️ Suscripción {sub_id} marcada como PAST_DUE: {reason}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marcando suscripción como PAST_DUE: {e}")
            return False
