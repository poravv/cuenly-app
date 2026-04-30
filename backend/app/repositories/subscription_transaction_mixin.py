"""
Transaction mixin: registro de pagos e historial paginado de transacciones.
"""
from datetime import datetime
from typing import Any, Dict, Optional
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class _TransactionMixin:

    def record_subscription_payment(
        self,
        sub_id: str,
        amount: float,
        transaction_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Registrar transacción de pago de suscripción."""
        try:
            subscription = self.subscriptions_collection.find_one({"_id": ObjectId(sub_id)})
            if not subscription:
                logger.error(f"Suscripción {sub_id} no encontrada")
                return False

            retry_count = subscription.get("retry_count", 0) + 1
            transaction_data = {
                "subscription_id": str(sub_id),
                "user_email": subscription.get("user_email"),
                "amount": amount,
                "currency": subscription.get("currency", "PYG"),
                "status": status,
                "pagopar_order_hash": transaction_id,
                "pagopar_order_id": transaction_id,
                "error_message": error_message,
                "attempt_number": retry_count,
                "created_at": datetime.utcnow(),
            }
            result = self.transactions_collection.insert_one(transaction_data)
            logger.info(f"💰 Transacción registrada: {transaction_id} - {status}")
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error registrando transacción: {e}")
            return False

    def has_successful_payment_this_month(self, user_email: str, sub_id: Optional[str] = None) -> bool:
        """
        Verificar si existe una transacción exitosa este mes.
        Usado por MonthlyResetService para condicionar el reset de IA al cobro.
        """
        try:
            today = datetime.utcnow()
            month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query: Dict[str, Any] = {
                "user_email": (user_email or "").lower(),
                "status": "success",
                "created_at": {"$gte": month_start},
            }
            if sub_id:
                query["subscription_id"] = sub_id
            return self.transactions_collection.find_one(query) is not None
        except Exception as e:
            logger.error(f"Error verificando pago exitoso de {user_email}: {e}")
            return False

    def get_user_transaction_history(
        self,
        user_email: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Historial paginado de transacciones de un usuario.
        Siempre filtra por user_email (multi-tenant).
        Retorna: {"items": [...], "total": int}
        """
        try:
            self._ensure_indexes()
            user_email = (user_email or "").lower()
            query: Dict[str, Any] = {"user_email": user_email}

            if status:
                query["status"] = status

            if date_from or date_to:
                date_filter: Dict[str, Any] = {}
                if date_from:
                    date_filter["$gte"] = date_from
                if date_to:
                    date_filter["$lte"] = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
                query["created_at"] = date_filter

            total = self.transactions_collection.count_documents(query)
            skip = (page - 1) * limit
            cursor = (
                self.transactions_collection
                .find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            items = []
            for doc in cursor:
                order_hash = doc.get("pagopar_order_hash")
                reference = order_hash[-8:] if order_hash and len(order_hash) >= 8 else order_hash
                created_at = doc.get("created_at")
                created_at_str = (
                    created_at.isoformat() if isinstance(created_at, datetime)
                    else str(created_at) if created_at else None
                )
                items.append({
                    "id": str(doc.get("_id", "")),
                    "amount": doc.get("amount", 0),
                    "currency": doc.get("currency", "PYG"),
                    "status": doc.get("status", "pending"),
                    "created_at": created_at_str,
                    "attempt_number": doc.get("attempt_number", 1),
                    "plan_name": doc.get("plan_name"),
                    "reference": reference,
                    "error_message": doc.get("error_message"),
                })

            return {"items": items, "total": total}
        except Exception as e:
            logger.error(f"Error obteniendo historial de transacciones de {user_email}: {e}")
            return {"items": [], "total": 0}
