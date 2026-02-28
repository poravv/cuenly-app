"""
Endpoints de perfil de usuario
Migrado desde api.py
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
import logging

from app.api.deps import _get_current_user, _get_current_user_with_trial_info
from app.config.settings import settings
from app.repositories.user_repository import UserRepository
from app.utils.validators import SecurityValidators

router = APIRouter()
logger = logging.getLogger(__name__)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    ruc: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    document_type: Optional[str] = "CI"  # CI, RUC, PASSPORT


class ProfileStatusResponse(BaseModel):
    is_complete: bool
    missing_fields: List[str]
    required_for_subscription: bool


class UpdateProcessingStartDatePayload(BaseModel):
    start_date: Optional[str] = None  # ISO format date, si es None usa fecha actual


class CancelActiveJobsPayload(BaseModel):
    scope: Literal["all", "single_email", "range", "full_sync"] = "all"
    max_jobs: int = 500


@router.get("")
async def get_user_profile(request: Request, user: Dict[str, Any] = Depends(_get_current_user_with_trial_info)):
    """
    Obtiene el perfil del usuario autenticado incluyendo información del trial
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    trial_info = user.get('trial_info', {})
    
    # Obtener información completa del usuario desde la base de datos
    user_repo = UserRepository()
    db_user = None
    try:
        db_user = user_repo.get_by_email(user.get('email', ''))
    except Exception as e:
        logger.error(f"Error fetching user from DB in get_user_profile: {e}")
    
    # Obtener fecha de inicio de procesamiento de correos
    processing_start_date = None
    if db_user:
        try:
            processing_start_date = user_repo.get_email_processing_start_date(user.get('email', ''))
            if processing_start_date:
                processing_start_date = processing_start_date.isoformat()
        except Exception as e:
            logger.warning(f"No se pudo obtener fecha de inicio de procesamiento: {e}")
    
    # Verificar si es admin
    is_admin = False
    if db_user:
        is_admin = db_user.get('role') == 'admin'
    else:
        # Fallback: verificar contra lista de admins configurada
        is_admin = user.get('email', '').lower() in settings.ADMIN_EMAILS
    
    # Usar datos de la DB si están disponibles, sino usar claims del token
    return {
        "email": db_user.get('email') if db_user else user.get('email'),
        "name": db_user.get('name') if db_user else user.get('name'),
        "picture": db_user.get('picture') if db_user else user.get('picture'),
        "role": db_user.get('role', 'user') if db_user else 'user',
        "is_admin": is_admin,
        "status": db_user.get('status', 'active') if db_user else 'active',
        "is_trial": trial_info.get('is_trial_user', True),
        "trial_expires_at": trial_info.get('trial_expires_at'),
        "trial_expired": trial_info.get('trial_expired', True),
        "trial_days_remaining": trial_info.get('days_remaining', 0),
        "can_process": not trial_info.get('trial_expired', True),
        "ai_invoices_processed": trial_info.get('ai_invoices_processed', 0),
        "ai_invoices_limit": trial_info.get('ai_invoices_limit', 50),
        "ai_limit_reached": trial_info.get('ai_limit_reached', True),
        "email_processing_start_date": processing_start_date,
        "phone": db_user.get('phone', ''),
        "ruc": db_user.get('ruc', ''),
        "address": db_user.get('address', ''),
        "city": db_user.get('city', ''),
        "document_type": db_user.get('document_type', 'CI')
    }


