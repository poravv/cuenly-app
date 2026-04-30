"""
Endpoints de sistema: health checks, cache, métricas, logs y observabilidad.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.api.deps import _get_current_user, _get_current_admin
from app.config.settings import settings
from app.repositories.user_repository import UserRepository
from app.utils.observability import observability_logger

router = APIRouter()
logger = logging.getLogger(__name__)


from app.api.state import invoice_sync


@router.get("/health")
async def health_check():
    """
    Health check endpoint for container health checks.
    Verifica que la aplicación esté lista para recibir requests.
    
    Returns:
        dict: Simple health status.
    """
    try:
        # Verificación básica de que la aplicación está funcionando
        current_time = datetime.now().isoformat()
        
        # Verificar que el invoice_sync esté inicializado
        if not invoice_sync:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "invoice_sync not initialized", "timestamp": current_time}
            )
        
        # Verificación simple de conectividad MongoDB (opcional, sin bloquear)
        try:
            from app.repositories.user_repository import UserRepository
            # Test rápido de conexión (timeout muy corto)
            UserRepository()._get_collection().find_one({}, {"_id": 1})
        except Exception:
            # No fallar health check por MongoDB temporalmente no disponible
            pass
        
        return {"status": "healthy", "timestamp": current_time}
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": str(e), "timestamp": datetime.now().isoformat()}
        )

@router.get("/email-processing/config")
async def get_email_processing_config(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene la configuración actual de procesamiento de emails.
    """
    from app.config.settings import settings
    
    return {
        "process_all_dates": settings.EMAIL_PROCESS_ALL_DATES,
        "description": "Si es true, procesa todos los correos sin restricción de fecha. Si es false, solo procesa desde fecha de alta del usuario.",
        "current_setting": "Procesando TODOS los correos" if settings.EMAIL_PROCESS_ALL_DATES else "Procesando solo desde fecha de alta"
    }

@router.get("/status")
async def get_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene el estado actual del sistema.
    
    Returns:
        dict: Estado del sistema.
    """
    try:
        # Excel deshabilitado: valores fijos
        excel_files = []
        excel_exists = False
        last_modified = None

        # Estado del job (automatización) + actividad manual en RQ para este usuario
        job_status = invoice_sync.get_job_status()
        owner_email = (user.get('email') or '').lower()
        manual_active_jobs = []
        try:
            from app.worker.queues import find_active_owner_jobs
            manual_active_jobs = find_active_owner_jobs(
                owner_email,
                func_filters=(
                    "process_emails_range_job",
                    "process_emails_job",
                    "process_single_email_from_uid_job",
                ),
            )
        except Exception as e:
            logger.warning(f"No se pudieron consultar jobs manuales activos para {owner_email}: {e}")
        
        # Configuraciones de correo (desde MongoDB)
        try:
            email_configs = db_list_configs(include_password=False, owner_email=(user.get('email') or '').lower())
        except Exception as _e:
            logger.warning(f"No se pudieron obtener configuraciones de correo desde MongoDB: {_e}")
            email_configs = []
        
        status_info = {
            "status": "active",
            "excel_files_count": 0,
            "excel_exists": False,
            "last_modified": None,
            "temp_dir": settings.TEMP_PDF_DIR,
            "email_configs_count": len(email_configs),
            "email_configured": len([c for c in email_configs if c.get('username')]) > 0,
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "job": {
                "running": job_status.running,
                "is_processing": bool(job_status.is_processing or manual_active_jobs),
                "interval_minutes": job_status.interval_minutes,
                "next_run": job_status.next_run,
                "last_run": job_status.last_run
            },
            "excel_files": []
        }
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error al obtener estado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estado: {str(e)}")

# -----------------------------
# V2 Invoices (headers + items)
# -----------------------------

@router.get("/cache/stats")
async def cache_stats(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Obtiene estadísticas del cache de OpenAI.
    Requiere permisos de administrador.

    Returns:
        dict: Estadísticas del cache.
    """
    try:
        if hasattr(invoice_sync.openai_processor, 'cache') and invoice_sync.openai_processor.cache:
            stats = invoice_sync.openai_processor.cache.get_cache_stats()
            return {
                "cache_enabled": True,
                **stats
            }
        else:
            return {"cache_enabled": False, "message": "Cache no habilitado"}
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas del cache: {str(e)}")

