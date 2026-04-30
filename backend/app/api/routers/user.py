"""
Endpoints de perfil de usuario y suscripción del usuario.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.api.deps import (
    _get_current_user,
    _get_current_user_with_trial_info,
    _get_current_user_with_trial_check,
    _get_current_admin,
)
from app.config.settings import settings
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.firestore_admin_repository import FirestoreAdminRepository
from app.utils.validators import SecurityValidators
from app.utils.observability import observability_logger

router = APIRouter()
logger = logging.getLogger(__name__)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    ruc: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    document_type: Optional[str] = "CI"
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class ProfileStatusResponse(BaseModel):
    is_complete: bool
    missing_fields: List[str]
    required_for_subscription: bool


class UpdateProcessingStartDatePayload(BaseModel):
    start_date: Optional[str] = None


@router.get("/")
async def root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"message": "CuenlyApp API está en funcionamiento"}

@router.get("/user/profile")
@router.get("/api/user/profile")  # Alias para compatibilidad con proxy
async def get_user_profile(request: Request, user: Dict[str, Any] = Depends(_get_current_user_with_trial_info)):
    """
    Obtiene el perfil del usuario autenticado incluyendo información del trial
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    trial_info = user.get('trial_info', {})
    
    # Obtener información completa del usuario desde la base de datos
    user_repo = UserRepository()
    db_user = None
    try:
        db_user = user_repo.get_by_email(user.get('email', ''))
    except Exception as e:
        logger.error(f"Error fetching user from DB in get_user_profile: {e}")
    
    # Obtener fecha de inicio de procesamiento de correos
    processing_start_date = None
    if db_user:
        try:
            processing_start_date = user_repo.get_email_processing_start_date(user.get('email', ''))
            if processing_start_date:
                processing_start_date = processing_start_date.isoformat()
        except Exception as e:
            logger.warning(f"No se pudo obtener fecha de inicio de procesamiento: {e}")
    
    # Verificar si es admin consultando Firestore (fuente de verdad)
    is_admin = False
    if db_user:
        is_admin = db_user.get('role') == 'admin'
    else:
        # Fallback: verificar contra Firestore si no hay registro en MongoDB
        try:
            is_admin = FirestoreAdminRepository().is_admin(user.get('email', ''))
        except Exception:
            is_admin = False

    # Usar datos de la DB si están disponibles, sino usar claims del token
    return {
        "email": db_user.get('email') if db_user else user.get('email'),
        "name": db_user.get('name') if db_user else user.get('name'),
        "picture": db_user.get('picture') if db_user else user.get('picture'),
        "role": db_user.get('role', 'user') if db_user else 'user',
        "is_admin": is_admin,
        "status": db_user.get('status', 'active') if db_user else 'active',
        "is_trial": trial_info.get('is_trial_user', True),
        "trial_expires_at": trial_info.get('trial_expires_at'),
        "trial_expired": trial_info.get('trial_expired', True),
        "trial_days_remaining": trial_info.get('days_remaining', 0),
        "can_process": not trial_info.get('trial_expired', True),
        "ai_invoices_processed": trial_info.get('ai_invoices_processed', 0),
        "ai_invoices_limit": trial_info.get('ai_invoices_limit', 50),
        "ai_limit_reached": trial_info.get('ai_limit_reached', True),
        "email_processing_start_date": processing_start_date,
        "phone": db_user.get('phone', ''),
        "ruc": db_user.get('ruc', ''),
        "address": db_user.get('address', ''),
        "city": db_user.get('city', ''),
        "document_type": db_user.get('document_type', 'CI'),
        "webhook_url": db_user.get('webhook_url', ''),
        "has_webhook_secret": bool(db_user.get('webhook_secret', ''))
    }

