"""
Endpoints de acceso a facturas: listado v2, descarga, búsqueda y estadísticas.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.api.deps import (
    _get_current_user,
    _get_current_user_with_trial_check,
    _get_current_admin,
)
from app.config.settings import settings
from app.repositories.user_repository import UserRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.mongo_query_service import get_mongo_query_service
from app.models.models import InvoiceData, ProductoFactura
from app.utils.validators import SecurityValidators, log_security_event, ValidationError
from app.api.routers.plans import _resolve_minio_key_strict

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/v2/invoices/headers")
async def v2_list_headers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    ruc_emisor: Optional[str] = None,
    ruc_receptor: Optional[str] = None,
    year_month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="fecha_emision", description="Campo de ordenamiento: fecha_emision | created_at"),
    emisor_nombre: Optional[str] = Query(default=None, description="Filtro por nombre del emisor (regex i)"),
    include_non_done: bool = Query(default=False, description="Si true, incluye PENDING_AI/FAILED/PROCESSING y ERR_*"),
    user: Dict[str, Any] = Depends(_get_current_user),
):
    try:
        repo = MongoInvoiceRepository()
        coll = repo._headers()
        q = {}
        if ruc_emisor:
            q["emisor.ruc"] = ruc_emisor
        if ruc_receptor:
            q["receptor.ruc"] = ruc_receptor
        if year_month:
            q["mes_proceso"] = year_month
        from datetime import datetime
        if date_from or date_to:
            rng = {}
            if date_from:
                try:
                    rng["$gte"] = datetime.fromisoformat(date_from)
                except Exception:
                    pass
            if date_to:
                try:
                    rng["$lte"] = datetime.fromisoformat(date_to)
                except Exception:
                    pass
            if rng:
                q["fecha_emision"] = rng
        if emisor_nombre:
            q["emisor.nombre"] = {"$regex": emisor_nombre, "$options": "i"}
        if search:
            q["$or"] = [
                {"emisor.nombre": {"$regex": search, "$options": "i"}},
                {"receptor.nombre": {"$regex": search, "$options": "i"}},
                {"numero_documento": {"$regex": search, "$options": "i"}},
            ]
        # Restringir por usuario si multi-tenant
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner

        # Por defecto, la lista de facturas muestra solo documentos finales válidos.
        # Los pendientes/errores van a la cola de procesos.
        if not include_non_done:
            q["status"] = {"$nin": ["FAILED", "PENDING_AI", "PROCESSING"]}
            q["numero_documento"] = {"$not": {"$regex": "^ERR_"}}
        
        # Lógica de ordenamiento
        sort_field = "fecha_emision"
        if sort_by == "created_at":
            sort_field = "created_at"
            
        total = coll.count_documents(q)
        cursor = coll.find(q).sort(sort_field, -1).skip((page-1)*page_size).limit(page_size)
        items = []
        # Pre-cargar colección de ítems para resumen de descripción
        items_coll = repo._items()
        for d in cursor:
            header_id = d.get("_id")
            # Generar resumen de descripción a partir de los primeros ítems
            try:
                sample_items = list(items_coll.find({"header_id": header_id}, {"descripcion": 1}).sort("linea", 1).limit(5))
                descripciones = [it.get("descripcion", "") for it in sample_items if it.get("descripcion")]
                if descripciones:
                    d["descripcion_factura"] = ", ".join(descripciones[:5])
                # Contar total de ítems para mostrar en UI
                d["item_count"] = items_coll.count_documents({"header_id": header_id})
            except Exception:
                pass
            d["id"] = header_id
            d.pop("_id", None)
            items.append(d)
        return {"success": True, "page": page, "page_size": page_size, "total": total, "data": items}
    except Exception as e:
        logger.error(f"Error listando headers v2: {e}")
        raise HTTPException(status_code=500, detail="Error listando headers")

@router.get("/v2/invoices/{header_id}")
async def v2_get_invoice(header_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        repo = MongoInvoiceRepository()
        q = {"_id": header_id}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        h = repo._headers().find_one(q)
        if not h:
            raise HTTPException(status_code=404, detail="No encontrado")
        iq = {"header_id": header_id}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                iq['owner_email'] = owner
        items = list(repo._items().find(iq).sort("linea", 1))
        
        # Ajuste de response: si las descripciones vinieran vacías por datos históricos,
        # intentar recuperar descripciones desde un header_id sin prefijo de owner (legacy)
        try:
            if (not items) or all(not (it.get("descripcion") or "").strip() for it in items):
                if ":" in header_id:
                    legacy_id = header_id.split(":", 1)[1]
                    legacy_items = list(repo._items().find({"header_id": legacy_id}).sort("linea", 1))
                    if legacy_items:
                        legacy_by_line = {int(it.get("linea", idx+1)): it for idx, it in enumerate(legacy_items)}
                        for it in items:
                            linea = int(it.get("linea", 0) or 0)
                            src = legacy_by_line.get(linea)
                            if src and (src.get("descripcion") or "").strip():
                                it["descripcion"] = src.get("descripcion")
        except Exception:
            pass
        h["id"] = h.get("_id")
        h.pop("_id", None)
        for it in items:
            it["id"] = str(it.get("_id"))
            it.pop("_id", None)
            # Alias de compatibilidad: 'nombre' y 'articulo' = 'descripcion'
            try:
                desc = (it.get("descripcion") or "").strip()
                it.setdefault("nombre", desc)
                it.setdefault("articulo", desc)
            except Exception:
                pass
        
        # Agregar descripcion_factura de conveniencia en el response (no en DB)
        try:
            descs = [str(it.get("descripcion", "")).strip() for it in items if (it.get("descripcion") or "").strip()]
            if descs:
                h["descripcion_factura"] = ", ".join(descs[:10])
        except Exception:
            pass
        
        return {"success": True, "header": h, "items": items}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo invoice v2: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo invoice")

@router.get("/v2/invoices/items")
async def v2_list_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    header_id: Optional[str] = None,
    iva: Optional[int] = Query(default=None, description="0,5,10"),
    search: Optional[str] = None,
    year_month: Optional[str] = None,
    user: Dict[str, Any] = Depends(_get_current_user),
):
    try:
        repo = MongoInvoiceRepository()
        items_coll = repo._items()
        q: Dict[str, Any] = {}
        if header_id:
            q["header_id"] = header_id
        if iva is not None:
            try:
                q["iva"] = int(iva)
            except Exception:
                pass
        if search:
            q["descripcion"] = {"$regex": search, "$options": "i"}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        if year_month and not header_id:
            hq = {"mes_proceso": year_month}
            if settings.MULTI_TENANT_ENFORCE and (user.get('email')):
                hq['owner_email'] = (user.get('email') or '').lower()
            header_ids = [h["_id"] for h in repo._headers().find(hq, {"_id": 1})]
            if header_ids:
                q["header_id"] = {"$in": header_ids}
            else:
                return {"success": True, "page": page, "page_size": page_size, "total": 0, "data": []}
        total = items_coll.count_documents(q)
        cursor = items_coll.find(q).sort([("header_id", 1), ("linea", 1)]).skip((page-1)*page_size).limit(page_size)
        data = []
        for d in cursor:
            d["id"] = str(d.get("_id"))
            d.pop("_id", None)
            # Alias de compatibilidad: 'nombre' y 'articulo' = 'descripcion'
            try:
                desc = (d.get("descripcion") or "").strip()
                d.setdefault("nombre", desc)
                d.setdefault("articulo", desc)
            except Exception:
                pass
            data.append(d)
        return {"success": True, "page": page, "page_size": page_size, "total": total, "data": data}
    except Exception as e:
        logger.error(f"Error listando items v2: {e}")
        raise HTTPException(status_code=500, detail="Error listando items")


def _cleanup_processing_cache_for_deleted_headers(
    repo: MongoInvoiceRepository,
    headers: List[Dict[str, Any]],
    fallback_owner: str = "",
) -> int:
    """
    Limpia cache de procesamiento (processed_emails) asociado a headers eliminados.
    Estrategia (multi-match para máxima cobertura):
    1. owner_email + message_id (RFC822 Message-ID, match principal)
    2. owner_email + minio_key + manual_upload (uploads manuales)
    3. _id regex por owner_email (fallback para datos legacy con IMAP UID como message_id)
    """
    if not headers:
        return 0

    try:
        coll = repo._get_db().processed_emails
        clauses: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for hdr in headers:
            owner = str((hdr.get("owner_email") or fallback_owner or "")).strip().lower()
            if not owner:
                continue

            msg_id = str(hdr.get("message_id") or "").strip()
            if msg_id:
                # Match por message_id field (RFC822 Message-ID)
                key = f"msg::{owner}::{msg_id}"
                if key not in seen:
                    clauses.append({"owner_email": owner, "message_id": msg_id})
                    seen.add(key)

                # Fallback: match por _id que contiene el message_id como UID
                # Handles legacy data where invoice_headers.message_id was the IMAP UID
                # _id format: "{owner}::{account}::{uid}"
                if not msg_id.startswith("<"):  # IMAP UID, not RFC822
                    id_key = f"id_suffix::{owner}::{msg_id}"
                    if id_key not in seen:
                        import re
                        safe_uid = re.escape(msg_id)
                        clauses.append({
                            "_id": {"$regex": f"^{re.escape(owner)}::.*::{safe_uid}$"},
                            "owner_email": owner,
                        })
                        seen.add(id_key)

            minio_key = str(hdr.get("minio_key") or "").strip()
            if minio_key:
                key = f"minio::{owner}::{minio_key}"
                if key not in seen:
                    clauses.append(
                        {
                            "owner_email": owner,
                            "manual_upload": True,
                            "minio_key": minio_key,
                        }
                    )
                    seen.add(key)

        if not clauses:
            return 0

        deleted = coll.delete_many({"$or": clauses}).deleted_count
        return int(deleted or 0)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo limpiar processed_emails tras eliminación de factura(s): {e}")
        return 0

@router.delete("/v2/invoices/{header_id}")
async def v2_delete_invoice(header_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Elimina una factura completa (header + todos sus items).
    """
    try:
        repo = MongoInvoiceRepository()
        
        # Verificar que la factura existe y pertenece al usuario
        q = {"_id": header_id}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        
        header = repo._headers().find_one(q)
        if not header:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        
        # Eliminar items primero (incluye owner_email para defensa en profundidad)
        item_q = {"header_id": header_id}
        if settings.MULTI_TENANT_ENFORCE and owner:
            item_q["owner_email"] = owner
        items_result = repo._items().delete_many(item_q)
        
        # Eliminar header
        header_result = repo._headers().delete_one({"_id": header_id})
        
        if header_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la factura")
        
        owner_fallback = (user.get("email") or "").lower()
        deleted_cache = _cleanup_processing_cache_for_deleted_headers(
            repo=repo,
            headers=[header],
            fallback_owner=owner_fallback,
        )

        logger.info(
            f"✅ Factura eliminada: {header_id} ({items_result.deleted_count} items, "
            f"{deleted_cache} cache entries)"
        )
        
        return {
            "success": True,
            "message": f"Factura eliminada correctamente",
            "deleted_items": items_result.deleted_count,
            "deleted_processing_cache": deleted_cache,
            "header_id": header_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando factura {header_id}: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando factura")

@router.delete("/v2/invoices/bulk")
async def v2_bulk_delete_invoices(
    header_ids: List[str],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Elimina múltiples facturas en lote.
    """
    try:
        if not header_ids:
            raise HTTPException(status_code=400, detail="No se proporcionaron IDs de facturas")
        
        if len(header_ids) > 100:
            raise HTTPException(status_code=400, detail="Máximo 100 facturas por operación")
        
        repo = MongoInvoiceRepository()
        
        # Construir query con filtro de usuario si aplica
        q = {"_id": {"$in": header_ids}}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        
        # Verificar que todas las facturas existen y pertenecen al usuario
        existing_headers = list(
            repo._headers().find(
                q,
                {
                    "_id": 1,
                    "owner_email": 1,
                    "message_id": 1,
                    "minio_key": 1,
                },
            )
        )
        existing_ids = [h["_id"] for h in existing_headers]
        
        if len(existing_ids) != len(header_ids):
            missing_ids = set(header_ids) - set(existing_ids)
            raise HTTPException(
                status_code=404, 
                detail=f"Facturas no encontradas: {list(missing_ids)}"
            )
        
        # Eliminar items de todas las facturas (incluye owner_email para defensa en profundidad)
        item_q = {"header_id": {"$in": existing_ids}}
        if settings.MULTI_TENANT_ENFORCE and owner:
            item_q["owner_email"] = owner
        items_result = repo._items().delete_many(item_q)
        
        # Eliminar headers
        headers_result = repo._headers().delete_many({"_id": {"$in": existing_ids}})
        
        owner_fallback = (user.get("email") or "").lower()
        deleted_cache = _cleanup_processing_cache_for_deleted_headers(
            repo=repo,
            headers=existing_headers,
            fallback_owner=owner_fallback,
        )

        logger.info(
            f"✅ Eliminación en lote: {headers_result.deleted_count} facturas, "
            f"{items_result.deleted_count} items, {deleted_cache} cache entries"
        )
        
        return {
            "success": True,
            "message": f"Se eliminaron {headers_result.deleted_count} facturas correctamente",
            "deleted_headers": headers_result.deleted_count,
            "deleted_items": items_result.deleted_count,
            "deleted_processing_cache": deleted_cache,
            "processed_ids": existing_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en eliminación en lote: {e}")
        raise HTTPException(status_code=500, detail="Error en eliminación en lote")

class BulkDeleteRequest(BaseModel):
    header_ids: List[str]

@router.post("/v2/invoices/bulk-delete")
async def v2_bulk_delete_invoices_post(
    request: BulkDeleteRequest,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Alternativa POST para eliminación en lote (para payloads grandes).
    """
    return await v2_bulk_delete_invoices(request.header_ids, user)

@router.get("/v2/invoices/{header_id}/delete-info")
async def v2_get_delete_info(header_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene información sobre lo que se eliminará antes de confirmar.
    """
    try:
        repo = MongoInvoiceRepository()
        
        # Verificar que la factura existe y pertenece al usuario
        q = {"_id": header_id}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        
        header = repo._headers().find_one(q)
        if not header:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        
        # Contar items
        items_count = repo._items().count_documents({"header_id": header_id})
        
        # Calcular total con fallback a totales.total si no existe monto_total directo
        total_monto = header.get("monto_total")
        if not total_monto:
            try:
                total_monto = (header.get("totales", {}) or {}).get("total", 0)
            except Exception:
                total_monto = 0

        return {
            "success": True,
            "can_delete": True,
            "header": {
                "id": header_id,
                "numero_documento": header.get("numero_documento", ""),
                "emisor": header.get("emisor", {}).get("nombre", ""),
                "fecha_emision": header.get("fecha_emision"),
                "monto_total": total_monto
            },
            "items_count": items_count,
            "warning": f"Se eliminará la factura completa con {items_count} ítems. Esta acción no se puede deshacer."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo información de eliminación: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo información")

@router.post("/v2/invoices/bulk-delete-info")
async def v2_get_bulk_delete_info(
    request: BulkDeleteRequest,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Obtiene información sobre eliminación en lote antes de confirmar.
    """
    try:
        if not request.header_ids:
            raise HTTPException(status_code=400, detail="No se proporcionaron IDs de facturas")
        
        if len(request.header_ids) > 100:
            raise HTTPException(status_code=400, detail="Máximo 100 facturas por operación")
        
        repo = MongoInvoiceRepository()
        
        # Construir query con filtro de usuario si aplica
        q = {"_id": {"$in": request.header_ids}}
        if settings.MULTI_TENANT_ENFORCE:
            owner = (user.get('email') or '').lower()
            if owner:
                q['owner_email'] = owner
        
        # Obtener facturas existentes
        headers = list(repo._headers().find(q, {
            "_id": 1,
            "numero_documento": 1,
            "emisor.nombre": 1,
            "fecha_emision": 1,
            "monto_total": 1,
            "totales.total": 1
        }))
        
        existing_ids = [h["_id"] for h in headers]
        missing_ids = set(request.header_ids) - set(existing_ids)
        
        # Contar items totales
        total_items = repo._items().count_documents({"header_id": {"$in": existing_ids}})
        
        # Calcular monto total con fallback a totales.total
        def _hdr_total(h: dict) -> float:
            v = h.get("monto_total")
            if not v:
                try:
                    v = (h.get("totales", {}) or {}).get("total", 0)
                except Exception:
                    v = 0
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        total_amount = sum(_hdr_total(h) for h in headers)
        
        return {
            "success": True,
            "can_delete": len(missing_ids) == 0,
            "summary": {
                "total_invoices": len(headers),
                "total_items": total_items,
                "total_amount": total_amount,
                "found_invoices": len(existing_ids),
                "missing_invoices": len(missing_ids)
            },
            "missing_ids": list(missing_ids) if missing_ids else [],
            "invoices": [
                {
                    "id": h["_id"],
                    "numero_documento": h.get("numero_documento", ""),
                    "emisor": h.get("emisor", {}).get("nombre", "") if h.get("emisor") else "",
                    "fecha_emision": h.get("fecha_emision"),
                    "monto_total": _hdr_total(h)
                }
                for h in headers
            ],
            "warning": f"Se eliminarán {len(headers)} facturas con un total de {total_items} ítems. Esta acción no se puede deshacer."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo información de eliminación en lote: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo información")

@router.get("/invoices/{invoice_id}/download")
async def get_invoice_download_url(
    invoice_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Genera una URL firmada para descargar la factura."""
    try:
        repo = MongoInvoiceRepository()
        from datetime import timedelta
        
        # Buscar factura
        # MongoInvoiceRepository es para v1/v2 mapping, usemos metodo directo si no existe get_header
        header = repo._headers().find_one({"_id": invoice_id})
        if not header:
            # Fallback a ObjectId si no es string
            try:
                from bson import ObjectId
                header = repo._headers().find_one({"_id": ObjectId(invoice_id)})
            except:
                pass
                
        if not header:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        
        # Verificar ownership
        owner = (user.get('email') or '').lower()
        if header.get("owner_email") != owner:
            # Si el usuario es admin, permitir
            user_repo = UserRepository()
            if not user_repo.is_admin(owner):
                raise HTTPException(status_code=403, detail="Acceso denegado")
        
        # Verificar si el plan del usuario permite descarga desde MinIO
        from app.repositories.subscription_repository import SubscriptionRepository
        sub_repo = SubscriptionRepository()
        subscription = await sub_repo.get_user_active_subscription(owner)
        
        # Permitir a admins o si el plan lo permite
        user_repo = UserRepository()
        is_admin = user_repo.is_admin(owner)
        
        if not is_admin:
            if not subscription:
                # Si no hay suscripción activa, es un usuario FREE/Trial
                # Por defecto, si queremos restringir el Trial también, bloqueamos aquí
                raise HTTPException(
                    status_code=403, 
                    detail="Tu plan actual no permite la descarga de archivos originales. Actualiza tu plan para habilitar esta función."
                )
            
            # Obtener features del plan
            plan_code = subscription.get("plan_code")
            plan = await sub_repo.get_plan_by_code(plan_code)
            if plan and plan.get("features"):
                if not plan["features"].get("minio_storage", True):
                    raise HTTPException(
                        status_code=403,
                        detail="Tu plan actual no permite la descarga de archivos originales. Actualiza tu plan para habilitar esta función."
                    )

        # Generar Signed URL
        # Re-importar para asegurar acceso si no estamos en scope gol
        try:
            from minio import Minio
            from urllib.parse import urlencode
        except ImportError:
            return {"success": False, "message": "Librería MinIO no instalada"}

        if not Minio or not settings.MINIO_ACCESS_KEY:
             return {"success": False, "message": "Almacenamiento seguro no configurado"}
             
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION
        )

        minio_key = _resolve_minio_key_strict(header, client)
        if not minio_key:
            return {"success": False, "message": "Archivo no disponible en el almacenamiento seguro"}
        
        # Determinar Content-Type basado en la extensión del archivo
        filename = minio_key.split("/")[-1]
        lname = filename.lower()
        if lname.endswith(".pdf"):
            content_type = "application/pdf"
        elif lname.endswith(".xml"):
            content_type = "application/xml"
        elif lname.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif lname.endswith(".png"):
            content_type = "image/png"
        elif lname.endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "application/octet-stream"
        
        # Generar URL presignada con headers de respuesta para compatibilidad HTTPS
        # response_headers fuerza al servidor a devolver estos headers
        response_headers = {
            "response-content-type": content_type,
            "response-content-disposition": f"inline; filename=\"{filename}\""
        }
        
        url = client.get_presigned_url(
            "GET",
            settings.MINIO_BUCKET,
            minio_key,
            expires=timedelta(hours=1),
            response_headers=response_headers
        )
        
        return {
            "success": True,
            "download_url": url,
            "filename": filename,
            "content_type": content_type
        }
        
    except Exception as e:
        logger.error(f"Error generando download url: {e}")
        raise HTTPException(status_code=500, detail="Error descarga")


@router.get("/invoices/{invoice_id}/file")
async def get_invoice_file_direct(
    invoice_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Descarga el archivo directamente como streaming (proxy).
    
    Este endpoint evita problemas de CORS al servir el archivo
    directamente desde el backend en lugar de redirigir a MinIO.
    """
    from fastapi.responses import StreamingResponse
    
    try:
        repo = MongoInvoiceRepository()
        
        # Buscar factura
        header = repo._headers().find_one({"_id": invoice_id})
        if not header:
            try:
                from bson import ObjectId
                header = repo._headers().find_one({"_id": ObjectId(invoice_id)})
            except:
                pass
                
        if not header:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        
        # Verificar ownership
        owner = (user.get('email') or '').lower()
        if header.get("owner_email") != owner:
            user_repo = UserRepository()
            if not user_repo.is_admin(owner):
                raise HTTPException(status_code=403, detail="Acceso denegado")

        # Verificar si el plan del usuario permite descarga desde MinIO
        user_repo = UserRepository()
        is_admin = user_repo.is_admin(owner)

        if not is_admin:
            from app.repositories.subscription_repository import SubscriptionRepository
            sub_repo = SubscriptionRepository()
            subscription = await sub_repo.get_user_active_subscription(owner)

            if not subscription:
                raise HTTPException(
                    status_code=403,
                    detail="Tu plan actual no permite la descarga de archivos originales. Actualiza tu plan para habilitar esta función."
                )

            plan_code = subscription.get("plan_code")
            plan = await sub_repo.get_plan_by_code(plan_code)
            if plan and plan.get("features"):
                if not plan["features"].get("minio_storage", True):
                    raise HTTPException(
                        status_code=403,
                        detail="Tu plan actual no permite la descarga de archivos originales. Actualiza tu plan para habilitar esta función."
                    )

        try:
            from minio import Minio
        except ImportError:
            raise HTTPException(status_code=500, detail="MinIO no instalado")

        if not settings.MINIO_ACCESS_KEY:
            raise HTTPException(status_code=500, detail="MinIO no configurado")
             
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION
        )

        minio_key = _resolve_minio_key_strict(header, client)
        if not minio_key:
            raise HTTPException(status_code=404, detail="Archivo no disponible")
        
        # Obtener el archivo desde MinIO
        response = client.get_object(settings.MINIO_BUCKET, minio_key)
        
        # Determinar Content-Type
        filename = minio_key.split("/")[-1]
        lname = filename.lower()
        if lname.endswith(".pdf"):
            content_type = "application/pdf"
        elif lname.endswith(".xml"):
            content_type = "application/xml"
        elif lname.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif lname.endswith(".png"):
            content_type = "image/png"
        elif lname.endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "application/octet-stream"
        
        # Streaming response
        def iter_content():
            try:
                for chunk in response.stream(32*1024):
                    yield chunk
            finally:
                response.close()
                response.release_conn()
        
        return StreamingResponse(
            iter_content(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{filename}\"",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "private, max-age=3600"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error descargando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error descarga")

# Endpoint para estadísticas filtradas con fecha
@router.get("/export/mongodb/stats")
async def mongodb_export_stats(user: Dict[str, Any] = Depends(_get_current_user)):
    """Estadísticas básicas de la base de facturas del usuario actual."""
    try:
        from app.modules.mongo_query_service import MongoQueryService
        from app.config.export_config import get_mongodb_config
        config = get_mongodb_config()
        service = MongoQueryService(connection_string=config["connection_string"])
        client = service._get_client()
        db = client[config["database"]]
        headers = db["invoice_headers"]
        items = db["invoice_items"]
        
        # Filtrar por usuario actual
        user_filter = {"owner_email": user["email"]}
        
        total_headers = headers.count_documents(user_filter)
        total_items = items.count_documents(user_filter)
        total_amount = list(headers.aggregate([
            {"$match": user_filter},
            {"$group": {"_id": None, "sum": {"$sum": "$totales.total"}}}
        ]))
        
        return {
            "success": True,
            "collection": "invoice_headers",
            "user_email": user["email"],
            "total_invoices": total_headers,
            "total_items": total_items,
            "total_amount": float(total_amount[0]["sum"]) if total_amount else 0.0
        }
    except Exception as e:
        logger.error(f"Error obteniendo stats MongoDB v2: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")


# -----------------------------
# Consultas MongoDB y Exports por Fecha
# -----------------------------

@router.get("/invoices/months")
async def get_available_months(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene lista de meses disponibles con estadísticas básicas desde MongoDB.
    """
    try:
        query_service = get_mongo_query_service()
        owner = (user.get('email') or '').lower() if settings.MULTI_TENANT_ENFORCE else None
        months = query_service.get_available_months(owner_email=owner)
        
        return {
            "success": True,
            "months": months,
            "total_months": len(months)
        }
    except Exception as e:
        logger.error(f"Error obteniendo meses disponibles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo meses: {str(e)}")

@router.get("/invoices/month/{year_month}")
async def get_invoices_by_month(year_month: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene todas las facturas de un mes específico desde MongoDB.
    
    Args:
        year_month: Mes en formato YYYY-MM
    """
    try:
        # Validar formato
        try:
            datetime.strptime(year_month, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de mes incorrecto. Use YYYY-MM")
        
        query_service = get_mongo_query_service()
        owner = (user.get('email') or '').lower() if settings.MULTI_TENANT_ENFORCE else None
        invoices = query_service.get_invoices_by_month(year_month, owner_email=owner)
        
        return {
            "success": True,
            "year_month": year_month,
            "invoices": invoices,
            "count": len(invoices)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo facturas del mes {year_month}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo facturas: {str(e)}")

@router.get("/invoices/month/{year_month}/stats")
async def get_month_statistics(request: Request, year_month: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene estadísticas detalladas de un mes específico desde MongoDB.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Validación de seguridad
        try:
            SecurityValidators.validate_year_month(year_month)
        except ValidationError as e:
            log_security_event("validation_error", {"error": str(e), "year_month": year_month}, client_ip)
            raise HTTPException(status_code=400, detail=str(e))
        
        query_service = get_mongo_query_service()
        owner = (user.get('email') or '').lower() if settings.MULTI_TENANT_ENFORCE else None
        stats = query_service.get_month_statistics(year_month, owner_email=owner)
        
        # Log acceso a estadísticas
        logger.info(f"📊 Stats solicitadas para {year_month} por IP {client_ip}")
        
        return {
            "success": True,
            "statistics": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del mes {year_month}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

@router.post("/invoices/search")
async def search_invoices(
    query: str = Query(default="", description="Texto libre para buscar"),
    start_date: Optional[str] = Query(default=None, description="Fecha inicio YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="Fecha fin YYYY-MM-DD"),
    provider_ruc: Optional[str] = Query(default=None, description="RUC del proveedor"),
    client_ruc: Optional[str] = Query(default=None, description="RUC del cliente"),
    min_amount: Optional[float] = Query(default=None, description="Monto mínimo"),
    max_amount: Optional[float] = Query(default=None, description="Monto máximo"),
    limit: int = Query(default=100, description="Límite de resultados"),
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Búsqueda avanzada de facturas en MongoDB con múltiples filtros.
    """
    try:
        query_service = get_mongo_query_service()
        owner = (user.get('email') or '').lower()
        if settings.MULTI_TENANT_ENFORCE and not owner:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
        owner_filter = owner if settings.MULTI_TENANT_ENFORCE else None
        results = query_service.search_invoices(
            query=query,
            start_date=start_date,
            end_date=end_date,
            provider_ruc=provider_ruc,
            client_ruc=client_ruc,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=limit,
            owner_email=owner_filter
        )
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error en búsqueda de facturas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

@router.get("/invoices/recent-activity")
async def get_recent_activity(
    days: int = Query(default=7, description="Días hacia atrás"),
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Obtiene actividad reciente del sistema desde MongoDB.
    """
    try:
        query_service = get_mongo_query_service()
        owner = (user.get('email') or '').lower()
        if settings.MULTI_TENANT_ENFORCE and not owner:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
        owner_filter = owner if settings.MULTI_TENANT_ENFORCE else None
        activity = query_service.get_recent_activity(days, owner_email=owner_filter)
        
        return {
            "success": True,
            "activity": activity
        }
    except Exception as e:
        logger.error(f"Error obteniendo actividad reciente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo actividad: {str(e)}")

def _mongo_doc_to_invoice_data(doc: Dict[str, Any]) -> InvoiceData:
    """
    Convierte documento MongoDB a InvoiceData para compatibilidad con exportadores existentes.
    """
    try:
        # DEBUG: Log de la estructura del documento
        logger.info(f"🔍 Estructura del documento MongoDB: {list(doc.keys())}")
        if "factura" in doc:
            logger.info(f"🔍 Keys en factura: {list(doc['factura'].keys())}")
        
        # Extraer datos principales - Los datos están directamente en el doc según los logs
        productos = doc.get("productos", [])
        
        # Función para limpiar datos de productos
        def clean_product(p):
            try:
                return ProductoFactura(
                    nombre=p.get("articulo", p.get("nombre", "")),
                    cantidad=float(p.get("cantidad", 0)) if p.get("cantidad") not in ['', None] else 0.0,
                    precio_unitario=float(p.get("precio_unitario", 0)) if p.get("precio_unitario") not in ['', None] else 0.0,
                    total=float(p.get("total", 0)) if p.get("total") not in ['', None] else 0.0,
                    iva=int(float(p.get("iva", 0))) if p.get("iva") not in ['', None] else 0
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Error limpiando producto {p}: {e}")
                return ProductoFactura(nombre="Error en producto", cantidad=0, precio_unitario=0, total=0, iva=0)
        
        # Convertir fecha
        fecha = None
        fecha_raw = doc.get("fecha")
        if fecha_raw:
            try:
                if isinstance(fecha_raw, str):
                    fecha = datetime.fromisoformat(fecha_raw.replace("Z", "+00:00"))
                else:
                    fecha = fecha_raw
            except:
                pass
        
        # Crear InvoiceData usando datos del modelo v2 correctamente mapeados
        logger.info(f"🔍 Valores específicos: numero_factura='{doc.get('numero_factura')}', cdc='{doc.get('cdc')}'")
        
        # Obtener totales desde el modelo v2 estructura
        totales_data = doc.get("totales", {})
        emisor_data = doc.get("emisor", {})
        receptor_data = doc.get("receptor", {})

        total_iva_v2 = totales_data.get("total_iva", None)
        if total_iva_v2 is None:
            total_iva_v2 = (totales_data.get("iva_5", 0) or 0) + (totales_data.get("iva_10", 0) or 0)
        
        invoice = InvoiceData(
            numero_factura=doc.get("numero_factura", "") or doc.get("numero_documento", ""),
            fecha=fecha,
            ruc_emisor=doc.get("ruc_emisor", "") or emisor_data.get("ruc", ""),
            nombre_emisor=doc.get("nombre_emisor", "") or emisor_data.get("nombre", ""),
            ruc_cliente=doc.get("ruc_cliente", "") or receptor_data.get("ruc", ""),
            nombre_cliente=doc.get("nombre_cliente", "") or receptor_data.get("nombre", ""),
            email_cliente=doc.get("email_cliente", "") or receptor_data.get("email", ""),
            monto_total=doc.get("monto_total", 0) or totales_data.get("total", 0),
            
            # Mapeo correcto desde modelo v2 - NOMBRES CORRECTOS DEL XML
            monto_exento=totales_data.get("monto_exento", 0) or totales_data.get("exentas", 0),
            base_gravada_5=totales_data.get("gravado_5", 0),  # base_gravada_5 del XML
            base_gravada_10=totales_data.get("gravado_10", 0),  # base_gravada_10 del XML
            iva_5=totales_data.get("iva_5", 0),
            iva_10=totales_data.get("iva_10", 0),
            
            # Campos adicionales del XML que faltaban
            total_operacion=totales_data.get("total_operacion", 0) or doc.get("total_operacion", 0),
            total_descuento=totales_data.get("total_descuento", 0) or doc.get("total_descuento", 0),
            total_iva=total_iva_v2 or 0,
            anticipo=totales_data.get("anticipo", 0) or doc.get("anticipo", 0),
            exonerado=totales_data.get("exonerado", 0) or doc.get("exonerado", 0),
            total_base_gravada=totales_data.get(
                "total_base_gravada",
                (totales_data.get("gravado_5", 0) or 0) + (totales_data.get("gravado_10", 0) or 0)
            ),
            isc_total=totales_data.get("isc_total", 0) or doc.get("isc_total", 0),
            isc_base_imponible=totales_data.get("isc_base_imponible", 0) or doc.get("isc_base_imponible", 0),
            isc_subtotal_gravado=totales_data.get("isc_subtotal_gravado", 0) or doc.get("isc_subtotal_gravado", 0),
            
            # Compatibilidad (campos legacy)
            subtotal_exentas=totales_data.get("exentas", 0),
            gravado_5=totales_data.get("gravado_5", 0),
            subtotal_5=totales_data.get("gravado_5", 0),
            gravado_10=totales_data.get("gravado_10", 0),
            subtotal_10=totales_data.get("gravado_10", 0),
            iva=doc.get("iva", 0),
            
            productos=[clean_product(p) for p in productos]
        )

        # Agregar campos adicionales directamente del documento
        invoice.cdc = doc.get("cdc", "")
        invoice.timbrado = doc.get("timbrado", "")
        invoice.tipo_documento = doc.get("tipo_documento", "") or invoice.tipo_documento
        invoice.tipo_documento_electronico = doc.get("tipo_documento_electronico", "")
        invoice.tipo_de_codigo = doc.get("tipo_de_codigo", "")
        invoice.ind_presencia = doc.get("ind_presencia", "")
        invoice.ind_presencia_codigo = doc.get("ind_presencia_codigo", "")
        invoice.cond_credito = doc.get("cond_credito", "")
        invoice.cond_credito_codigo = doc.get("cond_credito_codigo", "")
        invoice.plazo_credito_dias = int(doc.get("plazo_credito_dias", 0) or 0)
        invoice.ciclo_facturacion = doc.get("ciclo_facturacion", "")
        invoice.ciclo_fecha_inicio = doc.get("ciclo_fecha_inicio", "")
        invoice.ciclo_fecha_fin = doc.get("ciclo_fecha_fin", "")
        invoice.transporte_modalidad = doc.get("transporte_modalidad", "")
        invoice.transporte_modalidad_codigo = doc.get("transporte_modalidad_codigo", "")
        invoice.transporte_resp_flete_codigo = doc.get("transporte_resp_flete_codigo", "")
        invoice.transporte_nro_despacho = doc.get("transporte_nro_despacho", "")
        invoice.qr_url = doc.get("qr_url", "")
        invoice.info_adicional = doc.get("info_adicional", "")
        invoice.establecimiento = doc.get("establecimiento", "")
        invoice.punto_expedicion = doc.get("punto_expedicion", "") or doc.get("punto", "")
        invoice.fuente = doc.get("fuente", "")
        invoice.email_origen = doc.get("email_origen", "")

        # Normalizar y mapear campos críticos faltantes para exportación
        # Moneda: mapear PYG/GS → GS, USD/DOLAR → USD, default GS
        moneda_raw = (doc.get("moneda") or "GS")
        try:
            moneda_norm = str(moneda_raw).upper()
        except Exception:
            moneda_norm = "GS"
        if moneda_norm in ["PYG", "GS", None, ""]:
            invoice.moneda = "GS"
        elif moneda_norm in ["USD", "DOLLAR", "DOLAR"]:
            invoice.moneda = "USD"
        else:
            # Mantener el valor normalizado si viene otra moneda conocida
            invoice.moneda = moneda_norm or "GS"

        # Tipo de cambio (si existe en el documento)
        try:
            invoice.tipo_cambio = float(doc.get("tipo_cambio", 0.0) or 0.0)
        except Exception:
            pass

        # Condición de venta y tipo de documento
        condicion_raw = (doc.get("condicion_venta") or "CONTADO")
        try:
            condicion_norm = str(condicion_raw).upper()
        except Exception:
            condicion_norm = "CONTADO"
        invoice.condicion_venta = condicion_norm
        # CR si contiene CREDITO/CRÉDITO/CREDIT, caso contrario CO
        invoice.tipo_documento = "CR" if any(word in condicion_norm for word in ["CREDITO", "CRÉDITO", "CREDIT"]) else "CO"

        # Datos del emisor adicionales
        try:
            invoice.direccion_emisor = doc.get("direccion_emisor", "") or emisor_data.get("direccion", "")
        except Exception:
            pass
        try:
            invoice.telefono_emisor = doc.get("telefono_emisor", "") or emisor_data.get("telefono", "")
        except Exception:
            pass
        try:
            invoice.actividad_economica = doc.get("actividad_economica", "") or emisor_data.get("actividad_economica", "")
        except Exception:
            pass
        try:
            invoice.email_emisor = doc.get("email_emisor", "") or emisor_data.get("email", "")
        except Exception:
            pass

        # Datos del receptor adicionales
        try:
            invoice.direccion_cliente = doc.get("direccion_cliente", "") or receptor_data.get("direccion", "")
        except Exception:
            pass
        try:
            invoice.telefono_cliente = doc.get("telefono_cliente", "") or receptor_data.get("telefono", "")
        except Exception:
            pass

        # Mes de proceso y fecha de creación
        try:
            if not getattr(invoice, 'mes_proceso', None):
                invoice.mes_proceso = doc.get("mes_proceso", "")
        except Exception:
            pass
        try:
            invoice.created_at = doc.get("created_at")
        except Exception:
            pass

        # Descripción de la factura (si viene precomputada)
        try:
            if doc.get("descripcion_factura"):
                invoice.descripcion_factura = doc.get("descripcion_factura")
        except Exception:
            pass
        
        # También verificar en datos_tecnicos por compatibilidad
        if "datos_tecnicos" in doc:
            datos_tec = doc["datos_tecnicos"]
            if not invoice.cdc:
                invoice.cdc = datos_tec.get("cdc", "")
            if not invoice.timbrado:
                invoice.timbrado = datos_tec.get("timbrado", "")
        
        # Agregar metadata
        if "metadata" in doc:
            metadata = doc["metadata"]
            invoice.email_origen = metadata.get("email_origen", "")
            invoice.mes_proceso = doc.get("indices", {}).get("year_month", "")
        
        return invoice
        
    except Exception as e:
        logger.error(f"Error convirtiendo documento MongoDB: {e}")
        # Retornar InvoiceData mínimo en caso de error
        return InvoiceData(
            numero_factura=doc.get("factura_id", "ERROR"),
            fecha=datetime.now(),
            ruc_emisor="",
            nombre_emisor="Error en conversión",
            ruc_cliente="",
            nombre_cliente="",
            email_cliente="",
            monto_total=0
        )

# ================================
# ENDPOINTS PARA TEMPLATES DE EXPORTACIÓN
# ================================

