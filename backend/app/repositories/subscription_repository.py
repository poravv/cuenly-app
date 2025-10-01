"""
Repository para gestión de planes de suscripción y suscripciones de usuarios.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pymongo import MongoClient
from bson import ObjectId
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class SubscriptionRepository:
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

    # =====================================
    # GESTIÓN DE PLANES
    # =====================================
    
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
            # Obtener la suscripción activa
            subscription = self.subscriptions_collection.find_one(
                {
                    "user_email": user_email,
                    "status": "active",
                    "expires_at": {"$gt": datetime.utcnow()}  # No expirada
                },
                {"_id": 0}
            )
            
            if not subscription:
                return None
                
            # Si encontramos una suscripción, agregar información adicional
            # Obtener el plan actual para obtener el límite correcto
            plan = await self.get_plan_by_code(subscription.get("plan_code"))
            
            # Obtener uso actual de IA del usuario
            user = self.users_collection.find_one({"email": user_email}, {"ai_invoices_used": 1})
            
            # Usar límite del plan, no del usuario
            if plan and plan.get("features"):
                subscription["monthly_ai_limit"] = plan["features"].get("ai_invoices_limit", 50)
            else:
                subscription["monthly_ai_limit"] = 50
                
            # Uso actual del usuario
            if user:
                subscription["current_ai_usage"] = user.get("ai_invoices_used", 0)
            else:
                subscription["current_ai_usage"] = 0
            
            # Agregar información del plan si es necesario
            subscription["plan_id"] = subscription.get("plan_code", "unknown")
            subscription["plan_name"] = subscription.get("plan_name", "Plan Desconocido")
            subscription["user_id"] = user_email  # Usar email como user_id
            subscription["start_date"] = subscription.get("started_at", subscription.get("created_at"))
            subscription["end_date"] = subscription.get("expires_at")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error obteniendo suscripción activa de {user_email}: {e}")
            return None

    def has_active_subscription(self, user_email: str) -> bool:
        """Versión síncrona y ligera para verificar si existe una suscripción activa no expirada."""
        try:
            user_email = (user_email or "").lower()
            s = self.subscriptions_collection.find_one(
                {
                    "user_email": user_email,
                    "status": "active",
                    "expires_at": {"$gt": datetime.utcnow()}
                },
                {"_id": 1}
            )
            return bool(s)
        except Exception as e:
            logger.error(f"Error verificando suscripción activa de {user_email}: {e}")
            return False
    
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> bool:
        """Crear una nueva suscripción."""
        try:
            # Normalizar email
            subscription_data["user_email"] = (subscription_data.get("user_email") or "").lower()
            # Cancelar suscripciones activas existentes
            await self.cancel_user_subscriptions(subscription_data["user_email"])
            
            subscription_data["created_at"] = datetime.utcnow()
            subscription_data["updated_at"] = datetime.utcnow()
            
            # Calcular fecha de expiración
            if subscription_data["billing_period"] == "monthly":
                expires_at = datetime.utcnow() + timedelta(days=30)
            elif subscription_data["billing_period"] == "yearly":
                expires_at = datetime.utcnow() + timedelta(days=365)
            else:  # one_time
                expires_at = datetime.utcnow() + timedelta(days=365 * 10)  # 10 años para one_time
            
            subscription_data["expires_at"] = expires_at
            subscription_data["started_at"] = datetime.utcnow()
            
            result = self.subscriptions_collection.insert_one(subscription_data)
            
            # Actualizar el usuario para remover trial
            await self.update_user_plan_status(
                subscription_data["user_email"],
                subscription_data.get("plan_features", {})
            )
            
            logger.info(f"Suscripción creada para {subscription_data['user_email']}")
            return bool(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creando suscripción: {e}")
            return False
    
    async def cancel_user_subscriptions(self, user_email: str) -> bool:
        """Cancelar todas las suscripciones activas de un usuario."""
        try:
            user_email = (user_email or "").lower()
            result = self.subscriptions_collection.update_many(
                {
                    "user_email": user_email,
                    "status": "active"
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Canceladas {result.modified_count} suscripciones de {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelando suscripciones de {user_email}: {e}")
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
    
    async def assign_plan_to_user(self, user_email: str, plan_code: str, payment_method: str = "manual") -> bool:
        """Asignar un plan a un usuario específico (para admin)."""
        try:
            user_email = (user_email or "").lower()
            # Obtener información del plan
            plan = await self.get_plan_by_code(plan_code)
            if not plan:
                logger.error(f"Plan no encontrado: {plan_code}")
                return False
            
            subscription_data = {
                "user_email": user_email,
                "plan_code": plan_code,
                "plan_name": plan["name"],
                "plan_price": plan["price"],
                "currency": plan["currency"],
                "billing_period": plan["billing_period"],
                # Incluir features del plan para actualizar límites del usuario correctamente
                "plan_features": plan.get("features", {}),
                "status": "active",
                "payment_method": payment_method,
                "payment_reference": f"admin_assigned_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            }
            
            return await self.create_subscription(subscription_data)
            
        except Exception as e:
            logger.error(f"Error asignando plan {plan_code} a {user_email}: {e}")
            return False
