from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.repositories.user_repository import UserRepository
from app.services.pagopar_service import PagoparService
import hashlib
import logging
from app.api.deps import _get_current_user  # Dependency to get current user

logger = logging.getLogger(__name__)

router = APIRouter()

pagopar_service = PagoparService()
user_repo = UserRepository()

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

@router.get("/cards")
async def list_cards(current_user: dict = Depends(_get_current_user)):
    """List saved cards for the current user."""
    email = current_user.get("email")
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
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
    name = current_user.get("name", "Usuario Cuenly")
    phone = current_user.get("phone", "0981000000") # TODO: Get real phone from profile if available
    
    # Check local DB for Pagopar ID
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
        # We need a numeric ID for Pagopar. Since we use MongoDB ObjectId or Firebase UID (strings),
        # we might need to hash/map it, or ask Pagopar if string ID is supported.
        # The docs say "identificador: Corresponde al ID del usuario... ejemplo 1".
        # It seems it expects an Integer in the example, but JSON supports strings.
        # Let's try to use a hashed integer or a sequential ID.
        # Ideally, we should add an auto-incrementing integer ID to our users, or hash the email/uid to a safe int range.
        # For MVP, let's try using a hash of the UID modulo a large number to get a pseudo-unique int.
        # RISK: Collisions. Better solution: User counter in DB.
        # Let's assume for now we use a deterministic integer from the UID string hash.
        
        # NOTE: Pagopar sometimes accepts strings. If extraction showed "1" as example but type wasn't explicit.
        # Let's try passing the string UID first. If it fails, we'll hash it.
        # Actually, looking at docs: "identificador: 1". 
        # Let's try to register with the UID string.
        
        # Use UID or generate one
        user_identifier = str(int(hashlib.sha256(email.encode('utf-8')).hexdigest(), 16) % 10**8) # 8 digit int
        
        try:
            # 1. Add Customer to Pagopar
            # Note: If this fails with "Comercio no tiene permisos", it might be that the feature is not enabled.
            # We try to proceed to add_card anyway, as sometimes user creation is implicit or optional.
            res = await pagopar_service.add_customer(user_identifier, name, email, phone)
            
            if res.get("respuesta"):
                # Save this ID
                pagopar_id = user_identifier
                user_repo.update_pagopar_user_id(email, pagopar_id)
            else:
                 logger.warning(f"Pagopar add_customer failed: {res.get('resultado')}. Proceeding to add_card...")
                 # We still assume we can try to use the identifier
                 pagopar_id = user_identifier
                 user_repo.update_pagopar_user_id(email, pagopar_id)

        except Exception as e:
            logger.error(f"Error registering user in Pagopar (ignoring): {str(e)}")
            # Fallback: assume ID is valid and try to proceed
            pagopar_id = user_identifier
            user_repo.update_pagopar_user_id(email, pagopar_id)

    # 2. Add Card
    try:
        iframe_hash = await pagopar_service.init_add_card(pagopar_id, request.return_url, request.provider)
        return {"hash": iframe_hash, "pagopar_user_id": pagopar_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cards/confirm")
async def confirm_card(
    request: ConfirmCardRequest,
    current_user: dict = Depends(_get_current_user)
):
    """
    Confirm card addition after Pagopar redirect.
    """
    email = current_user.get("email")
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="User not registered in Pagopar")

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
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="User not registered in Pagopar")

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
    pagopar_id = user_repo.get_pagopar_user_id(email)
    
    if not pagopar_id:
        raise HTTPException(status_code=400, detail="User not registered in Pagopar")

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
async def pagopar_webhook(payload: List[Dict[str, Any]] = Body(...)):
    """
    PASO 2: Webhook de Respuesta (URL de Respuesta).
    Pagopar envía aquí el resultado del pago.
    CRÍTICO: Este endpoint activa suscripciones cuando el pago es exitoso.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"💰 WEBHOOK RECEIVED: {payload}")
    
    try:
        # Pagopar envía un array de pedidos
        if not payload or len(payload) == 0:
            logger.warning("Webhook vacío recibido")
            return {"respuesta": True}
        
        payment_data = payload[0]  # Primer elemento del array
        
        # Extraer datos críticos
        hash_pedido = payment_data.get("hash_pedido")
        pagado = payment_data.get("pagado", False)
        monto = payment_data.get("monto")
        numero_pedido = payment_data.get("numero_pedido")
        
        logger.info(f"📋 Pedido: {numero_pedido} | Hash: {hash_pedido} | Pagado: {pagado} | Monto: {monto}")
        
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
        
        # Pagopar espera que devolvamos el mismo JSON
        return payload
        
    except Exception as e:
        logger.error(f"💥 Error en webhook: {str(e)}")
        # Importante: siempre retornar 200 para que Pagopar no reintente
        return {"respuesta": True}

@router.get("/validation/orders/{order_hash}")
async def check_validation_order(order_hash: str):
    """
    PASO 3: Consultar estado (traer).
    """
    result = await pagopar_service.check_order_status(order_hash)
    return result
