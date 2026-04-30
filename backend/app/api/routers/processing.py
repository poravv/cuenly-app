"""
Endpoints de procesamiento de correos, cola de tareas y control de jobs.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import time
import logging

from app.api.deps import (
    _get_current_user,
    _get_current_user_with_trial_check,
    _get_current_user_with_ai_check,
    _get_current_admin,
)
from app.config.settings import settings
from app.models.models import ProcessResult, JobStatus, MultiEmailConfig, InvoiceData
from app.repositories.user_repository import UserRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.mapping.invoice_mapping import map_invoice
from app.modules.scheduler.processing_lock import PROCESSING_LOCK
from app.modules.scheduler.task_queue import task_queue
from app.utils.security import validate_frontend_key
from app.utils.observability import observability_logger
from app.middleware.observability_middleware import BusinessEventLogger
from app.api.rate_limit import rate_limit as _rate_limit
from app.api.state import invoice_sync

router = APIRouter()
logger = logging.getLogger(__name__)


class IntervalPayload(BaseModel):
    minutes: int


class ProcessRangeRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    run_async: bool = True


def process_emails_task():
    """Tarea en segundo plano para procesar correos."""
    try:
        result = invoice_sync.process_emails()
        logger.info(f"Tarea en segundo plano completada: {result.message}")
    except Exception as e:
        logger.error(f"Error en tarea en segundo plano: {str(e)}")

def process_emails_range_task(user_email: str, start_date=None, end_date=None):
    """Tarea background para procesar rango de fechas"""
    try:
        from app.modules.email_processor.config_store import get_enabled_configs
        from app.modules.email_processor.email_processor import MultiEmailProcessor
        from app.models.models import ProcessResult
        
        configs = get_enabled_configs(include_password=True, owner_email=user_email) if user_email else []
        if not configs:
            logger.warning(f"ProcessRange: Sin configs para {user_email}")
            return ProcessResult(success=False, message="No hay cuentas de correo configuradas", invoice_count=0, invoices=[])

        email_configs = []
        for c in configs:
            config_data = dict(c)
            config_data['owner_email'] = user_email
            email_configs.append(MultiEmailConfig(**config_data))
            
        mp = MultiEmailProcessor(email_configs=email_configs, owner_email=user_email)
        logger.info(f"🚀 Iniciando job por rango para {user_email}: {start_date} - {end_date}")
        return mp.process_all_emails(
            start_date=start_date,
            end_date=end_date,
            force_search_criteria_all=True,
            fanout_batch_size=50,
            disable_fanout_account_cap=True
        )
        
    except Exception as e:
        logger.error(f"❌ Error en process_emails_range_task para {user_email}: {e}")
        from app.models.models import ProcessResult
        return ProcessResult(success=False, message=str(e), invoice_count=0, invoices=[])

def _get_ai_block_reason(owner_email: str) -> Optional[str]:
    """Retorna razón textual si IA no está disponible para el usuario, o None si sí puede usar IA."""
    if not owner_email:
        return "IA_NO_DISPONIBLE: Usuario no identificado"
    try:
        ai_check = UserRepository().can_use_ai(owner_email)
        if ai_check.get("can_use", False):
            return None
        reason = str(ai_check.get("reason", "")).strip().lower()
        message = str(ai_check.get("message", "No disponible")).strip()
        if reason == "ai_limit_reached":
            return f"LIMITE_IA: {message}"
        return f"IA_NO_DISPONIBLE: {message}"
    except Exception as e:
        logger.warning(f"⚠️ Error verificando disponibilidad IA para {owner_email}: {e}")
        return "IA_NO_DISPONIBLE: No fue posible validar disponibilidad de IA"


def _get_ai_reason_code(ai_block_reason: Optional[str]) -> Optional[str]:
    """Mapea razón textual de IA a código estable para frontend."""
    if not ai_block_reason:
        return None
    return "ai_limit_reached" if ai_block_reason.startswith("LIMITE_IA:") else "ai_unavailable"


def _store_manual_pending_ai(
    owner_email: str,
    sender: str,
    date_obj: Optional[datetime],
    minio_key: str,
    fuente: str,
    reason: str,
) -> None:
    """
    Registra uploads manuales bloqueados por IA:
    1) En processed_emails (cola de procesos UI) con status=pending.
    2) En invoice_headers con status=PENDING_AI (tracking interno).
    """
    try:
        # 1) Cola de procesos (processed_emails) para visibilidad en UI de "Actividad/Cola".
        try:
            from app.modules.email_processor.processed_registry import _repo, build_key as build_processed_key

            event_uid = f"manual_ai_pending_{uuid.uuid4().hex}"
            event_key = build_processed_key(event_uid, "manual_upload", owner_email)
            base_reason = (reason or "Pendiente por IA").strip()
            event_reason = f"{base_reason} | Manual: sin reproceso automático"[:500]

            _repo.mark_processed(
                key=event_key,
                status="pending",
                reason=event_reason,
                owner_email=owner_email,
                account_email="manual_upload",
                message_id=f"manual_pending_ai:{event_uid}",
                subject=f"Carga manual pendiente de IA ({fuente})",
                sender=(sender or "Carga manual")[:200],
                email_date=date_obj or datetime.utcnow(),
            )

            # Metadatos extra útiles para UI/debug.
            _repo._get_collection().update_one(
                {"_id": event_key},
                {"$set": {
                    "manual_upload": True,
                    "fuente": fuente,
                    "minio_key": (minio_key or ""),
                    "retry_supported": False,
                }},
                upsert=False,
            )
            logger.info(
                "🕒 Upload manual registrado en cola (processed_emails) owner=%s fuente=%s",
                owner_email,
                fuente,
            )
        except Exception as qerr:
            logger.error(f"❌ Error registrando pending manual en processed_emails: {qerr}")

        # 2) Tracking interno en invoice_headers (PENDING_AI).
        pending_msg_id = f"manual_pending_ai:{uuid.uuid4().hex}"
        inv = InvoiceData(
            numero_factura=f"PENDING_AI_{uuid.uuid4().hex[:10]}",
            ruc_emisor="UNKNOWN",
            nombre_emisor=(sender or "Carga manual")[:100],
            fecha=date_obj or datetime.utcnow(),
            email_origen=owner_email,
            message_id=pending_msg_id,
            status="PENDING_AI",
            processing_error=(reason or "Pendiente por IA")[:500],
            fuente=fuente,
            minio_key=minio_key or "",
        )
        doc = map_invoice(inv, fuente=fuente, minio_key=minio_key or "")
        if owner_email:
            doc.header.owner_email = owner_email
            for it in doc.items:
                it.owner_email = owner_email
        doc.header.status = "PENDING_AI"
        doc.header.processing_error = (reason or "Pendiente por IA")[:500]
        MongoInvoiceRepository().save_document(doc)
        logger.info(
            "🕒 Upload manual guardado en PENDING_AI (owner=%s, fuente=%s, minio_key=%s)",
            owner_email,
            fuente,
            minio_key or "",
        )
    except Exception as e:
        logger.error(f"❌ Error guardando PENDING_AI manual: {e}")


def _create_completed_task(action: str, result: ProcessResult) -> str:
    """
    Crea una tarea finalizada en memoria para mantener contrato async (retorno job_id)
    cuando el procesamiento se resuelve de forma inmediata.
    """
    job_id = uuid.uuid4().hex
    now = time.time()
    with task_queue._lock:
        task_queue._jobs[job_id] = {
            'job_id': job_id,
            'action': action,
            'status': 'done',
            'created_at': now,
            'started_at': now,
            'finished_at': now,
            'message': result.message,
            'result': result,
            '_func': None,
        }
    return job_id


@router.post("/process", response_model=ProcessResult)
async def process_emails(background_tasks: BackgroundTasks, run_async: bool = False, request: Request = None, user: Dict[str, Any] = Depends(_get_current_user_with_ai_check), _frontend_key: bool = Depends(validate_frontend_key)):
    """
    Procesa correos electrónicos para extraer facturas.
    
    Args:
        background_tasks: Gestor de tareas en segundo plano.
        run_async: Si es True, el procesamiento se ejecuta en segundo plano.
        
    Returns:
        ProcessResult: Resultado del procesamiento.
    """
    try:
        # Verificar trial antes de procesar
        user_repo = UserRepository()
        owner_email = (user.get('email') or '').lower()
        trial_info = user_repo.get_trial_info(owner_email)
        
        if trial_info['is_trial_user'] and trial_info['trial_expired']:
            observability_logger.log_business_event(
                "trial_expired_processing_attempt",
                user_email=owner_email,
                attempted_action="email_processing",
                trial_expired=True,
                security_event=True
            )
            BusinessEventLogger.log_trial_expiration_attempt(owner_email, "email_processing")
            return ProcessResult(
                success=False,
                message="TRIAL_EXPIRED: Tu período de prueba ha expirado. Por favor, actualiza tu suscripción para continuar procesando facturas.",
                invoice_count=0,
                invoices=[]
            )
        
        if run_async:
            # Ejecutar en segundo plano
            background_tasks.add_task(process_emails_task)
            return ProcessResult(
                success=True,
                message="Procesamiento iniciado en segundo plano"
            )
        else:
            # Ejecutar de forma síncrona
            # Procesar solo cuentas del usuario (multiusuario)
            from app.modules.email_processor.config_store import get_enabled_configs
            from app.modules.email_processor.email_processor import MultiEmailProcessor
            owner_email = (user.get('email') or '').lower()
            configs = get_enabled_configs(include_password=True, owner_email=owner_email) if owner_email else []
            if not configs:
                return ProcessResult(success=False, message="Sin cuentas de correo habilitadas para este usuario", invoice_count=0)
            
            # Crear configs con owner_email agregado
            email_configs = []
            for c in configs:
                config_data = dict(c)
                config_data['owner_email'] = owner_email
                email_configs.append(MultiEmailConfig(**config_data))
                
            mp = MultiEmailProcessor(email_configs=email_configs, owner_email=owner_email)
            result = mp.process_all_emails()
            return result
    except Exception as e:
        observability_logger.log_error(
            "email_processing_error",
            str(e),
            user_email=user.get('email', ''),
            endpoint="/process",
            async_mode=run_async
        )
        return ProcessResult(
            success=False,
            message=f"Error al procesar correos: {str(e)}"
        )

@router.post("/process-direct")
async def process_emails_direct(
    limit: Optional[int] = None,
    # USA _get_current_user_with_trial_check para permitir que llegue al procesador
    # y allí se aplique la lógica "XML allowed"
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check),
    request: Request = None,
    _frontend_key: bool = Depends(validate_frontend_key)
):
    """Procesa correos directamente con fan-out a cola y límite configurable."""
    try:
        default_limit = max(1, int(getattr(settings, "PROCESS_DIRECT_DEFAULT_LIMIT", 50) or 50))
        max_limit = max(default_limit, int(getattr(settings, "PROCESS_DIRECT_MAX_LIMIT", 200) or 200))

        # Validar límite
        if limit is None or limit <= 0:
            limit = default_limit
        if limit > max_limit:
            limit = max_limit
            
        # Ejecutar procesamiento limitado
        from app.modules.email_processor.config_store import get_enabled_configs
        from app.modules.email_processor.email_processor import MultiEmailProcessor
        owner_email = (user.get('email') or '').lower()
        configs = get_enabled_configs(include_password=True, owner_email=owner_email) if owner_email else []
        if not configs:
            return {"success": False, "message": "Sin cuentas de correo habilitadas para este usuario", "invoice_count": 0}
        
        # Crear configs con owner_email agregado
        email_configs = []
        for c in configs:
            config_data = dict(c)
            config_data['owner_email'] = owner_email  # Agregar owner_email explícitamente
            email_configs.append(MultiEmailConfig(**config_data))
            
        mp = MultiEmailProcessor(email_configs=email_configs, owner_email=owner_email)
        # 🚀 ACTIVAR FAN-OUT POR DEFECTO PARA NO BLOQUEAR BACKEND
        result = mp.process_limited_emails(limit=limit, fan_out=True)
        
        if result and hasattr(result, 'success') and result.success:
            return {
                "success": True,
                "message": result.message,
                "invoice_count": getattr(result, 'invoice_count', 0),
                "limit_used": limit,
                "default_limit": default_limit,
                "max_limit": max_limit,
            }
        else:
            return {
                "success": False,
                "message": getattr(result, 'message', 'Error en el procesamiento'),
                "invoice_count": 0
            }
            
    except Exception as e:
        logger.error(f"Error en process-direct: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/tasks/process")
async def enqueue_process_emails(
    # Permitir encolado aunque no haya cupo IA: los XML se procesan y
    # lo que requiera IA quedará en PENDING_AI dentro del pipeline.
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check),
    request: Request = None,
    _frontend_key: bool = Depends(validate_frontend_key)
):
    """Encola una ejecución de procesamiento de correos y retorna un job_id."""
    
    # Verificar si el job automático está ejecutándose
    job_status = invoice_sync.get_job_status()
    if job_status.running:
        # Retornar error inmediatamente si el job automático está activo
        job_id = str(uuid.uuid4().hex)
        task_queue._jobs[job_id] = {
            'job_id': job_id,
            'action': 'process_emails',
            'status': 'error',
            'created_at': time.time(),
            'started_at': time.time(),
            'finished_at': time.time(),
            'message': 'No se puede procesar manualmente mientras la automatización esté activa. Detenga la automatización primero.',
            'result': ProcessResult(
                success=False,
                message='No se puede procesar manualmente mientras la automatización esté activa. Detenga la automatización primero.',
                invoice_count=0,
                processed_emails=0
            ),
            '_func': None,
        }
        return {"job_id": job_id}
    
    try:
        from app.worker.queues import enqueue_job
        from app.worker.jobs import process_emails_job

        owner_email = (user.get('email') or '').lower()
        job = enqueue_job(
            process_emails_job,
            owner_email=owner_email,
            priority='high',
            timeout='30m'
        )
        return {"job_id": job.id}
    except Exception as e:
        logger.error(f"Error encolando /tasks/process en RQ: {e}")
        raise HTTPException(status_code=500, detail="No se pudo encolar el procesamiento")

@router.get("/tasks/{job_id}")
async def get_task_status(job_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """Consulta el estado de un job enviado a la cola. Requiere autenticación."""
    # 1) Compatibilidad con cola local (uploads/range/legacy)
    job = task_queue.get(job_id)
    if job:
        return job

    # 2) Cola RQ distribuida (manual async multiusuario)
    from app.worker.queues import get_job_status as get_rq_job_status

    rq_job = get_rq_job_status(job_id)
    raw_status = str(rq_job.get("status", "")).lower().strip()
    if "." in raw_status:
        raw_status = raw_status.split(".")[-1]
    if raw_status in {"", "not_found"}:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    def _map_status(value: str) -> str:
        if value in {"queued", "deferred", "scheduled"}:
            return "queued"
        if value in {"started", "running", "busy"}:
            return "running"
        if value in {"finished", "done"}:
            return "done"
        if value in {"failed", "stopped", "canceled", "cancelled"}:
            return "error"
        return "queued"

    def _to_ts(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except Exception:
                return None
        return None

    raw_result = rq_job.get("result")
    raw_error = rq_job.get("error")
    raw_meta = rq_job.get("meta")
    job_meta = raw_meta if isinstance(raw_meta, dict) else {}
    progress = job_meta.get("progress") if isinstance(job_meta.get("progress"), dict) else None
    cancel_requested = bool(job_meta.get("cancelled_by_user"))
    ended_ts = _to_ts(rq_job.get("ended_at"))

    mapped_status = _map_status(raw_status)
    # Fallback robusto: si ya terminó (ended_at/result), no dejar estado en queued.
    if mapped_status == "queued" and (ended_ts is not None or raw_result is not None):
        mapped_status = "error" if raw_error else "done"
    elif mapped_status == "queued" and raw_error:
        mapped_status = "error"
    message = None
    if mapped_status == "done":
        if isinstance(raw_result, dict):
            message = raw_result.get("message") or "Completado"
        else:
            message = "Completado"
    elif mapped_status == "running" and cancel_requested:
        message = "Cancelación solicitada. El proceso se está deteniendo."
    elif mapped_status == "error":
        lowered_error = str(raw_error or "").lower()
        if raw_status in {"stopped", "canceled", "cancelled"} or any(
            token in lowered_error for token in ("stopped", "cancel")
        ):
            message = "Proceso cancelado por el usuario"
        elif "abandonedjob" in lowered_error or "abandonedjoberror" in lowered_error:
            message = "Tarea interrumpida por reinicio del servidor. Puedes reintentar el procesamiento."
        elif "timeout" in lowered_error or "timedout" in lowered_error:
            message = "La tarea excedio el tiempo maximo permitido. Puedes reintentar."
        else:
            message = raw_error or "Error en procesamiento"

    def _format_progress_message(action_name: str, progress_payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if not progress_payload:
            return None

        queued = int(progress_payload.get("queued_count") or 0)
        skipped = int(progress_payload.get("skipped_existing") or 0)
        requeued = int(progress_payload.get("requeued_errors") or 0)
        matches = int(progress_payload.get("discovered_matches") or 0)
        stage = str(progress_payload.get("stage") or "").strip().lower()

        if action_name == "process_emails_range":
            if stage in {"starting"}:
                return "Inicializando procesamiento histórico..."
            if stage in {"fanout_discovery_complete", "fanout_streaming", "fanout_batch", "fanout_streaming_done", "fanout_done"}:
                parts = [f"Se encontraron {matches} correos"]
                if queued > 0:
                    parts.append(f"{queued} en cola de procesamiento")
                if skipped > 0:
                    parts.append(f"{skipped} ya procesados anteriormente")
                if requeued > 0:
                    parts.append(f"{requeued} reintentando por error previo")
                return "Procesando historico: " + ", ".join(parts) + "."
            if stage == "fanout_no_matches":
                return "Procesamiento histórico en ejecución: no se encontraron nuevos correos para encolar."
            if stage == "fanout_error":
                return "Procesamiento histórico en ejecución: ocurrió un error en fan-out, continuando con fallback."
        return None

    func_name = str(rq_job.get("func_name", "") or "")
    action = "process_emails"
    if "process_emails_range_job" in func_name:
        action = "process_emails_range"
    elif "process_single_email_from_uid_job" in func_name:
        action = "process_single_email"
    elif "process_manual_pdf_job" in func_name:
        action = "process_pdf_manual"
    elif "process_manual_image_job" in func_name:
        action = "process_image_manual"
    elif "process_manual_xml_job" in func_name:
        action = "upload_xml"
    elif "process_emails_job" in func_name:
        action = "process_emails"

    if mapped_status == "running":
        progress_message = _format_progress_message(action, progress)
        if progress_message:
            message = progress_message

    return {
        "job_id": job_id,
        "action": action,
        "status": mapped_status,
        "created_at": _to_ts(rq_job.get("created_at")),
        "started_at": _to_ts(rq_job.get("started_at")),
        "finished_at": ended_ts,
        "message": message,
        "progress": progress,
        "result": raw_result,
    }


@router.post("/tasks/{job_id}/cancel")
async def cancel_task(
    job_id: str,
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check),
):
    """Cancela una tarea en cola (o solicita stop si ya está en ejecución)."""
    owner_email = (user.get("email") or "").lower()

    # 1) Compatibilidad con cola local en memoria
    local_job = task_queue.get(job_id)
    if local_job:
        status = str(local_job.get("status", "")).lower()
        if status in {"done", "error"}:
            return {"success": False, "job_id": job_id, "status": status, "message": "La tarea ya finalizó"}
        with task_queue._lock:
            if job_id in task_queue._jobs:
                task_queue._jobs[job_id]["status"] = "error"
                task_queue._jobs[job_id]["message"] = "Proceso cancelado por el usuario"
                task_queue._jobs[job_id]["finished_at"] = time.time()
        return {"success": True, "job_id": job_id, "status": "cancelled", "message": "Tarea cancelada"}

    # 2) Cola distribuida RQ
    from app.worker.queues import cancel_job as cancel_rq_job

    result = cancel_rq_job(job_id, requester_email=owner_email)
    status = str(result.get("status", "")).lower()
    if status == "forbidden":
        raise HTTPException(status_code=403, detail=result.get("message") or "No autorizado")
    if status in {"not_found", ""}:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if not result.get("cancelled", False):
        return {
            "success": False,
            "job_id": job_id,
            "status": status or "unknown",
            "message": result.get("message") or "No se pudo cancelar el job",
        }
    return {
        "success": True,
        "job_id": job_id,
        "status": status,
        "message": result.get("message") or "Cancelación solicitada",
    }

@router.delete("/tasks/cleanup")
async def cleanup_old_tasks(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Limpia tareas antiguas que están atoradas. Requiere permisos de administrador."""
    cleanup_count = 0
    current_time = time.time()
    
    # Limpiar tareas que llevan más de 1 hora atoradas
    with task_queue._lock:
        jobs_to_remove = []
        for job_id, job in task_queue._jobs.items():
            if job.get('status') == 'running':
                created_at = job.get('created_at', current_time)
                # Si la tarea lleva más de 1 hora "running", marcarla como error
                if current_time - created_at > 3600:  # 1 hora
                    job['status'] = 'error'
                    job['message'] = 'Tarea cancelada por tiempo excesivo'
                    job['finished_at'] = current_time
                    cleanup_count += 1
                    
            # Eliminar tareas completadas que tengan más de 24 horas
            elif job.get('status') in ['done', 'error']:
                created_at = job.get('created_at', current_time)
                if current_time - created_at > 86400:  # 24 horas
                    jobs_to_remove.append(job_id)
                    cleanup_count += 1
        
        # Remover tareas antiguas
        for job_id in jobs_to_remove:
            del task_queue._jobs[job_id]
    
    return {"message": f"Se limpiaron {cleanup_count} tareas", "cleaned_count": cleanup_count}

