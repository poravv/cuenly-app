"""
API endpoints públicos para gestión de suscripciones de usuarios.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
import logging
from datetime import datetime, timedelta

from app.api.deps import _get_current_user
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.services.pagopar_service import PagoparService
from app.models.subscription_models import (
    PlanResponse,
    SubscribeRequest,
    SubscribeResponse,
    ConfirmCardRequest,
    SubscriptionResponse,
    PaymentMethodResponse,
    CancelSubscriptionRequest,
    PlanCode
)

router = APIRouter()
logger = logging.getLogger(__name__)

sub_repo = SubscriptionRepository()
pagopar_service = PagoparService()
user_repo = UserRepository()


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans():
    """
    Obtener lista de planes de suscripción disponibles.
    No requiere autenticación.
    """
    try:
        plans = await sub_repo.get_all_plans(include_inactive=False)
        
        result = []
        for plan in plans:
            result.append(PlanResponse(
                id=str(plan.get("_id", plan.get("code"))),
                code=plan["code"],
                name=plan["name"],
                description=plan.get("description", ""),
                amount=plan.get("price", plan.get("amount", 0)),
                currency=plan.get("currency", "PYG"),
                billing_period=plan.get("billing_period", "MONTHLY"),
                features=plan.get("features", {}),
                active=plan.get("active", True)
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo planes: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo planes")


@router.post("/ensure-customer")
async def ensure_pagopar_customer(
    current_user: dict = Depends(_get_current_user)
):
    """
    Verificar/crear cliente en Pagopar automáticamente.
    Se llama después del login de Firebase.
    Este es el PASO 2 del flujo de Pagopar (se hace 1 sola vez).
    """
    try:
        user_email = current_user.get("email")
        
        # Verificar si ya tiene pagopar_user_id
        payment_method = sub_repo.get_user_payment_method(user_email)
        
        if payment_method and payment_method.get("pagopar_user_id"):
            logger.info(f"✅ Cliente Pagopar ya existe: {user_email}")
            return {
                "success": True,
                "message": "Cliente ya existe en Pagopar",
                "pagopar_user_id": payment_method["pagopar_user_id"],
                "already_exists": True
            }
        
        # Crear cliente en Pagopar
        import hashlib
        pagopar_user_id = hashlib.md5(user_email.encode()).hexdigest()[:10]
        
        # Get user profile for real name/phone
        user_repo = UserRepository()
        db_user = user_repo.get_by_email(user_email)
        
        try:
            await pagopar_service.add_customer(
                identifier=pagopar_user_id,
                name=(db_user or {}).get("name") or current_user.get("displayName") or current_user.get("name") or user_email,
                email=user_email,
                phone=(db_user or {}).get("phone") or ""
            )
            
            logger.info(f"✅ Cliente creado en Pagopar: {user_email} -> {pagopar_user_id}")
            
            # Guardar temporalmente en payment_methods
            sub_repo.payment_methods_collection.update_one(
                {"user_email": user_email},
                {
                    "$set": {
                        "user_email": user_email,
                        "pagopar_user_id": pagopar_user_id,
                        "provider": "Bancard",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            return {
                "success": True,
                "message": "Cliente creado en Pagopar exitosamente",
                "pagopar_user_id": pagopar_user_id,
                "already_exists": False
            }
            
        except Exception as e:
            # Si ya existe en Pagopar, no es error crítico
            logger.warning(f"Cliente posiblemente ya existe en Pagopar: {e}")
            
            # De todos modos guardamos el ID localmente
            sub_repo.payment_methods_collection.update_one(
                {"user_email": user_email},
                {
                    "$set": {
                        "user_email": user_email,
                        "pagopar_user_id": pagopar_user_id,
                        "provider": "Bancard",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            return {
                "success": True,
                "message": "Cliente verificado en Pagopar",
                "pagopar_user_id": pagopar_user_id,
                "already_exists": True
            }
        
    except Exception as e:
        logger.error(f"Error en ensure_pagopar_customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    request: SubscribeRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Iniciar proceso de suscripción.
    
    Pasos:
    1. Verificar que el usuario no tenga una suscripción activa
    2. Crear/verificar cliente en Pagopar
    3. Iniciar catastro de tarjeta
    4. Retornar form_id para mostrar iframe
    """
    try:
        user_email = current_user.get("email")
        
        # Verificar si ya tiene suscripción activa
        existing_sub = await sub_repo.get_user_subscription(user_email)
        if existing_sub:
            logger.info(f"🔄 Usuario {user_email} iniciando cambio de plan (Upgrade/Downgrade)")
            # No bloqueamos, permitimos continuar para cambiar de plan
            pass
        
        # Obtener plan
        plan = await sub_repo.get_plan_by_code(request.plan_code)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        if not plan.get("active", True):
            raise HTTPException(status_code=400, detail="Plan no disponible")
        
        # Generar ID de usuario para Pagopar (único)
        # Usamos hash del email para asegurar consistencia
        import hashlib
        pagopar_user_id = hashlib.md5(user_email.encode()).hexdigest()[:10]
        
        # 1. Agregar/verificar cliente en Pagopar
        user_repo = UserRepository()
        db_user = user_repo.get_by_email(user_email)
        
        try:
            await pagopar_service.add_customer(
                identifier=pagopar_user_id,
                name=(db_user or {}).get("name") or current_user.get("displayName") or user_email,
                email=user_email,
                phone=(db_user or {}).get("phone") or ""
            )
            logger.info(f"✅ Cliente {user_email} registrado en Pagopar")
        except Exception as e:
            logger.warning(f"Cliente ya existe o error: {e}")
            # Continuar de todos modos, puede que ya exista
        
        # 2. Verificar Tarjetas Existentes SIEMPRE (auto-detectar)
        # Si el usuario ya tiene tarjetas, activar directamente sin pedir nueva
        existing_cards = []
        pagopar_id_lookup = pagopar_user_id  # Default al ID generado por hash
        
        # IMPORTANTE: Primero verificar si ya existe un pagopar_id guardado en users collection
        saved_pagopar_id = user_repo.get_pagopar_user_id(user_email)
        if saved_pagopar_id:
            pagopar_id_lookup = saved_pagopar_id
            logger.info(f"📎 Usando pagopar_id existente de users: {pagopar_id_lookup}")
        else:
            # Fallback: verificar si hay un método de pago guardado con otro ID
            pm = sub_repo.get_user_payment_method(user_email)
            if pm and pm.get("pagopar_user_id"):
                pagopar_id_lookup = pm.get("pagopar_user_id")
                logger.info(f"📎 Usando pagopar_id de payment_methods: {pagopar_id_lookup}")
        
        try:
            existing_cards = await pagopar_service.list_cards(pagopar_id_lookup)
            logger.info(f"🔍 Tarjetas encontradas para {user_email}: {len(existing_cards) if existing_cards else 0}")
        except Exception as e:
            logger.warning(f"⚠️ Error listando tarjetas (puede que no existan aún): {e}")
            existing_cards = []
            
        if existing_cards and len(existing_cards) > 0:
            logger.info(f"💳 Usando tarjeta existente para {user_email}")
            
            # Activar suscripción directamente
            subscription_data = {
                "user_email": user_email,
                "pagopar_user_id": pagopar_id_lookup,
                "plan_code": plan["code"],
                "plan_name": plan["name"],
                "plan_price": plan.get("price", plan.get("amount", 0)),
                "currency": plan.get("currency", "PYG"),
                "billing_period": plan.get("billing_period", "monthly"),
                "plan_features": plan.get("features", {}),
                "status": "ACTIVE",
                "next_billing_date": datetime.utcnow() + timedelta(days=30),
                "payment_method": "pagopar_recurring"  
            }
            
            success = await sub_repo.create_subscription(subscription_data)
            
            if success:
                return SubscribeResponse(
                    form_id=None,
                    pagopar_user_id=pagopar_id_lookup,
                    message="Suscripción activada con tu tarjeta existente",
                    subscription_active=True
                )

        # 3. Iniciar catastro de tarjeta (Si no hay existentes o no se solicitó usar)
        redirect_url = "https://app.cuenly.com/subscription/confirm"  # TODO: Obtener de config
        
        provider_to_use = request.provider if request.provider else "Bancard"
        
        logger.info(f"🆕 Iniciando add_card para {user_email} con proveedor {provider_to_use}")
        
        form_id = await pagopar_service.init_add_card(
            identifier=pagopar_user_id,
            redirect_url=redirect_url,
            provider=provider_to_use
        )
        
        if not form_id:
            raise HTTPException(
                status_code=500,
                detail="Error iniciando catastro de tarjeta"
            )
        
        # Guardar pagopar_user_id temporalmente para cuando confirme
        # (Podríamos usar una colección temporal o cache)
        sub_repo.payment_methods_collection.update_one(
            {"user_email": user_email},
            {
                "$set": {
                    "user_email": user_email,
                    "pagopar_user_id": pagopar_user_id,
                    "provider": provider_to_use,
                    "pending_plan_code": request.plan_code,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return SubscribeResponse(
            form_id=form_id,
            pagopar_user_id=pagopar_user_id,
            message="Completa el formulario de tarjeta para activar tu suscripción",
            subscription_active=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en suscripción: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-card")
async def confirm_card(
    request: ConfirmCardRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Confirmar tarjeta catastrada y activar suscripción.
    Se llama después de que el usuario completa el iframe de Bancard.
    """
    try:
        user_email = current_user.get("email")
        
        # Obtener pagopar_user_id del registro temporal
        payment_method = sub_repo.get_user_payment_method(user_email)
        if not payment_method:
            raise HTTPException(
                status_code=400,
                detail="No se encontró información de pago pendiente"
            )
        
        pagopar_user_id = payment_method.get("pagopar_user_id")
        pending_plan_code = payment_method.get("pending_plan_code")
        
        if not pagopar_user_id or not pending_plan_code:
            raise HTTPException(
                status_code=400,
                detail="Información de pago incompleta"
            )
        
        # Confirmar tarjeta en Pagopar
        redirect_url = "https://app.cuenly.com/subscription/confirm"
        confirmed = await pagopar_service.confirm_card(
            identifier=pagopar_user_id,
            redirect_url=redirect_url
        )
        
        if not confirmed:
            raise HTTPException(
                status_code=400,
                detail="No se pudo confirmar la tarjeta. Intenta nuevamente."
            )
        
        # Verificar que tenga al menos una tarjeta
        cards = await pagopar_service.list_cards(pagopar_user_id)
        if not cards or len(cards) == 0:
            raise HTTPException(
                status_code=400,
                detail="No se encontró ninguna tarjeta catastrada"
            )
        
        # Actualizar método de pago como confirmado
        sub_repo.save_payment_method(
            user_email=user_email,
            pagopar_user_id=pagopar_user_id,
            provider="Bancard"
        )
        
        # Crear suscripción
        plan = await sub_repo.get_plan_by_code(pending_plan_code)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        subscription_data = {
            "user_email": user_email,
            "pagopar_user_id": pagopar_user_id,
            "plan_code": plan["code"],
            "plan_name": plan["name"],
            "plan_price": plan.get("price", plan.get("amount", 0)),
            "currency": plan.get("currency", "PYG"),
            "billing_period": plan.get("billing_period", "monthly"),
            "plan_features": plan.get("features", {}),
            "status": "ACTIVE",
            "next_billing_date": datetime.utcnow() + timedelta(days=30),
            "payment_method": "pagopar_recurring"
        }
        
        success = await sub_repo.create_subscription(subscription_data)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Error creando suscripción"
            )
        
        logger.info(f"✅ Suscripción activada para {user_email}")
        
        return {
            "success": True,
            "message": "Suscripción activada exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirmando tarjeta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-subscription")
async def get_my_subscription(
    current_user: dict = Depends(_get_current_user)
):
    """Obtener suscripción activa del usuario."""
    try:
        user_email = current_user.get("email")
        
        subscription = await sub_repo.get_user_active_subscription(user_email)
        
        if not subscription:
            # Retornar 200 OK con success=false en lugar de 404
            return {
                "success": False,
                "subscription": None,
                "message": "No tienes una suscripción activa"
            }
        
        # Verificar si tiene método de pago
        payment_method = sub_repo.get_user_payment_method(user_email)
        has_payment_method = bool(payment_method)
        
        return {
            "success": True,
            "subscription": {
                "id": str(subscription.get("_id", "")),
                "user_email": user_email,
                "plan_code": subscription.get("plan_code", ""),
                "plan_name": subscription.get("plan_name", ""),
                "plan_price": subscription.get("plan_price", 0),
                "currency": subscription.get("currency", "PYG"),
                "status": subscription.get("status", ""),
                "next_billing_date": subscription.get("next_billing_date").isoformat() if subscription.get("next_billing_date") else None,
                "last_billing_date": subscription.get("last_billing_date").isoformat() if subscription.get("last_billing_date") else None,
                "has_payment_method": has_payment_method,
                "created_at": subscription.get("created_at").isoformat() if subscription.get("created_at") else None,
                # Campos para frontend - límites de IA
                "start_date": subscription.get("started_at").isoformat() if subscription.get("started_at") else (subscription.get("created_at").isoformat() if subscription.get("created_at") else None),
                "monthly_ai_limit": subscription.get("monthly_ai_limit", 0),
                "current_ai_usage": subscription.get("current_ai_usage", 0),
                "plan_features": subscription.get("plan_features", {}),
                "is_indefinite": subscription.get("is_indefinite", True)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo suscripción: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: dict = Depends(_get_current_user)
):
    """Cancelar suscripción activa (solicitud del usuario)."""
    try:
        user_email = current_user.get("email")
        
        # Cancelar con razón "user_request"
        success = await sub_repo.cancel_user_subscriptions(
            user_email, 
            reason="user_request"
        )
        
        if success:
            # SEGURIDAD: Revertir límites del usuario al plan gratuito inmediatamente
            # Asumimos Plan Free = 0 facturas IA (solo XML)
            # También quitamos status de trial si lo tuviera (ya consumió un plan)
            await sub_repo.update_user_plan_status(
                user_email, 
                {"ai_invoices_limit": 0} 
            )
            logger.info(f"⬇️ Usuario {user_email} revertido a límites gratuitos tras cancelación")
        else:
            raise HTTPException(
                status_code=404,
                detail="No se encontró suscripción activa para cancelar"
            )
        
        logger.info(f"✅ Usuario {user_email} canceló su suscripción")
        
        return {
            "success": True,
            "message": "Suscripción cancelada exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelando suscripción: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment-methods")
async def get_payment_methods(
    current_user: dict = Depends(_get_current_user)
):
    """Listar métodos de pago del usuario."""
    try:
        user_email = current_user.get("email")
        
        # Obtener pagopar_user_id
        payment_method = sub_repo.get_user_payment_method(user_email)
        if not payment_method:
            return {"cards": []}
        
        pagopar_user_id = payment_method.get("pagopar_user_id")
        if not pagopar_user_id:
            return {"cards": []}
        
        # Listar tarjetas en Pagopar
        cards = await pagopar_service.list_cards(pagopar_user_id)
        
        result = []
        for card in cards:
            result.append({
                "id": card.get("id"),
                "alias_token": card.get("alias_token"),
                "card_type": card.get("tipo_tarjeta", ""),
                "last_four_digits": card.get("ultimos_digitos", "****"),
                "provider": payment_method.get("provider", "Bancard")
            })
        
        return {"cards": result}
        
    except Exception as e:
        logger.error(f"Error obteniendo métodos de pago: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payment-methods/{card_token}")
async def delete_payment_method(
    card_token: str,
    current_user: dict = Depends(_get_current_user)
):
    """Eliminar método de pago."""
    try:
        user_email = current_user.get("email")
        
        # Obtener pagopar_user_id
        payment_method = sub_repo.get_user_payment_method(user_email)
        if not payment_method:
            raise HTTPException(status_code=404, detail="Método de pago no encontrado")
        
        pagopar_user_id = payment_method.get("pagopar_user_id")

        # SEGURIDAD: Verificar si tiene suscripción activa antes de eliminar
        # Si tiene suscripción activa, NO permitir eliminar la tarjeta si es la única
        active_sub = await sub_repo.get_user_active_subscription(user_email)
        
        if active_sub and active_sub.get("status") == "ACTIVE":
             # Listar tarjetas para ver cuántas tiene
            cards = await pagopar_service.list_cards(pagopar_user_id)
            if cards and len(cards) <= 1:
                 raise HTTPException(
                    status_code=400,
                    detail="No puedes eliminar tu única tarjeta con una suscripción activa. Agrega otra tarjeta primero o cancela tu suscripción."
                )
        
        # Eliminar en Pagopar
        success = await pagopar_service.delete_card(pagopar_user_id, card_token)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No se pudo eliminar el método de pago"
            )
        
        # Si no quedan tarjetas, eliminar el registro local
        cards = await pagopar_service.list_cards(pagopar_user_id)
        if not cards or len(cards) == 0:
            sub_repo.delete_payment_method(user_email)
        
        return {
            "success": True,
            "message": "Método de pago eliminado"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando método de pago: {e}")
        raise HTTPException(status_code=500, detail=str(e))
