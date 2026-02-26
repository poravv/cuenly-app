"""
Queue Configuration - RQ Queues para jobs de procesamiento.

Define tres colas con diferentes prioridades:
- high: Jobs urgentes (procesamiento manual)
- default: Jobs normales (procesamiento automático)
- low: Jobs de baja prioridad (limpieza, reportes)

Uso:
    from app.worker.queues import default_queue
    
    job = default_queue.enqueue(my_function, arg1, arg2)
    print(f"Job enqueued: {job.id}")
"""
import logging
from typing import Optional, Any, Dict, List
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy imports para evitar ciclos
_queues_initialized = False
_high_queue = None
_default_queue = None
_low_queue = None


def _init_queues():
    """Inicializa las colas RQ con conexión Redis."""
    global _queues_initialized, _high_queue, _default_queue, _low_queue
    
    if _queues_initialized:
        return
    
    try:
        from rq import Queue
        from app.core.redis_client import get_redis_client
        
        # RQ necesita conexión RAW para manejar datos binarios (pickle) exitosamente
        redis_conn = get_redis_client(decode_responses=False)
        
        _high_queue = Queue('high', connection=redis_conn, default_timeout='30m')
        _default_queue = Queue('default', connection=redis_conn, default_timeout='2h')
        _low_queue = Queue('low', connection=redis_conn, default_timeout='4h')
        
        _queues_initialized = True
        logger.info("✅ RQ Queues inicializadas correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando RQ Queues: {e}")
        raise


def get_queue(priority: str = 'default'):
    """
    Obtiene una cola RQ por prioridad.
    
    Args:
        priority: 'high', 'default', o 'low'
        
    Returns:
        Queue: Cola RQ correspondiente
    """
    _init_queues()
    
    queues = {
        'high': _high_queue,
        'default': _default_queue,
        'low': _low_queue
    }
    
    return queues.get(priority, _default_queue)


@property
def high_queue():
    """Cola de alta prioridad."""
    _init_queues()
    return _high_queue


@property  
def default_queue():
    """Cola de prioridad normal."""
    _init_queues()
    return _default_queue


@property
def low_queue():
    """Cola de baja prioridad."""
    _init_queues()
    return _low_queue


def enqueue_job(func, *args, priority: str = 'default', timeout: str = None, **kwargs):
    """
    Encola un job con la prioridad especificada.
    
    Args:
        func: Función a ejecutar
        *args: Argumentos posicionales para la función
        priority: 'high', 'default', o 'low'
        timeout: Timeout del job (ej: '1h', '30m')
        **kwargs: Argumentos keyword para la función
        
    Returns:
        Job: Objeto job de RQ con id y estado
    """
    queue = get_queue(priority)
    
    job_kwargs = {}
    if timeout:
        job_kwargs['job_timeout'] = timeout
    
    job = queue.enqueue(func, *args, **kwargs, **job_kwargs)
    
    logger.info(f"📥 Job encolado: {job.id} en cola '{priority}'")
    return job


def get_job_status(job_id: str) -> dict:
    """
    Obtiene el estado de un job por su ID.
    
    Args:
        job_id: ID del job
        
    Returns:
        dict: Estado del job
    """
    try:
        from rq.job import Job
        from app.core.redis_client import get_redis_client
        
        # Usar RAW para fetch de jobs (datos binarios)
        job = Job.fetch(job_id, connection=get_redis_client(decode_responses=False))
        
        # Forzar refresh y derivar estado real para evitar falsos "queued"
        # cuando el job ya terminó pero el campo status quedó desfasado.
        raw_status = str(job.get_status(refresh=True) or "").lower().strip()
        if "." in raw_status:
            raw_status = raw_status.split(".")[-1]
        if job.is_finished:
            final_status = "finished"
        elif job.is_failed:
            final_status = "failed"
        elif raw_status in {"started", "running", "busy"}:
            final_status = "started"
        elif raw_status in {"queued", "deferred", "scheduled"}:
            final_status = raw_status
        else:
            final_status = raw_status or "queued"

        return {
            "id": job.id,
            "status": final_status,
            "func_name": str(getattr(job, "func_name", "") or ""),
            "meta": dict(getattr(job, "meta", {}) or {}),
            "result": job.result if job.is_finished else None,
            "error": str(job.exc_info) if job.is_failed else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }
        
    except Exception as e:
        return {
            "id": job_id,
            "status": "not_found",
            "error": str(e)
        }


