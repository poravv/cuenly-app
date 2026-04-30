"""
Endpoints de planes (públicos), admin stats y admin check.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.api.deps import _get_current_user, _get_current_admin
from app.config.settings import settings
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
import re

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/admin/stats")
async def admin_get_stats(admin: Dict[str, Any] = Depends(_get_current_admin)):
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
                    "total_amount": {"$sum": "$monto_total"},
                    "xml_nativo": {"$sum": {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$fuente", ""]}, "regex": "XML"}}, 1, 0]}},
                    "openai_vision": {"$sum": {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$fuente", ""]}, "regex": "OPENAI"}}, 1, 0]}},
                }
            },
            {"$sort": {"_id": 1}}
        ]

        monthly_stats = list(headers_coll.aggregate(monthly_pipeline))

        # Source totals (XML nativo vs OpenAI Vision)
        source_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "xml_nativo": {"$sum": {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$fuente", ""]}, "regex": "XML"}}, 1, 0]}},
                    "openai_vision": {"$sum": {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$fuente", ""]}, "regex": "OPENAI"}}, 1, 0]}},
                    "total_amount": {"$sum": "$monto_total"},
                }
            }
        ]
        source_result = list(headers_coll.aggregate(source_pipeline))
        source_totals = source_result[0] if source_result else {"xml_nativo": 0, "openai_vision": 0, "total_amount": 0}
        source_totals.pop("_id", None)
        
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
                "user_invoices": user_invoices_stats,
                "source_totals": source_totals
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@router.get("/admin/check")
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

# =====================================
# ENDPOINTS DE PLANES Y SUSCRIPCIONES
# =====================================

# Modelos para planes
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

class SubscriptionCreateRequest(BaseModel):
    user_email: str
    plan_code: str
    payment_method: str = "manual"
    payment_reference: Optional[str] = None

# API pública para planes (sin autenticación)
@router.get("/api/plans", tags=["Plans - Public"])
async def get_public_plans():
    """Obtiene todos los planes activos - API pública para integración externa"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        plans = await repo.get_all_plans(include_inactive=False)
        
        return {
            "success": True,
            "data": plans,
            "count": len(plans)
        }
    except Exception as e:
        logger.error(f"Error obteniendo planes públicos: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo planes")

