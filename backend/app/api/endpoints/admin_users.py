"""
Endpoints de administración de usuarios
Migrado desde api.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.api.deps import _get_current_user, _get_current_admin_user
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository

router = APIRouter()
logger = logging.getLogger(__name__)


class UpdateUserRoleRequest(BaseModel):
    role: str  # 'admin' o 'user'


class UpdateUserStatusRequest(BaseModel):
    status: str  # 'active' o 'suspended'


@router.get("")
async def admin_get_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Obtiene lista de usuarios (solo para admins)"""
    try:
        user_repo = UserRepository()
        result = user_repo.get_all_users(page, page_size)
        
        # Convertir ObjectId y datetime a string para serialización
        for user in result['users']:
            if '_id' in user:
                user['id'] = str(user['_id'])
                del user['_id']
            for field in ['created_at', 'last_login', 'trial_expires_at', 'email_processing_start_date']:
                if field in user and user[field]:
                    user[field] = user[field].isoformat() if hasattr(user[field], 'isoformat') else str(user[field])
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Error obteniendo usuarios: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo usuarios")


@router.put("/{user_email}/role")
async def admin_update_user_role(
    user_email: str,
    request: UpdateUserRoleRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Actualiza el rol de un usuario (solo para admins)"""
    try:
        user_repo = UserRepository()
        
        # Verificar que el usuario existe
        target_user = user_repo.get_by_email(user_email)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # No permitir cambiar el rol del admin principal
        if user_email.lower() == 'andyvercha@gmail.com' and request.role != 'admin':
            raise HTTPException(status_code=400, detail="No se puede cambiar el rol del administrador principal")
        
        success = user_repo.update_user_role(user_email, request.role)
        if not success:
            raise HTTPException(status_code=400, detail="Rol inválido o usuario no encontrado")
        
        return {
            "success": True,
            "message": f"Rol actualizado a '{request.role}' para {user_email}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando rol: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando rol")


@router.put("/{user_email}/status")
async def admin_update_user_status(
    user_email: str,
    request: UpdateUserStatusRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Actualiza el estado de un usuario (solo para admins)"""
    try:
        user_repo = UserRepository()
        
        # Verificar que el usuario existe
        target_user = user_repo.get_by_email(user_email)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # No permitir suspender al admin principal
        if user_email.lower() == 'andyvercha@gmail.com' and request.status == 'suspended':
            raise HTTPException(status_code=400, detail="No se puede suspender al administrador principal")
        
        success = user_repo.update_user_status(user_email, request.status)
        if not success:
            raise HTTPException(status_code=400, detail="Estado inválido o usuario no encontrado")
        
        # Si se suspendió al usuario, cancelar sus suscripciones activas (idempotente)
        cancelled_msg = ""
        if request.status == 'suspended':
            try:
                sub_repo = SubscriptionRepository()
                ok = await sub_repo.cancel_user_subscriptions(user_email)
                if ok:
                    cancelled_msg = "; suscripciones activas canceladas"
            except Exception as e:
                logger.error(f"Error cancelando suscripciones al suspender {user_email}: {e}")
        
        return {
            "success": True,
            "message": f"Estado actualizado a '{request.status}' para {user_email}{cancelled_msg}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando estado: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando estado")


@router.get("/stats")
async def admin_get_stats(admin: Dict[str, Any] = Depends(_get_current_admin_user)):
    """Obtiene estadísticas del sistema (solo para admins)"""
    try:
        user_repo = UserRepository()
        repo = MongoInvoiceRepository()
        
        # Estadísticas de usuarios
        user_stats = user_repo.get_user_stats()
        
        # Estadísticas de facturas
        headers_coll = repo._headers()
        items_coll = repo._items()
        
        # Total de facturas
        total_invoices = headers_coll.count_documents({})
        
        # Facturas por mes (últimos 6 meses)
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        six_months_ago = now - timedelta(days=180)
        
        monthly_pipeline = [
            {"$match": {"fecha_emision": {"$gte": six_months_ago}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m", "date": "$fecha_emision"}},
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$monto_total"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        monthly_stats = list(headers_coll.aggregate(monthly_pipeline))
        
        # Facturas por usuario (top 10)
        user_pipeline = [
            {"$match": {"owner_email": {"$exists": True, "$ne": None}}},
            {
                "$group": {
                    "_id": "$owner_email",
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$monto_total"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        user_invoices_stats = list(headers_coll.aggregate(user_pipeline))
        
        # Estadísticas por fecha (últimos 30 días)
        thirty_days_ago = now - timedelta(days=30)
        daily_pipeline = [
            {"$match": {"fecha_emision": {"$gte": thirty_days_ago}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_emision"}},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_stats = list(headers_coll.aggregate(daily_pipeline))
        
        return {
            "success": True,
            "user_stats": user_stats,
            "invoice_stats": {
                "total_invoices": total_invoices,
                "total_items": items_coll.count_documents({}),
                "monthly_invoices": monthly_stats,
                "daily_invoices": daily_stats,
                "user_invoices": user_invoices_stats
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")


@router.get("/check")
async def admin_check(user: Dict[str, Any] = Depends(_get_current_user)):
    """Verifica si el usuario actual es admin"""
    try:
        user_repo = UserRepository()
        is_admin = user_repo.is_admin(user.get('email', ''))
        
        return {
            "success": True,
            "is_admin": is_admin,
            "email": user.get('email'),
            "message": "Acceso de administrador verificado" if is_admin else "Usuario sin permisos de administrador"
        }
    except Exception as e:
        logger.error(f"Error verificando admin: {e}")
        raise HTTPException(status_code=500, detail="Error verificando permisos")