def cancel_job(job_id: str, requester_email: Optional[str] = None) -> dict:
    """
    Cancela un job RQ.

    - queued/deferred/scheduled: cancelación inmediata
    - started/running: envía comando de stop al worker
    """
    try:
        from rq.job import Job
        try:
            from rq.command import send_stop_job_command
        except Exception:
            send_stop_job_command = None
        from app.core.redis_client import get_redis_client

        conn = get_redis_client(decode_responses=False)
        job = Job.fetch(job_id, connection=conn)

        owner_email = str((job.kwargs or {}).get("owner_email", "")).strip().lower()
        if requester_email and owner_email and requester_email.strip().lower() != owner_email:
            return {
                "id": job_id,
                "cancelled": False,
                "status": "forbidden",
                "message": "No autorizado para cancelar este job",
            }

        raw_status = str(job.get_status(refresh=True) or "").lower().strip()
        if "." in raw_status:
            raw_status = raw_status.split(".")[-1]

        if job.is_finished:
            return {
                "id": job_id,
                "cancelled": False,
                "status": "finished",
                "message": "El job ya finalizó",
            }
        if job.is_failed or raw_status in {"failed", "stopped", "canceled", "cancelled"}:
            return {
                "id": job_id,
                "cancelled": False,
                "status": raw_status or "failed",
                "message": "El job ya no está en ejecución",
            }

        # Cancelación inmediata si aún está en cola
        if raw_status in {"queued", "deferred", "scheduled"}:
            job.meta["cancelled_by_user"] = True
            job.save_meta()
            job.cancel()
            return {
                "id": job_id,
                "cancelled": True,
                "status": "cancelled",
                "message": "Job cancelado en cola",
            }

        # Si está corriendo, solicitar stop al worker
        if raw_status in {"started", "running", "busy"}:
            if send_stop_job_command is None:
                return {
                    "id": job_id,
                    "cancelled": False,
                    "status": "running",
                    "message": "El worker no soporta stop remoto para jobs en ejecución",
                }
            job.meta["cancelled_by_user"] = True
            job.save_meta()
            send_stop_job_command(conn, job_id)
            return {
                "id": job_id,
                "cancelled": True,
                "status": "stopping",
                "message": "Cancelación solicitada. El proceso se detendrá en breve.",
            }

        # Fallback: intentar cancel()
        job.cancel()
        return {
            "id": job_id,
            "cancelled": True,
            "status": "cancelled",
            "message": "Job cancelado",
        }
    except Exception as e:
        return {
            "id": job_id,
            "cancelled": False,
            "status": "error",
            "message": str(e),
        }


def get_queue_stats() -> dict:
    """
    Obtiene estadísticas de todas las colas.
    
    Returns:
        dict: Estadísticas por cola
    """
    _init_queues()
    
    return {
        "high": {
            "name": "high",
            "count": len(_high_queue) if _high_queue else 0,
        },
        "default": {
            "name": "default", 
            "count": len(_default_queue) if _default_queue else 0,
        },
        "low": {
            "name": "low",
            "count": len(_low_queue) if _low_queue else 0,
        }
    }


def _iter_active_jobs(queue_names: tuple[str, ...] = ("high", "default", "low")) -> List[Dict[str, Any]]:
    """
    Recorre jobs activos (queued/started/deferred/scheduled) en Redis para todas las colas.
    """
    try:
        from rq import Queue
        from rq.job import Job
        from rq.registry import StartedJobRegistry, DeferredJobRegistry, ScheduledJobRegistry
        from app.core.redis_client import get_redis_client

        conn = get_redis_client(decode_responses=False)
        seen: set[str] = set()
        jobs: List[Dict[str, Any]] = []

        for qname in queue_names:
            q = Queue(qname, connection=conn)
            candidate_ids: List[str] = []
            candidate_ids.extend(q.job_ids or [])
            # En RQ 2.x el parámetro `queue` debe ser un objeto Queue, no el nombre str.
            # Pasar el nombre como string provoca: "'str' object has no attribute 'name'".
            candidate_ids.extend(StartedJobRegistry(queue=q, connection=conn).get_job_ids() or [])
            candidate_ids.extend(DeferredJobRegistry(queue=q, connection=conn).get_job_ids() or [])
            candidate_ids.extend(ScheduledJobRegistry(queue=q, connection=conn).get_job_ids() or [])

            for jid in candidate_ids:
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                try:
                    job = Job.fetch(jid, connection=conn)
                    status = str(job.get_status(refresh=True) or "").lower().strip()
                    if "." in status:
                        status = status.split(".")[-1]
                    if status in {"finished", "failed", "stopped", "canceled", "cancelled"}:
                        continue
                    jobs.append(
                        {
                            "id": job.id,
                            "status": status or "queued",
                            "origin": str(getattr(job, "origin", "") or qname),
                            "func_name": str(getattr(job, "func_name", "") or ""),
                            "kwargs": dict(getattr(job, "kwargs", {}) or {}),
                            "args": list(getattr(job, "args", ()) or ()),
                            "created_at": job.created_at.isoformat() if job.created_at else None,
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                        }
                    )
                except Exception:
                    continue

        return jobs
    except Exception as e:
        logger.error(f"❌ Error listando jobs activos RQ: {e}")
        return []


