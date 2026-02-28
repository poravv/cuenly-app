"""
Endpoints de administración de límites de IA y scheduler.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from app.api.deps import _get_current_admin_user
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.audit_repository import get_audit_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/reset-stats")
async def get_reset_stats(admin: Dict[str, Any] = Depends(_get_current_admin_user)):
    """Estadísticas de reseteo de límites de IA."""
    try:
        sub_repo = SubscriptionRepository()
        user_repo = UserRepository()
        coll = user_repo._coll()

        # Suscripciones activas
        active_subs = sub_repo.subscriptions_collection.count_documents({"status": "active"})

        # Usuarios reseteados este mes (ai_invoices_processed == 0 y tienen plan activo)
        now = datetime.utcnow()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        resetted = coll.count_documents({
            "ai_last_reset": {"$gte": first_of_month}
        })

        return {
            "success": True,
            "data": {
                "active_subscriptions": active_subs,
                "resetted_this_month": resetted,
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo reset stats: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas de reseteo")


@router.post("/reset-monthly")
async def execute_monthly_reset(
    http_request: Request,
    admin: Dict[str, Any] = Depends(_get_current_admin_user),
):
    """Ejecuta reseteo mensual de límites de IA para todos los usuarios con suscripción activa."""
    try:
        sub_repo = SubscriptionRepository()
        user_repo = UserRepository()
        coll = user_repo._coll()
        now = datetime.utcnow()

        # Obtener emails con suscripción activa
        active_subs = list(sub_repo.subscriptions_collection.find(
            {"status": "active"},
            {"user_email": 1, "_id": 0}
        ))
        active_emails = [s["user_email"] for s in active_subs if s.get("user_email")]

        if not active_emails:
            return {"success": True, "data": {"users_reset": 0, "message": "No hay suscripciones activas"}}

        # Resetear ai_invoices_processed para todos los usuarios con suscripción activa
        result = coll.update_many(
            {"email": {"$in": active_emails}},
            {"$set": {"ai_invoices_processed": 0, "ai_last_reset": now}}
        )

        get_audit_repo().log(
            action="monthly_ai_reset",
            admin_email=admin.get("email", "unknown"),
            details={"users_reset": result.modified_count, "total_active": len(active_emails)},
            ip_address=http_request.client.host if http_request.client else None,
        )

        return {
            "success": True,
            "data": {
                "users_reset": result.modified_count,
                "message": f"Límites de IA reseteados para {result.modified_count} usuarios"
            }
        }
    except Exception as e:
        logger.error(f"Error en reseteo mensual: {e}")
        raise HTTPException(status_code=500, detail="Error ejecutando reseteo mensual")


@router.post("/reset-user/{user_email}")
async def reset_user_ai_limits(
    user_email: str,
    http_request: Request,
    admin: Dict[str, Any] = Depends(_get_current_admin_user),
):
    """Resetea los límites de IA de un usuario específico."""
    try:
        user_repo = UserRepository()
        user = user_repo.get_by_email(user_email)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        old_processed = user.get("ai_invoices_processed", 0)
        result = user_repo._coll().update_one(
            {"email": user_email.lower()},
            {"$set": {"ai_invoices_processed": 0, "ai_last_reset": datetime.utcnow()}}
        )

        get_audit_repo().log(
            action="user_ai_reset",
            admin_email=admin.get("email", "unknown"),
            target_user=user_email,
            details={"old_processed": old_processed},
            ip_address=http_request.client.host if http_request.client else None,
        )

        return {
            "success": True,
            "message": f"Límites de IA reseteados para {user_email} (anterior: {old_processed})"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reseteando límites para {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Error reseteando límites")
