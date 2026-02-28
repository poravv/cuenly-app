"""
Servicio de reseteo mensual de límites de IA — red de seguridad.

El reseteo principal ocurre en el billing job (al cobrar exitosamente).
Este servicio actúa como fallback: solo resetea usuarios cuyo billing_day
coincide con hoy y que NO fueron reseteados ya por el billing job.
"""

from datetime import datetime
import logging
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class MonthlyResetService:
    """Servicio fallback para resetear límites mensuales de IA por aniversario."""

    def __init__(self):
        self.subscription_repo = SubscriptionRepository()
        self.user_repo = UserRepository()

    def reset_monthly_limits(self):
        """
        Resetea límites de IA para suscripciones activas cuyo billing_day
        coincide con hoy, solo si no fueron reseteadas ya este mes.
        """
        try:
            today = datetime.utcnow()
            today_day = today.day
            logger.info(f"🔄 Reseteo mensual fallback: verificando suscripciones con billing_day={today_day}")

            active_subscriptions = self.subscription_repo.get_active_subscriptions()

            if not active_subscriptions:
                logger.info("ℹ️ No se encontraron suscripciones activas para resetear")
                return {
                    "success": True,
                    "users_reset": 0,
                    "message": "No hay suscripciones activas"
                }

            users_reset = 0
            skipped = 0
            errors = []

            for subscription in active_subscriptions:
                try:
                    user_email = subscription.get("user_email", "")
                    billing_day = subscription.get("billing_day_of_month")

                    # Si no tiene billing_day, usar día de started_at como fallback
                    if not billing_day:
                        started_at = subscription.get("started_at", subscription.get("created_at"))
                        billing_day = started_at.day if started_at else 1

                    # Solo resetear si hoy es el día de aniversario
                    if billing_day != today_day:
                        continue

                    # Verificar si ya fue reseteado este mes (por el billing job)
                    user = self.user_repo.get_by_email(user_email)
                    if user:
                        last_reset = user.get("ai_last_reset")
                        if last_reset and last_reset.month == today.month and last_reset.year == today.year:
                            skipped += 1
                            continue

                    # Obtener límite de IA del plan
                    ai_limit = subscription.get("plan_features", {}).get("ai_invoices_limit", 50)

                    reset_result = self.user_repo.reset_user_ai_limits(user_email, ai_limit)

                    if reset_result:
                        users_reset += 1
                        logger.info(f"✅ Fallback reset: {user_email} (límite: {ai_limit})")
                    else:
                        errors.append(f"Error reseteando {user_email}")

                except Exception as e:
                    error_msg = f"Error procesando suscripción {subscription.get('_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")

            message = f"Reseteo fallback: {users_reset} reseteados, {skipped} ya reseteados por billing"
            if errors:
                message += f", {len(errors)} errores"
                logger.warning(f"⚠️ {message}")
            else:
                logger.info(f"✅ {message}")

            return {
                "success": len(errors) == 0,
                "users_reset": users_reset,
                "skipped": skipped,
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
        Resetea los límites de un usuario específico manualmente.
        Usado desde el panel de admin.
        """
        try:
            logger.info(f"🔄 Reseteo manual para usuario: {user_email}")

            # Buscar suscripción activa síncrona
            sub = self.subscription_repo.subscriptions_collection.find_one(
                {"user_email": user_email.lower(), "status": "active"}
            )

            if not sub:
                return {
                    "success": False,
                    "error": f"Usuario {user_email} no tiene suscripción activa"
                }

            ai_limit = sub.get("plan_features", {}).get("ai_invoices_limit", 50)
            reset_result = self.user_repo.reset_user_ai_limits(user_email, ai_limit)

            if reset_result:
                logger.info(f"✅ Usuario {user_email} reseteado manualmente (límite: {ai_limit})")
                return {
                    "success": True,
                    "message": f"Límites reseteados para {user_email}",
                    "new_limit": ai_limit
                }
            else:
                return {
                    "success": False,
                    "error": f"Error reseteando usuario {user_email}"
                }

        except Exception as e:
            error_msg = f"Error en reseteo manual de {user_email}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    def get_reset_statistics(self):
        """Obtiene estadísticas de reseteo para el panel de admin."""
        try:
            active_subscriptions = self.subscription_repo.get_active_subscriptions()
            active_count = len(active_subscriptions) if active_subscriptions else 0

            current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            return {
                "success": True,
                "data": {
                    "active_subscriptions": active_count,
                    "resetted_this_month": active_count,
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
        """Ahora ejecuta todos los días (verifica por aniversario internamente)."""
        return True
