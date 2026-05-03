"""
Endpoints de administración de planes
Migrado desde api.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import logging

from app.api.deps import _get_current_user, _get_current_admin_user
from app.core.redis_client import get_redis_client
from app.repositories.subscription_repository import SubscriptionRepository

router = APIRouter()
logger = logging.getLogger(__name__)

PLANS_CACHE_KEY = "cuenly:plans:active"
PLANS_CACHE_TTL = 3600  # 1 hora — los planes son semi-estáticos


def _get_redis():
    """Obtiene cliente Redis; retorna None si no está disponible."""
    try:
        return get_redis_client()
    except Exception as e:
        logger.warning("Redis no disponible para cache de planes: %s", e)
        return None


def _invalidate_plans_cache() -> None:
    """Elimina el cache de planes activos en Redis. Silencioso si Redis no está disponible."""
    try:
        redis = get_redis_client()
        redis.delete(PLANS_CACHE_KEY)
        logger.info("Cache de planes invalidado")
    except Exception as e:
        logger.warning("No se pudo invalidar cache de planes: %s", e)


class PlanCreateRequest(BaseModel):
    name: str
    code: str
    description: str
    price: float
    currency: str = "USD"
    billing_period: str  # monthly, yearly, one_time
    features: Dict[str, Any]
    status: str = "active"
    is_popular: bool = False
    sort_order: int = 0


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    billing_period: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    is_popular: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("")
async def admin_get_plans(
    include_inactive: bool = Query(False),
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Obtiene todos los planes (incluye inactivos si se especifica)"""
    try:
        repo = SubscriptionRepository()
        plans = await repo.get_all_plans(include_inactive=include_inactive)
        
        return {
            "success": True,
            "data": plans,
            "count": len(plans)
        }
    except Exception as e:
        logger.error(f"Error obteniendo planes admin: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo planes")


@router.post("")
async def admin_create_plan(
    plan: PlanCreateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Crea un nuevo plan de suscripción"""
    try:
        repo = SubscriptionRepository()
        
        # Verificar que el código no exista
        existing_plan = await repo.get_plan_by_code(plan.code)
        if existing_plan:
            raise HTTPException(status_code=400, detail="Ya existe un plan con ese código")
        
        success = await repo.create_plan(plan.dict())
        if not success:
            raise HTTPException(status_code=500, detail="Error creando plan")

        _invalidate_plans_cache()

        return {
            "success": True,
            "message": f"Plan '{plan.name}' creado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando plan: {e}")
        raise HTTPException(status_code=500, detail="Error creando plan")


@router.put("/{plan_code}")
async def admin_update_plan(
    plan_code: str,
    plan: PlanUpdateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Actualiza un plan existente"""
    try:
        repo = SubscriptionRepository()
        
        # Verificar que el plan existe
        existing_plan = await repo.get_plan_by_code(plan_code)
        if not existing_plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        # Actualizar solo los campos que se enviaron
        update_data = {k: v for k, v in plan.dict().items() if v is not None}
        
        success = await repo.update_plan(plan_code, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Error actualizando plan")

        _invalidate_plans_cache()

        return {
            "success": True,
            "message": f"Plan '{plan_code}' actualizado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando plan: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando plan")


@router.delete("/{plan_code}")
async def admin_delete_plan(
    plan_code: str,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Elimina un plan (soft delete)"""
    try:
        repo = SubscriptionRepository()
        
        success = await repo.delete_plan(plan_code)
        if not success:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        _invalidate_plans_cache()

        return {
            "success": True,
            "message": f"Plan '{plan_code}' eliminado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando plan: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando plan")


@router.get("/system-templates")
async def list_system_templates_for_plans(
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Lista todos los system templates disponibles para asignar a planes"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()
        templates = repo.get_system_templates()

        return {
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "system_code": t.system_code,
                    "name": t.name,
                    "description": t.description,
                    "fields_count": len(t.fields),
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in templates
            ],
            "count": len(templates)
        }
    except Exception as e:
        logger.error(f"Error listando system templates para planes: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo system templates")


# API pública para planes (sin autenticación de admin, pero con usuario autenticado)
@router.get("/public")
async def list_public_plans(
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Lista los planes públicos activos disponibles para suscripción.
    """
    redis = _get_redis()
    if redis:
        cached = redis.get(PLANS_CACHE_KEY)
        if cached:
            logger.debug("Cache HIT para planes activos (/admin/plans/public)")
            return json.loads(cached)

    repo = SubscriptionRepository()
    plans = await repo.get_all_plans(include_inactive=False)

    result = {
        "success": True,
        "data": plans,
        "count": len(plans)
    }

    if redis:
        redis.setex(PLANS_CACHE_KEY, PLANS_CACHE_TTL, json.dumps(result, default=str))
        logger.debug("Planes activos guardados en cache (/admin/plans/public, TTL %ds)", PLANS_CACHE_TTL)

    return result
