"""
Job de cobros recurrentes automáticos para suscripciones Pagopar.

Este job se ejecuta diariamente y:
1. Busca suscripciones que deben cobrarse (next_billing_date <= hoy)
2. Para cada suscripción:
   - Crea un pedido en Pagopar
   - Obtiene el alias_token de la tarjeta (temporal, 15 min)
   - Procesa el pago
   - Actualiza el estado según resultado
3. Maneja reintentos (1, 3, 7 días)
4. Cancela después de múltiples fallos
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.services.pagopar_service import PagoparService
from app.services.email_notification_service import EmailNotificationService

logger = logging.getLogger(__name__)


def _acquire_billing_lock(ttl: int = 300) -> bool:
    """
    Lock distribuido via Redis para evitar que múltiples pods
    ejecuten el billing job simultáneamente.
    Retorna True si se adquirió el lock, False si otro pod ya lo tiene.
    """
    try:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client(decode_responses=True)
        acquired = redis.set("cuenly:billing_job_lock", "1", nx=True, ex=ttl)
        return bool(acquired)
    except Exception as e:
        logger.warning(f"⚠️ Redis no disponible para billing lock, ejecutando de todas formas: {e}")
        return True  # Sin Redis, asumir single-pod


def _release_billing_lock():
    """Liberar el lock de billing."""
    try:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client(decode_responses=True)
        redis.delete("cuenly:billing_job_lock")
    except Exception:
        pass


class SubscriptionBillingJob:
    """Job para procesar cobros recurrentes de suscripciones."""
    
    def __init__(self):
        self.repo = SubscriptionRepository()
        self.user_repo = UserRepository()
        self.pagopar = PagoparService()
        self.email = EmailNotificationService()
        self.retry_schedule = [1, 3, 7]  # Días para reintentar
        
    async def run(self):
        """Ejecutar job de cobros."""
        # Lock distribuido: solo un pod ejecuta el billing
        if not _acquire_billing_lock(ttl=600):
            logger.info("⏭️ Billing job: otro pod ya está ejecutando, saltando")
            return

        logger.info("=" * 80)
        logger.info("🔄 Iniciando job de cobros recurrentes de suscripciones")
        logger.info("=" * 80)

        try:
            # Buscar suscripciones que deben cobrarse
            subscriptions = self.repo.get_subscriptions_due_for_billing()
            
            if not subscriptions:
                logger.info("✅ No hay suscripciones para cobrar en este momento")
                return
            
            logger.info(f"📋 Procesando {len(subscriptions)} suscripción(es)")
            
            # Procesar cada suscripción
            success_count = 0
            failed_count = 0
            
            for sub in subscriptions:
                try:
                    result = await self._process_subscription(sub)
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error procesando suscripción {sub.get('_id')}: {e}")
                    failed_count += 1
            
            logger.info("=" * 80)
            logger.info(f"✅ Job completado: {success_count} éxitos, {failed_count} fallos")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error fatal en job de cobros: {e}")
            raise
        finally:
            _release_billing_lock()
    
    async def _process_subscription(self, sub: Dict[str, Any]) -> bool:
        """
        Procesar cobro de una suscripción individual.
        
        Returns:
            True si el cobro fue exitoso, False si falló
        """
        sub_id = str(sub.get("_id"))
        user_email = sub.get("user_email")
        plan_name = sub.get("plan_name", "Plan")
        amount = sub.get("plan_price", 0)
        
        logger.info(f"💳 Procesando cobro: {user_email} - {plan_name} - {amount} PYG")
        
        try:
            # 1. Resolver pagopar_user_id desde múltiples fuentes
            pagopar_user_id = self.repo.resolve_pagopar_user_id(user_email)
            if not pagopar_user_id:
                logger.error(f"❌ Usuario {user_email} no tiene pagopar_user_id en ninguna fuente")
                self._handle_payment_failure(
                    sub,
                    "Pagopar user ID no disponible"
                )
                return False
            
            # 2. Crear pedido en Pagopar
            logger.info(f"📝 Creando pedido en Pagopar...")
            order_hash = await self.pagopar.create_order(
                identifier=pagopar_user_id,
                amount=amount,
                description=f"Suscripción {plan_name} - {datetime.now().strftime('%B %Y')}",
                ref_id=sub_id
            )
            
            if not order_hash:
                logger.error(f"❌ No se pudo crear el pedido en Pagopar")
                self._handle_payment_failure(
                    sub,
                    "Error creando pedido en Pagopar"
                )
                return False
            
            logger.info(f"✅ Pedido creado: {order_hash}")
            
            # 3. Obtener alias_token de la tarjeta (temporal, 15 min)
            logger.info(f"🃏 Obteniendo alias_token de tarjeta...")
            card_token = await self.pagopar.get_card_alias_token(pagopar_user_id)
            
            if not card_token:
                logger.error(f"❌ No se pudo obtener alias_token de tarjeta")
                self._handle_payment_failure(
                    sub,
                    "Tarjeta no disponible o expirada"
                )
                return False
            
            logger.info(f"✅ Alias token obtenido")
            
            # 4. Procesar pago
            logger.info(f"💰 Procesando pago...")
            payment_success = await self.pagopar.process_payment(
                identifier=pagopar_user_id,
                order_hash=order_hash,
                card_token=card_token
            )
            
            # 5. Registrar transacción y actualizar estado
            if payment_success:
                logger.info(f"✅ Pago exitoso para {user_email}")
                self._handle_payment_success(sub, order_hash)
                return True
            else:
                logger.error(f"❌ Pago fallido para {user_email}")
                self._handle_payment_failure(
                    sub,
                    "Pago rechazado por Pagopar"
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ Error procesando suscripción {sub_id}: {e}")
            self._handle_payment_failure(
                sub,
                f"Error técnico: {str(e)}"
            )
            return False
    
    def _handle_payment_success(self, sub: Dict[str, Any], transaction_id: str):
        """Manejar pago exitoso: actualizar fecha, resetear AI, notificar."""
        sub_id = str(sub.get("_id"))
        user_email = sub.get("user_email", "")
        amount = sub.get("plan_price", 0)

        # Calcular próxima fecha de cobro usando día de aniversario (no +30 días)
        billing_day = sub.get("billing_day_of_month")
        if not billing_day:
            # Fallback: usar día de started_at, o día actual
            started_at = sub.get("started_at", sub.get("created_at", datetime.utcnow()))
            billing_day = started_at.day
        next_billing_date = self.repo.calculate_next_billing_date(datetime.utcnow(), billing_day)

        # Actualizar fecha de cobro
        self.repo.update_billing_date(sub_id, next_billing_date)

        # Resetear contador de IA para el nuevo período
        ai_limit = sub.get("plan_features", {}).get("ai_invoices_limit", 50)
        self.user_repo.reset_user_ai_limits(user_email, ai_limit)

        # Registrar transacción exitosa
        self.repo.record_subscription_payment(
            sub_id=sub_id,
            amount=amount,
            transaction_id=transaction_id,
            status="success"
        )

        logger.info(f"✅ Suscripción actualizada. Próximo cobro: {next_billing_date.strftime('%Y-%m-%d')}. AI reseteado para {user_email}")

        self.email.send_payment_success(
            to_email=user_email,
            plan_name=sub.get("plan_name", "Plan"),
            amount=amount,
            next_billing_date=next_billing_date.strftime('%d/%m/%Y')
        )
    
    def _handle_payment_failure(self, sub: Dict[str, Any], reason: str):
        """Manejar fallo en el pago."""
        sub_id = str(sub.get("_id"))
        user_email = sub.get("user_email")
        retry_count = sub.get("retry_count", 0)
        amount = sub.get("plan_price", 0)
        
        # Incrementar contador de reintentos
        retry_count += 1
        
        # Registrar transacción fallida
        self.repo.record_subscription_payment(
            sub_id=sub_id,
            amount=amount,
            transaction_id=f"FAILED-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            status="failed",
            error_message=reason
        )
        
        # Determinar acción según número de reintentos
        if retry_count <= len(self.retry_schedule):
            # Programar reintento
            retry_days = self.retry_schedule[retry_count - 1]
            next_retry_date = datetime.utcnow() + timedelta(days=retry_days)
            
            # Marcar como PAST_DUE y programar reintento
            self.repo.mark_subscription_past_due(
                sub_id=sub_id,
                reason=reason,
                retry_count=retry_count
            )
            
            # Actualizar next_billing_date para el reintento
            self.repo.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {"$set": {"next_billing_date": next_retry_date}}
            )
            
            logger.warning(f"⚠️ Reintento {retry_count}/{len(self.retry_schedule)} programado para {next_retry_date.strftime('%Y-%m-%d')}")

            self.email.send_payment_failed(
                to_email=user_email,
                plan_name=sub.get("plan_name", "Plan"),
                reason=reason,
                retry_number=retry_count,
                next_retry_date=next_retry_date.strftime('%d/%m/%Y')
            )
            
        else:
            # Cancelar suscripción después de múltiples fallos
            self.repo.subscriptions_collection.update_one(
                {"_id": ObjectId(sub_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "cancellation_reason": f"Múltiples fallos de pago: {reason}",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.error(f"❌ Suscripción cancelada por múltiples fallos de pago: {user_email}")

            self.email.send_subscription_cancelled(
                to_email=user_email,
                plan_name=sub.get("plan_name", "Plan"),
                reason=f"Múltiples fallos de pago: {reason}"
            )


async def run_billing_job():
    """Función helper para ejecutar el job."""
    job = SubscriptionBillingJob()
    await job.run()


if __name__ == "__main__":
    # Para testing manual
    import asyncio
    asyncio.run(run_billing_job())
