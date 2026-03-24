from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import math

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

@router.get("/stats")
async def admin_get_subscription_stats(admin: Dict[str, Any] = Depends(_get_current_admin_user)):
    """Obtiene estadísticas de suscripciones"""
    try:
        stats = await sub_repo.get_subscription_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de suscripciones: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@router.get("")
async def list_subscriptions(
    page: int = 1, 
    page_size: int = 20, 
    status: str = "active",
    current_user: dict = Depends(_get_current_admin_user)
):
    """List subscriptions with pagination and status filter."""
    skip = (page - 1) * page_size
    query = {}
    if status != "all":
        query["status"] = status.lower().replace("-", "_")

    total = sub_repo.subscriptions_collection.count_documents(query)
    cursor = sub_repo.subscriptions_collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    
    subscriptions = list(cursor)

    # Cache de payment_methods por email para evitar N+1 queries
    emails = list(set(sub.get("user_email", "") for sub in subscriptions))
    payment_methods_map = {}
    for email in emails:
        if email:
            pm = sub_repo.get_user_payment_method(email)
            payment_methods_map[email] = bool(pm and pm.get("pagopar_user_id"))

    for sub in subscriptions:
        sub["_id"] = str(sub.get("_id"))
        sub["has_card"] = payment_methods_map.get(sub.get("user_email", ""), False)
        
    return {
        "data": subscriptions,
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size
    }

@router.post("/{sub_id}/retry-charge")
async def retry_charge(
    sub_id: str,
    current_user: dict = Depends(_get_current_admin_user)
):
    """Manually trigger a charge for a subscription."""
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

        db_user = user_repo.get_by_email(sub["user_email"]) or {}

        order_hash = await pagopar_service.create_order(
            pagopar_user_id,
            amount,
            f"Suscripción {sub['plan_name']}",
            str(sub["_id"]),
            buyer_name=db_user.get("name", ""),
            buyer_email=sub["user_email"],
            buyer_phone=db_user.get("phone", "")
        )
        
        if not order_hash:
            raise HTTPException(status_code=500, detail="Failed to create Pagopar Order")

        success = await pagopar_service.process_payment(pagopar_user_id, order_hash, card_token)
        
        status = "success" if success else "failed"
        
        await trans_repo.log_transaction(
            sub["user_email"],
            amount,
            sub.get("currency", "PYG"),
            status,
            reference=order_hash,
            subscription_id=str(sub["_id"])
        )
        
        if success:
            return {"success": True, "message": "Charge successful"}
        else:
            return {"success": False, "message": "Charge failed"}

    except Exception as e:
        logger.error(f"Error retrying charge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sub_id}")
async def get_subscription_details(
    sub_id: str,
    tx_page: int = Query(default=1, ge=1, description="Página de transacciones"),
    tx_limit: int = Query(default=20, ge=1, le=100, description="Transacciones por página (máx 100)"),
    current_user: dict = Depends(_get_current_admin_user)
):
    """Obtener detalles completos de una suscripción específica con transacciones paginadas."""
    from bson import ObjectId
    try:
        sub = sub_repo.subscriptions_collection.find_one({"_id": ObjectId(sub_id)})
        if not sub:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")

        sub["_id"] = str(sub["_id"])
        payment_method = sub_repo.get_user_payment_method(sub.get("user_email"))
        sub["has_payment_method"] = bool(payment_method)

        # Consultar transacciones desde subscription_transactions (colección correcta)
        try:
            tx_query = {"subscription_id": sub_id}
            tx_total = sub_repo.transactions_collection.count_documents(tx_query)
            tx_skip = (tx_page - 1) * tx_limit
            transactions = list(
                sub_repo.transactions_collection
                .find(tx_query)
                .sort("created_at", -1)
                .skip(tx_skip)
                .limit(tx_limit)
            )
            for tx in transactions:
                tx["_id"] = str(tx.get("_id"))
            sub["recent_transactions"] = transactions
            sub["transactions_total"] = tx_total
            sub["transactions_pages"] = math.ceil(tx_total / tx_limit) if tx_total > 0 else 0
        except Exception as e:
            logger.warning(f"Error obteniendo transacciones de suscripción {sub_id}: {e}")
            sub["recent_transactions"] = []
            sub["transactions_total"] = 0
            sub["transactions_pages"] = 0

        return sub
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo detalles de suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sub_id}/cancel")
async def cancel_subscription_admin(
    sub_id: str,
    reason: str = Body("admin_action", embed=True),
    current_user: dict = Depends(_get_current_admin_user)
):
    """Anular/cancelar una suscripción manualmente (admin)."""
    try:
        success = await sub_repo.cancel_subscription_by_id(
            sub_id=sub_id,
            reason=reason,
            cancelled_by="admin"
        )
        if not success:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada o ya cancelada")
        return {"success": True, "message": "Suscripción anulada exitosamente", "subscription_id": sub_id}
    except Exception as e:
        logger.error(f"Error cancelando suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sub_id}/status")