@router.put("")
async def update_user_profile(
    profile_data_update: UserProfileUpdate,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Actualiza la información del perfil del usuario.
    Sync con Pagopar si existe.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    email = user.get('email', '')
    profile_data = profile_data_update.dict(exclude_unset=True)
    
    if not profile_data:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar")
    
    # Validaciones
    if 'phone' in profile_data:
        phone = profile_data['phone']
        if phone and not SecurityValidators.validate_phone(phone):
             raise HTTPException(status_code=400, detail="Número de teléfono inválido. Verifique longitud y formato.")

    if 'ruc' in profile_data:
        ruc = profile_data['ruc']
        if ruc and not SecurityValidators.validate_ruc(ruc):
             raise HTTPException(status_code=400, detail="RUC inválido. Verifique el formato.")
        
    user_repo = UserRepository()
    success = user_repo.update_user_profile(email, profile_data)
    
    if success:
        # Intentar actualizar en Pagopar si tiene pagopar_user_id
        pagopar_user_id = user_repo.get_pagopar_user_id(email)
        if pagopar_user_id:
            try:
                from app.services.pagopar_service import PagoparService
                pagopar_service = PagoparService()
                await pagopar_service.add_customer(
                    identifier=pagopar_user_id,
                    name=profile_data.get('name', user.get('name', 'Usuario')),
                    email=email,
                    phone=profile_data.get('phone', '')
                )
            except Exception as e:
                logger.warning(f"No se pudo sincronizar perfil con Pagopar: {e}")
        
        return {"success": True, "message": "Perfil actualizado correctamente"}
    else:
        raise HTTPException(status_code=500, detail="Error al actualizar el perfil en la base de datos")


@router.get("/status", response_model=ProfileStatusResponse)
async def get_profile_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Verifica si el perfil del usuario está completo (requerido para suscripciones).
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    email = user.get('email', '')
    user_repo = UserRepository()
    status = user_repo.is_profile_complete(email)
    
    return status


@router.get("/trial-status")
async def get_trial_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Verifica el estado del trial del usuario actual.
    Retorna información específica sobre el estado del trial para automatización de procesamiento.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    try:
        user_repo = UserRepository()
        owner_email = (user.get('email') or '').lower()
        trial_info = user_repo.get_trial_info(owner_email)
        
        return {
            "success": True,
            "can_process": not trial_info.get('trial_expired', True),
            "is_trial_user": trial_info.get('is_trial_user', False),
            "trial_expired": trial_info.get('trial_expired', True),
            "trial_end_date": trial_info.get('trial_end_date'),
            "ai_invoices_processed": trial_info.get('ai_invoices_processed', 0),
            "ai_invoice_limit": trial_info.get('ai_invoice_limit', 0),
            "message": "Trial expirado. Actualiza tu suscripción para continuar." if trial_info.get('trial_expired', True) else "Trial activo"
        }
    except Exception as e:
        logger.error(f"Error al verificar trial status: {str(e)}")
        return {
            "success": False,
            "can_process": False,
            "message": f"Error al verificar estado del trial: {str(e)}"
        }


@router.post("/email-processing-start-date")
async def update_email_processing_start_date(
    payload: UpdateProcessingStartDatePayload,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Actualiza la fecha desde la cual se procesarán los correos para este usuario.
    Si no se proporciona fecha, usa la fecha actual.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    try:
        # Parsear fecha o usar actual
        if payload.start_date:
            try:
                start_date = datetime.fromisoformat(payload.start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        else:
            start_date = datetime.utcnow()
        
        # Actualizar en base de datos
        user_repo = UserRepository()
        success = user_repo.update_email_processing_start_date(user.get('email', ''), start_date)
        
        if success:
            return {
                "success": True,
                "message": f"Fecha de inicio de procesamiento actualizada a {start_date.isoformat()}",
                "start_date": start_date.isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando fecha de inicio de procesamiento: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/debug")
async def debug_user_info(request: Request, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Endpoint de debug para verificar información del usuario autenticado
    """
    if not user:
        return {"authenticated": False, "message": "No authenticated user"}
    
    try:
        # Verificar si el usuario existe en la base de datos
        user_repo = UserRepository()
        db_user = user_repo.get_by_email(user.get('email'))
        trial_info = user_repo.get_trial_info(user.get('email'))
        
        return {
            "authenticated": True,
            "firebase_claims": user,
            "database_user": db_user,
            "trial_info": trial_info
        }
    except Exception as e:
        return {
            "authenticated": True,
            "firebase_claims": user,
            "error": str(e)
        }

@router.get("/queue-events")
async def get_queue_events(
    page: int = 1, 
    page_size: int = 50, 
    status: str = "all", 
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Obtiene los eventos pendientes (procesamientos fallidos o pausados por IA) del usuario.
    Soporta paginación y filtrado por estado.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
         
    email = (user.get("email") or "").lower()
    
    try:
        from pymongo import MongoClient, DESCENDING
        from app.config.settings import settings
        
        client = MongoClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DATABASE]
        coll = db.processed_emails
        
        # Filtrar por owner_email y status problemáticos o pendientes
        query = {"owner_email": email}
        
        if status and status != "all":
            query["status"] = status
        else:
            # Por defecto mostrar todos los que no son éxitos directos (o todos si se prefiere)
            # El usuario pidió poder filtrar, así que si es "all" no filtramos por status
            # pero el comportamiento original filtraba por estos:
            if status == "all":
                 query["status"] = {
                     "$in": [
                         "skipped_ai_limit",
                         "skipped_ai_limit_unread",
                         "pending_ai_unread",
                         "pending",
                         "processing",
                         "retry_requested",
                         "failed",
                         "error",
                         "missing_metadata",
                     ]
                 }
        
        # Contar total para paginación
        total = coll.count_documents(query)
        
        skip = (page - 1) * page_size
        cursor = coll.find(query).sort("processed_at", DESCENDING).skip(skip).limit(page_size)
        events = []
        retryable_statuses = {
            "skipped_ai_limit",
            "skipped_ai_limit_unread",
            "pending_ai_unread",
            "failed",
            "error",
            "missing_metadata",
        }
        for doc in cursor:
            # Señal explícita para frontend: eventos manuales (uploads) no son reintentables por UID IMAP.
            is_manual = bool(doc.get("manual_upload")) or doc.get("account_email") == "manual_upload"
            retry_supported = doc.get("retry_supported")
            can_retry = (
                (doc.get("status") in retryable_statuses)
                and (not is_manual)
                and (retry_supported is not False)
            )
            doc["can_retry"] = bool(can_retry)
            if not can_retry and is_manual:
                doc["retry_disabled_reason"] = "Evento manual: no aplica reintento"

            doc["_id"] = str(doc["_id"])
            if "processed_at" in doc and hasattr(doc["processed_at"], "isoformat"):
                doc["processed_at"] = doc["processed_at"].isoformat()
            if "last_retry_at" in doc and hasattr(doc["last_retry_at"], "isoformat"):
                doc["last_retry_at"] = doc["last_retry_at"].isoformat()
            if "email_date" in doc and hasattr(doc["email_date"], "isoformat"):
                doc["email_date"] = doc["email_date"].isoformat()
            events.append(doc)

        # En clúster con múltiples réplicas, un job RQ de alto nivel puede estar corriendo
        # aunque aún no existan documentos procesados en Mongo. Exponerlo como evento sintético
        # evita que la cola aparezca vacía durante discovery inicial.
        def _collect_active_owner_jobs(owner_email: str, requested_status: str) -> list[dict]:
            try:
                from rq.job import Job
                from rq.registry import StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry
                from app.worker.queues import get_queue

                candidate_ids = set()
                queue_sources: Dict[str, str] = {}
                conn = None

                for qname in ("high", "default"):
                    q = get_queue(qname)
                    conn = q.connection
                    try:
                        for jid in (q.get_job_ids() or []):
                            candidate_ids.add(jid)
                            queue_sources.setdefault(jid, qname)
                    except Exception:
                        pass

                    for registry_cls in (StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry):
                        try:
                            reg = registry_cls(queue=q, connection=conn)
                            for jid in (reg.get_job_ids() or []):
                                candidate_ids.add(jid)
                                queue_sources.setdefault(jid, qname)
                        except Exception:
                            continue

                if conn is None:
                    return []

                def _build_reason_from_progress(default_reason: str, progress_payload: Optional[Dict[str, Any]]) -> str:
                    if not isinstance(progress_payload, dict):
                        return default_reason

                    queued = int(progress_payload.get("queued_count") or 0)
                    skipped = int(progress_payload.get("skipped_existing") or 0)
                    requeued = int(progress_payload.get("requeued_errors") or 0)
                    matches = int(progress_payload.get("discovered_matches") or 0)
                    stage = str(progress_payload.get("stage") or "").strip().lower()

                    if stage in {"fanout_discovery_complete", "fanout_streaming", "fanout_batch", "fanout_streaming_done", "fanout_done"}:
                        return (
                            "Procesando histórico: "
                            f"matches={matches}, encolados={queued}, omitidos_existentes={skipped}, "
                            f"reencolados_error={requeued}"
                        )
                    if stage == "fanout_no_matches":
                        return "Procesando histórico: no hay nuevos correos para encolar en este rango."
                    if stage == "starting":
                        return "Inicializando procesamiento histórico..."
                    return default_reason

                synthetic_events = []
                for job_id in candidate_ids:
                    try:
                        job = Job.fetch(job_id, connection=conn)
                        kwargs = job.kwargs or {}
                        args = list(getattr(job, "args", ()) or ())
                        func_name = str(getattr(job, "func_name", "") or "")

                        # owner_email puede venir por kwargs (range/manual) o por args (single UID).
                        candidate_owner = str(kwargs.get("owner_email", "")).lower().strip()
                        if not candidate_owner and "process_single_email_from_uid_job" in func_name and len(args) >= 2:
                            candidate_owner = str(args[1] or "").lower().strip()
                        if not candidate_owner and "process_emails_range_job" in func_name and len(args) >= 1:
                            candidate_owner = str(args[0] or "").lower().strip()
                        if not candidate_owner and "process_emails_job" in func_name and len(args) >= 1:
                            candidate_owner = str(args[0] or "").lower().strip()

                        if candidate_owner != owner_email:
                            continue

                        if "process_emails_range_job" in func_name:
                            action = "process_emails_range"
                            subject = "Procesamiento por rango"
                            email_uid = str(job.id)
                        elif "process_emails_job" in func_name:
                            action = "process_emails"
                            subject = "Procesamiento manual"
                            email_uid = str(job.id)
                        elif "process_single_email_from_uid_job" in func_name:
                            action = "process_single_email"
                            uid_from_kw = kwargs.get("email_uid")
                            uid_from_args = args[2] if len(args) >= 3 else None
                            uid_val = uid_from_kw if uid_from_kw else uid_from_args
                            email_uid = str(uid_val) if uid_val is not None else str(job.id)
                            subject = f"Procesamiento de correo UID {email_uid}"
                        else:
                            continue

                        raw_status = str(job.get_status(refresh=True) or "").lower().strip()
                        if "." in raw_status:
                            raw_status = raw_status.split(".")[-1]

                        if raw_status in {"queued", "deferred", "scheduled"}:
                            mapped_status = "pending"
                        elif raw_status in {"started", "running", "busy"}:
                            mapped_status = "processing"
                        elif raw_status in {"failed", "stopped", "canceled", "cancelled"}:
                            mapped_status = "error"
                        else:
                            continue

                        if requested_status != "all" and requested_status != mapped_status:
                            continue

                        ts = job.started_at or job.created_at
                        processed_at = ts.isoformat() if hasattr(ts, "isoformat") else None
                        job_meta = dict(getattr(job, "meta", {}) or {})
                        progress = job_meta.get("progress") if isinstance(job_meta.get("progress"), dict) else None
                        default_reason = (
                            "Job en ejecución desde cola distribuida"
                            if mapped_status == "processing"
                            else "Job encolado y pendiente de ejecución"
                        )
                        reason = _build_reason_from_progress(default_reason, progress)

                        synthetic_events.append({
                            "_id": f"rq::{job.id}",
                            "owner_email": owner_email,
                            "account_email": "system",
                            "email_uid": email_uid,
                            "status": mapped_status,
                            "reason": reason,
                            "subject": subject,
                            "sender": "Sistema",
                            "processed_at": processed_at,
                            "can_retry": False,
                            "retry_supported": False,
                            "job_id": str(job.id),
                            "job_action": action,
                            "source": f"rq_{queue_sources.get(job.id, 'unknown')}",
                        })
                    except Exception:
                        continue

                synthetic_events.sort(key=lambda item: str(item.get("processed_at") or ""), reverse=True)
                return synthetic_events
            except Exception as e:
                logger.warning(f"No se pudieron recolectar jobs activos RQ para {owner_email}: {e}")
                return []

        if page == 1 and status in {"all", "pending", "processing"}:
            synthetic = _collect_active_owner_jobs(email, status)
            if synthetic:
                events = (synthetic + events)[:page_size]
                total += len(synthetic)
            
        return {
            "success": True, 
            "events": events,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size
            }
        }
    except Exception as e:
        logger.error(f"Error fetching queue events for {email}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching queue events")

@router.post("/queue-events/cancel-active")
async def cancel_active_queue_events(
    payload: CancelActiveJobsPayload,
    user: Dict[str, Any] = Depends(_get_current_user),
):
    """
    Cancela en bloque jobs activos del usuario autenticado en RQ.
    Permite filtrar por tipo de job para evitar cancelar más de lo necesario.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    owner_email = (user.get("email") or "").lower().strip()
    if not owner_email:
        raise HTTPException(status_code=400, detail="Usuario inválido")

    try:
        from app.worker.queues import cancel_active_owner_jobs

        scope_to_filters: Dict[str, Optional[tuple[str, ...]]] = {
            "all": None,
            "single_email": ("process_single_email_from_uid_job",),
            "range": ("process_emails_range_job",),
            "full_sync": ("process_emails_job",),
        }
        func_filters = scope_to_filters.get(payload.scope, None)
        safe_max_jobs = max(1, min(int(payload.max_jobs or 500), 2000))

        result = cancel_active_owner_jobs(
            owner_email=owner_email,
            func_filters=func_filters,
            max_jobs=safe_max_jobs,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error cancelando jobs activos para {owner_email}: {e}")
        raise HTTPException(status_code=500, detail="No se pudieron cancelar jobs activos")

async def _get_sse_user(request: Request, token: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """
    Dependencia de autenticación para endpoints SSE.
    Acepta el token JWT vía query param porque EventSource del navegador
    no puede enviar cabeceras personalizadas (como Authorization: Bearer).
    Fallback: lee el header Authorization estándar si no hay query param.
    """
    if token:
        from app.utils.firebase_auth import verify_firebase_token
        try:
            claims = verify_firebase_token(token)
        except HTTPException:
            raise HTTPException(status_code=401, detail="Token inválido")

        try:
            user_repo = UserRepository()
            user_repo.upsert_user({
                "email": claims.get("email"),
                "uid": claims.get("user_id"),
                "name": claims.get("name"),
                "picture": claims.get("picture") or claims.get("photoURL"),
            })
            db_user = user_repo.get_by_email(claims.get("email"))
            if db_user and db_user.get("status") == "suspended":
                raise HTTPException(status_code=403, detail="Tu cuenta está suspendida. Contacta al administrador.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"SSE auth upsert warning: {e}")

        return {
            "email": claims.get("email"),
            "uid": claims.get("user_id"),
            "name": claims.get("name"),
        }

    # Fallback: intentar con header Bearer estándar
    return _get_current_user(request)


@router.get("/queue-events/stream")
async def stream_queue_events(
    request: Request,
    token: Optional[str] = Query(default=None),
    status: str = Query(default="all"),
    page_size: int = Query(default=20),
    user: Dict[str, Any] = Depends(_get_sse_user),
):
    """
    SSE stream para actualizaciones en tiempo real de la cola de procesamiento.
    Emite eventos 'queue-update' cuando los datos cambian y 'heartbeat' cada 3 s
    cuando no hay cambios, para mantener la conexión viva.
    """
    from sse_starlette.sse import EventSourceResponse
    import json
    import asyncio
    import hashlib
    from pymongo import MongoClient, DESCENDING

    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    owner = (user.get("email") or "").lower()

    async def event_generator():
        last_data_hash: Optional[str] = None

        while True:
            if await request.is_disconnected():
                logger.debug(f"SSE desconectado para {owner}")
                break

            try:
                client = MongoClient(settings.MONGODB_URL)
                db = client[settings.MONGODB_DATABASE]
                coll = db.processed_emails

                query: Dict[str, Any] = {"owner_email": owner}
                if status and status != "all":
                    query["status"] = status
                else:
                    query["status"] = {
                        "$in": [
                            "skipped_ai_limit",
                            "skipped_ai_limit_unread",
                            "pending_ai_unread",
                            "pending",
                            "processing",
                            "retry_requested",
                            "failed",
                            "error",
                            "missing_metadata",
                        ]
                    }

                total = coll.count_documents(query)
                cursor = coll.find(query).sort("processed_at", DESCENDING).limit(page_size)

                retryable_statuses = {
                    "skipped_ai_limit",
                    "skipped_ai_limit_unread",
                    "pending_ai_unread",
                    "failed",
                    "error",
                    "missing_metadata",
                }
                events: List[Dict[str, Any]] = []
                for doc in cursor:
                    is_manual = bool(doc.get("manual_upload")) or doc.get("account_email") == "manual_upload"
                    retry_supported = doc.get("retry_supported")
                    can_retry = (
                        (doc.get("status") in retryable_statuses)
                        and (not is_manual)
                        and (retry_supported is not False)
                    )
                    doc["can_retry"] = bool(can_retry)
                    if not can_retry and is_manual:
                        doc["retry_disabled_reason"] = "Evento manual: no aplica reintento"
                    doc["_id"] = str(doc["_id"])
                    if "processed_at" in doc and hasattr(doc["processed_at"], "isoformat"):
                        doc["processed_at"] = doc["processed_at"].isoformat()
                    if "last_retry_at" in doc and hasattr(doc["last_retry_at"], "isoformat"):
                        doc["last_retry_at"] = doc["last_retry_at"].isoformat()
                    if "email_date" in doc and hasattr(doc["email_date"], "isoformat"):
                        doc["email_date"] = doc["email_date"].isoformat()
                    events.append(doc)

                client.close()

                # Recolectar jobs RQ activos (misma lógica que get_queue_events)
                if status in {"all", "pending", "processing"}:
                    try:
                        from rq.job import Job
                        from rq.registry import StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry
                        from app.worker.queues import get_queue

                        candidate_ids: set = set()
                        queue_sources: Dict[str, str] = {}
                        conn = None

                        for qname in ("high", "default"):
                            q = get_queue(qname)
                            conn = q.connection
                            try:
                                for jid in (q.get_job_ids() or []):
                                    candidate_ids.add(jid)
                                    queue_sources.setdefault(jid, qname)
                            except Exception:
                                pass
                            for registry_cls in (StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry):
                                try:
                                    reg = registry_cls(queue=q, connection=conn)
                                    for jid in (reg.get_job_ids() or []):
                                        candidate_ids.add(jid)
                                        queue_sources.setdefault(jid, qname)
                                except Exception:
                                    continue

                        synthetic_events: List[Dict[str, Any]] = []
                        if conn is not None:
                            for job_id in candidate_ids:
                                try:
                                    job = Job.fetch(job_id, connection=conn)
                                    kwargs = job.kwargs or {}
                                    args = list(getattr(job, "args", ()) or ())
                                    func_name = str(getattr(job, "func_name", "") or "")

                                    candidate_owner = str(kwargs.get("owner_email", "")).lower().strip()
                                    if not candidate_owner and "process_single_email_from_uid_job" in func_name and len(args) >= 2:
                                        candidate_owner = str(args[1] or "").lower().strip()
                                    if not candidate_owner and "process_emails_range_job" in func_name and len(args) >= 1:
                                        candidate_owner = str(args[0] or "").lower().strip()
                                    if not candidate_owner and "process_emails_job" in func_name and len(args) >= 1:
                                        candidate_owner = str(args[0] or "").lower().strip()

                                    if candidate_owner != owner:
                                        continue

                                    if "process_emails_range_job" in func_name:
                                        action = "process_emails_range"
                                        subject = "Procesamiento por rango"
                                        email_uid = str(job.id)
                                    elif "process_emails_job" in func_name:
                                        action = "process_emails"
                                        subject = "Procesamiento manual"
                                        email_uid = str(job.id)
                                    elif "process_single_email_from_uid_job" in func_name:
                                        action = "process_single_email"
                                        uid_from_kw = kwargs.get("email_uid")
                                        uid_from_args = args[2] if len(args) >= 3 else None
                                        uid_val = uid_from_kw if uid_from_kw else uid_from_args
                                        email_uid = str(uid_val) if uid_val is not None else str(job.id)
                                        subject = f"Procesamiento de correo UID {email_uid}"
                                    else:
                                        continue

                                    raw_status = str(job.get_status(refresh=True) or "").lower().strip()
                                    if "." in raw_status:
                                        raw_status = raw_status.split(".")[-1]

                                    if raw_status in {"queued", "deferred", "scheduled"}:
                                        mapped_status = "pending"
                                    elif raw_status in {"started", "running", "busy"}:
                                        mapped_status = "processing"
                                    elif raw_status in {"failed", "stopped", "canceled", "cancelled"}:
                                        mapped_status = "error"
                                    else:
                                        continue

                                    if status != "all" and status != mapped_status:
                                        continue

                                    ts = job.started_at or job.created_at
                                    processed_at = ts.isoformat() if hasattr(ts, "isoformat") else None
                                    job_meta = dict(getattr(job, "meta", {}) or {})
                                    progress = job_meta.get("progress") if isinstance(job_meta.get("progress"), dict) else None

                                    default_reason = (
                                        "Job en ejecución desde cola distribuida"
                                        if mapped_status == "processing"
                                        else "Job encolado y pendiente de ejecución"
                                    )
                                    if isinstance(progress, dict):
                                        queued_c = int(progress.get("queued_count") or 0)
                                        skipped_c = int(progress.get("skipped_existing") or 0)
                                        requeued_c = int(progress.get("requeued_errors") or 0)
                                        matches_c = int(progress.get("discovered_matches") or 0)
                                        stage_c = str(progress.get("stage") or "").strip().lower()
                                        if stage_c in {"fanout_discovery_complete", "fanout_streaming", "fanout_batch", "fanout_streaming_done", "fanout_done"}:
                                            default_reason = (
                                                f"Procesando histórico: matches={matches_c}, "
                                                f"encolados={queued_c}, omitidos_existentes={skipped_c}, "
                                                f"reencolados_error={requeued_c}"
                                            )
                                        elif stage_c == "fanout_no_matches":
                                            default_reason = "Procesando histórico: no hay nuevos correos para encolar en este rango."
                                        elif stage_c == "starting":
                                            default_reason = "Inicializando procesamiento histórico..."

                                    synthetic_events.append({
                                        "_id": f"rq::{job.id}",
                                        "owner_email": owner,
                                        "account_email": "system",
                                        "email_uid": email_uid,
                                        "status": mapped_status,
                                        "reason": default_reason,
                                        "subject": subject,
                                        "sender": "Sistema",
                                        "processed_at": processed_at,
                                        "can_retry": False,
                                        "retry_supported": False,
                                        "job_id": str(job.id),
                                        "job_action": action,
                                        "source": f"rq_{queue_sources.get(job.id, 'unknown')}",
                                    })
                                except Exception:
                                    continue

                        if synthetic_events:
                            synthetic_events.sort(key=lambda item: str(item.get("processed_at") or ""), reverse=True)
                            events = (synthetic_events + events)[:page_size]
                            total += len(synthetic_events)

                    except Exception as e:
                        logger.warning(f"SSE: no se pudieron recolectar jobs RQ para {owner}: {e}")

                data = {
                    "success": True,
                    "events": events,
                    "pagination": {
                        "total": total,
                        "page": 1,
                        "pages": max(1, (total + page_size - 1) // page_size),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }

                data_hash = hashlib.md5(json.dumps(data, default=str).encode()).hexdigest()

                if data_hash != last_data_hash:
                    last_data_hash = data_hash
                    yield {"event": "queue-update", "data": json.dumps(data, default=str)}
                else:
                    yield {"event": "heartbeat", "data": "{}"}

            except Exception as e:
                logger.error(f"SSE error para {owner}: {e}")
                yield {"event": "error", "data": json.dumps({"error": str(e)})}

            await asyncio.sleep(3)

    from sse_starlette.sse import EventSourceResponse
    return EventSourceResponse(event_generator())


@router.post("/queue-events/{event_id}/retry")
async def retry_queue_event(event_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Re-intenta un evento fallido o pausado empujándolo a la cola de RQ nuevamente.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
        
    email = (user.get("email") or "").lower()
    
    try:
        from pymongo import MongoClient
        from app.config.settings import settings
        from app.worker.queues import enqueue_job
        from app.worker.jobs import process_single_email_from_uid_job
        from datetime import datetime
        
        client = MongoClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DATABASE]
        coll = db.processed_emails
        
        # Verificar que el evento pertenezca al usuario
        doc = coll.find_one({"_id": event_id, "owner_email": email})
        if not doc:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        # Eventos manuales se exponen para visibilidad, pero no son reintentables por UID IMAP.
        if bool(doc.get("manual_upload")) or doc.get("account_email") == "manual_upload" or doc.get("retry_supported") is False:
            raise HTTPException(
                status_code=400,
                detail="Este evento manual no admite reintento desde la cola de correos"
            )

        allowed_statuses = {"skipped_ai_limit", "skipped_ai_limit_unread", "failed", "error", "missing_metadata"}
        if doc.get("status") not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Estado no reintentable: {doc.get('status')}"
            )
            
        owner = doc.get("owner_email")
        account = doc.get("account_email")
        uid = doc.get("email_uid")
        msg_id = doc.get("message_id")

        if not owner or not account or not uid:
            raise HTTPException(
                status_code=400,
                detail="Evento incompleto para reintento (owner/account/uid requeridos)"
            )
        
        # Actualizar estado a retry_requested (estado explícitamente reintentable)
        coll.update_one(
            {"_id": event_id},
            {"$set": {
                "status": "retry_requested",
                "reason": "Reintento manual por usuario",
                "last_retry_at": datetime.utcnow()
            }}
        )
        
        # Encolar a RQ
        job = enqueue_job(
            process_single_email_from_uid_job,
            account,
            owner,
            uid
        )

        logger.info(
            f"🔄 Usuario {email} solicitó reintento manual para evento {event_id}. "
            f"Job {job.id} (account={account}, uid={uid}, msg_id={msg_id})"
        )
        return {"success": True, "message": "Evento reencolado exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying queue event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
