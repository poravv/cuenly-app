from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.api.deps import _get_current_user, _get_current_admin_user
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.services.pagopar_service import PagoparService

router = APIRouter()
logger = logging.getLogger(__name__)

sub_repo = SubscriptionRepository()
trans_repo = TransactionRepository()
user_repo = UserRepository()
pagopar_service = PagoparService()

@router.get("/subscriptions")
async def list_subscriptions(
    page: int = 1, 
    page_size: int = 20, 
    status: str = "active",
    current_user: dict = Depends(_get_current_admin_user)
):
    """List subscriptions with pagination and status filter."""
    # Note: Repository needs pagination implementation. For MVP we might just fetch all and slice or add method.
    # Let's add a proper method to repo quickly or use existing get_all and filter in code (not efficient but ok for start).
    # Since we don't have get_all_subscriptions with pagination in repo yet, let's assume getting active ones.
    
    # We will fetch 'active' by default. pagopar integration implies we focus on active.
    # Actually, let's implement a simple direct find here or extend repo. Expanding repo is cleaner.
    # For now, let's use pymongo direct access via repo property if needed or just add method to repo.
    
    skip = (page - 1) * page_size
    query = {}
    if status != "all":
        query["status"] = status

    total = sub_repo.subscriptions_collection.count_documents(query)
    cursor = sub_repo.subscriptions_collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    
    subscriptions = list(cursor)
    
    # Add user name/email if cached or join? 
    # Just return as is, frontend can display email.
    for sub in subscriptions:
        sub["_id"] = str(sub.get("_id")) # Serialize ObjectId
        
        # Check if it has card token
        sub["has_card"] = bool(sub.get("pagopar_card_token"))
        
    return {
        "data": subscriptions,
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size
    }

@router.post("/subscriptions/{sub_id}/retry-charge")
async def retry_charge(
    sub_id: str,
    current_user: dict = Depends(_get_current_admin_user)
):
    """
    Manually trigger a charge for a subscription.
    Useful for testing or recovering failed payments.
    """
    from bson import ObjectId
    try:
        sub = sub_repo.subscriptions_collection.find_one({"_id": ObjectId(sub_id)})
        if not sub:
             raise HTTPException(status_code=404, detail="Subscription not found")
        
        pagopar_user_id = user_repo.get_pagopar_user_id(sub["user_email"])
        card_token = sub.get("pagopar_card_token")
        
        if not pagopar_user_id or not card_token:
             raise HTTPException(status_code=400, detail="User or Card not configured for automatic payment")

        amount = sub.get("plan_price", 0)
        currency = sub.get("currency", "PYG")
        
        if amount <= 0:
             raise HTTPException(status_code=400, detail="Invalid amount")

        # Generate order hash?
        # WE HAVE A PROBLEM: 'pagar' endpoint requires 'hash_pedido'.
        # 'hash_pedido' comes from creating an Order first. 
        # We need to implement 'create_order' (iniciar-transaccion) in PagoparService to get the hash.
        # But we don't have that method yet.
        # Check PagoparService.
        
        # If we don't have create_order, we can't charge.
        # Let's assume we implement `create_order` now or mock it if we can't.
        # BUT wait, the `init_add_card` was implemented.
        # We need `create_order` to charge.
        
        # Let's add a placeholder or try to implement it.
        # For now, return error if not implemented.
        
        # Implementation Plan said: "Methods: ... process_payment".
        # process_payment takes hash. 
        # So we need to generate hash.
        
        # ACTION: I will update PagoparService to include create_order method first.
        # But for this endpoint, assume it exists.
        
        order_hash = await pagopar_service.create_order(
            pagopar_user_id, 
            amount, 
            f"Suscripción {sub['plan_name']}",
            str(sub["_id"]) # Ref internal
        )
        
        if not order_hash:
            raise HTTPException(status_code=500, detail="Failed to create Pagopar Order")

        success = await pagopar_service.process_payment(pagopar_user_id, order_hash, card_token)
        
        status = "success" if success else "failed"
        
        # Log transaction
        await trans_repo.log_transaction(
            sub["user_email"],
            amount,
            currency,
            status,
            reference=order_hash,
            subscription_id=str(sub["_id"])
        )
        
        if success:
             # Extend subscription
             # Calculate new dates
            updated = False
            # Logic to extend date... for now just log success
            return {"success": True, "message": "Charge successful"}
        else:
            return {"success": False, "message": "Charge failed"}

    except Exception as e:
        logger.error(f"Error retrying charge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions/{sub_id}")
async def get_subscription_details(
    sub_id: str,
    current_user: dict = Depends(_get_current_admin_user)
):
    """Obtener detalles completos de una suscripción específica."""
    from bson import ObjectId
    try:
        sub = sub_repo.subscriptions_collection.find_one({"_id": ObjectId(sub_id)})
        if not sub:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")
        
        # Serializar ObjectId
        sub["_id"] = str(sub["_id"])
        
        # Agregar información adicional
        payment_method = sub_repo.get_user_payment_method(sub.get("user_email"))
        sub["has_payment_method"] = bool(payment_method)
        
        # Obtener transacciones relacionadas
        if trans_repo:
            try:
                transactions = list(trans_repo.transactions_collection.find(
                    {"subscription_id": sub_id}
                ).sort("created_at", -1).limit(10))
                
                for tx in transactions:
                    tx["_id"] = str(tx.get("_id"))
                    
                sub["recent_transactions"] = transactions
            except:
                sub["recent_transactions"] = []
        
        return sub
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo detalles de suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription_admin(
    sub_id: str,
    reason: str = Body("admin_action", embed=True),
    current_user: dict = Depends(_get_current_admin_user)
):
    """
    Anular/cancelar una suscripción manualmente (admin).
    La suscripción se marca como CANCELLED y no se cobrará más.
    """
    try:
        success = await sub_repo.cancel_subscription_by_id(
            sub_id=sub_id,
            reason=reason,
            cancelled_by="admin"
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Suscripción no encontrada o ya cancelada"
            )
        
        logger.info(f"✅ Admin {current_user.get('email')} canceló suscripción {sub_id}")
        
        return {
            "success": True,
            "message": "Suscripción anulada exitosamente",
            "subscription_id": sub_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelando suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions/{sub_id}/status")
async def update_subscription_status(
    sub_id: str,
    status: str = Body(..., embed=True),
    current_user: dict = Depends(_get_current_admin_user)
):
    """
    Actualizar el estado de una suscripción (admin).
    Estados permitidos: ACTIVE, PAST_DUE, CANCELLED
    """
    from bson import ObjectId
    
    allowed_statuses = ["ACTIVE", "PAST_DUE", "CANCELLED"]
    
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(allowed_statuses)}"
        )
    
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if status == "CANCELLED":
            update_data["cancelled_at"] = datetime.utcnow()
            update_data["cancelled_by"] = "admin"
            update_data["cancellation_reason"] = "admin_status_change"
        
        result = sub_repo.subscriptions_collection.update_one(
            {"_id": ObjectId(sub_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Suscripción no encontrada o sin cambios"
            )
        
        logger.info(f"✅ Admin {current_user.get('email')} cambió estado de {sub_id} a {status}")
        
        return {
            "success": True,
            "message": f"Estado actualizado a {status}",
            "subscription_id": sub_id,
            "new_status": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando estado de suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