@router.post("/debug/fix-user-trial-status")
async def debug_fix_user_trial_status(user_email: str, admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Endpoint de debugging para corregir manualmente el estado de trial de un usuario"""
    try:
        from app.repositories.user_repository import UserRepository
        from app.repositories.subscription_repository import SubscriptionRepository
        
        user_repo = UserRepository()
        sub_repo = SubscriptionRepository()
        
        # Verificar si tiene suscripción activa
        active_subscription = await sub_repo.get_user_active_subscription(user_email.lower())
        
        if active_subscription:
            # Forzar actualización del estado del usuario
            update_result = await sub_repo.update_user_plan_status(
                user_email.lower(),
                active_subscription.get("plan_features", {})
            )
            
            return {
                "success": True,
                "message": f"Estado de trial corregido para {user_email}",
                "update_result": update_result,
                "active_subscription": active_subscription.get("plan_name")
            }
        else:
            return {
                "success": False,
                "message": f"No hay suscripción activa para {user_email}"
            }
            
    except Exception as e:
        logger.error(f"Error corrigiendo estado de trial para {user_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_cache(older_than_hours: Optional[int] = None, admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Limpia el cache de OpenAI.
    Requiere permisos de administrador.

    Args:
        older_than_hours: Si se especifica, elimina solo cache más viejo que X horas

    Returns:
        dict: Resultado de la limpieza.
    """
    try:
        if hasattr(invoice_sync.openai_processor, 'cache') and invoice_sync.openai_processor.cache:
            files_removed = invoice_sync.openai_processor.cache.clear_cache(older_than_hours)
            return {
                "success": True,
                "files_removed": files_removed,
                "message": f"Cache limpiado: {files_removed} archivos eliminados"
            }
        else:
            return {"success": False, "message": "Cache no habilitado"}
    except Exception as e:
        logger.error(f"Error limpiando cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error limpiando cache: {str(e)}")

@router.get("/imap/pool/stats")
async def imap_pool_stats(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Obtiene estadísticas del pool de conexiones IMAP.
    Requiere permisos de administrador.

    Returns:
        dict: Estadísticas del pool de conexiones.
    """
    try:
        from app.modules.email_processor.connection_pool import get_imap_pool
        pool = get_imap_pool()
        stats = pool.get_pool_stats()
        
        return {
            "pool_enabled": True,
            "configurations": stats,
            "total_pools": len(stats)
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del pool IMAP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas del pool: {str(e)}")

@router.get("/health/detailed")
async def detailed_health(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Health check comprensivo con métricas detalladas de todos los componentes.
    Requiere permisos de administrador.

    Returns:
        dict: Estado detallado del sistema con métricas de performance.
    """
    try:
        from app.modules.monitoring import get_health_checker
        health_checker = get_health_checker()
        health_report = await health_checker.comprehensive_health_check()
        
        return health_report
    except Exception as e:
        logger.error(f"Error en health check detallado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en health check: {str(e)}")

@router.get("/health/redis")
async def redis_health(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Health check específico para Redis.
    Requiere permisos de administrador.

    Returns:
        dict: Estado de conexión Redis y estadísticas de cache.
    """
    try:
        from app.core.redis_client import redis_health_check
        from app.modules.openai_processor.redis_cache import get_openai_cache
        
        redis_status = redis_health_check()
        
        # Obtener stats del cache si está disponible
        cache_stats = {}
        try:
            cache = get_openai_cache()
            cache_stats = cache.stats()
        except Exception:
            cache_stats = {"available": False}
        
        return {
            "redis": redis_status,
            "openai_cache": cache_stats
        }
    except Exception as e:
        logger.error(f"Error en Redis health check: {str(e)}")
        return {
            "redis": {"healthy": False, "message": str(e)},
            "openai_cache": {"available": False}
        }


@router.get("/health/trends")
async def health_trends(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Obtiene tendencias de salud del sistema basadas en histórico.
    Requiere permisos de administrador.

    Returns:
        dict: Tendencias y métricas históricas.
    """
    try:
        from app.modules.monitoring import get_health_checker
        health_checker = get_health_checker()
        trends = health_checker.get_health_trends()
        
        return trends
    except Exception as e:
        logger.error(f"Error obteniendo tendencias de salud: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo tendencias: {str(e)}")

@router.post("/system/force-restart")
async def force_system_restart(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Endpoint de emergencia para forzar reinicio del sistema cuando hay bloqueos.
    Requiere permisos de administrador.

    Returns:
        dict: Confirmación de reinicio.
    """
    global invoice_sync
    
    try:
        logger.warning("🚨 REINICIO DE EMERGENCIA SOLICITADO - Forzando limpieza del sistema")
        
        # Detener job programado si está corriendo
        try:
            invoice_sync.stop_scheduled_job()
            logger.info("✅ Job programado detenido")
        except Exception as e:
            logger.warning(f"⚠️ Error deteniendo job: {e}")
        
        # Limpiar tareas pendientes
        try:
            task_queue.cleanup_old_tasks()
            logger.info("✅ Tareas limpiadas")
        except Exception as e:
            logger.warning(f"⚠️ Error limpiando tareas: {e}")
        
        # Liberar lock de procesamiento
        try:
            if PROCESSING_LOCK.locked():
                PROCESSING_LOCK.release()
                logger.info("✅ Processing lock liberado")
        except Exception as e:
            logger.warning(f"⚠️ Error liberando lock: {e}")
        
        # Reinicializar invoice_sync
        try:
            invoice_sync = CuenlyApp()
            logger.info("✅ CuenlyApp reinicializado")
        except Exception as e:
            logger.warning(f"⚠️ Error reinicializando CuenlyApp: {e}")
        
        return {
            "success": True,
            "message": "Sistema reiniciado exitosamente",
            "timestamp": datetime.now().isoformat(),
            "actions": [
                "Job programado detenido",
                "Tareas limpiadas", 
                "Processing lock liberado",
                "CuenlyApp reinicializado"
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error en reinicio de emergencia: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en reinicio: {str(e)}")

@router.get("/system/health")
async def get_system_health(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """
    Endpoint de salud del sistema con información detallada.
    Requiere permisos de administrador.

    Returns:
        dict: Estado de salud del sistema.
    """
    try:
        import psutil
        import threading
        
        # Información básica del sistema
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": time.time() - getattr(app.state, 'start_time', time.time()),
            
            # Estado de threads
            "active_threads": threading.active_count(),
            "thread_names": [t.name for t in threading.enumerate()],
            
            # Estado de procesamiento
            "processing_lock_acquired": PROCESSING_LOCK.locked(),
            "pending_tasks": task_queue.get_pending_tasks_count(),
            
            # Job programado
            "scheduled_job_running": invoice_sync.get_job_status().get("running", False),
            
            # Memoria y CPU
            "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
            "cpu_percent": psutil.Process().cpu_percent(),
        }
        
        # Determinar estado general
        if health_info["active_threads"] > 20:
            health_info["status"] = "warning"
            health_info["warning"] = "Alto número de threads activos"
        elif health_info["memory_usage_mb"] > 500:
            health_info["status"] = "warning"  
            health_info["warning"] = "Alto uso de memoria"
        elif health_info["processing_lock_acquired"] and health_info["pending_tasks"] == 0:
            health_info["status"] = "warning"
            health_info["warning"] = "Processing lock adquirido sin tareas pendientes"
            
        return health_info
        
    except Exception as e:
        logger.error(f"Error obteniendo salud del sistema: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# -----------------------------
# Admin Endpoints
# -----------------------------

class UpdateUserRoleRequest(BaseModel):
    role: str  # 'admin' o 'user'

class UpdateUserStatusRequest(BaseModel):
    status: str  # 'active' o 'suspended'

@router.post("/logs/frontend")
async def receive_frontend_logs(
    payload: FrontendLogsPayload,
    user: Dict[str, Any] = Depends(_get_current_user),
    _frontend_key: bool = Depends(validate_frontend_key)
):
    """
    Recibe logs del frontend para centralizar observabilidad
    """
    try:
        user_email = user.get('email', '') if user else ''
        
        for log_entry in payload.logs:
            # Enriquecer con información del usuario autenticado
            if user_email and not log_entry.user_email:
                log_entry.user_email = user_email
            
            # Log en el sistema centralizado
            observability_logger.logger.log(
                getattr(logging, log_entry.level, logging.INFO),
                f"Frontend: {log_entry.message}",
                extra={
                    'event_type': 'frontend_log',
                    'frontend_component': log_entry.component,
                    'frontend_url': log_entry.url,
                    'frontend_user_agent': log_entry.user_agent,
                    'frontend_request_id': log_entry.request_id,
                    'frontend_event_type': log_entry.event_type,
                    'frontend_extra_data': log_entry.extra_data,
                    'frontend_stack_trace': log_entry.stack_trace,
                    'user_email': log_entry.user_email or user_email,
                    'original_timestamp': log_entry.timestamp
                }
            )
        
        return {"success": True, "logs_received": len(payload.logs)}
        
    except Exception as e:
        logger.error(f"Error procesando logs frontend: {e}")
        raise HTTPException(status_code=500, detail="Error procesando logs")

# ================================
# MÉTRICAS PROMETHEUS
# ================================

@router.get("/metrics")
async def prometheus_metrics():
    """
    Endpoint para métricas de Prometheus
    """
    try:
        from app.utils.metrics import metrics_collector
        
        # Obtener métricas en formato Prometheus
        metrics_output = metrics_collector.get_metrics_output()
        
        # Retornar con el content-type correcto
        return Response(
            content=metrics_output,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Error generando métricas Prometheus: {e}")
        # Retornar respuesta vacía en caso de error para no romper Prometheus
        return Response(
            content="",
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )

