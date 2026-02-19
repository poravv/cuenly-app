from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.pagopar_service import PagoparService
import hashlib
import logging
from app.api.deps import _get_current_user  # Dependency to get current user

logger = logging.getLogger(__name__)

router = APIRouter()

pagopar_service = PagoparService()
user_repo = UserRepository()
sub_repo = SubscriptionRepository()

class AddCardRequest(BaseModel):
    return_url: str
    provider: str = 'Bancard'  # 'Bancard' or 'uPay'

class ConfirmCardRequest(BaseModel):
    return_url: str

class DeleteCardRequest(BaseModel):
    card_token: str

class PayRequest(BaseModel):
    order_hash: str
    card_token: str

# Helper function to get pagopar_id consistently from both collections
def _get_pagopar_id(email: str) -> Optional[str]:
    """
    Get pagopar_user_id from users collection, falling back to payment_methods.
    Also syncs the ID to users collection if only found in payment_methods.
    """
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
        payment_method = sub_repo.get_user_payment_method(email)
        if payment_method:
            pagopar_id = payment_method.get("pagopar_user_id")
            if pagopar_id:
                logger.info(f"📎 Usando pagopar_id de payment_methods: {pagopar_id}")
                user_repo.update_pagopar_user_id(email, pagopar_id)
    
    return pagopar_id

@router.get("/cards")
async def list_cards(current_user: dict = Depends(_get_current_user)):
    """List saved cards for the current user."""
    email = current_user.get("email")
    pagopar_id = _get_pagopar_id(email)
    
    if not pagopar_id:
        logger.warning(f"⚠️ list_cards: No se encontró pagopar_id para {email}")
        return []

    cards = await pagopar_service.list_cards(pagopar_id)
    return cards


@router.post("/cards/init")
async def init_add_card(
    request: AddCardRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Initialize card addition process.
    1. Check if user exists in Pagopar (managed via DB ID). If not, create them.
    2. Request 'add card' to Pagopar.
    3. Return the hash for the iframe.
    """
    email = current_user.get("email")
    
    # Check local DB for Pagopar ID and Profile info
    db_user = user_repo.get_by_email(email)
    pagopar_id = db_user.get("pagopar_user_id") if db_user else None
    
    # CRITICAL: Also check payment_methods collection (where /ensure-customer stores the ID)
    # This ensures consistency with the /subscriptions/ensure-customer endpoint
    if not pagopar_id:
        payment_method = sub_repo.get_user_payment_method(email)
        if payment_method:
            pagopar_id = payment_method.get("pagopar_user_id")
            logger.info(f"📎 Usando pagopar_id existente de payment_methods: {pagopar_id}")
            # Sync to users collection for future lookups
            if pagopar_id:
                user_repo.update_pagopar_user_id(email, pagopar_id)
    
    # Get profile data with fallbacks
    name = (db_user or {}).get("name") or current_user.get("name") or "Usuario Cuenly"
    phone = (db_user or {}).get("phone") or "0981000000"
    
    if not pagopar_id:
        # Generate a unique identifier for Pagopar using MD5 hash
        # IMPORTANT: Use MD5[:10] for consistency with /subscriptions/ensure-customer
        user_identifier = hashlib.md5(email.encode()).hexdigest()[:10]
        
        try:
            # 1. Add Customer to Pagopar
            # CRÍTICO: Este paso es OBLIGATORIO antes de poder agregar tarjetas
            # Si falla, NO podemos continuar porque PagoPar retornará "No existe comprador"
            logger.info(f"🔄 Registrando nuevo cliente en PagoPar: {email} (ID: {user_identifier})")
            res = await pagopar_service.add_customer(user_identifier, name, email, phone)
            
            # Verificar que la respuesta sea exitosa
            if not res.get("respuesta"):
                error_msg = res.get("resultado", "Error desconocido")
                logger.error(f"❌ No se pudo registrar cliente en PagoPar: {error_msg}")
                
                # Verificar si es un error de permisos del comercio
                if "permisos" in error_msg.lower() or "no tiene permisos" in error_msg.lower():
                    raise HTTPException(
                        status_code=403,
                        detail=f"El comercio no tiene permisos habilitados para pagos recurrentes. Error de PagoPar: {error_msg}"
                    )
                
                # Para otros errores, lanzar excepción genérica
                raise HTTPException(
                    status_code=500,
                    detail=f"No se pudo registrar el cliente en PagoPar: {error_msg}. Contacte al administrador."
                )
            
            # Cliente registrado exitosamente
            pagopar_id = user_identifier
            user_repo.update_pagopar_user_id(email, pagopar_id)
            logger.info(f"✅ Cliente registrado exitosamente en PagoPar: {email}")

        except HTTPException:
            # Re-lanzar excepciones HTTP
            raise
        except Exception as e:
            logger.error(f"💥 Error inesperado al registrar usuario en Pagopar: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al comunicarse con PagoPar: {str(e)}"
            )

    # 2. Add Card
    try:
        iframe_hash = await pagopar_service.init_add_card(pagopar_id, request.return_url, request.provider)
        return {"hash": iframe_hash, "pagopar_user_id": pagopar_id}
    except Exception as e:
        error_str = str(e)
        if "No existe comprador" in error_str:
            logger.warning(f"⚠️ Error 'No existe comprador' detectado para det-{pagopar_id}. Intentando auto-registro...")
            try:
                # Intentar registrar al cliente con el ID que ya tenemos
                await pagopar_service.add_customer(pagopar_id, name, email, phone)
                logger.info(f"✅ Auto-registro exitoso para {email}. Reintentando add_card...")
                
                # Reintentar add_card
                iframe_hash = await pagopar_service.init_add_card(pagopar_id, request.return_url, request.provider)
                return {"hash": iframe_hash, "pagopar_user_id": pagopar_id}
            except Exception as retry_error:
                logger.error(f"❌ Falló el auto-registro/reintento: {retry_error}")
                raise HTTPException(status_code=500, detail=f"Error irrecobertible de PagoPar: {str(retry_error)}")
        
        # Si no es ese error, relanzar
        raise HTTPException(status_code=500, detail=error_str)

@router.post("/cards/confirm")
async def confirm_card(
    request: ConfirmCardRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Confirm card addition after Pagopar redirect.
    """
    email = current_user.get("email")
    pagopar_id = _get_pagopar_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="Usuario no registrado en Pagopar. Por favor, agregue una tarjeta primero.")

    success = await pagopar_service.confirm_card(pagopar_id, request.return_url)
    if not success:
         raise HTTPException(status_code=400, detail="Failed to confirm card")
    
    return {"success": True}

@router.delete("/cards/{card_token}")
async def delete_card(
    card_token: str,
    current_user: dict = Depends(_get_current_user)
):
    """Delete a saved card."""
    email = current_user.get("email")
    pagopar_id = _get_pagopar_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="Usuario no registrado en Pagopar")

    # Block deletion if user has active subscription
    active_sub = await sub_repo.get_user_active_subscription(email)
    if active_sub and active_sub.get("status", "").lower() == "active":
         # Listar tarjetas para ver cuántas tiene
        cards = await pagopar_service.list_cards(pagopar_id)
        if cards and len(cards) <= 1:
            raise HTTPException(
                status_code=400, 
                detail="No puedes eliminar tu única tarjeta con una suscripción activa. Agrega otra tarjeta primero o cancela tu suscripción."
            )

    success = await pagopar_service.delete_card(pagopar_id, card_token)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete card")
        
    return {"success": True}

@router.post("/pay")
async def pay(
    request: PayRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Test endpoint to charge a saved card. 
    Requires an existing order hash (created separately via 'iniciar-transaccion').
    """
    email = current_user.get("email")
    pagopar_id = _get_pagopar_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="Usuario no registrado en Pagopar")

    success = await pagopar_service.process_payment(pagopar_id, request.order_hash, request.card_token)
    if not success:
        raise HTTPException(status_code=400, detail="Payment failed")
        
    return {"success": True}

    success = await pagopar_service.process_payment(pagopar_id, request.order_hash, request.card_token)
    if not success:
        raise HTTPException(status_code=400, detail="Payment failed")
        
    return {"success": True}

# --- Validation / Staging -> Production Flow Endpoints ---

class CreateOrderV11Request(BaseModel):
    amount: float
    description: str
    order_id: str # User provided ID (unique)

@router.post("/validation/orders/init")
async def init_validation_order(
    request: CreateOrderV11Request,
    current_user: dict = Depends(_get_current_user)
):
    """
    PASO 1: Crear Pedido V1.1.
    Retorna el hash del pedido.
    """
    email = current_user.get("email")
    name = current_user.get("name", "Usuario Staging")
    
    buyer = {
        "email": email,
        "nombre": name,
        "ruc": "",
        "telefono": "",
        "direccion": "",
        "documento": "",
        "coordenadas": "",
        "razon_social": name,
        "tipo_documento": "CI",
        "ciudad": None
    }
    
    try:
        order_hash = await pagopar_service.create_order_v11(
            request.order_id, 
            request.amount, 
            request.description,
            buyer
        )
        # Construct Checkout URL for User to Click/Pay
        checkout_url = f"https://www.pagopar.com/pagos/{order_hash}"
        
        return {
            "success": True, 
            "order_hash": order_hash, 
            "checkout_url": checkout_url,
            "message": "Click checkout_url to simulate Step 2 (Payment)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def pagopar_webhook(payload: Dict[str, Any] = Body(...)):
    """
    PASO 2: Webhook de Respuesta (URL de Respuesta).
    Pagopar envía aquí el resultado del pago.
    CRÍTICO: Este endpoint activa suscripciones cuando el pago es exitoso.
    """
    import logging
    from datetime import datetime
    logger = logging.getLogger(__name__)
    logger.info(f"💰 WEBHOOK RECEIVED: {payload}")
    
    try:
        # Pagopar envía un objeto con "resultado" que es un array
        resultado = payload.get("resultado")
        if not resultado or not isinstance(resultado, list) or len(resultado) == 0:
            logger.warning("Respuesta de Pagopar no contiene resultados válidos")
            return {"respuesta": True}
        
        payment_data = resultado[0]  # Primer elemento del array
        
        # Extraer datos críticos
        hash_pedido = payment_data.get("hash_pedido")
        pagado = payment_data.get("pagado", False)
        monto = payment_data.get("monto")
        numero_pedido = payment_data.get("numero_pedido")
        
        logger.info(f"📋 Pedido: {numero_pedido} | Hash: {hash_pedido} | Pagado: {pagado} | Monto: {monto}")
        
        # PASO 3 AUTOMÁTICO PARA SIMULADORES: Llamar a /1.1/traer
        # Pagopar espera que validemos el pedido consultando "Paso 3", así que lo hacemos aquí mismo.
        try:
            await pagopar_service.check_order_status(hash_pedido)
            logger.info(f"🔍 PASO 3 AUTOMÁTICO: Estado validado exitosamente para hash {hash_pedido}")
        except Exception as e:
            logger.error(f"❌ Error en Paso 3 automático para hash {hash_pedido}: {str(e)}")
        
        # Si el pago fue exitoso, activar suscripción
        if pagado:
            from app.repositories.subscription_repository import SubscriptionRepository
            from pymongo import MongoClient
            from app.config.settings import settings
            
            # Buscar orden pendiente
            client = MongoClient(settings.MONGODB_URL)
            db = client[settings.MONGODB_DATABASE]
            
            pending_order = db.pending_subscriptions.find_one({
                "order_hash": hash_pedido,
                "status": "pending"
            })
            
            if pending_order:
                logger.info(f"✅ Orden pendiente encontrada para {pending_order['user_email']}")
                
                # Activar suscripción
                repo = SubscriptionRepository()
                success = await repo.assign_plan_to_user(
                    user_email=pending_order["user_email"],
                    plan_code=pending_order["plan_code"],
                    payment_method="pagopar",
                    payment_reference=hash_pedido
                )
                
                if success:
                    # Marcar orden como completada
                    db.pending_subscriptions.update_one(
                        {"_id": pending_order["_id"]},
                        {"$set": {
                            "status": "completed",
                            "completed_at": datetime.utcnow(),
                            "pagopar_pedido_number": numero_pedido
                        }}
                    )
                    logger.info(f"🎉 Suscripción activada exitosamente para {pending_order['user_email']}")
                else:
                    logger.error(f"❌ Error al activar suscripción para {pending_order['user_email']}")
            else:
                logger.warning(f"⚠️ No se encontró orden pendiente para hash: {hash_pedido}")
        
        # Pagopar espera que devolvamos exactamente el array de resultados que nos envió
        return payload.get("resultado", [])
        
    except Exception as e:
        logger.error(f"💥 Error en webhook: {str(e)}")
        # Importante: siempre retornar 200 para que Pagopar no reintente
        return []

@router.get("/validation/orders/{order_hash}")
async def check_validation_order(order_hash: str):
    """
    PASO 3: Consultar estado (traer).
    """
    result = await pagopar_service.check_order_status(order_hash)
    return result