@router.put("/user/profile")
@router.put("/api/user/profile") # Alias
async def update_user_profile(
    profile_data_update: UserProfileUpdate,  # Renombrado para evitar conflicto nombre
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Actualiza la información del perfil del usuario.
    Sync con Pagopar si existe.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    email = user.get('email', '')
    profile_data = profile_data_update.dict(exclude_unset=True)
    
    if not profile_data:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar")
    
    # Validaciones
    if 'phone' in profile_data:
        phone = profile_data['phone']
        if phone and not SecurityValidators.validate_phone(phone):
             raise HTTPException(status_code=400, detail="Número de teléfono inválido. Verifique longitud y formato.")

    if 'ruc' in profile_data:
        ruc = profile_data['ruc']
        if ruc and not SecurityValidators.validate_ruc(ruc):
             raise HTTPException(status_code=400, detail="RUC inválido. Verifique el formato.")
        
    user_repo = UserRepository()
    success = user_repo.update_user_profile(email, profile_data)
    
    if success:
        # Intentar actualizar en Pagopar si tiene pagopar_user_id
        pagopar_user_id = user_repo.get_pagopar_user_id(email)
        if pagopar_user_id:
            try:
                from app.services.pagopar_service import PagoparService
                pagopar_service = PagoparService()
                await pagopar_service.add_customer(
                    identifier=pagopar_user_id,
                    name=profile_data.get('name', user.get('name', 'Usuario')),
                    email=email,
                    phone=profile_data.get('phone', '')
                )
            except Exception as e:
                logger.warning(f"No se pudo sincronizar perfil con Pagopar: {e}")
        
        return {"success": True, "message": "Perfil actualizado correctamente"}
    else:
        raise HTTPException(status_code=500, detail="Error al actualizar el perfil en la base de datos")

@router.get("/user/profile/status", response_model=ProfileStatusResponse)
async def get_profile_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Verifica si el perfil del usuario está completo (requerido para suscripciones).
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    email = user.get('email', '')
    user_repo = UserRepository()
    status = user_repo.is_profile_complete(email)
    
    return status

@router.get("/debug/user-info")
async def debug_user_info(request: Request, admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Endpoint de debug para verificar información del usuario autenticado.
    Requiere permisos de administrador para evitar exposición de claims internos.
    """
    try:
        user_repo = UserRepository()
        db_user = user_repo.get_by_email(admin.get('email'))
        trial_info = user_repo.get_trial_info(admin.get('email'))

        return {
            "authenticated": True,
            "email": admin.get('email'),
            "role": db_user.get('role') if db_user else None,
            "trial_info": trial_info
        }
    except Exception as e:
        return {
            "authenticated": True,
            "email": admin.get('email'),
            "database_error": "Error consultando datos de usuario"
        }

@router.get("/user/subscription", tags=["User - Subscription"])
async def get_user_subscription(current_user: dict = Depends(_get_current_user)):
    """Obtiene la suscripción actual del usuario autenticado"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        subscription = await repo.get_user_active_subscription(current_user["email"])
        
        if not subscription:
            return {
                "success": True,
                "data": None,
                "message": "Usuario sin suscripción activa"
            }
        
        return {
            "success": True,
            "data": subscription
        }
    except Exception as e:
        logger.error(f"Error obteniendo suscripción de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo suscripción")

@router.get("/user/subscription/history", tags=["User - Subscription"])
async def get_user_subscription_history(current_user: dict = Depends(_get_current_user)):
    """Obtiene el historial de suscripciones del usuario"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        history = await repo.get_user_subscriptions_history(current_user["email"])
        
        return {
            "success": True,
            "data": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Error obteniendo historial de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo historial")

@router.post("/user/subscription/change-plan", tags=["User - Subscription"])
async def request_plan_change(
    request: dict,
    current_user: dict = Depends(_get_current_user)
):
    """Solicita cambio de plan - redirige a checkout de Pagopar para pago con tarjeta"""
    try:
        new_plan_id = request.get("plan_id")
        if not new_plan_id:
            raise HTTPException(status_code=400, detail="plan_id es requerido")
        
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.services.pagopar_service import PagoparService
        import hashlib
        
        repo = SubscriptionRepository()
        pagopar_service = PagoparService()
        
        # Verificar que el plan existe (buscar por código)
        plan = await repo.get_plan_by_code(new_plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        # Verificar si el usuario ya tiene este plan
        current_subscription = await repo.get_user_active_subscription(current_user["email"])
        if current_subscription and current_subscription.get("plan_code") == new_plan_id:
            raise HTTPException(status_code=400, detail="Ya tienes este plan activo")
            
        # ============================================================
        # CREAR PEDIDO EN PAGOPAR (V1.1 Standard)
        # ============================================================
        
        email = current_user["email"]
        name = current_user.get("name", "Usuario Cuenly")
        
        # Generar ID único para el pedido
        timestamp = int(time.time())
        order_id = f"CUENLY-SUB-{timestamp}"
        
        # Obtener datos del comprador del request (si vienen del frontend)
        buyer_data = request.get("buyer_data", {})
        
        # Datos del comprador para Pagopar
        buyer = {
            "email": email,
            "nombre": name,
            "ruc": buyer_data.get("ruc", ""),
            "telefono": buyer_data.get("telefono", ""),
            "direccion": buyer_data.get("direccion", ""),
            "documento": buyer_data.get("documento", ""),
            "coordenadas": "",
            "razon_social": buyer_data.get("razon_social") or name,
            "tipo_documento": buyer_data.get("tipo_documento", "CI"),
            "ciudad": None,
            "direccion_referencia": None
        }
        
        # Validar campos obligatorios
        if not buyer["documento"]:
            raise HTTPException(status_code=400, detail="El número de documento es requerido")
        if not buyer["telefono"]:
            raise HTTPException(status_code=400, detail="El número de teléfono es requerido")
        
        # Crear pedido en Pagopar
        amount = plan["price"]
        description = f"Suscripción {plan['name']}"
        
        try:
            order_hash = await pagopar_service.create_order_v11(
                order_id, 
                amount, 
                description,
                buyer
            )
            
            if not order_hash:
                raise Exception("No se pudo generar el hash del pedido")
            
            # Guardar orden pendiente en DB para reconciliación en webhook
            db = repo._get_db()
            db.pending_subscriptions.insert_one({
                "user_email": email,
                "plan_code": new_plan_id,
                "plan_name": plan["name"],
                "amount": amount,
                "order_id": order_id,
                "order_hash": order_hash,
                "status": "pending",
                "created_at": datetime.utcnow()
            })
            
            # Construir URL de checkout
            checkout_url = f"https://www.pagopar.com/pagos/{order_hash}"
            
            return {
                "success": True,
                "checkout_url": checkout_url,
                "order_hash": order_hash,
                "message": "Redirigiendo a Pagopar para completar el pago..."
            }
            
        except Exception as e:
            logger.error(f"Error al crear pedido en Pagopar: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al procesar el pago: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en request_plan_change: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando cambio de plan para {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error procesando solicitud")

@router.post("/user/subscription/cancel", tags=["User - Subscription"])
async def cancel_user_subscription(current_user: dict = Depends(_get_current_user)):
    """Cancela la suscripción activa del usuario autenticado."""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()

        # Verificar si el usuario tiene una suscripción activa
        active = await repo.get_user_active_subscription(current_user["email"])
        if not active:
            return {
                "success": True,
                "message": "No tienes una suscripción activa para cancelar"
            }

        # Cancelar suscripciones activas (idempotente)
        ok = await repo.cancel_user_subscriptions(current_user["email"])
        if not ok:
            raise HTTPException(status_code=500, detail="No se pudo cancelar la suscripción")

        logger.info(f"✅ Suscripción cancelada para {current_user['email']}")
        return {
            "success": True,
            "message": "Tu suscripción ha sido cancelada correctamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelando suscripción de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error cancelando suscripción")

# Endpoints administrativos para planes (requieren auth admin)
