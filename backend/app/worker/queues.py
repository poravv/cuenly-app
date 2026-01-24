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
from typing import Optional
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
        
        redis_conn = get_redis_client()
        
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
        
        job = Job.fetch(job_id, connection=get_redis_client())
        
        return {
            "id": job.id,
            "status": job.get_status(),
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
