"""
Subscriptions mixin: gestión completa del ciclo de vida de suscripciones.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class _SubscriptionsMixin:

    async def get_user_subscription(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Obtener la suscripción activa de un usuario (sin _id)."""
        try:
            return self.subscriptions_collection.find_one(
                {"user_email": (user_email or "").lower(), "status": "active"},
                {"_id": 0},
            )
        except Exception as e:
            logger.error(f"Error obteniendo suscripción de {user_email}: {e}")
            return None

    async def get_user_active_subscription(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Suscripción activa con detalles de plan y uso de IA."""
        try:
            user_email = (user_email or "").lower()
            subscription = self.subscriptions_collection.find_one(
                {"user_email": user_email, "status": "active"}
            )
            if not subscription:
                return None

            plan = await self.get_plan_by_code(subscription.get("plan_code"))
            user = self.users_collection.find_one({"email": user_email}, {"ai_invoices_processed": 1})

            subscription["monthly_ai_limit"] = (
                plan["features"].get("ai_invoices_limit", 50)
                if plan and plan.get("features")
                else 50
            )
            subscription["current_ai_usage"] = user.get("ai_invoices_processed", 0) if user else 0
            subscription["plan_id"] = subscription.get("plan_code", "unknown")
            subscription["plan_name"] = subscription.get("plan_name", "Plan Desconocido")
            subscription["user_id"] = user_email
            subscription["start_date"] = subscription.get("started_at", subscription.get("created_at"))
            subscription["end_date"] = None
            subscription["is_indefinite"] = True
            return subscription
        except Exception as e:
            logger.error(f"Error obteniendo suscripción activa de {user_email}: {e}")
            return None

    def has_active_subscription(self, user_email: str) -> bool:
        """Versión síncrona y ligera para verificar si existe suscripción activa."""
        try:
            return bool(
                self.subscriptions_collection.find_one(
                    {"user_email": (user_email or "").lower(), "status": "active"},
                    {"_id": 1},
                )
            )
        except Exception as e:
            logger.error(f"Error verificando suscripción activa de {user_email}: {e}")
            return False

    def get_active_subscriptions(self) -> List[Dict[str, Any]]:
        try:
            return list(self.subscriptions_collection.find({"status": "active"}))
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones activas: {e}")
            return []

    async def create_subscription(self, subscription_data: Dict[str, Any]) -> Optional[str]:
        """
        Crear suscripción INDEFINIDA (mes a mes).
        Retorna el ID creado, o None si falla.
        """
        try:
            subscription_data["user_email"] = (subscription_data.get("user_email") or "").lower()
            await self.cancel_user_subscriptions(subscription_data["user_email"])

            now = datetime.utcnow()
            subscription_data.setdefault("billing_day_of_month", now.day)
            subscription_data.setdefault(
                "next_billing_date",
                self.calculate_next_billing_date(now, subscription_data["billing_day_of_month"]),
            )
            subscription_data["created_at"] = now
            subscription_data["updated_at"] = now
            subscription_data["started_at"] = now

            result = self.subscriptions_collection.insert_one(subscription_data)
            await self.update_user_plan_status(
                subscription_data["user_email"],
                subscription_data.get("plan_features", {}),
            )
            logger.info(f"✅ Suscripción INDEFINIDA creada para {subscription_data['user_email']}")
            return str(result.inserted_id) if result.inserted_id else None
        except Exception as e:
            logger.error(f"Error creando suscripción: {e}")
            return None

    async def cancel_user_subscriptions(self, user_email: str, reason: str = "user_request") -> bool:
        """Cancelar todas las suscripciones activas de un usuario."""
        try:
            user_email = (user_email or "").lower()
            result = self.subscriptions_collection.update_many(
                {"user_email": user_email, "status": "active"},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "cancellation_reason": reason,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.modified_count > 0:
                logger.info(f"✅ Canceladas {result.modified_count} suscripciones de {user_email}")
                return True
            logger.info(f"ℹ️ No hay suscripciones activas para cancelar de {user_email}")
            return False
        except Exception as e:
            logger.error(f"Error cancelando suscripciones de {user_email}: {e}")
            return False

    async def cancel_subscription_by_id(
        self, sub_id: str, reason: str = "admin_action", cancelled_by: str = "admin"
    ) -> bool:
        """Cancelar una suscripción específica por ID (acción admin)."""
        try:
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "cancelled_by": cancelled_by,
                        "cancellation_reason": reason,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.modified_count > 0:
                logger.info(f"✅ Suscripción {sub_id} cancelada por {cancelled_by}")
                return True
            logger.warning(f"⚠️ No se pudo cancelar suscripción {sub_id}")
            return False
        except Exception as e:
            logger.error(f"Error cancelando suscripción {sub_id}: {e}")
            return False

    async def update_user_plan_status(self, user_email: str, plan_features: Dict[str, Any]) -> bool:
        """Actualizar campos del usuario al cambiar de plan (quitar trial, resetear IA)."""
        try:
            user_email = (user_email or "").lower()
            update_data = {
                "is_trial_user": False,
                "ai_invoices_limit": plan_features.get("ai_invoices_limit", 50),
                "ai_invoices_processed": 0,
                "last_updated": datetime.utcnow(),
            }
            result = self.users_collection.update_one(
                {"email": user_email},
                {"$set": update_data, "$unset": {"trial_expires_at": ""}},
            )
            if result.modified_count == 0:
                logger.warning(f"⚠️ No se modificó estado de plan para {user_email}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error actualizando estado de plan para {user_email}: {e}")
            return False

    async def get_subscription_stats(self) -> Dict[str, Any]:
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$plan_code",
                        "plan_name": {"$first": "$plan_name"},
                        "total_subscriptions": {"$sum": 1},
                        "active_subscriptions": {
                            "$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}
                        },
                        "total_revenue": {"$sum": "$plan_price"},
                        "avg_price": {"$avg": "$plan_price"},
                    }
                },
                {"$sort": {"total_subscriptions": -1}},
            ]
            plan_stats = list(self.subscriptions_collection.aggregate(pipeline))

            total = self.subscriptions_collection.count_documents({})
            active = self.subscriptions_collection.count_documents({"status": "active"})
            revenue_agg = list(
                self.subscriptions_collection.aggregate(
                    [{"$group": {"_id": None, "total": {"$sum": "$plan_price"}}}]
                )
            )
            total_revenue = revenue_agg[0]["total"] if revenue_agg else 0

            return {
                "total_subscriptions": total,
                "active_subscriptions": active,
                "total_revenue": total_revenue,
                "plan_stats": plan_stats,
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de suscripciones: {e}")
            return {}

    async def get_user_subscriptions_history(self, user_email: str) -> List[Dict[str, Any]]:
        try:
            subs = list(
                self.subscriptions_collection.find({"user_email": user_email}, {"_id": 0}).sort("created_at", -1)
            )
            for s in subs:
                s.setdefault("plan_name", s.get("plan_code", "Plan"))
                s["start_date"] = s.get("started_at") or s.get("created_at")
                s["end_date"] = s.get("cancelled_at") or s.get("expires_at")
            return subs
        except Exception as e:
            logger.error(f"Error obteniendo historial de suscripciones para {user_email}: {e}")
            return []

    async def get_subscriptions_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        plan_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            query: Dict[str, Any] = {"created_at": {"$gte": start_date, "$lte": end_date}}
            if plan_code:
                query["plan_code"] = plan_code
            return list(self.subscriptions_collection.find(query, {"_id": 0}).sort("created_at", -1))
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones por fecha: {e}")
            return []

    async def assign_plan_to_user(
        self, user_email: str, plan_code: str, payment_method: str = "manual", **kwargs
    ) -> bool:
        """Asignar plan a un usuario (uso admin)."""
        try:
            user_email = (user_email or "").lower()
            plan = await self.get_plan_by_code(plan_code)
            if not plan:
                logger.error(f"Plan no encontrado: {plan_code}")
                return False

            pagopar_user_id = kwargs.get("pagopar_user_id")
            if not pagopar_user_id:
                user = self.users_collection.find_one({"email": user_email}, {"pagopar_user_id": 1})
                pagopar_user_id = (user or {}).get("pagopar_user_id")
            if not pagopar_user_id:
                pm = self.get_user_payment_method(user_email)
                pagopar_user_id = (pm or {}).get("pagopar_user_id")

            if pagopar_user_id:
                existing_pm = self.get_user_payment_method(user_email)
                if not existing_pm or not existing_pm.get("pagopar_user_id"):
                    self.save_payment_method(user_email, pagopar_user_id, "Bancard")

            subscription_data: Dict[str, Any] = {
                "user_email": user_email,
                "plan_code": plan_code,
                "plan_name": plan["name"],
                "plan_price": plan["price"],
                "currency": plan["currency"],
                "billing_period": plan["billing_period"],
                "plan_features": plan.get("features", {}),
                "status": "active",
                "payment_method": payment_method,
                "payment_reference": kwargs.get(
                    "payment_reference",
                    f"admin_assigned_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                ),
            }
            if pagopar_user_id:
                subscription_data["pagopar_user_id"] = pagopar_user_id
            subscription_data.update(kwargs)

            return bool(await self.create_subscription(subscription_data))
        except Exception as e:
            logger.error(f"Error asignando plan {plan_code} a {user_email}: {e}")
            return False