@router.get("/tasks/debug")
async def debug_tasks(user: Dict[str, Any] = Depends(_get_current_user)):
    """Debug endpoint para ver el estado de todas las tareas."""
    current_time = time.time()
    task_info = []
    
    with task_queue._lock:
        for job_id, job in task_queue._jobs.items():
            job_copy = {k: v for k, v in job.items() if k != '_func'}
            created_at = job.get('created_at', current_time)
            running_time = current_time - created_at
            job_copy['running_time_seconds'] = running_time
            task_info.append(job_copy)
    
    return {
        "total_tasks": len(task_info),
        "tasks": task_info,
        "processing_lock_available": not PROCESSING_LOCK.locked()
    }

@router.post("/jobs/full-sync")
async def trigger_full_sync(
    user: Dict[str, Any] = Depends(_get_current_user)  # Auth required
):
    """
    Encola un job de sincronización completa (histórico) para el usuario.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    owner_email = (user.get('email') or '').lower()
    
    # Encolar job persistente
    try:
        from app.modules.scheduler.async_jobs import async_job_manager
        
        job_id = async_job_manager.enqueue_job(
            "full_sync",
            {"owner_email": owner_email},
            owner_email=owner_email
        )
        return {"success": True, "message": "Sincronización histórica iniciada", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error encolando job full_sync: {e}")
        raise HTTPException(status_code=500, detail="Error interno al iniciar sincronización")

@router.post("/jobs/retry-skipped")
async def trigger_retry_skipped(
    user: Dict[str, Any] = Depends(_get_current_user)  # Auth required
):
    """
    Encola un job para reintentar correos que fueron omitidos por límites de IA.
    Útil cuando el usuario renueva su plan o comienza un nuevo mes.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    owner_email = (user.get('email') or '').lower()
    
    try:
        from app.modules.scheduler.async_jobs import async_job_manager
        
        job_id = async_job_manager.enqueue_job(
            "retry_skipped",
            {"owner_email": owner_email},
            owner_email=owner_email
        )
        return {"success": True, "message": "Reintento de correos omitidos iniciado", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error encolando job retry_skipped: {e}")
        raise HTTPException(status_code=500, detail="Error interno")

@router.post("/jobs/process-range")
@_rate_limit("5/hour")
async def process_range_job(
    request: Request,
    payload: ProcessRangeRequest,
    # Importante: no bloquear por límite IA a nivel endpoint.
    # El procesamiento interno ya maneja XML vs IA y deja pendientes cuando corresponde.
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)
):
    """
    Inicia un job de procesamiento filtrado por rango de fechas (fecha del correo).
    Formatos de fecha: YYYY-MM-DD.
    """
    owner_email = (user.get('email') or '').lower()
    
    # Validar fechas
    s_date = None
    e_date = None
    if payload.start_date:
        try:
            s_date = datetime.strptime(payload.start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato start_date inválido (Use YYYY-MM-DD)")
            
    if payload.end_date:
        try:
            e_date = datetime.strptime(payload.end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato end_date inválido (Use YYYY-MM-DD)")

    if payload.run_async:
        # Evitar solapamiento con scheduler automático.
        job_status = invoice_sync.get_job_status()
        if job_status.running:
            raise HTTPException(
                status_code=409,
                detail="No se puede procesar el historial mientras la automatización esté activa. Detenga la automatización primero."
            )

        try:
            from app.worker.queues import enqueue_job, find_active_range_jobs, cancel_job
            from app.worker.jobs import process_emails_range_job

            start_str = payload.start_date if payload.start_date else None
            end_str = payload.end_date if payload.end_date else None

            # Si el usuario dispara de nuevo el proceso por rango, cancelar jobs previos activos
            # del mismo owner para evitar duplicados en entornos con réplicas.
            cancelled_previous: List[str] = []
            previous_jobs = find_active_range_jobs(owner_email)
            for prev in previous_jobs:
                prev_id = str(prev.get("id", "")).strip()
                if not prev_id:
                    continue
                cancel_result = cancel_job(prev_id, requester_email=owner_email)
                if cancel_result.get("cancelled") or str(cancel_result.get("status", "")).lower() in {"stopping", "cancelled"}:
                    cancelled_previous.append(prev_id)

            job = enqueue_job(
                process_emails_range_job,
                owner_email=owner_email,
                start_date=start_str,
                end_date=end_str,
                priority='high',
                timeout='2h'
            )
            return {
                "success": True,
                "message": (
                    "Procesamiento por rango encolado exitosamente"
                    if not cancelled_previous
                    else f"Procesamiento por rango encolado. Se cancelaron {len(cancelled_previous)} job(s) previos del mismo usuario."
                ),
                "job_id": job.id,
                "cancelled_previous_job_ids": cancelled_previous,
            }
        except Exception as e:
            logger.error(f"Error encolando /jobs/process-range en RQ: {e}")
            raise HTTPException(status_code=500, detail="No se pudo encolar el procesamiento por rango")
    else:
        # Ejecución síncrona (con precaución)
        try:
            from app.modules.email_processor.config_store import get_enabled_configs
            from app.modules.email_processor.email_processor import MultiEmailProcessor
            
            configs = get_enabled_configs(include_password=True, owner_email=owner_email) if owner_email else []
            if not configs:
                 return {"success": False, "message": "No hay cuentas de correo configuradas"}
                 
            email_configs = [MultiEmailConfig(**{**c, 'owner_email': owner_email}) for c in configs]
            mp = MultiEmailProcessor(email_configs=email_configs, owner_email=owner_email)
            
            result = mp.process_all_emails(
                start_date=s_date,
                end_date=e_date,
                force_search_criteria_all=True,
                fanout_batch_size=50,
                disable_fanout_account_cap=True
            )
            return result
        except Exception as e:
            logger.error(f"Error range sync: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/process-range/active")
async def get_active_range_job(
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)
):
    """
    Retorna el job de rango activo más reciente del usuario (si existe).
    Permite al frontend recuperar estado aunque cambie de réplica/pod.
    """
    owner_email = (user.get("email") or "").lower()
    try:
        from app.worker.queues import find_active_range_jobs
        active_jobs = find_active_range_jobs(owner_email)
        if not active_jobs:
            return {"success": True, "active": False, "job": None}
        return {"success": True, "active": True, "job": active_jobs[0]}
    except Exception as e:
        logger.error(f"Error consultando job activo de rango para {owner_email}: {e}")
        raise HTTPException(status_code=500, detail="No se pudo consultar job activo de rango")

@router.post("/job/start", response_model=JobStatus)
async def start_job(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Inicia el trabajo programado para procesar correos periódicamente.
    Requiere permisos de administrador.

    Returns:
        JobStatus: Estado del trabajo.
    """
    try:
        job_status = invoice_sync.start_scheduled_job()
        return job_status
    except Exception as e:
        logger.error(f"Error al iniciar el job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al iniciar el job: {str(e)}")

@router.post("/job/stop", response_model=JobStatus)
async def stop_job(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Detiene el trabajo programado.
    Requiere permisos de administrador.

    Returns:
        JobStatus: Estado del trabajo.
    """
    try:
        job_status = invoice_sync.stop_scheduled_job()
        return job_status
    except Exception as e:
        logger.error(f"Error al detener el job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al detener el job: {str(e)}")

@router.get("/job/status", response_model=JobStatus)
async def job_status(request: Request):
    """
    Obtiene el estado actual del trabajo programado.
    
    Returns:
        JobStatus: Estado del trabajo.
    """
    status = invoice_sync.get_job_status()

    # Compatibilidad UI: reflejar también procesamiento manual en RQ para el usuario autenticado.
    # `running` sigue representando automatización; `is_processing` incluye manual/rango.
    try:
        owner_email = ""
        token = extract_bearer_token(request)
        if token:
            claims = verify_firebase_token(token)
            owner_email = str(claims.get("email") or "").lower()

        if owner_email:
            from app.worker.queues import find_active_owner_jobs
            active_jobs = find_active_owner_jobs(
                owner_email,
                func_filters=(
                    "process_emails_range_job",
                    "process_emails_job",
                    "process_single_email_from_uid_job",
                ),
            )
            if active_jobs:
                status.is_processing = True
    except Exception as e:
        logger.warning(f"No se pudo enriquecer /job/status con jobs manuales activos: {e}")

    return status

@router.post("/job/interval", response_model=JobStatus)
async def set_job_interval(payload: IntervalPayload, admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Ajusta el intervalo (minutos) del job de automatización. Requiere permisos de administrador."""
    try:
        logger.info(f"🛠️ Ajustando intervalo de job a {payload.minutes} minutos")
        status = invoice_sync.update_job_interval(payload.minutes)
        logger.info(
            "✅ Intervalo actualizado: running=%s, interval=%s, next_run=%s, last_run=%s",
            getattr(status, 'running', False), getattr(status, 'interval_minutes', None),
            getattr(status, 'next_run', None), getattr(status, 'last_run', None)
        )
        return status
    except Exception as e:
        logger.error(f"Error al ajustar intervalo del job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al ajustar intervalo: {str(e)}")

