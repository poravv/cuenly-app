"""
Servicio para el reseteo mensual automático de límites de IA
Resetea los límites de procesamiento IA para usuarios con suscripciones activas
"""

from datetime import datetime, timedelta
import logging
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonthlyResetService:
    """Servicio para resetear límites mensuales de IA"""
    
    def __init__(self):
        self.subscription_repo = SubscriptionRepository()
        self.user_repo = UserRepository()
    
    def reset_monthly_limits(self):
        """
        Resetea los límites de IA para todos los usuarios con suscripciones activas
        Solo resetea usuarios cuya suscripción esté activa y vigente
        """
        try:
            logger.info("🔄 Iniciando proceso de reseteo mensual de límites IA")
            
            # Obtener todas las suscripciones activas
            active_subscriptions = self.subscription_repo.get_active_subscriptions()
            
            if not active_subscriptions:
                logger.info("ℹ️ No se encontraron suscripciones activas para resetear")
                return {
                    "success": True,
                    "users_reset": 0,
                    "message": "No hay suscripciones activas"
                }
            
            users_reset = 0
            errors = []
            
            for subscription in active_subscriptions:
                try:
                    user_email = subscription['user_email']
                    plan = subscription['plan']
                    ai_limit = plan.get('ai_invoices_limit', -1)  # -1 = ilimitado
                    
                    # Resetear límites del usuario
                    reset_result = self.user_repo.reset_user_ai_limits(user_email, ai_limit)
                    
                    if reset_result:
                        users_reset += 1
                        logger.info(f"✅ Usuario {user_email} reseteado (límite: {ai_limit})")
                    else:
                        error_msg = f"Error reseteando usuario {user_email}"
                        errors.append(error_msg)
                        logger.warning(f"⚠️ {error_msg}")
                        
                except Exception as e:
                    error_msg = f"Error procesando suscripción {subscription.get('_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            # Resultado final
            success = len(errors) == 0
            message = f"Reseteo completado: {users_reset} usuarios"
            
            if errors:
                message += f", {len(errors)} errores"
                logger.warning(f"⚠️ Reseteo completado con errores: {errors}")
            else:
                logger.info(f"✅ {message}")
            
            return {
                "success": success,
                "users_reset": users_reset,
                "errors": errors,
                "message": message
            }
            
        except Exception as e:
            error_msg = f"Error crítico en reseteo mensual: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "users_reset": 0,
                "error": error_msg
            }
    
    def reset_user_limits_manually(self, user_email: str):
        """
        Resetea los límites de un usuario específico manualmente
        Usado desde el panel de admin
        """
        try:
            logger.info(f"🔄 Reseteo manual para usuario: {user_email}")
            
            # Obtener la suscripción activa del usuario
            subscription = self.subscription_repo.get_user_active_subscription(user_email)
            
            if not subscription:
                error_msg = f"Usuario {user_email} no tiene suscripción activa"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Obtener el límite del plan
            plan = subscription['plan']
            ai_limit = plan.get('ai_invoices_limit', -1)
            
            # Resetear límites
            reset_result = self.user_repo.reset_user_ai_limits(user_email, ai_limit)
            
            if reset_result:
                logger.info(f"✅ Usuario {user_email} reseteado manualmente (límite: {ai_limit})")
                return {
                    "success": True,
                    "message": f"Límites reseteados para {user_email}",
                    "new_limit": ai_limit
                }
            else:
                error_msg = f"Error reseteando usuario {user_email}"
                logger.error(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = f"Error en reseteo manual de {user_email}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_reset_statistics(self):
        """Obtiene estadísticas de reseteo para el panel de admin"""
        try:
            # Contar suscripciones activas
            active_subscriptions = self.subscription_repo.get_active_subscriptions()
            active_count = len(active_subscriptions) if active_subscriptions else 0
            
            # Contar usuarios que fueron reseteados este mes
            current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Esta es una aproximación - en un sistema real tendrías un log de reseteos
            resetted_this_month = active_count  # Asumimos que todos los activos fueron reseteados
            
            return {
                "success": True,
                "data": {
                    "active_subscriptions": active_count,
                    "resetted_this_month": resetted_this_month,
                    "last_reset_date": current_month.isoformat()
                }
            }
            
        except Exception as e:
            error_msg = f"Error obteniendo estadísticas de reseteo: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def should_run_today(self):
        """Verifica si el reseteo debería ejecutarse hoy"""
        today = datetime.now()
        return today.day == 1