"""
Endpoint de estado del scheduler para el panel de administración.
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime
import logging

from app.api.deps import _get_current_admin_user
from app.modules.scheduler.task_queue import task_queue

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_scheduler_status(admin: Dict[str, Any] = Depends(_get_current_admin_user)):
    """Estado del scheduler y próximo reseteo."""
    try:
        now = datetime.utcnow()

        # Próximo reseteo: primer día del mes siguiente
        if now.month == 12:
            next_reset = datetime(now.year + 1, 1, 1)
        else:
            next_reset = datetime(now.year, now.month + 1, 1)

        # El reseteo debe correr el día 1 de cada mes
        should_run_today = now.day == 1

        # Estado del task_queue interno
        is_running = hasattr(task_queue, '_running') and task_queue._running
        jobs_count = len(getattr(task_queue, '_jobs', {}))

        return {
            "success": True,
            "data": {
                "scheduler": {
                    "running": is_running,
                    "jobs_count": jobs_count,
                },
                "next_reset_date": next_reset.isoformat(),
                "should_run_today": should_run_today,
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo estado del scheduler: {e}")
        return {
            "success": True,
            "data": {
                "scheduler": {"running": False, "jobs_count": 0},
                "next_reset_date": None,
                "should_run_today": False,
            }
        }