async def update_subscription_status(
    sub_id: str,
    status: str = Body(..., embed=True),
    current_user: dict = Depends(_get_current_admin_user)
):
    """Actualizar el estado de una suscripción (admin)."""
    from bson import ObjectId
    allowed_statuses = ["active", "past_due", "cancelled"]
    status = status.lower().replace("-", "_")
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Debe ser uno de: {', '.join(allowed_statuses)}")
    try:
        update_data = {"status": status, "updated_at": datetime.utcnow()}
        if status == "cancelled":
            update_data["cancelled_at"] = datetime.utcnow()
            update_data["cancelled_by"] = "admin"
            update_data["cancellation_reason"] = "admin_status_change"
        result = sub_repo.subscriptions_collection.update_one({"_id": ObjectId(sub_id)}, {"$set": update_data})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada o sin cambios")
        return {"success": True, "message": f"Estado actualizado a {status}", "subscription_id": sub_id, "new_status": status}
    except Exception as e:
        logger.error(f"Error actualizando estado de suscripción {sub_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================
# Endpoints migrados desde api.py
# =========================================

@router.post("")
async def admin_create_subscription(
    user_email: str = Body(..., embed=True),
    plan_code: str = Body(..., embed=True),
    payment_method: str = Body("manual", embed=True),
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Asigna un plan a un usuario"""
    try:
        success = await sub_repo.assign_plan_to_user(
            user_email,
            plan_code,
            payment_method
        )

        if not success:
            raise HTTPException(status_code=400, detail="Error asignando plan al usuario")

        # Verificar si el usuario tiene tarjeta para cobro automático
        warnings = []
        pagopar_id = sub_repo.resolve_pagopar_user_id(user_email)
        if not pagopar_id:
            warnings.append("Usuario no tiene Pagopar configurado. No se podrá cobrar automáticamente.")
        else:
            try:
                cards = await pagopar_service.list_cards(pagopar_id)
                if not cards:
                    warnings.append("Usuario no tiene tarjeta registrada en Pagopar. El cobro automático fallará hasta que registre una.")
            except Exception:
                warnings.append("No se pudo verificar tarjetas en Pagopar.")

        response = {
            "success": True,
            "message": f"Plan '{plan_code}' asignado a {user_email}"
        }
        if warnings:
            response["warnings"] = warnings
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error asignando plan: {e}")
        raise HTTPException(status_code=500, detail="Error asignando plan")


@router.get("/user/{user_email}")
async def admin_get_user_subscriptions(
    user_email: str,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Obtiene el historial de suscripciones de un usuario"""
    try:
        current_subscription = await sub_repo.get_user_subscription(user_email)
        history = await sub_repo.get_user_subscriptions_history(user_email)
        
        return {
            "success": True,
            "data": {
                "current_subscription": current_subscription,
                "history": history
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo suscripciones de {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo suscripciones")
