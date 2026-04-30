"""
Endpoints de dashboard y preferencias de UI.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from app.api.deps import _get_current_user, _get_current_admin
from app.repositories.user_repository import UserRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.config.settings import settings
from app.modules.mongo_query_service import get_mongo_query_service
from app.modules.email_processor.config_store import list_configs as db_list_configs

router = APIRouter()
logger = logging.getLogger(__name__)


# Preferencias UI
class AutoRefreshPayload(BaseModel):
    enabled: bool
    interval_ms: int = 30000
    uid: Optional[str] = None

class AutoRefreshPref(BaseModel):
    uid: str
    enabled: bool
    interval_ms: int

class ToggleEnabledPayload(BaseModel):
    enabled: bool


@router.get("/dashboard/stats")
async def get_dashboard_stats(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtiene estadísticas generales para el dashboard."""
    try:
        user_repo = UserRepository()
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        
        # Filtro base
        q = {"owner_email": owner_email} if owner_email else {}
        q["status"] = {"$nin": ["FAILED", "PENDING_AI", "PROCESSING"]}
        q["numero_documento"] = {"$not": {"$regex": "^ERR_"}}
        
        # Total facturas
        total_invoices = repo._headers().count_documents(q)
        
        # Total monto
        pipeline = [
            {"$match": q},
            {"$group": {"_id": None, "total_amount": {"$sum": "$totales.total"}, "avg_amount": {"$avg": "$totales.total"}}}
        ]
        res = list(repo._headers().aggregate(pipeline))
        stats = res[0] if res else {"total_amount": 0, "avg_amount": 0}
        
        return {
            "success": True,
            "stats": {
                "total_invoices": total_invoices,
                "total_amount": stats.get("total_amount", 0),
                "average_amount": stats.get("avg_amount", 0)
            }
        }
    except Exception as e:
        logger.error(f"Error dashboard stats: {e}")
        return {"success": False, "stats": {"total_invoices": 0, "total_amount": 0, "average_amount": 0}}

