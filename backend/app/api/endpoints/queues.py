from fastapi import APIRouter, Depends, HTTPException
import logging
from typing import Dict, Any

from app.api.deps import _get_current_admin_user
from app.worker.queues import get_queue

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats")
async def get_queue_stats(admin: Dict[str, Any] = Depends(_get_current_admin_user)):
    """
    Obtiene métricas de las colas de mensajería (RQ), 
    como cantidad de mensajes encolados y fallidos por tipo.
    """
    try:
        from rq.registry import FailedJobRegistry, StartedJobRegistry
        from rq import Worker
        
        queue_names = ['high', 'default', 'low']
        stats = {}
        total_workers = 0
        
        try:
            # Tratamos de obtener la cantidad de workers desde la conexión compartida
            # Ocupamos la conexión de la cola 'default' como base
            base_q = get_queue('default')
            workers = Worker.all(connection=base_q.connection)
            total_workers = len(workers)
        except Exception as e:
            logger.warning(f"No se pudieron cargar los workers de RQ: {e}")
            
        for q_name in queue_names:
            q = get_queue(q_name)
            failed_registry = FailedJobRegistry(queue=q)
            started_registry = StartedJobRegistry(queue=q)
            
            stats[q_name] = {
                "queued": len(q),
                "started": len(started_registry),
                "failed": len(failed_registry)
            }
            
        return {
            "success": True,
            "workers_online": total_workers,
            "queues": stats
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de colas RQ: {e}")
        raise HTTPException(status_code=500, detail="Error de conexión con RQ/Redis")