def _extract_owner_email_from_active_job(item: Dict[str, Any]) -> str:
    kwargs = item.get("kwargs") or {}
    owner = str(kwargs.get("owner_email", "")).strip().lower()
    if owner:
        return owner

    func_name = str(item.get("func_name", "")).strip()
    args = item.get("args") or []

    # process_single_email_from_uid_job(email_address, owner_email, email_uid, ...)
    if "process_single_email_from_uid_job" in func_name and len(args) >= 2:
        return str(args[1] or "").strip().lower()

    # process_emails_range_job(owner_email, ...)
    if "process_emails_range_job" in func_name and len(args) >= 1:
        return str(args[0] or "").strip().lower()

    # process_emails_job(owner_email, ...)
    if "process_emails_job" in func_name and len(args) >= 1:
        return str(args[0] or "").strip().lower()

    # process_single_account_job(email_address, owner_email, ...)
    if "process_single_account_job" in func_name and len(args) >= 2:
        return str(args[1] or "").strip().lower()

    return ""


def find_active_owner_jobs(
    owner_email: str,
    func_filters: Optional[tuple[str, ...]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna jobs activos del owner_email (queued/started/deferred/scheduled).

    - `func_filters`: tupla opcional de substrings de func_name para filtrar.
      Ej: ("process_emails_range_job", "process_emails_job")
    """
    target_owner = str(owner_email or "").strip().lower()
    if not target_owner:
        return []

    active_jobs = _iter_active_jobs()
    result: List[Dict[str, Any]] = []
    for item in active_jobs:
        item_owner = _extract_owner_email_from_active_job(item)
        if item_owner != target_owner:
            continue

        func_name = str(item.get("func_name", "")).strip()
        if func_filters and not any(f in func_name for f in func_filters):
            continue

        result.append(item)

    result.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return result


def find_active_range_jobs(owner_email: str) -> List[Dict[str, Any]]:
    """
    Retorna jobs activos de `process_emails_range_job` para un owner_email.
    """
    return find_active_owner_jobs(
        owner_email,
        func_filters=("process_emails_range_job",),
    )


def cancel_active_owner_jobs(
    owner_email: str,
    func_filters: Optional[tuple[str, ...]] = None,
    max_jobs: int = 500,
) -> Dict[str, Any]:
    """
    Cancela en bloque jobs activos de un owner_email.

    Retorna un resumen con conteos y IDs afectados.
    """
    target_owner = str(owner_email or "").strip().lower()
    if not target_owner:
        return {
            "owner_email": "",
            "total_found": 0,
            "attempted": 0,
            "cancelled": 0,
            "stopping": 0,
            "failed": 0,
            "cancelled_job_ids": [],
            "stopping_job_ids": [],
            "failed_jobs": [],
        }

    safe_max = max(1, min(int(max_jobs or 500), 2000))
    active_jobs = find_active_owner_jobs(target_owner, func_filters=func_filters)
    selected_jobs = active_jobs[:safe_max]

    cancelled_job_ids: List[str] = []
    stopping_job_ids: List[str] = []
    failed_jobs: List[Dict[str, Any]] = []

    for item in selected_jobs:
        job_id = str(item.get("id") or "").strip()
        if not job_id:
            continue

        result = cancel_job(job_id, requester_email=target_owner)
        status = str(result.get("status", "")).lower().strip()
        was_cancelled = bool(result.get("cancelled"))

        if was_cancelled and status == "stopping":
            stopping_job_ids.append(job_id)
            continue
        if was_cancelled:
            cancelled_job_ids.append(job_id)
            continue

        failed_jobs.append(
            {
                "id": job_id,
                "status": status or "unknown",
                "message": str(result.get("message") or ""),
            }
        )

    return {
        "owner_email": target_owner,
        "total_found": len(active_jobs),
        "attempted": len(selected_jobs),
        "cancelled": len(cancelled_job_ids),
        "stopping": len(stopping_job_ids),
        "failed": len(failed_jobs),
        "cancelled_job_ids": cancelled_job_ids,
        "stopping_job_ids": stopping_job_ids,
        "failed_jobs": failed_jobs,
    }