@router.get("/api/plans/{plan_code}", tags=["Plans - Public"])
async def get_public_plan(plan_code: str):
    """Obtiene un plan específico - API pública"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        plan = await repo.get_plan_by_code(plan_code)
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        return {
            "success": True,
            "data": plan
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo plan {plan_code}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo plan")

# Endpoints de suscripción para usuario autenticado
@router.get("/plans", tags=["Plans"]) # Public alias — no auth required (por diseño)
async def list_public_plans():
    """
    Lista los planes públicos activos disponibles para suscripción.
    """
    repo = SubscriptionRepository()
    # Solo planes activos para usuarios normales
    plans = await repo.get_all_plans(include_inactive=False)
    
    return {
        "success": True, 
        "data": plans,
        "count": len(plans)
    }


_CDC_TOKEN_RE = re.compile(r"\d{44}")


def _minio_key_matches_header_strict(
    client: "Minio",
    header: Dict[str, Any],
    minio_key: str,
) -> bool:
    """Validación estricta: solo sirve archivo si evidencia fuerte de correspondencia."""
    key = str(minio_key or "").strip()
    if not key:
        return False

    cdc = str(header.get("cdc") or "").strip()
    if not cdc:
        # Sin CDC no se puede validar criptográficamente; confiamos solo en llave persistida.
        return True

    cdc_tokens = _CDC_TOKEN_RE.findall(key)
    if cdc_tokens:
        return cdc in cdc_tokens

    # Si no hay CDC en el nombre, intentamos validar solo para XML por contenido.
    if not key.lower().endswith(".xml"):
        return False

    try:
        obj = client.get_object(settings.MINIO_BUCKET, key)
        try:
            content = obj.read().decode("utf-8", errors="ignore")
        finally:
            obj.close()
            obj.release_conn()
    except Exception as e:
        logger.warning(f"⚠️ No se pudo validar XML por contenido para {header.get('_id')}: {e}")
        return False

    cdc_digits = "".join(ch for ch in cdc if ch.isdigit())
    content_digits = "".join(ch for ch in content if ch.isdigit())
    return cdc in content or (cdc_digits and cdc_digits in content_digits)


def _resolve_minio_key_strict(
    header: Dict[str, Any],
    client: "Minio",
) -> str:
    """No adivina ni backfillea: solo acepta minio_key persistido y validado."""
    minio_key = str(header.get("minio_key") or "").strip()
    if not minio_key:
        return ""

    if not _minio_key_matches_header_strict(client, header, minio_key):
        logger.warning(
            "⚠️ minio_key rechazado por inconsistencia con factura %s: %s",
            header.get("_id"),
            minio_key,
        )
        return ""

    return minio_key

# Endpoints de suscripciones - TODOS MIGRADOS a admin_subscriptions.py
# Rutas: /admin/subscriptions/stats, POST /admin/subscriptions, GET /admin/subscriptions/user/{user_email}

@router.get("/admin/stats/filtered", tags=["Admin - Stats"])
async def admin_get_filtered_stats(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    user_email: Optional[str] = Query(None, description="Email del usuario"),
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Obtiene estadísticas filtradas por fecha y usuario"""
    try:
        user_repo = UserRepository()
        repo = MongoInvoiceRepository()
        headers_coll = repo._headers()
        
        # Construir filtro de fecha
        date_filter = {}
        if start_date:
            from datetime import datetime
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            date_filter["$gte"] = start_dt
        if end_date:
            from datetime import datetime
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Agregar 1 día para incluir todo el día final
            from datetime import timedelta
            end_dt = end_dt + timedelta(days=1)
            date_filter["$lt"] = end_dt
        
        # Construir query principal
        main_query = {}
        if date_filter:
            main_query["fecha_emision"] = date_filter
        if user_email:
            main_query["owner_email"] = user_email
        
        # Estadísticas básicas
        total_invoices = headers_coll.count_documents(main_query)
        
        # Aggregation para estadísticas detalladas
        pipeline = [
            {"$match": main_query},
            {
                "$group": {
                    "_id": None,
                    "total_amount": {"$sum": "$monto_total"},
                    "avg_amount": {"$avg": "$monto_total"},
                    "min_amount": {"$min": "$monto_total"},
                    "max_amount": {"$max": "$monto_total"}
                }
            }
        ]
        
        amount_stats = list(headers_coll.aggregate(pipeline))
        amount_data = amount_stats[0] if amount_stats else {
            "total_amount": 0,
            "avg_amount": 0,
            "min_amount": 0,
            "max_amount": 0
        }
        
        # Estadísticas por día
        daily_pipeline = [
            {"$match": main_query},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_emision"}},
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$monto_total"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_stats = list(headers_coll.aggregate(daily_pipeline))
        
        # Estadísticas por hora (si hay datos del mismo día)
        hourly_stats = []
        if not user_email and start_date == end_date:  # Solo si es el mismo día
            hourly_pipeline = [
                {"$match": main_query},
                {
                    "$group": {
                        "_id": {"$hour": "$fecha_emision"},
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            hourly_stats = list(headers_coll.aggregate(hourly_pipeline))
        
        # Estadísticas por usuario (si no se filtró por usuario específico)
        user_stats = []
        if not user_email:
            user_pipeline = [
                {"$match": main_query},
                {
                    "$group": {
                        "_id": "$owner_email",
                        "count": {"$sum": 1},
                        "total_amount": {"$sum": "$monto_total"}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 20}
            ]
            user_stats = list(headers_coll.aggregate(user_pipeline))
        
        return {
            "success": True,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "user_email": user_email
            },
            "stats": {
                "total_invoices": total_invoices,
                "total_amount": amount_data["total_amount"],
                "avg_amount": amount_data["avg_amount"],
                "min_amount": amount_data["min_amount"],
                "max_amount": amount_data["max_amount"],
                "daily_breakdown": daily_stats,
                "hourly_breakdown": hourly_stats,
                "user_breakdown": user_stats
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas filtradas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

# =====================================
# ENDPOINTS DE RESETEO MENSUAL DE IA
# =====================================

