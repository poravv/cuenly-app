"""
Servicio de reseteo mensual de límites de IA — post-cobro.

El reseteo de IA SOLO ocurre si el billing job cobró exitosamente.
Este servicio verifica que exista una transacción exitosa en el período
actual antes de resetear. NO resetea sin cobro confirmado.
"""

from datetime import datetime
import logging
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class MonthlyResetService:
    """Servicio de reseteo de IA condicionado a cobro exitoso."""

    def __init__(self):
        self.subscription_repo = SubscriptionRepository()
        self.user_repo = UserRepository()

    def reset_monthly_limits(self):
        """
        Resetea límites de IA SOLO para suscripciones cuyo billing_day
        coincide con hoy Y que tienen un cobro exitoso registrado este mes.
        Sin cobro exitoso = sin reset de IA.
        """
        try:
            today = datetime.utcnow()
            today_day = today.day
            logger.info(f"🔄 Verificando resets post-cobro: billing_day={today_day}")

            active_subscriptions = self.subscription_repo.get_active_subscriptions()

            if not active_subscriptions:
                logger.info("ℹ️ No se encontraron suscripciones activas")
                return {
                    "success": True,
                    "users_reset": 0,
                    "message": "No hay suscripciones activas"
                }

            users_reset = 0
            skipped_no_payment = 0
            skipped_already_reset = 0
            skipped_not_today = 0
            errors = []

            for subscription in active_subscriptions:
                try:
                    user_email = subscription.get("user_email", "")
                    sub_id = str(subscription.get("_id", ""))
                    billing_day = subscription.get("billing_day_of_month")

                    if not billing_day:
                        started_at = subscription.get("started_at", subscription.get("created_at"))
                        billing_day = started_at.day if started_at else 1

                    # Solo procesar si hoy es el día de aniversario
                    if billing_day != today_day:
                        skipped_not_today += 1
                        continue

                    # Verificar si ya fue reseteado este mes
                    user = self.user_repo.get_by_email(user_email)
                    if user:
                        last_reset = user.get("ai_last_reset")
                        if last_reset and last_reset.month == today.month and last_reset.year == today.year:
                            skipped_already_reset += 1
                            continue

                    # CRÍTICO: Verificar que existe un cobro exitoso este mes
                    has_payment = self.subscription_repo.has_successful_payment_this_month(
                        user_email=user_email,
                        sub_id=sub_id
                    )

                    if not has_payment:
                        skipped_no_payment += 1
                        logger.warning(
                            f"⚠️ Sin cobro exitoso este mes para {user_email} — NO se resetea IA"
                        )
                        continue

                    # Cobro confirmado → resetear IA
                    ai_limit = subscription.get("plan_features", {}).get("ai_invoices_limit", 50)
                    reset_result = self.user_repo.reset_user_ai_limits(user_email, ai_limit)

                    if reset_result:
                        users_reset += 1
                        logger.info(f"✅ Reset post-cobro: {user_email} (límite: {ai_limit})")
                    else:
                        errors.append(f"Error reseteando {user_email}")

                except Exception as e:
                    error_msg = f"Error procesando suscripción {subscription.get('_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")

            message = (
                f"Reset post-cobro: {users_reset} reseteados, "
                f"{skipped_already_reset} ya reseteados, "
                f"{skipped_no_payment} sin cobro exitoso"
            )
            if errors:
                message += f", {len(errors)} errores"
                logger.warning(f"⚠️ {message}")
            else:
                logger.info(f"✅ {message}")

            return {
                "success": len(errors) == 0,
                "users_reset": users_reset,
                "skipped": skipped_already_reset,
                "skipped_no_payment": skipped_no_payment,
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
