"""
Repository para gestión de planes de suscripción y suscripciones de usuarios.
"""

import calendar
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pymongo import MongoClient
from bson import ObjectId
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class SubscriptionRepository:
    _indexes_ensured: bool = False

    def __init__(self, conn_str: Optional[str] = None, db_name: Optional[str] = None):
        self.conn_str = conn_str or settings.MONGODB_URL
        self.db_name = db_name or settings.MONGODB_DATABASE
        self._client: Optional[MongoClient] = None

    def _get_db(self):
        """Obtener la base de datos MongoDB."""
        if not self._client:
            self._client = MongoClient(self.conn_str, serverSelectionTimeoutMS=60000)
            self._client.admin.command('ping')
        return self._client[self.db_name]

    @property
    def plans_collection(self):
        return self._get_db().subscription_plans

    @property
    def subscriptions_collection(self):
        return self._get_db().user_subscriptions

    @property
    def users_collection(self):
        return self._get_db().auth_users

    @property
    def payment_methods_collection(self):
        return self._get_db().payment_methods

    @property
    def transactions_collection(self):
        return self._get_db().subscription_transactions

    def _ensure_indexes(self):
        """Crear índices una sola vez por proceso."""
        if SubscriptionRepository._indexes_ensured:
            return
        try:
            self.subscriptions_collection.create_index([("user_email", 1)])
            self.subscriptions_collection.create_index([("status", 1), ("next_billing_date", 1)])
            self.subscriptions_collection.create_index([("pagopar_user_id", 1)])

            self.payment_methods_collection.create_index([("user_email", 1)], unique=True)
            self.payment_methods_collection.create_index([("pagopar_user_id", 1)])

            self.transactions_collection.create_index([("subscription_id", 1)])
            self.transactions_collection.create_index([("user_email", 1)])
            self.transactions_collection.create_index([("created_at", -1)])

            SubscriptionRepository._indexes_ensured = True
            logger.info("Índices de suscripciones creados/verificados")
        except Exception as e:
            logger.warning(f"Error creando índices: {e}")

    # =====================================
    # CÁLCULO DE FECHA DE COBRO POR ANIVERSARIO
    # =====================================

    @staticmethod
    def calculate_next_billing_date(from_date: datetime, billing_day: int) -> datetime:
        """
        Calcula la próxima fecha de cobro basada en el día de aniversario.
        Si billing_day=31 y el mes tiene 28 días, usa día 28.
        Ej: suscrito el 31 → ene31, feb28, mar31, abr30...
        """
        if from_date.month == 12:
            next_month, next_year = 1, from_date.year + 1
        else:
            next_month, next_year = from_date.month + 1, from_date.year
        max_day = calendar.monthrange(next_year, next_month)[1]
        actual_day = min(billing_day, max_day)
        return datetime(next_year, next_month, actual_day, 0, 0, 0)

    # =====================================
    # RESOLUCIÓN DE PAGOPAR USER ID
    # =====================================

    def resolve_pagopar_user_id(self, user_email: str) -> Optional[str]:
        """
        Resolver pagopar_user_id buscando en todas las fuentes disponibles.
        Orden: payment_methods → auth_users → suscripción activa.
        Sincroniza automáticamente a payment_methods si falta.
        """
        user_email = (user_email or "").lower()
        pagopar_id = None

        # 1. payment_methods (fuente principal para billing)
        pm = self.get_user_payment_method(user_email)
        if pm:
            pagopar_id = pm.get("pagopar_user_id")

        # 2. auth_users
        if not pagopar_id:
            user = self.users_collection.find_one({"email": user_email}, {"pagopar_user_id": 1})
            if user:
                pagopar_id = user.get("pagopar_user_id")

        # 3. suscripción activa
        if not pagopar_id:
            sub = self.subscriptions_collection.find_one(
                {"user_email": user_email, "status": "active"},
                {"pagopar_user_id": 1}
            )
            if sub:
                pagopar_id = sub.get("pagopar_user_id")

        # Sincronizar a payment_methods si encontramos en otra fuente
        if pagopar_id and (not pm or not pm.get("pagopar_user_id")):
            self.save_payment_method(user_email, pagopar_id, "Bancard")
            logger.info(f"📎 Sincronizado pagopar_user_id a payment_methods para {user_email}")

        return pagopar_id

    # =====================================
    # GESTIÓN DE MÉTODOS DE PAGO
    # =====================================

    def get_user_payment_method(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Obtener método de pago del usuario."""
        try:
            user_email = (user_email or "").lower()
            payment_method = self.payment_methods_collection.find_one(
                {"user_email": user_email}
            )
            return payment_method
        except Exception as e:
            logger.error(f"Error obteniendo método de pago de {user_email}: {e}")
            return None

    def save_payment_method(
        self, 
        user_email: str, 
        pagopar_user_id: str, 
        provider: str = "Bancard"
    ) -> bool:
        """Guardar o actualizar método de pago del usuario."""
        try:
            user_email = (user_email or "").lower()
            payment_data = {
                "user_email": user_email,
                "pagopar_user_id": pagopar_user_id,
                "provider": provider,
                "confirmed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = self.payment_methods_collection.update_one(
                {"user_email": user_email},
                {
                    "$set": payment_data,
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                },
                upsert=True
            )
            
            logger.info(f"💳 Método de pago guardado para {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando método de pago para {user_email}: {e}")
            return False

    def delete_payment_method(self, user_email: str) -> bool:
        """Eliminar método de pago del usuario."""
        try:
            user_email = (user_email or "").lower()
            result = self.payment_methods_collection.delete_one(
                {"user_email": user_email}
            )
            logger.info(f"Método de pago eliminado para {user_email}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error eliminando método de pago de {user_email}: {e}")
            return False

    # =====================================
    # MÉTODOS PARA COBROS RECURRENTES
    # =====================================

    def get_subscriptions_due_for_billing(
        self,
        target_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtener suscripciones que deben cobrarse.
        Incluye suscripciones ACTIVE y PAST_DUE cuyo next_billing_date ya venció.
        PAST_DUE son reintentos programados tras un fallo de pago anterior.
        """
        try:
            if target_date is None:
                target_date = datetime.utcnow()

            query = {
                "status": {"$in": ["active", "past_due"]},
                "next_billing_date": {"$lte": target_date, "$ne": None}
            }
            
            subscriptions = list(
                self.subscriptions_collection.find(query).sort("next_billing_date", 1)
            )
            
            logger.info(f"📅 Encontradas {len(subscriptions)} suscripciones para cobrar")
            return subscriptions
            
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones para cobrar: {e}")
            return []

    def update_billing_date(
        self,
        sub_id: str,
        next_billing_date: datetime
    ) -> bool:
        """Actualizar fecha de próximo cobro y restaurar status a active."""
        try:
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "active",  # Restaurar a activo tras cobro exitoso
                        "next_billing_date": next_billing_date,
                        "last_billing_date": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "retry_count": 0
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error actualizando fecha de cobro: {e}")
            return False

    def mark_subscription_past_due(
        self, 
        sub_id: str, 
        reason: str,
        retry_count: int = 0
    ) -> bool:
        """Marcar suscripción como morosa."""
        try:
            update_data = {
                "status": "past_due",
                "updated_at": datetime.utcnow(),
                "last_retry_date": datetime.utcnow(),
                "retry_count": retry_count,
                "last_error": reason
            }
            
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {"$set": update_data}
            )
            
            logger.warning(f"⚠️ Suscripción {sub_id} marcada como PAST_DUE: {reason}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error marcando suscripción como PAST_DUE: {e}")
            return False

    def record_subscription_payment(
        self,
        sub_id: str,
        amount: float,
        transaction_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Registrar transacción de pago de suscripción."""
        try:
            # Obtener datos de la suscripción
            subscription = self.subscriptions_collection.find_one(
                {"_id": ObjectId(sub_id)}
            )
            
            if not subscription:
                logger.error(f"Suscripción {sub_id} no encontrada")
                return False
            
            # Obtener retry count actual
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
                "created_at": datetime.utcnow()
            }
            
            result = self.transactions_collection.insert_one(transaction_data)
            logger.info(f"💰 Transacción registrada: {transaction_id} - {status}")
            return bool(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error registrando transacción: {e}")
            return False

    def has_successful_payment_this_month(
        self,
        user_email: str,
        sub_id: Optional[str] = None
    ) -> bool:
        """
        Verificar si existe una transacción exitosa este mes para el usuario.
        Usado por MonthlyResetService para condicionar el reset de IA al cobro.
        """
        try:
            today = datetime.utcnow()
            month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            query = {
                "user_email": (user_email or "").lower(),
                "status": "success",
                "created_at": {"$gte": month_start}
            }

            if sub_id:
                query["subscription_id"] = sub_id

            payment = self.transactions_collection.find_one(query)
            return payment is not None

        except Exception as e:
            logger.error(f"Error verificando pago exitoso de {user_email}: {e}")
            return False

    # =====================================
    # GESTIÓN DE PLANES
    # ====================================='
    
    async def get_all_plans(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Obtener todos los planes de suscripción."""
        try:
            query = {}
            if not include_inactive:
                query["status"] = "active"
            
            plans = list(self.plans_collection.find(
                query,
                {"_id": 0}  # Excluir _id de MongoDB
            ).sort("sort_order", 1))
            
            logger.info(f"Obtenidos {len(plans)} planes")
            return plans
            
        except Exception as e:
            logger.error(f"Error obteniendo planes: {e}")
            return []
    
    async def get_plan_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Obtener un plan específico por código."""
        try:
            plan = self.plans_collection.find_one(
                {"code": code},
                {"_id": 0}
            )
            return plan
            
        except Exception as e:
            logger.error(f"Error obteniendo plan {code}: {e}")
            return None
    
    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Obtener un plan específico por ID."""
        try:
            from bson import ObjectId
            plan = self.plans_collection.find_one(
                {"_id": ObjectId(plan_id)},
                {"_id": 0}
            )
            return plan
            
        except Exception as e:
            logger.error(f"Error obteniendo plan {plan_id}: {e}")
            return None
    
    async def create_plan(self, plan_data: Dict[str, Any]) -> bool:
        """Crear un nuevo plan."""
        try:
            plan_data["created_at"] = datetime.utcnow()
            plan_data["updated_at"] = datetime.utcnow()
            
            result = self.plans_collection.insert_one(plan_data)
            logger.info(f"Plan creado: {plan_data['code']}")
            return bool(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creando plan: {e}")
            return False
    
    async def update_plan(self, code: str, plan_data: Dict[str, Any]) -> bool:
        """Actualizar un plan existente."""
        try:
            plan_data["updated_at"] = datetime.utcnow()
            
            result = self.plans_collection.update_one(
                {"code": code},
                {"$set": plan_data}
            )
            
            logger.info(f"Plan actualizado: {code}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error actualizando plan {code}: {e}")
            return False
    
    async def delete_plan(self, code: str) -> bool:
        """Eliminar un plan (soft delete)."""
        try:
            result = self.plans_collection.update_one(
                {"code": code},
                {"$set": {"status": "deprecated", "updated_at": datetime.utcnow()}}
            )
            
            logger.info(f"Plan eliminado: {code}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error eliminando plan {code}: {e}")
            return False

    # =====================================
    # GESTIÓN DE SUSCRIPCIONES
    # =====================================
    
    async def get_user_subscription(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Obtener la suscripción activa de un usuario."""
        try:
            user_email = (user_email or "").lower()
            subscription = self.subscriptions_collection.find_one(
                {
                    "user_email": user_email,
                    "status": "active"
                },
                {"_id": 0}
            )
            return subscription

        except Exception as e:
            logger.error(f"Error obteniendo suscripción de {user_email}: {e}")
            return None

    async def get_user_active_subscription(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Obtener la suscripción activa de un usuario con detalles completos."""
        try:
            user_email = (user_email or "").lower()
            # Obtener la suscripción activa (INDEFINIDA - no verificar expires_at)
            subscription = self.subscriptions_collection.find_one(
                {
                    "user_email": user_email,
                    "status": "active"
                }
                # No excluir _id para poder identificar la suscripción
            )
            
            if not subscription:
                return None
                
            # Si encontramos una suscripción, agregar información adicional
            # Obtener el plan actual para obtener el límite correcto
            plan = await self.get_plan_by_code(subscription.get("plan_code"))
            
            # Obtener uso actual de IA del usuario
            user = self.users_collection.find_one({"email": user_email}, {"ai_invoices_processed": 1})
            
            # Usar límite del plan, no del usuario
            if plan and plan.get("features"):
                subscription["monthly_ai_limit"] = plan["features"].get("ai_invoices_limit", 50)
            else:
                subscription["monthly_ai_limit"] = 50
                
            # Uso actual del usuario
            if user:
                subscription["current_ai_usage"] = user.get("ai_invoices_processed", 0)
            else:
                subscription["current_ai_usage"] = 0
            
            # Agregar información del plan si es necesario
            subscription["plan_id"] = subscription.get("plan_code", "unknown")
            subscription["plan_name"] = subscription.get("plan_name", "Plan Desconocido")
            subscription["user_id"] = user_email  # Usar email como user_id
            subscription["start_date"] = subscription.get("started_at", subscription.get("created_at"))
            # No hay end_date - suscripción indefinida
            subscription["end_date"] = None
            subscription["is_indefinite"] = True  # Flag para el frontend
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error obteniendo suscripción activa de {user_email}: {e}")
            return None

    def has_active_subscription(self, user_email: str) -> bool:
        """Versión síncrona y ligera para verificar si existe una suscripción activa."""
        try:
            user_email = (user_email or "").lower()
            s = self.subscriptions_collection.find_one(
                {
                    "user_email": user_email,
                    "status": "active"
                },
                {"_id": 1}
            )
            return bool(s)
        except Exception as e:
            logger.error(f"Error verificando suscripción activa de {user_email}: {e}")
            return False
    
    def get_active_subscriptions(self) -> List[Dict[str, Any]]:
        """Obtener todas las suscripciones activas."""
        try:
            return list(self.subscriptions_collection.find({"status": "active"}))
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones activas: {e}")
            return []

    async def create_subscription(self, subscription_data: Dict[str, Any]) -> Optional[str]:
        """
        Crear una nueva suscripción INDEFINIDA (mes a mes).
        No tiene fecha de expiración, solo se cobra mensualmente.
        Retorna el ID de la suscripción creada, o None si falló.
        """
        try:
            # Normalizar email
            subscription_data["user_email"] = (subscription_data.get("user_email") or "").lower()
            # Cancelar suscripciones activas existentes
            await self.cancel_user_subscriptions(subscription_data["user_email"])
            
            subscription_data["created_at"] = datetime.utcnow()
            subscription_data["updated_at"] = datetime.utcnow()
            subscription_data["started_at"] = datetime.utcnow()

            # Guardar día de aniversario para cobros futuros
            if "billing_day_of_month" not in subscription_data:
                subscription_data["billing_day_of_month"] = datetime.utcnow().day

            # Calcular próximo cobro usando aniversario (no +30 días fijos)
            if "next_billing_date" not in subscription_data:
                subscription_data["next_billing_date"] = self.calculate_next_billing_date(
                    datetime.utcnow(), subscription_data["billing_day_of_month"]
                )
            
            # No establecer expires_at - la suscripción es indefinida
            # Se mantendrá activa hasta que el usuario o admin la cancele
            
            # Asegurar que guardamos el token de tarjeta si existe
            if "pagopar_card_token" in subscription_data:
                 logger.info(f"💾 Guardando token de tarjeta para cobros recurrentes de {subscription_data['user_email']}")

            result = self.subscriptions_collection.insert_one(subscription_data)
            
            # Actualizar el usuario para remover trial
            await self.update_user_plan_status(
                subscription_data["user_email"],
                subscription_data.get("plan_features", {})
            )
            
            logger.info(f"✅ Suscripción INDEFINIDA creada para {subscription_data['user_email']}")
            return str(result.inserted_id) if result.inserted_id else None
            
        except Exception as e:
            logger.error(f"Error creando suscripción: {e}")
            return None
    
    async def cancel_user_subscriptions(self, user_email: str, reason: str = "user_request") -> bool:
        """
        Cancelar (anular) todas las suscripciones activas de un usuario.
        Puede ser por solicitud del usuario o acción del admin.
        Returns True if any subscriptions were cancelled, False otherwise.
        """
        try:
            user_email = (user_email or "").lower()
            result = self.subscriptions_collection.update_many(
                {
                    "user_email": user_email,
                    "status": "active"
                },
                {
                    "$set": {
                        "status": "cancelled",  # lowercase per MongoDB schema
                        "cancelled_at": datetime.utcnow(),
                        "cancellation_reason": reason,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Canceladas {result.modified_count} suscripciones de {user_email} - Razón: {reason}")
                return True
            else:
                logger.info(f"ℹ️ No se encontraron suscripciones activas para cancelar de {user_email}")
                return False
            
        except Exception as e:
            logger.error(f"Error cancelando suscripciones de {user_email}: {e}")
            return False
    
    async def cancel_subscription_by_id(
        self, 
        sub_id: str, 
        reason: str = "admin_action",
        cancelled_by: str = "admin"
    ) -> bool:
        """
        Cancelar/anular una suscripción específica por ID.
        Usado por admin para anular manualmente suscripciones.
        """
        try:
            from bson import ObjectId
            result = self.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "cancelled_by": cancelled_by,  # "user" o "admin"
                        "cancellation_reason": reason,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Suscripción {sub_id} cancelada por {cancelled_by} - Razón: {reason}")
                return True
            else:
                logger.warning(f"⚠️ No se pudo cancelar suscripción {sub_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelando suscripción {sub_id}: {e}")
            return False
    
    async def update_user_plan_status(self, user_email: str, plan_features: Dict[str, Any]) -> bool:
        """Actualizar el estado del plan del usuario."""
        try:
            user_email = (user_email or "").lower()
            
            # Log estado antes de actualizar
            current_user = self.users_collection.find_one({"email": user_email})
            logger.info(f"🔍 Usuario ANTES de actualizar plan {user_email}: is_trial_user={current_user.get('is_trial_user') if current_user else 'NO_FOUND'}")
            
            update_data = {
                "is_trial_user": False,
                # No actualizar trial_expires_at para evitar error de validación del schema
                "ai_invoices_limit": plan_features.get("ai_invoices_limit", 50),
                "ai_invoices_processed": 0,  # Reset AI usage on new plan
                "last_updated": datetime.utcnow()
            }
            
            logger.info(f"🔧 Actualizando usuario {user_email} con datos: {update_data}")
            
            # Usar una operación combinada: $set para campos a actualizar, $unset para remover trial_expires_at
            result = self.users_collection.update_one(
                {"email": user_email},
                {
                    "$set": update_data,
                    "$unset": {"trial_expires_at": ""}  # Remover el campo para evitar conflictos de schema
                }
            )
            
            # Log estado después de actualizar
            updated_user = self.users_collection.find_one({"email": user_email})
            logger.info(f"✅ Usuario DESPUÉS de actualizar plan {user_email}: is_trial_user={updated_user.get('is_trial_user') if updated_user else 'NO_FOUND'}")
            
            if result.modified_count == 0:
                logger.warning(f"⚠️ No se modificó el estado de plan para {user_email} (matched: {result.matched_count}, modified: {result.modified_count})")
            else:
                logger.info(f"✅ Estado de plan actualizado exitosamente para {user_email}")
                
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error actualizando estado de plan para {user_email}: {e}")
            return False

    # =====================================
    # ESTADÍSTICAS Y REPORTES
    # =====================================
    
    async def get_subscription_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de suscripciones."""
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
                        "avg_price": {"$avg": "$plan_price"}
                    }
                },
                {
                    "$sort": {"total_subscriptions": -1}
                }
            ]
            
            plan_stats = list(self.subscriptions_collection.aggregate(pipeline))
            
            # Estadísticas generales
            total_subscriptions = self.subscriptions_collection.count_documents({})
            active_subscriptions = self.subscriptions_collection.count_documents({"status": "active"})
            total_revenue = list(self.subscriptions_collection.aggregate([
                {"$group": {"_id": None, "total": {"$sum": "$plan_price"}}}
            ]))
            total_revenue = total_revenue[0]["total"] if total_revenue else 0
            
            return {
                "total_subscriptions": total_subscriptions,
                "active_subscriptions": active_subscriptions,
                "total_revenue": total_revenue,
                "plan_stats": plan_stats
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de suscripciones: {e}")
            return {}
    
    async def get_user_subscriptions_history(self, user_email: str) -> List[Dict[str, Any]]:
        """Obtener historial de suscripciones de un usuario."""
        try:
            subscriptions = list(self.subscriptions_collection.find(
                {"user_email": user_email},
                {"_id": 0}
            ).sort("created_at", -1))
            # Normalizar campos para frontend
            for s in subscriptions:
                s.setdefault("plan_name", s.get("plan_code", "Plan"))
                s["start_date"] = s.get("started_at") or s.get("created_at")
                end = s.get("cancelled_at") or s.get("expires_at")
                s["end_date"] = end
            return subscriptions
            
        except Exception as e:
            logger.error(f"Error obteniendo historial de suscripciones para {user_email}: {e}")
            return []
    
    # =====================================
    # FILTROS Y BÚSQUEDAS AVANZADAS
    # =====================================
    
    async def get_subscriptions_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        plan_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtener suscripciones por rango de fechas."""
        try:
            query = {
                "created_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
            
            if plan_code:
                query["plan_code"] = plan_code
            
            subscriptions = list(self.subscriptions_collection.find(
                query,
                {"_id": 0}
            ).sort("created_at", -1))
            
            return subscriptions
            
        except Exception as e:
            logger.error(f"Error obteniendo suscripciones por fecha: {e}")
            return []
    
    async def assign_plan_to_user(self, user_email: str, plan_code: str, payment_method: str = "manual", **kwargs) -> bool:
        """Asignar un plan a un usuario específico (para admin)."""
        try:
            user_email = (user_email or "").lower()
            # Obtener información del plan
            plan = await self.get_plan_by_code(plan_code)
            if not plan:
                logger.error(f"Plan no encontrado: {plan_code}")
                return False
            
            # Sincronizar pagopar_user_id: buscar en auth_users y garantizar
            # que esté en payment_methods y en la suscripción para billing
            pagopar_user_id = kwargs.get("pagopar_user_id")
            if not pagopar_user_id:
                user = self.users_collection.find_one({"email": user_email}, {"pagopar_user_id": 1})
                pagopar_user_id = (user or {}).get("pagopar_user_id")
            if not pagopar_user_id:
                pm = self.get_user_payment_method(user_email)
                pagopar_user_id = (pm or {}).get("pagopar_user_id")

            # Si encontramos pagopar_user_id, asegurar que exista en payment_methods
            if pagopar_user_id:
                existing_pm = self.get_user_payment_method(user_email)
                if not existing_pm or not existing_pm.get("pagopar_user_id"):
                    self.save_payment_method(user_email, pagopar_user_id, "Bancard")
                    logger.info(f"📎 Sincronizado pagopar_user_id a payment_methods para {user_email}")

            subscription_data = {
                "user_email": user_email,
                "plan_code": plan_code,
                "plan_name": plan["name"],
                "plan_price": plan["price"],
                "currency": plan["currency"],
                "billing_period": plan["billing_period"],
                "plan_features": plan.get("features", {}),
                "status": "active",
                "payment_method": payment_method,
                "payment_reference": kwargs.get("payment_reference", f"admin_assigned_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
            }

            # Incluir pagopar_user_id en la suscripción si disponible
            if pagopar_user_id:
                subscription_data["pagopar_user_id"] = pagopar_user_id

            # Merge extra data
            subscription_data.update(kwargs)

            return await self.create_subscription(subscription_data)
            
        except Exception as e:
            logger.error(f"Error asignando plan {plan_code} a {user_email}: {e}")
            return False