@router.get("/dashboard/monthly-stats")
async def get_dashboard_monthly(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtiene evolución mensual de inversión con histórico completo."""
    try:
        owner_email = (user.get('email') or '').lower()
        query_service = get_mongo_query_service()
        owner = owner_email if settings.MULTI_TENANT_ENFORCE else None

        months = query_service.get_available_months(owner_email=owner)
        monthly_data = [
            {
                "year_month": m.get("year_month"),
                "total_amount": float(m.get("total_amount", 0)),
                "count": int(m.get("count", 0))
            }
            for m in months
            if m.get("year_month")
        ]
        monthly_data.sort(key=lambda item: item["year_month"])
        
        return {"success": True, "monthly_data": monthly_data}
    except Exception as e:
        logger.error(f"Error dashboard monthly: {e}")
        return {"success": False, "monthly_data": []}

@router.get("/dashboard/top-emisores")
async def get_dashboard_top_emisores(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        q = {"owner_email": owner_email} if owner_email else {}
        q["status"] = {"$nin": ["FAILED", "PENDING_AI", "PROCESSING"]}
        q["numero_documento"] = {"$not": {"$regex": "^ERR_"}}
        
        pipeline = [
            {"$match": q},
            {
                "$group": {
                    "_id": "$emisor.nombre",
                    "total_amount": {"$sum": "$totales.total"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"total_amount": -1}},
            {"$limit": 5}
        ]
        data = list(repo._headers().aggregate(pipeline))
        top = [
            {"nombre": d["_id"] or "Desconocido", "total_amount": d["total_amount"], "count": d["count"]}
            for d in data
        ]
        return {"success": True, "top_emisores": top}
    except Exception as e:
        logger.error(f"Error dashboard top emisores: {e}")
        return {"success": False, "top_emisores": []}

@router.get("/dashboard/recent-invoices")
async def get_dashboard_recent(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        q = {"owner_email": owner_email} if owner_email else {}
        q["status"] = {"$nin": ["FAILED", "PENDING_AI", "PROCESSING"]}
        q["numero_documento"] = {"$not": {"$regex": "^ERR_"}}
        
        cursor = repo._headers().find(q).sort("fecha_emision", -1).limit(5)
        invoices = []
        for doc in cursor:
            # Fallback a totales.total si monto_total no existe
            monto = doc.get("monto_total")
            if monto is None or monto == 0:
                monto = doc.get("totales", {}).get("total", 0)
                
            invoices.append({
                "id": str(doc["_id"]),
                "numero_documento": doc.get("numero_documento"),
                "emisor": doc.get("emisor", {}).get("nombre"),
                "monto_total": monto,
                "fecha_emision": doc.get("fecha_emision"),
                "moneda": doc.get("moneda", "GS")
            })
        return {"success": True, "invoices": invoices}
    except Exception as e:
        logger.error(f"Error dashboard recent: {e}")
        return {"success": False, "invoices": []}

@router.get("/dashboard/system-status")
async def get_dashboard_system_status(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
         owner_email = (user.get('email') or '').lower()
         
         # Safely get email configs
         email_configs = []
         try:
            email_configs = db_list_configs(include_password=False, owner_email=owner_email)
         except Exception as db_err:
            logger.error(f"Error DB listing configs: {db_err}")
            
         # Check OpenAI Key
         openai_key = getattr(settings, "OPENAI_API_KEY", "")
         masked_key = f"{openai_key[:5]}...({len(str(openai_key))})" if openai_key else "None"
         logger.info(f"🔍 DEBUG SYSTEM STATUS: OpenAI Key: {masked_key}")
         openai_ok = bool(openai_key and len(str(openai_key)) > 10)

         return {
             "success": True,
             "status": {
                 "email_configured": len(email_configs) > 0,
                 "email_configs_count": len(email_configs),
                 "openai_configured": openai_ok
             }
         }
    except Exception as e:
        logger.error(f"Error dashboard system status: {e}")
        # Return partial success to avoid frontend blanking out everything if possible, 
        # but frontend checks success=True. 
        return {"success": False, "status": {"openai_configured": False, "email_configured": False}}

# -----------------------------
# Preferencias (UI / Auto‑refresh) - Storage en memoria
# -----------------------------
_auto_refresh_prefs: Dict[str, Dict] = {}

def prefs_get_auto_refresh(uid: str) -> Dict:
    return _auto_refresh_prefs.get(uid, {"enabled": False, "interval_ms": 30000})

def prefs_set_auto_refresh(uid: str, enabled: bool, interval_ms: int) -> Dict:
    _auto_refresh_prefs[uid] = {"enabled": enabled, "interval_ms": interval_ms}
    return _auto_refresh_prefs[uid]

@router.get("/prefs/auto-refresh", response_model=AutoRefreshPref)
async def get_auto_refresh(uid: Optional[str] = Query(default="global"), user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtiene preferencia de auto-refresh. Requiere autenticación."""
    try:
        # Forzar uid al email del usuario autenticado para tenant isolation
        effective_uid = (user.get("email") or "global").lower()
        data = prefs_get_auto_refresh(effective_uid)
        return AutoRefreshPref(uid=effective_uid, enabled=bool(data.get("enabled", False)), interval_ms=int(data.get("interval_ms", 30000)))
    except Exception as e:
        logger.error(f"Error al obtener preferencia auto-refresh: {e}")
        raise HTTPException(status_code=500, detail="No se pudo obtener preferencia")

@router.post("/prefs/auto-refresh", response_model=AutoRefreshPref)
async def set_auto_refresh(payload: AutoRefreshPayload, user: Dict[str, Any] = Depends(_get_current_user)):
    """Guarda preferencia de auto-refresh. Requiere autenticación."""
    try:
        # Forzar uid al email del usuario autenticado para tenant isolation
        effective_uid = (user.get("email") or "global").lower()
        data = prefs_set_auto_refresh(effective_uid, payload.enabled, payload.interval_ms)
        return AutoRefreshPref(uid=effective_uid, enabled=bool(data.get("enabled", False)), interval_ms=int(data.get("interval_ms", 30000)))
    except Exception as e:
        logger.error(f"Error al guardar preferencia auto-refresh: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar preferencia")

