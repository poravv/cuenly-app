from app.api.endpoints import pagopar, admin_subscriptions, subscriptions, admin_users, admin_plans, user_profile
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File, Form, Query, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import uvicorn
import uuid
import time
from typing import List, Optional, Dict, Any
import shutil
from datetime import datetime

# Importar validadores de seguridad
from app.utils.validators import SecurityValidators, DataValidators, ValidationError, log_security_event
from fastapi.responses import FileResponse
from fastapi import Response
from pydantic import BaseModel

from app.config.settings import settings
from app.utils.firebase_auth import verify_firebase_token, extract_bearer_token
from app.utils.trial_middleware import check_trial_limits_optional, check_trial_limits, check_ai_limits
from app.utils.security import validate_frontend_key
from app.repositories.user_repository import UserRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.models.models import InvoiceData, EmailConfig, ProcessResult, JobStatus, MultiEmailConfig, ProductoFactura, EmailConfigUpdate
from app.main import CuenlyApp
from app.modules.scheduler.processing_lock import PROCESSING_LOCK
from app.modules.scheduler.task_queue import task_queue
from app.modules.email_processor.storage import save_binary
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.repositories.user_repository import UserRepository
from app.modules.mapping.invoice_mapping import map_invoice
from app.modules.mongo_query_service import get_mongo_query_service
from app.modules.email_processor.config_store import (
    list_configs as db_list_configs,
    create_config as db_create_config,
    update_config as db_update_config,
    delete_config as db_delete_config,
    set_enabled as db_set_enabled,
    toggle_enabled as db_toggle_enabled,
    get_by_id as db_get_by_id,
    get_by_username as db_get_by_username,
)
from app.utils.observability import observability_logger
from app.middleware.observability_middleware import ObservabilityMiddleware, BusinessEventLogger

# Configurar logging mejorado para observabilidad
observability_logger.setup_logging(level=settings.LOG_LEVEL)

# Configurar logging tradicional para compatibilidad
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cuenlyapp_api.log")
    ]
)

logger = logging.getLogger(__name__)

# Crear la aplicación FastAPI
app = FastAPI(
    title="CuenlyApp API",
    description="API para procesar facturas desde correo electrónico y almacenarlas en MongoDB",
    version="2.0.0"
)

# Configurar middleware de observabilidad
app.add_middleware(ObservabilityMiddleware)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.cuenly.com",
        "http://localhost:4200", 
        "http://localhost",
        "http://127.0.0.1"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# API Routers - Módulos Refactorizados
# =========================================
app.include_router(pagopar.router, prefix="/pagopar", tags=["Pagopar"])
app.include_router(admin_subscriptions.router, prefix="/admin/subscriptions", tags=["Admin Subscriptions"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
app.include_router(admin_users.router, prefix="/admin/users", tags=["Admin Users"])
app.include_router(admin_plans.router, prefix="/admin/plans", tags=["Admin Plans"])
app.include_router(user_profile.router, prefix="/user", tags=["User Profile"])


# Startup event para inicializar servicios
@app.on_event("startup")
async def startup_event():
    """Inicializa servicios cuando arranca el servidor FastAPI"""
    try:
        from app.modules.scheduler import ScheduledTasks
        scheduler_tasks = ScheduledTasks()
        scheduler_tasks.start_background_scheduler()
        logger.info("✅ Scheduler de límites IA iniciado correctamente")
    except Exception as e:
        logger.error(f"❌ Error iniciando scheduler de límites IA: {e}")

    try:
        from app.modules.scheduler.async_jobs import async_job_manager
        from app.modules.scheduler.job_handlers import handle_full_sync_job, handle_retry_skipped_job
        
        async_job_manager.register_handler("full_sync", handle_full_sync_job)
        async_job_manager.register_handler("retry_skipped", handle_retry_skipped_job)
        async_job_manager.start_worker()
        logger.info("✅ AsyncJobWorker iniciado correctamente")
    except Exception as e:
        logger.error(f"❌ Error iniciando AsyncJobWorker: {e}")

# Instancia global del procesador
invoice_sync = CuenlyApp()

# Payloads
class IntervalPayload(BaseModel):
    minutes: int

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

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    ruc: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    document_type: Optional[str] = "CI" # CI, RUC, PASSPORT

class ProfileStatusResponse(BaseModel):
    is_complete: bool
    missing_fields: List[str]
    required_for_subscription: bool

class ProcessRangeRequest(BaseModel):
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    run_async: bool = True


from app.api.deps import (
    _get_current_user, 
    _get_current_user_with_trial_info,
    _get_current_user_with_trial_check,
    _get_current_user_with_ai_check,
    _get_current_admin
)

# Tarea en segundo plano para procesar correos
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
        
        configs = get_enabled_configs(include_password=True, owner_email=user_email) if user_email else []
        if not configs:
            logger.warning(f"ProcessRange: Sin configs para {user_email}")
            return

        email_configs = []
        for c in configs:
            config_data = dict(c)
            config_data['owner_email'] = user_email
            email_configs.append(MultiEmailConfig(**config_data))
            
        mp = MultiEmailProcessor(email_configs=email_configs, owner_email=user_email)
        logger.info(f"🚀 Iniciando job por rango para {user_email}: {start_date} - {end_date}")
        mp.process_all_emails(start_date=start_date, end_date=end_date)
        
    except Exception as e:
        logger.error(f"❌ Error en process_emails_range_task para {user_email}: {e}")

@app.get("/")
async def root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"message": "CuenlyApp API está en funcionamiento"}

@app.get("/user/profile")
@app.get("/api/user/profile")  # Alias para compatibilidad con proxy
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
        # Fallback para el usuario principal si la DB falla
        is_admin = user.get('email') == 'andyvercha@gmail.com'
    
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

@app.put("/user/profile")
@app.put("/api/user/profile") # Alias
async def update_user_profile(
    profile_data_update: UserProfileUpdate,  # Renombrado para evitar conflicto nombre
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

@app.get("/user/profile/status", response_model=ProfileStatusResponse)
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

@app.get("/user/trial-status")
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

class UpdateProcessingStartDatePayload(BaseModel):
    start_date: Optional[str] = None  # ISO format date, si es None usa fecha actual

@app.post("/user/email-processing-start-date")
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
        from datetime import datetime
        
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

@app.get("/debug/user-info")
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
            "database_error": str(e)
        }

@app.post("/process", response_model=ProcessResult)
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

@app.post("/process-direct")
async def process_emails_direct(
    limit: Optional[int] = 10,
    # USA _get_current_user_with_trial_check para permitir que llegue al procesador
    # y allí se aplique la lógica "XML allowed"
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check),
    request: Request = None,
    _frontend_key: bool = Depends(validate_frontend_key)
):
    """Procesa correos directamente con límite (máximo 10 para procesamiento manual)."""
    try:
        # Validar límite
        if limit is None or limit <= 0:
            limit = 10
        if limit > 50:  # Límite máximo de seguridad
            limit = 50
            
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
        result = mp.process_limited_emails(limit=limit)
        
        if result and hasattr(result, 'success') and result.success:
            return {
                "success": True,
                "message": result.message,
                "invoice_count": getattr(result, 'invoice_count', 0),
                "limit_used": limit
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

@app.post("/tasks/process")
async def enqueue_process_emails(
    user: Dict[str, Any] = Depends(_get_current_user_with_ai_check),
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
    
    def _runner():
        from app.modules.email_processor.config_store import get_enabled_configs
        from app.modules.email_processor.email_processor import MultiEmailProcessor
        owner_email = (user.get('email') or '').lower()
        configs = get_enabled_configs(include_password=True, owner_email=owner_email) if owner_email else []
        
        # Crear configs con owner_email agregado
        email_configs = []
        for c in configs:
            config_data = dict(c)
            config_data['owner_email'] = owner_email
            email_configs.append(MultiEmailConfig(**config_data))
            
        mp = MultiEmailProcessor(email_configs=email_configs, owner_email=owner_email)
        return mp.process_all_emails()

    job_id = task_queue.enqueue("process_emails", _runner)
    return {"job_id": job_id}

@app.get("/tasks/{job_id}")
async def get_task_status(job_id: str):
    """Consulta el estado de un job enviado a la cola."""
    job = task_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job

@app.delete("/tasks/cleanup")
async def cleanup_old_tasks():
    """Limpia tareas antiguas que están atoradas."""
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

@app.get("/tasks/debug")
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

@app.post("/jobs/full-sync")
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

@app.post("/jobs/retry-skipped")
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

@app.post("/jobs/process-range")
async def process_range_job(
    payload: ProcessRangeRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)
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
        background_tasks.add_task(process_emails_range_task, owner_email, s_date, e_date)
        return {"success": True, "message": "Procesamiento por rango iniciado en segundo plano"}
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
            
            result = mp.process_all_emails(start_date=s_date, end_date=e_date)
            return result
        except Exception as e:
            logger.error(f"Error range sync: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload", response_model=ProcessResult)
async def upload_pdf(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)):  # PDFs usan IA
    """
    Sube un archivo PDF para procesarlo directamente.
    
    Args:
        file: Archivo PDF a procesar.
        sender: Remitente (opcional).
        date: Fecha del documento (opcional).
        
    Returns:
        ProcessResult: Resultado del procesamiento.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    try:
        # Leer contenido
        content = await file.read()
        
        # Guardar binario (Local + MinIO)
        owner = (user.get('email') or '').lower()
        storage_result = await run_in_threadpool(
            save_binary,
            content=content, 
            filename=file.filename, 
            force_pdf=True,
            owner_email=owner
        )
        pdf_path = storage_result.local_path
        minio_key = storage_result.minio_key

        # Preparar metadatos
        email_meta = {
            "sender": sender or "Carga manual",
        }

        # Convertir fecha si se proporciona
        if date:
            try:
                email_meta["date"] = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                logger.warning(f"Formato de fecha incorrecto: {date}")

        # Extraer + guardar en esquema v2 (invoice_headers/items)
        def _process_sync():
            with PROCESSING_LOCK:
                owner = (user.get('email') or '').lower()
                invoice_data = invoice_sync.openai_processor.extract_invoice_data(pdf_path, email_meta, owner_email=owner)
                invoices = [invoice_data] if invoice_data else []
                if invoices:
                    try:
                        repo = MongoInvoiceRepository()
                        owner = (user.get('email') or '').lower()
                        doc = map_invoice(invoice_data, fuente="OPENAI_VISION", minio_key=minio_key)
                        if owner:
                            try:
                                doc.header.owner_email = owner
                                for it in doc.items:
                                    it.owner_email = owner
                            except Exception:
                                pass
                        repo.save_document(doc)
                    except Exception as e:
                        logger.error(f"❌ Error persistiendo v2 (upload PDF): {e}")
                return invoices

        # Ejecutar en threadpool para no bloquear el event loop
        invoices = await run_in_threadpool(_process_sync)

        if not invoices:
            return ProcessResult(
                success=False,
                message="No se pudo extraer factura del PDF",
                invoice_count=0,
                invoices=[]
            )

        return ProcessResult(
            success=True,
            message=f"Factura procesada y almacenada",
            invoice_count=1,
            invoices=invoices
        )
        
    except Exception as e:
        logger.error(f"Error al procesar el archivo: {str(e)}")
        return ProcessResult(
            success=False,
            message=f"Error al procesar el archivo: {str(e)}"
        )

@app.post("/upload-xml", response_model=ProcessResult)
async def upload_xml(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)):
    """
    Sube un archivo XML SIFEN para procesarlo directamente con el parser nativo (fallback OpenAI).
    """
    if not (file.filename.lower().endswith('.xml')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML")

    try:
        # Leer contenido
        content = await file.read()
        
        # Guardar binario (Local + MinIO)
        owner = (user.get('email') or '').lower()
        storage_result = await run_in_threadpool(
            save_binary,
            content=content, 
            filename=file.filename, 
            force_pdf=False,
            owner_email=owner
        )
        xml_path = storage_result.local_path
        minio_key = storage_result.minio_key

        # Metadatos opcionales
        email_meta = {
            "sender": sender or "Carga manual",
        }
        if date:
            try:
                email_meta["date"] = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                logger.warning(f"Formato de fecha incorrecto: {date}")

        def _process_sync():
            with PROCESSING_LOCK:
                # Procesar XML y almacenar en esquema v2
                owner = (user.get('email') or '').lower()
                invoice_data = invoice_sync.openai_processor.extract_invoice_data_from_xml(xml_path, email_meta, owner_email=owner)
                invoices = [invoice_data] if invoice_data else []
                if invoices:
                    try:
                        repo = MongoInvoiceRepository()
                        doc = map_invoice(invoice_data, fuente="XML_NATIVO" if getattr(invoice_data, 'cdc', '') else "OPENAI_VISION", minio_key=minio_key)
                        if owner:
                            try:
                                doc.header.owner_email = owner
                                for it in doc.items:
                                    it.owner_email = owner
                            except Exception:
                                pass
                        repo.save_document(doc)
                    except Exception as e:
                        logger.error(f"❌ Error persistiendo v2 (upload XML): {e}")
                return invoices

        # Ejecutar en threadpool
        invoices = await run_in_threadpool(_process_sync)

        if not invoices:
            return ProcessResult(
                success=False,
                message="No se pudo extraer información desde el XML",
                invoice_count=0,
                invoices=[]
            )

        return ProcessResult(
            success=True,
            message=f"Factura XML procesada y almacenada",
            invoice_count=1,
            invoices=invoices
        )

    except Exception as e:
        logger.error(f"Error al procesar el XML: {str(e)}")
        return ProcessResult(
            success=False,
            message=f"Error al procesar el XML: {str(e)}"
        )

@app.post("/tasks/upload-pdf")
async def enqueue_upload_pdf(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)):  # PDFs usan IA
    """Encola el procesamiento de un PDF manual y retorna job_id."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    try:
        file_bytes = await file.read()
        # Parsear fecha
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                pass
                
        # Usar save_binary modernizado
        owner_email = (user.get('email') or '').lower()
        pdf_storage = save_binary(
            file_bytes, 
            file.filename, 
            force_pdf=True,
            owner_email=owner_email,
            date_obj=date_obj
        )
        pdf_path = pdf_storage.local_path
        pdf_minio_key = pdf_storage.minio_key
        
        email_meta = {"sender": sender or "Carga manual"}
        if date_obj:
            email_meta["date"] = date_obj

        def _runner():
            owner = (user.get('email') or '').lower()
            inv = invoice_sync.openai_processor.extract_invoice_data(pdf_path, email_meta, owner_email=owner)
            invoices = [inv] if inv else []
            if invoices:
                # Asignar minio_key
                if pdf_minio_key and inv:
                    inv.minio_key = pdf_minio_key
                    
                try:
                    repo = MongoInvoiceRepository()
                    owner = (user.get('email') or '').lower()
                    doc = map_invoice(inv, fuente="OPENAI_VISION")
                    if owner:
                        try:
                            doc.header.owner_email = owner
                            for it in doc.items:
                                it.owner_email = owner
                        except Exception:
                            pass
                    repo.save_document(doc)
                except Exception as e:
                    logger.error(f"❌ Error persistiendo v2 (upload PDF): {e}")

            if not invoices:
                return ProcessResult(success=False, message="No se pudo extraer información del PDF")
            return ProcessResult(success=True, message="PDF procesado correctamente", invoice_count=1, invoices=invoices)

        job_id = task_queue.enqueue("process_pdf_manual", _runner)
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Error encolando PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-image", response_model=Dict[str, str])
async def upload_image(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)):
    """
    Sube una imagen (JPG/PNG) para procesarla como factura (vía IA).
    AHORA ASÍNCRONO: Retorna job_id.
    """
    allowed_exts = ('.jpg', '.jpeg', '.png', '.webp')
    if not (file.filename.lower().endswith(allowed_exts)):
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes (JPG, PNG, WEBP)")
    
    try:
        # Parsear fecha
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                pass
                
        # Guardar archivo usando save_binary (soporta MinIO + Optimización)
        file_bytes = await file.read()
        owner_email = (user.get('email') or '').lower()
        
        # Ejecutar save_binary en threadpool para no bloquear por MinIO
        img_storage = await run_in_threadpool(
            save_binary,
            content=file_bytes, 
            filename=file.filename,
            owner_email=owner_email,
            date_obj=date_obj
        )
        img_path = img_storage.local_path
        img_minio_key = img_storage.minio_key

        email_meta = {
            "sender": sender or "Carga manual (Imagen)",
        }
        if date_obj:
            email_meta["date"] = date_obj

        def _runner():
            owner = (user.get('email') or '').lower()
            # extract_invoice_data usa pdf_to_base64_first_page que ahora soporta imágenes
            invoice_data = invoice_sync.openai_processor.extract_invoice_data(img_path, email_meta, owner_email=owner)
            invoices = [invoice_data] if invoice_data else []
            
            if invoices:
                # Asignar minio_key
                if img_minio_key and invoice_data:
                    invoice_data.minio_key = img_minio_key
                    
                try:
                    repo = MongoInvoiceRepository()
                    doc = map_invoice(invoice_data, fuente="OPENAI_VISION_IMAGE", minio_key=img_minio_key)
                    if owner:
                        try:
                            doc.header.owner_email = owner
                            for it in doc.items:
                                it.owner_email = owner
                        except Exception:
                            pass
                    repo.save_document(doc)
                except Exception as e:
                    logger.error(f"❌ Error persistiendo v2 (upload Image): {e}")

            if not invoices:
                return ProcessResult(
                    success=False,
                    message="No se pudo extraer factura de la imagen",
                    invoice_count=0,
                    invoices=[]
                )

            return ProcessResult(
                success=True,
                message=f"Imagen procesada y almacenada",
                invoice_count=1,
                invoices=invoices
            )

        # Encolar tarea en lugar de ejecutar síncronamente
        job_id = task_queue.enqueue("process_image_manual", _runner)
        return {"job_id": job_id}

    except Exception as e:
        logger.error(f"Error al procesar imagen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")




@app.post("/tasks/upload-xml")
async def enqueue_upload_xml(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_ai_check)):
    """Encola el procesamiento de un XML manual y retorna job_id."""
    if not file.filename.lower().endswith('.xml'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML")

    try:
        file_bytes = await file.read()
        
        # Parse date
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                logger.warning(f"Formato de fecha incorrecto: {date}")

        # Save binary with MinIO
        owner_email = (user.get('email') or '').lower()
        xml_storage = save_binary(
            file_bytes, 
            file.filename,
            owner_email=owner_email,
            date_obj=date_obj
        )
        xml_path = xml_storage.local_path
        xml_minio_key = xml_storage.minio_key
        
        email_meta = {"sender": sender or "Carga manual"}
        if date_obj:
            email_meta["date"] = date_obj

        def _runner():
            owner = (user.get('email') or '').lower()
            inv = invoice_sync.openai_processor.extract_invoice_data_from_xml(xml_path, email_meta, owner_email=owner)
            invoices = [inv] if inv else []
            if invoices:
                # Assign minio key
                if xml_minio_key and inv:
                    inv.minio_key = xml_minio_key
                    
                try:
                    repo = MongoInvoiceRepository()
                    owner = (user.get('email') or '').lower()
                    doc = map_invoice(inv, fuente="XML_NATIVO" if getattr(inv, 'cdc', '') else "OPENAI_VISION")
                    if owner:
                        try:
                            doc.header.owner_email = owner
                            for it in doc.items:
                                it.owner_email = owner
                        except Exception:
                            pass
                    repo.save_document(doc)
                except Exception as e:
                    logger.error(f"❌ Error persistiendo (tasks upload XML): {e}")
            return ProcessResult(
                success=bool(invoices),
                message=("Factura XML procesada y almacenada " if invoices else "No se pudo extraer información desde el XML"),
                invoice_count=len(invoices), 
                invoices=invoices
            )

        job_id = task_queue.enqueue("upload_xml", _runner)
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Error al encolar XML: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Endpoints legacy de Excel eliminados

@app.post("/email-config/test")
async def test_email_config(config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Prueba la conexión a una configuración de correo.
    
    Args:
        config: Configuración de correo a probar
        
    Returns:
        dict: Resultado de la prueba
    """
    try:
        from app.modules.email_processor.email_processor import EmailProcessor
        from app.models.models import EmailConfig
        
        # Resolver password ausente con DB por id o username
        pwd = config.password
        if not pwd:
            db_cfg = None
            owner_email = (user.get('email') or '').lower()
            if config.id:
                db_cfg = db_get_by_id(config.id, include_password=True, owner_email=owner_email)
            if not db_cfg and config.username:
                db_cfg = db_get_by_username(config.username, include_password=True, owner_email=owner_email)
            if db_cfg and db_cfg.get("password"):
                pwd = db_cfg.get("password")

        # Crear configuración temporal para probar
        test_config = EmailConfig(
            host=config.host,
            port=config.port,
            username=config.username,
            password=pwd or "",
            search_criteria=config.search_criteria,
            search_terms=config.search_terms or []
        )
        
        # Crear procesador temporal
        processor = EmailProcessor(test_config)
        
        # Intentar conectar
        success = processor.connect()
        processor.disconnect()
        
        if success:
            return {"success": True, "message": "Conexión exitosa"}
        else:
            return {"success": False, "message": "Error al conectar"}
            
    except Exception as e:
        logger.error(f"Error al probar configuración de correo: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}

@app.post("/email-configs/{config_id}/test")
async def test_email_config_by_id(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """Prueba una configuración guardada, identificada por su ID en MongoDB. Soporta OAuth2."""
    try:
        from app.modules.email_processor.imap_client import IMAPClient
        from app.modules.oauth.google_oauth import get_google_oauth_manager

        db_cfg = db_get_by_id(config_id, include_password=True, owner_email=(user.get('email') or '').lower())
        if not db_cfg:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        auth_type = db_cfg.get("auth_type", "password")
        access_token = db_cfg.get("access_token")
        
        # For OAuth configs, check if token needs refresh
        if auth_type == "oauth2" and access_token:
            token_expiry_str = db_cfg.get("token_expiry")
            if token_expiry_str:
                from datetime import datetime
                try:
                    token_expiry = datetime.fromisoformat(token_expiry_str.replace('Z', '+00:00'))
                    oauth_manager = get_google_oauth_manager()
                    if oauth_manager.is_token_expired(token_expiry):
                        # Try to refresh the token
                        refresh_token = db_cfg.get("refresh_token")
                        if refresh_token:
                            try:
                                tokens = await oauth_manager.refresh_access_token(refresh_token)
                                access_token = tokens.get("access_token")
                                # Update token in DB
                                new_expiry = oauth_manager.calculate_token_expiry(tokens.get("expires_in", 3600))
                                db_update_config(config_id, {
                                    "access_token": access_token,
                                    "token_expiry": new_expiry.isoformat()
                                }, owner_email=(user.get('email') or '').lower())
                            except Exception as e:
                                logger.warning(f"Could not refresh token: {e}")
                                return {"success": False, "message": "Token OAuth expirado. Por favor, reconecta la cuenta."}
                except Exception as e:
                    logger.warning(f"Error parsing token expiry: {e}")

        # Create IMAP client with OAuth support
        client = IMAPClient(
            host=db_cfg.get("host"),
            port=int(db_cfg.get("port", 993)),
            username=db_cfg.get("username"),
            password=db_cfg.get("password") or "",
            mailbox="INBOX",
            auth_type=auth_type,
            access_token=access_token if auth_type == "oauth2" else None
        )
        
        success = client.connect()
        client.close()

        if success:
            auth_method = "OAuth2" if auth_type == "oauth2" else "contraseña"
            return {"success": True, "message": f"Conexión exitosa ({auth_method})"}
        else:
            return {"success": False, "message": "Error al conectar"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al probar configuración por ID: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# -----------------------------
# Email Config CRUD (MongoDB)
# -----------------------------

@app.get("/email-configs")
async def list_email_configs(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        owner_email = (user.get('email') or '').lower()
        cfgs = db_list_configs(include_password=False, owner_email=owner_email)
        
        # Obtener límites del plan para enviar al frontend
        from app.modules.email_processor.config_store import count_configs_by_owner
        from app.repositories.subscription_repository import SubscriptionRepository
        
        current_count = len(cfgs)
        sub_repo = SubscriptionRepository()
        subscription = await sub_repo.get_user_active_subscription(owner_email)
        
        max_accounts = 1  # Default para usuarios sin plan
        if subscription:
            plan_features = subscription.get('plan_features', {})
            max_accounts = plan_features.get('max_email_accounts', 2)
        
        return {
            "success": True, 
            "configs": cfgs, 
            "total": current_count,
            "max_allowed": max_accounts,
            "can_add_more": max_accounts == -1 or current_count < max_accounts,
            "has_active_plan": bool(subscription)
        }
    except Exception as e:
        logger.error(f"Error listando configuraciones de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudieron obtener configuraciones")


@app.post("/email-configs")
async def create_email_config(config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        owner_email = (user.get('email') or '').lower()
        
        # Validar que password esté presente al crear
        if not config.password:
            raise HTTPException(status_code=400, detail="La contraseña es obligatoria al crear una cuenta")
        
        # ✅ VALIDAR LÍMITE DE CUENTAS DE CORREO POR PLAN
        from app.modules.email_processor.config_store import count_configs_by_owner
        from app.repositories.subscription_repository import SubscriptionRepository
        
        # Contar cuentas actuales del usuario
        current_count = count_configs_by_owner(owner_email)
        
        # Obtener límite del plan del usuario
        sub_repo = SubscriptionRepository()
        subscription = await sub_repo.get_user_active_subscription(owner_email)
        
        if subscription:
            plan_features = subscription.get('plan_features', {})
            max_accounts = plan_features.get('max_email_accounts', 2)  # Default: 2 cuentas
            
            # -1 significa ilimitado
            if max_accounts != -1 and current_count >= max_accounts:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Has alcanzado el límite de {max_accounts} cuentas de correo de tu plan. Actualiza tu suscripción para agregar más."
                )
        else:
            # Usuario sin suscripción activa (trial o free)
            max_accounts = 1  # Solo 1 cuenta para usuarios sin plan
            if current_count >= max_accounts:
                raise HTTPException(
                    status_code=403,
                    detail="Has alcanzado el límite de cuentas de correo. Suscríbete a un plan para agregar más cuentas."
                )
        
        cfg_dict = config.model_dump()
        cfg_id = db_create_config(cfg_dict, owner_email=owner_email)
        
        logger.info(f"✅ Nueva cuenta de correo creada para {owner_email}: {current_count + 1}/{max_accounts}")
        
        return {"success": True, "id": cfg_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo crear configuración")


@app.put("/email-configs/{config_id}")
async def update_email_config(config_id: str, config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        update_data = config.model_dump()
        # Evitar sobreescribir password a null si no se envía
        if update_data.get("password") in (None, ""):
            update_data.pop("password", None)
        ok = db_update_config(config_id, update_data, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "id": config_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar configuración")


@app.patch("/email-configs/{config_id}")
async def patch_email_config(config_id: str, config: EmailConfigUpdate, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Actualización parcial de configuración de email.
    Permite actualizar solo campos específicos sin requerir todos los campos.
    Especialmente útil para configuraciones OAuth2 donde solo se pueden editar search_terms.
    """
    try:
        # Solo incluir campos que fueron explícitamente enviados (no None)
        update_data = {k: v for k, v in config.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
        
        ok = db_update_config(config_id, update_data, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "id": config_id, "updated_fields": list(update_data.keys())}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en actualización parcial de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar configuración")


@app.delete("/email-configs/{config_id}")
async def delete_email_config(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        ok = db_delete_config(config_id, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo eliminar configuración")


@app.patch("/email-configs/{config_id}/enabled")
async def set_email_config_enabled(config_id: str, payload: ToggleEnabledPayload, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        ok = db_set_enabled(config_id, bool(payload.enabled), owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "enabled": bool(payload.enabled)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando 'enabled' de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado")


@app.post("/email-configs/{config_id}/toggle")
async def toggle_email_config_enabled(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        new_val = db_toggle_enabled(config_id, owner_email=(user.get('email') or '').lower())
        if new_val is None:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "enabled": new_val}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error alternando 'enabled' de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo alternar el estado")


# -----------------------------
# OAuth 2.0 for Gmail (XOAUTH2)
# -----------------------------

@app.get("/email-configs/oauth/google/status")
async def get_google_oauth_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Check if Google OAuth is configured and available.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    
    oauth_manager = get_google_oauth_manager()
    return {
        "configured": oauth_manager.is_configured(),
        "provider": "google",
        "message": "OAuth configurado correctamente" if oauth_manager.is_configured() else "OAuth no configurado. Configure GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET"
    }


@app.get("/email-configs/oauth/google/authorize")
async def initiate_google_oauth(
    request: Request,
    user: Dict[str, Any] = Depends(_get_current_user),
    login_hint: Optional[str] = Query(None, description="Email to pre-fill in Google sign-in")
):
    """
    Initiate Google OAuth flow for Gmail IMAP access.
    Returns an authorization URL to redirect the user to.
    
    The state parameter encodes the user's email for security validation on callback.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    import base64
    import json
    
    oauth_manager = get_google_oauth_manager()
    
    if not oauth_manager.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google OAuth no está configurado. Contacta al administrador."
        )
    
    owner_email = (user.get('email') or '').lower()
    
    # Get the host from the request to build the correct redirect URI
    # This allows the same backend to work for both local and production
    # Use X-Forwarded-Host (includes port) if available, fallback to host
    request_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    redirect_uri = oauth_manager.get_redirect_uri(request_host)
    
    # Create state with user info for CSRF protection
    # Include redirect_uri so callback can use the same one
    state_data = {
        "owner_email": owner_email,
        "redirect_uri": redirect_uri,
        "timestamp": datetime.now().isoformat(),
        "nonce": str(uuid.uuid4())
    }
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    auth_url = oauth_manager.generate_auth_url(
        state=state,
        login_hint=login_hint,
        redirect_uri=redirect_uri
    )
    
    logger.info(f"🔐 OAuth authorization initiated for {owner_email} (redirect: {redirect_uri})")
    
    return {
        "auth_url": auth_url,
        "state": state,
        "message": "Redirige al usuario a auth_url para autorizar acceso a Gmail"
    }


@app.get("/email-configs/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from Google if authorization failed")
):
    """
    Handle Google OAuth callback after user grants permission.
    Exchanges the authorization code for access and refresh tokens.
    
    This endpoint is called by Google after user authorization.
    It returns an HTML page that sends the result to the opener window.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    import base64
    import json
    
    # Handle error from Google
    if error:
        logger.error(f"Google OAuth error: {error}")
        return HTMLResponse(content=_oauth_popup_response(False, f"Error de autorización: {error}"))
    
    oauth_manager = get_google_oauth_manager()
    
    try:
        # Decode and validate state
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        owner_email = state_data.get("owner_email", "").lower()
        redirect_uri = state_data.get("redirect_uri", "")
        
        if not owner_email:
            raise ValueError("Invalid state: missing owner_email")
        
        # Exchange code for tokens using the same redirect_uri from authorization
        tokens = await oauth_manager.exchange_code_for_tokens(code, redirect_uri=redirect_uri)
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        if not access_token:
            raise ValueError("No access token received from Google")
        
        # Get user info to confirm the Gmail address
        user_info = await oauth_manager.get_user_info(access_token)
        gmail_address = user_info.get("email", "").lower()
        
        # Calculate token expiry
        token_expiry = oauth_manager.calculate_token_expiry(expires_in)
        
        # SAVE DIRECTLY TO DATABASE - no popup communication needed
        # Check if this Gmail account already exists for this owner
        existing_configs = db_list_configs(owner_email=owner_email)
        existing_gmail_config = next(
            (c for c in existing_configs if c.get("username", "").lower() == gmail_address),
            None
        )
        
        if existing_gmail_config:
            # Update existing config with new OAuth tokens
            update_data = {
                "auth_type": "oauth2",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry.isoformat(),
                "password": "",  # Clear password for OAuth
                "enabled": True
            }
            db_update_config(existing_gmail_config["id"], update_data, owner_email=owner_email)
            logger.info(f"✅ Updated existing Gmail config with OAuth for {gmail_address}")
        else:
            # Create new config as dict
            new_config_data = {
                "name": f"Gmail - {gmail_address}",
                "host": "imap.gmail.com",
                "port": 993,
                "username": gmail_address,
                "password": "",
                "use_ssl": True,
                "auth_type": "oauth2",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry.isoformat(),
                "oauth_email": gmail_address,
                "search_terms": ["factura", "invoice", "comprobante", "documento electronico"],
                "search_criteria": "UNSEEN",
                "provider": "gmail",
                "enabled": True,
                "owner_email": owner_email
            }
            db_create_config(new_config_data, owner_email=owner_email)
            logger.info(f"✅ Created new Gmail OAuth config for {gmail_address}")
        
        logger.info(f"✅ Google OAuth successful for {gmail_address} (owner: {owner_email})")
        
        return HTMLResponse(content=_oauth_popup_response(True, "Cuenta Gmail conectada exitosamente. Puedes cerrar esta ventana.", None))
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return HTMLResponse(content=_oauth_popup_response(False, f"Error procesando autorización: {str(e)}"))


def _oauth_popup_response(success: bool, message: str, data: dict = None) -> str:
    """
    Generate an HTML response for the OAuth popup.
    Since we save directly to DB, we just show success/error and close.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Autorización Google - Cuenly</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.1);
                border-radius: 16px;
                backdrop-filter: blur(10px);
            }}
            .icon {{ font-size: 48px; margin-bottom: 20px; }}
            .message {{ font-size: 18px; margin-bottom: 10px; }}
            .submessage {{ font-size: 14px; opacity: 0.8; }}
            .btn {{
                margin-top: 20px;
                padding: 12px 24px;
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                color: white;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .btn:hover {{ background: rgba(255,255,255,0.3); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">{'✅' if success else '❌'}</div>
            <div class="message">{message}</div>
            <div class="submessage">{'Refresca la página de configuración para ver tu cuenta.' if success else 'Intenta nuevamente.'}</div>
            <button class="btn" onclick="window.close()">Cerrar ventana</button>
        </div>
        <script>
            // Notify parent to refresh if possible
            if (window.opener && !window.opener.closed) {{
                try {{
                    window.opener.postMessage({{ type: 'GOOGLE_OAUTH_COMPLETE', success: {'true' if success else 'false'} }}, '*');
                }} catch(e) {{}}
            }}
            // Auto close after 3 seconds if successful
            if ({'true' if success else 'false'}) {{
                setTimeout(() => window.close(), 3000);
            }}
        </script>
    </body>
    </html>
    """


@app.post("/email-configs/{config_id}/oauth/refresh")
async def refresh_oauth_token(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Refresh the OAuth access token for a saved email configuration.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    
    owner_email = (user.get('email') or '').lower()
    
    # Get the config from database
    db_cfg = db_get_by_id(config_id, include_password=True, owner_email=owner_email)
    if not db_cfg:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    
    if db_cfg.get("auth_type") != "oauth2":
        raise HTTPException(status_code=400, detail="Esta configuración no usa OAuth")
    
    refresh_token = db_cfg.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No hay refresh token almacenado")
    
    oauth_manager = get_google_oauth_manager()
    
    try:
        # Refresh the token
        tokens = await oauth_manager.refresh_access_token(refresh_token)
        
        new_access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in", 3600)
        token_expiry = oauth_manager.calculate_token_expiry(expires_in)
        
        # Update the config in database
        update_data = {
            "access_token": new_access_token,
            "token_expiry": token_expiry.isoformat()
        }
        
        ok = db_update_config(config_id, update_data, owner_email=owner_email)
        if not ok:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el token")
        
        logger.info(f"✅ OAuth token refreshed for config {config_id}")
        
        return {
            "success": True,
            "token_expiry": token_expiry.isoformat(),
            "message": "Token actualizado exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing OAuth token: {e}")
        raise HTTPException(status_code=500, detail=f"Error renovando token: {str(e)}")


@app.post("/email-configs/oauth/save")
async def save_oauth_email_config(
    gmail_address: str = Body(..., embed=True),
    access_token: str = Body(..., embed=True),
    refresh_token: str = Body(..., embed=True),
    token_expiry: str = Body(..., embed=True),
    name: Optional[str] = Body("", embed=True),
    search_terms: Optional[List[str]] = Body(None, embed=True),
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Save a new email configuration with OAuth tokens after successful Google authorization.
    """
    from app.modules.email_processor.config_store import count_configs_by_owner
    from app.repositories.subscription_repository import SubscriptionRepository
    
    owner_email = (user.get('email') or '').lower()
    
    # Validate subscription limits
    current_count = count_configs_by_owner(owner_email)
    sub_repo = SubscriptionRepository()
    subscription = await sub_repo.get_user_active_subscription(owner_email)
    
    if subscription:
        plan_features = subscription.get('plan_features', {})
        max_accounts = plan_features.get('max_email_accounts', 2)
        
        if max_accounts != -1 and current_count >= max_accounts:
            raise HTTPException(
                status_code=403,
                detail=f"Has alcanzado el límite de {max_accounts} cuentas de correo de tu plan."
            )
    else:
        if current_count >= 1:
            raise HTTPException(
                status_code=403,
                detail="Has alcanzado el límite de cuentas de correo. Suscríbete a un plan para agregar más."
            )
    
    # Verificar si ya existe config para este email para preservar settings
    existing_config = None
    try:
        from app.modules.email_processor.config_store import get_by_username
        existing_config = get_by_username(gmail_address, owner_email=owner_email)
    except Exception as e:
        logger.warning(f"Error checking existing config for {gmail_address}: {e}")

    # Preservar search_terms si existen y no se enviaron nuevos
    final_search_terms = search_terms
    if not final_search_terms:
        if existing_config and existing_config.get("search_terms"):
            final_search_terms = existing_config.get("search_terms")
        else:
            final_search_terms = ["factura", "invoice", "comprobante"]

    # Create the email config with OAuth
    config_data = {
        "name": name or (existing_config.get("name") if existing_config else f"Gmail - {gmail_address}"),
        "host": "imap.gmail.com",
        "port": 993,
        "username": gmail_address,
        "password": None,  # No password needed for OAuth
        "use_ssl": True,
        "search_criteria": "UNSEEN",
        "search_terms": final_search_terms,
        "provider": "gmail",
        "enabled": True,
        "auth_type": "oauth2",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": token_expiry,
        "oauth_email": gmail_address
    }
    
    try:
        config_id = db_create_config(config_data, owner_email=owner_email)
        logger.info(f"✅ OAuth email config created for {gmail_address} (owner: {owner_email})")
        
        return {
            "success": True,
            "id": config_id,
            "message": "Cuenta de Gmail configurada exitosamente con OAuth"
        }
    except Exception as e:
        logger.error(f"Error creating OAuth email config: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración")


@app.get("/health")
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

@app.get("/email-processing/config")
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

@app.get("/status")
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

        # Estado del job
        job_status = invoice_sync.get_job_status()
        
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

@app.get("/v2/invoices/headers")
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

@app.get("/v2/invoices/{header_id}")
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

@app.get("/v2/invoices/items")
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

@app.delete("/v2/invoices/{header_id}")
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
        
        # Eliminar items primero
        items_result = repo._items().delete_many({"header_id": header_id})
        
        # Eliminar header
        header_result = repo._headers().delete_one({"_id": header_id})
        
        if header_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la factura")
        
        logger.info(f"✅ Factura eliminada: {header_id} ({items_result.deleted_count} items)")
        
        return {
            "success": True,
            "message": f"Factura eliminada correctamente",
            "deleted_items": items_result.deleted_count,
            "header_id": header_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando factura {header_id}: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando factura")

@app.delete("/v2/invoices/bulk")
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
        existing_headers = list(repo._headers().find(q, {"_id": 1}))
        existing_ids = [h["_id"] for h in existing_headers]
        
        if len(existing_ids) != len(header_ids):
            missing_ids = set(header_ids) - set(existing_ids)
            raise HTTPException(
                status_code=404, 
                detail=f"Facturas no encontradas: {list(missing_ids)}"
            )
        
        # Eliminar items de todas las facturas
        items_result = repo._items().delete_many({"header_id": {"$in": existing_ids}})
        
        # Eliminar headers
        headers_result = repo._headers().delete_many({"_id": {"$in": existing_ids}})
        
        logger.info(f"✅ Eliminación en lote: {headers_result.deleted_count} facturas, {items_result.deleted_count} items")
        
        return {
            "success": True,
            "message": f"Se eliminaron {headers_result.deleted_count} facturas correctamente",
            "deleted_headers": headers_result.deleted_count,
            "deleted_items": items_result.deleted_count,
            "processed_ids": existing_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en eliminación en lote: {e}")
        raise HTTPException(status_code=500, detail="Error en eliminación en lote")

class BulkDeleteRequest(BaseModel):
    header_ids: List[str]

@app.post("/v2/invoices/bulk-delete")
async def v2_bulk_delete_invoices_post(
    request: BulkDeleteRequest,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Alternativa POST para eliminación en lote (para payloads grandes).
    """
    return await v2_bulk_delete_invoices(request.header_ids, user)

@app.get("/v2/invoices/{header_id}/delete-info")
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

@app.post("/v2/invoices/bulk-delete-info")
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

@app.post("/job/start", response_model=JobStatus)
async def start_job():
    """
    Inicia el trabajo programado para procesar correos periódicamente.
    
    Returns:
        JobStatus: Estado del trabajo.
    """
    try:
        job_status = invoice_sync.start_scheduled_job()
        return job_status
    except Exception as e:
        logger.error(f"Error al iniciar el job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al iniciar el job: {str(e)}")

@app.post("/job/stop", response_model=JobStatus)
async def stop_job():
    """
    Detiene el trabajo programado.
    
    Returns:
        JobStatus: Estado del trabajo.
    """
    try:
        job_status = invoice_sync.stop_scheduled_job()
        return job_status
    except Exception as e:
        logger.error(f"Error al detener el job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al detener el job: {str(e)}")

@app.get("/job/status", response_model=JobStatus)
async def job_status():
    """
    Obtiene el estado actual del trabajo programado.
    
    Returns:
        JobStatus: Estado del trabajo.
    """
    return invoice_sync.get_job_status()

@app.post("/job/interval", response_model=JobStatus)
async def set_job_interval(payload: IntervalPayload):
    """Ajusta el intervalo (minutos) del job de automatización."""
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

@app.get("/cache/stats")
async def cache_stats():
    """
    Obtiene estadísticas del cache de OpenAI.
    
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

@app.post("/debug/fix-user-trial-status")
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

@app.post("/cache/clear")
async def clear_cache(older_than_hours: Optional[int] = None):
    """
    Limpia el cache de OpenAI.
    
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

@app.get("/imap/pool/stats")
async def imap_pool_stats():
    """
    Obtiene estadísticas del pool de conexiones IMAP.
    
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

    # Endpoint legacy /excel/stats eliminado

@app.get("/health/detailed")
async def detailed_health():
    """
    Health check comprensivo con métricas detalladas de todos los componentes.
    
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

@app.get("/health/redis")
async def redis_health():
    """
    Health check específico para Redis.
    
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


@app.get("/health/trends")
async def health_trends():
    """
    Obtiene tendencias de salud del sistema basadas en histórico.
    
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

@app.post("/system/force-restart")
async def force_system_restart():
    """
    Endpoint de emergencia para forzar reinicio del sistema cuando hay bloqueos.
    
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

@app.get("/system/health")
async def get_system_health():
    """
    Endpoint de salud del sistema con información detallada.
    
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

@app.get("/admin/users")
async def admin_get_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Obtiene lista de usuarios (solo para admins)"""
    try:
        user_repo = UserRepository()
        result = user_repo.get_all_users(page, page_size)
        
        # Convertir ObjectId y datetime a string para serialización
        for user in result['users']:
            if '_id' in user:
                user['id'] = str(user['_id'])
                del user['_id']
            for field in ['created_at', 'last_login', 'trial_expires_at', 'email_processing_start_date']:
                if field in user and user[field]:
                    user[field] = user[field].isoformat() if hasattr(user[field], 'isoformat') else str(user[field])
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Error obteniendo usuarios: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo usuarios")

@app.put("/admin/users/{user_email}/role")
async def admin_update_user_role(
    user_email: str,
    request: UpdateUserRoleRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Actualiza el rol de un usuario (solo para admins)"""
    try:
        user_repo = UserRepository()
        
        # Verificar que el usuario existe
        target_user = user_repo.get_by_email(user_email)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # No permitir cambiar el rol del admin principal
        if user_email.lower() == 'andyvercha@gmail.com' and request.role != 'admin':
            raise HTTPException(status_code=400, detail="No se puede cambiar el rol del administrador principal")
        
        success = user_repo.update_user_role(user_email, request.role)
        if not success:
            raise HTTPException(status_code=400, detail="Rol inválido o usuario no encontrado")
        
        return {
            "success": True,
            "message": f"Rol actualizado a '{request.role}' para {user_email}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando rol: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando rol")

@app.put("/admin/users/{user_email}/status")
async def admin_update_user_status(
    user_email: str,
    request: UpdateUserStatusRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Actualiza el estado de un usuario (solo para admins)"""
    try:
        user_repo = UserRepository()
        
        # Verificar que el usuario existe
        target_user = user_repo.get_by_email(user_email)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # No permitir suspender al admin principal
        if user_email.lower() == 'andyvercha@gmail.com' and request.status == 'suspended':
            raise HTTPException(status_code=400, detail="No se puede suspender al administrador principal")
        
        success = user_repo.update_user_status(user_email, request.status)
        if not success:
            raise HTTPException(status_code=400, detail="Estado inválido o usuario no encontrado")
        
        # Si se suspendió al usuario, cancelar sus suscripciones activas (idempotente)
        cancelled_msg = ""
        job_msg = ""
        if request.status == 'suspended':
            try:
                sub_repo = SubscriptionRepository()
                ok = await sub_repo.cancel_user_subscriptions(user_email)
                if ok:
                    cancelled_msg = "; suscripciones activas canceladas"
            except Exception as e:
                logger.error(f"Error cancelando suscripciones al suspender {user_email}: {e}")
            
            # Detener job global de procesamiento si está en ejecución
            try:
                current_job = invoice_sync.get_job_status()
                if getattr(current_job, 'running', False):
                    invoice_sync.stop_scheduled_job()
                    job_msg = "; job de ejecución detenido"
            except Exception as e:
                logger.error(f"Error deteniendo job al suspender {user_email}: {e}")
        
        return {
            "success": True,
            "message": f"Estado actualizado a '{request.status}' para {user_email}{cancelled_msg}{job_msg}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando estado: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando estado")

@app.get("/admin/stats")
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
                    "total_amount": {"$sum": "$monto_total"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        monthly_stats = list(headers_coll.aggregate(monthly_pipeline))
        
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
                "user_invoices": user_invoices_stats
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@app.get("/admin/check")
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
@app.get("/api/plans", tags=["Plans - Public"])
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

@app.get("/api/plans/{plan_code}", tags=["Plans - Public"])
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
@app.get("/user/subscription", tags=["User - Subscription"])
async def get_user_subscription(current_user: dict = Depends(_get_current_user)):
    """Obtiene la suscripción actual del usuario autenticado"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        subscription = await repo.get_user_active_subscription(current_user["email"])
        
        if not subscription:
            return {
                "success": True,
                "data": None,
                "message": "Usuario sin suscripción activa"
            }
        
        return {
            "success": True,
            "data": subscription
        }
    except Exception as e:
        logger.error(f"Error obteniendo suscripción de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo suscripción")

@app.get("/user/subscription/history", tags=["User - Subscription"])
async def get_user_subscription_history(current_user: dict = Depends(_get_current_user)):
    """Obtiene el historial de suscripciones del usuario"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        history = await repo.get_user_subscriptions_history(current_user["email"])
        
        return {
            "success": True,
            "data": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Error obteniendo historial de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo historial")

@app.post("/user/subscription/change-plan", tags=["User - Subscription"])
async def request_plan_change(
    request: dict,
    current_user: dict = Depends(_get_current_user)
):
    """Solicita cambio de plan - redirige a checkout de Pagopar para pago con tarjeta"""
    try:
        new_plan_id = request.get("plan_id")
        if not new_plan_id:
            raise HTTPException(status_code=400, detail="plan_id es requerido")
        
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.services.pagopar_service import PagoparService
        import hashlib
        
        repo = SubscriptionRepository()
        pagopar_service = PagoparService()
        
        # Verificar que el plan existe (buscar por código)
        plan = await repo.get_plan_by_code(new_plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        # Verificar si el usuario ya tiene este plan
        current_subscription = await repo.get_user_active_subscription(current_user["email"])
        if current_subscription and current_subscription.get("plan_code") == new_plan_id:
            raise HTTPException(status_code=400, detail="Ya tienes este plan activo")
            
        # ============================================================
        # CREAR PEDIDO EN PAGOPAR (V1.1 Standard)
        # ============================================================
        
        email = current_user["email"]
        name = current_user.get("name", "Usuario Cuenly")
        
        # Generar ID único para el pedido
        timestamp = int(time.time())
        order_id = f"CUENLY-SUB-{timestamp}"
        
        # Obtener datos del comprador del request (si vienen del frontend)
        buyer_data = request.get("buyer_data", {})
        
        # Datos del comprador para Pagopar
        buyer = {
            "email": email,
            "nombre": name,
            "ruc": buyer_data.get("ruc", ""),
            "telefono": buyer_data.get("telefono", ""),
            "direccion": buyer_data.get("direccion", ""),
            "documento": buyer_data.get("documento", ""),
            "coordenadas": "",
            "razon_social": buyer_data.get("razon_social") or name,
            "tipo_documento": buyer_data.get("tipo_documento", "CI"),
            "ciudad": None,
            "direccion_referencia": None
        }
        
        # Validar campos obligatorios
        if not buyer["documento"]:
            raise HTTPException(status_code=400, detail="El número de documento es requerido")
        if not buyer["telefono"]:
            raise HTTPException(status_code=400, detail="El número de teléfono es requerido")
        
        # Crear pedido en Pagopar
        amount = plan["price"]
        description = f"Suscripción {plan['name']}"
        
        try:
            order_hash = await pagopar_service.create_order_v11(
                order_id, 
                amount, 
                description,
                buyer
            )
            
            if not order_hash:
                raise Exception("No se pudo generar el hash del pedido")
            
            # Guardar orden pendiente en DB para reconciliación en webhook
            db = repo._get_db()
            db.pending_subscriptions.insert_one({
                "user_email": email,
                "plan_code": new_plan_id,
                "plan_name": plan["name"],
                "amount": amount,
                "order_id": order_id,
                "order_hash": order_hash,
                "status": "pending",
                "created_at": datetime.utcnow()
            })
            
            # Construir URL de checkout
            checkout_url = f"https://www.pagopar.com/pagos/{order_hash}"
            
            return {
                "success": True,
                "checkout_url": checkout_url,
                "order_hash": order_hash,
                "message": "Redirigiendo a Pagopar para completar el pago..."
            }
            
        except Exception as e:
            logger.error(f"Error al crear pedido en Pagopar: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al procesar el pago: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en request_plan_change: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando cambio de plan para {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error procesando solicitud")

@app.post("/user/subscription/cancel", tags=["User - Subscription"])
async def cancel_user_subscription(current_user: dict = Depends(_get_current_user)):
    """Cancela la suscripción activa del usuario autenticado."""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()

        # Verificar si el usuario tiene una suscripción activa
        active = await repo.get_user_active_subscription(current_user["email"])
        if not active:
            return {
                "success": True,
                "message": "No tienes una suscripción activa para cancelar"
            }

        # Cancelar suscripciones activas (idempotente)
        ok = await repo.cancel_user_subscriptions(current_user["email"])
        if not ok:
            raise HTTPException(status_code=500, detail="No se pudo cancelar la suscripción")

        logger.info(f"✅ Suscripción cancelada para {current_user['email']}")
        return {
            "success": True,
            "message": "Tu suscripción ha sido cancelada correctamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelando suscripción de {current_user['email']}: {e}")
        raise HTTPException(status_code=500, detail="Error cancelando suscripción")

# Endpoints administrativos para planes (requieren auth admin)
@app.get("/admin/plans", tags=["Admin - Plans"])
async def admin_get_plans(
    include_inactive: bool = Query(False),
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Obtiene todos los planes (incluye inactivos si se especifica)"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        plans = await repo.get_all_plans(include_inactive=include_inactive)
        
        return {
            "success": True,
            "data": plans,
            "count": len(plans)
        }
    except Exception as e:
        logger.error(f"Error obteniendo planes admin: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo planes")

@app.post("/admin/plans", tags=["Admin - Plans"])
async def admin_create_plan(
    plan: PlanCreateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Crea un nuevo plan de suscripción"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        
        # Verificar que el código no exista
        existing_plan = await repo.get_plan_by_code(plan.code)
        if existing_plan:
            raise HTTPException(status_code=400, detail="Ya existe un plan con ese código")
        
        success = await repo.create_plan(plan.dict())
        if not success:
            raise HTTPException(status_code=500, detail="Error creando plan")
        
        return {
            "success": True,
            "message": f"Plan '{plan.name}' creado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando plan: {e}")
        raise HTTPException(status_code=500, detail="Error creando plan")

@app.put("/admin/plans/{plan_code}", tags=["Admin - Plans"])
async def admin_update_plan(
    plan_code: str,
    plan: PlanUpdateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Actualiza un plan existente"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        
        # Verificar que el plan existe
        existing_plan = await repo.get_plan_by_code(plan_code)
        if not existing_plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        # Actualizar solo los campos que se enviaron
        update_data = {k: v for k, v in plan.dict().items() if v is not None}
        
        success = await repo.update_plan(plan_code, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Error actualizando plan")
        
        return {
            "success": True,
            "message": f"Plan '{plan_code}' actualizado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando plan: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando plan")

@app.delete("/admin/plans/{plan_code}", tags=["Admin - Plans"])
async def admin_delete_plan(
    plan_code: str,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Elimina un plan (soft delete)"""
    try:
        from app.repositories.subscription_repository import SubscriptionRepository
        repo = SubscriptionRepository()
        
        success = await repo.delete_plan(plan_code)
        if not success:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        
        return {
            "success": True,
            "message": f"Plan '{plan_code}' eliminado exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando plan: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando plan")

# ==========================================
# PUBLIC PLANS ENDPOINTS
# ==========================================

@app.get("/api/plans", tags=["Plans"])
@app.get("/plans", tags=["Plans"]) # Alias for convenience
async def list_public_plans(
    user: Dict[str, Any] = Depends(_get_current_user)
):
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

# Endpoints de suscripciones - TODOS MIGRADOS a admin_subscriptions.py
# Rutas: /admin/subscriptions/stats, POST /admin/subscriptions, GET /admin/subscriptions/user/{user_email}

@app.get("/invoices/{invoice_id}/download")
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

        minio_key = header.get("minio_key")
        if not minio_key:
            return {"success": False, "message": "Archivo no disponible en el almacenamiento seguro"}
            
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


@app.get("/invoices/{invoice_id}/file")
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
            
        minio_key = header.get("minio_key")
        if not minio_key:
            raise HTTPException(status_code=404, detail="Archivo no disponible")
            
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
@app.get("/admin/stats/filtered", tags=["Admin - Stats"])
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

@app.post("/admin/ai-limits/reset-monthly", tags=["Admin - AI Limits"])
async def admin_reset_monthly_ai_limits(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Ejecuta el reseteo mensual de límites de IA para usuarios con planes activos"""
    try:
        from app.services.monthly_reset_service import MonthlyResetService
        reset_service = MonthlyResetService()
        
        result = await reset_service.reset_monthly_limits()
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "resetted_users": result["resetted_users"],
                    "total_subscriptions": result.get("total_subscriptions", 0),
                    "errors": result.get("errors", []),
                    "execution_date": result.get("execution_date")
                }
            }
        else:
            return {
                "success": False,
                "message": result["message"]
            }
            
    except Exception as e:
        logger.error(f"Error en reseteo mensual manual: {e}")
        raise HTTPException(status_code=500, detail="Error ejecutando reseteo mensual")

@app.post("/admin/ai-limits/reset-user/{user_email}", tags=["Admin - AI Limits"])
async def admin_reset_user_ai_limits(
    user_email: str,
    admin: Dict[str, Any] = Depends(_get_current_admin)
):
    """Resetea manualmente los límites de IA de un usuario específico"""
    try:
        from app.services.monthly_reset_service import MonthlyResetService
        reset_service = MonthlyResetService()
        
        result = await reset_service.reset_user_limits_manually(user_email)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "user_email": user_email,
                    "new_limit": result.get("new_limit")
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en reset manual para {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Error reseteando límites del usuario")

@app.get("/admin/ai-limits/reset-stats", tags=["Admin - AI Limits"])
async def admin_get_reset_stats(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Obtiene estadísticas sobre los resets de límites de IA"""
    try:
        from app.services.monthly_reset_service import MonthlyResetService
        reset_service = MonthlyResetService()
        
        stats = await reset_service.get_reset_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de reset: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@app.get("/admin/scheduler/status", tags=["Admin - Scheduler"])
async def admin_get_scheduler_status(admin: Dict[str, Any] = Depends(_get_current_admin)):
    """Obtiene el estado del scheduler de tareas programadas"""
    try:
        from app.services.scheduler import get_scheduler_status
        from app.services.monthly_reset_service import MonthlyResetService
        
        reset_service = MonthlyResetService()
        scheduler_status = get_scheduler_status()
        
        return {
            "success": True,
            "data": {
                "scheduler": scheduler_status,
                "next_reset_date": reset_service.get_next_reset_date().isoformat(),
                "should_run_today": reset_service.should_run_today()
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del scheduler: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado del scheduler")

# ==========================================
# DASHBOARD ENDPOINTS (User)
# ==========================================

@app.get("/dashboard/stats")
async def get_dashboard_stats(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtiene estadísticas generales para el dashboard."""
    try:
        user_repo = UserRepository()
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        
        # Filtro base
        q = {"owner_email": owner_email} if owner_email else {}
        
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

@app.get("/dashboard/monthly-stats")
async def get_dashboard_monthly(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtiene evolución mensual de inversión (usando fecha_emision)."""
    try:
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        q = {"owner_email": owner_email} if owner_email else {}
        
        # Filter > 12 months ago
        from datetime import datetime, timedelta
        start_date = datetime.now() - timedelta(days=365)
        
        # Asegurar que fecha_emision existe y es > start_date
        q["fecha_emision"] = {"$gte": start_date}

        pipeline = [
             {"$match": q},
             {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m", "date": "$fecha_emision"}},
                    "total_amount": {"$sum": "$totales.total"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]

        data = list(repo._headers().aggregate(pipeline))
        monthly_data = [
            {"year_month": d["_id"], "total_amount": d["total_amount"], "count": d["count"]}
            for d in data
        ]
        
        return {"success": True, "monthly_data": monthly_data}
    except Exception as e:
        logger.error(f"Error dashboard monthly: {e}")
        return {"success": False, "monthly_data": []}

@app.get("/dashboard/top-emisores")
async def get_dashboard_top_emisores(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        q = {"owner_email": owner_email} if owner_email else {}
        
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

@app.get("/dashboard/recent-invoices")
async def get_dashboard_recent(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        repo = MongoInvoiceRepository()
        owner_email = (user.get('email') or '').lower()
        q = {"owner_email": owner_email} if owner_email else {}
        
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

@app.get("/dashboard/system-status")
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

def start():
    """Inicia el servidor API."""
    # Guardar tiempo de inicio
    app.state.start_time = time.time()
    
    # Iniciar scheduler para tareas programadas
    try:
        from app.services.scheduler import start_background_scheduler
        start_background_scheduler()
        logger.info("🚀 Scheduler de tareas programadas iniciado")
    except Exception as e:
        logger.error(f"❌ Error iniciando scheduler: {e}")
    
    uvicorn.run(
        "app.api.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )

if __name__ == "__main__":
    start()

# -----------------------------
# Preferencias (UI / Auto‑refresh) - Storage en memoria
# -----------------------------
_auto_refresh_prefs: Dict[str, Dict] = {}

def prefs_get_auto_refresh(uid: str) -> Dict:
    return _auto_refresh_prefs.get(uid, {"enabled": False, "interval_ms": 30000})

def prefs_set_auto_refresh(uid: str, enabled: bool, interval_ms: int) -> Dict:
    _auto_refresh_prefs[uid] = {"enabled": enabled, "interval_ms": interval_ms}
    return _auto_refresh_prefs[uid]

@app.get("/prefs/auto-refresh", response_model=AutoRefreshPref)
async def get_auto_refresh(uid: Optional[str] = Query(default="global")):
    try:
        data = prefs_get_auto_refresh(uid)
        return AutoRefreshPref(uid=uid, enabled=bool(data.get("enabled", False)), interval_ms=int(data.get("interval_ms", 30000)))
    except Exception as e:
        logger.error(f"Error al obtener preferencia auto-refresh: {e}")
        raise HTTPException(status_code=500, detail="No se pudo obtener preferencia")

@app.post("/prefs/auto-refresh", response_model=AutoRefreshPref)
async def set_auto_refresh(payload: AutoRefreshPayload):
    try:
        uid = payload.uid or "global"
        data = prefs_set_auto_refresh(uid, payload.enabled, payload.interval_ms)
        return AutoRefreshPref(uid=uid, enabled=bool(data.get("enabled", False)), interval_ms=int(data.get("interval_ms", 30000)))
    except Exception as e:
        logger.error(f"Error al guardar preferencia auto-refresh: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar preferencia")

# Endpoints legacy de exportación eliminados (Excel/Documental)

@app.get("/export/mongodb/stats")
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

    # Endpoint legacy process-and-export eliminado

# Funciones auxiliares para tareas en segundo plano

    # Tareas legacy de exportación eliminadas

async def _export_completo_month_task(year_month: str):
    return {"success": False, "message": "Exportación a Excel deshabilitada"}

# -----------------------------
# Consultas MongoDB y Exports por Fecha
# -----------------------------

@app.get("/invoices/months")
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

@app.get("/invoices/month/{year_month}")
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

@app.get("/invoices/month/{year_month}/stats")
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

@app.post("/invoices/search")
async def search_invoices(
    query: str = Query(default="", description="Texto libre para buscar"),
    start_date: Optional[str] = Query(default=None, description="Fecha inicio YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="Fecha fin YYYY-MM-DD"),
    provider_ruc: Optional[str] = Query(default=None, description="RUC del proveedor"),
    client_ruc: Optional[str] = Query(default=None, description="RUC del cliente"),
    min_amount: Optional[float] = Query(default=None, description="Monto mínimo"),
    max_amount: Optional[float] = Query(default=None, description="Monto máximo"),
    limit: int = Query(default=100, description="Límite de resultados")
):
    """
    Búsqueda avanzada de facturas en MongoDB con múltiples filtros.
    """
    try:
        query_service = get_mongo_query_service()
        results = query_service.search_invoices(
            query=query,
            start_date=start_date,
            end_date=end_date,
            provider_ruc=provider_ruc,
            client_ruc=client_ruc,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=limit
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

@app.get("/invoices/recent-activity")
async def get_recent_activity(days: int = Query(default=7, description="Días hacia atrás")):
    """
    Obtiene actividad reciente del sistema desde MongoDB.
    """
    try:
        query_service = get_mongo_query_service()
        activity = query_service.get_recent_activity(days)
        
        return {
            "success": True,
            "activity": activity
        }
    except Exception as e:
        logger.error(f"Error obteniendo actividad reciente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo actividad: {str(e)}")

    # Endpoint legacy /export/excel-from-mongodb eliminado

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
        
        invoice = InvoiceData(
            numero_factura=doc.get("numero_factura", "") or doc.get("numero_documento", ""),
            fecha=fecha,
            ruc_emisor=doc.get("ruc_emisor", ""),
            nombre_emisor=doc.get("nombre_emisor", ""),
            ruc_cliente=doc.get("ruc_cliente", ""),
            nombre_cliente=doc.get("nombre_cliente", ""),
            email_cliente=doc.get("email_cliente", ""),
            monto_total=doc.get("monto_total", 0) or totales_data.get("total", 0),
            
            # Mapeo correcto desde modelo v2 - NOMBRES CORRECTOS DEL XML
            monto_exento=totales_data.get("exentas", 0),  # monto_exento en lugar de subtotal_exentas
            base_gravada_5=totales_data.get("gravado_5", 0),  # base_gravada_5 del XML
            base_gravada_10=totales_data.get("gravado_10", 0),  # base_gravada_10 del XML
            iva_5=totales_data.get("iva_5", 0),
            iva_10=totales_data.get("iva_10", 0),
            
            # Campos adicionales del XML que faltaban
            total_operacion=doc.get("total_operacion", 0),
            total_descuento=doc.get("total_descuento", 0),
            total_iva=totales_data.get("iva_5", 0) + totales_data.get("iva_10", 0),
            anticipo=doc.get("anticipo", 0),
            
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
            invoice.direccion_emisor = doc.get("direccion_emisor", "")
        except Exception:
            pass
        try:
            invoice.telefono_emisor = doc.get("telefono_emisor", "")
        except Exception:
            pass
        try:
            invoice.actividad_economica = doc.get("actividad_economica", "")
        except Exception:
            pass
        try:
            invoice.email_emisor = doc.get("email_emisor", "")
        except Exception:
            pass

        # Datos del receptor adicionales
        try:
            invoice.direccion_cliente = doc.get("direccion_cliente", "")
        except Exception:
            pass
        try:
            invoice.telefono_cliente = doc.get("telefono_cliente", "")
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

@app.get("/export-templates")
async def get_export_templates(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtener todos los templates de exportación del usuario"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        repo = ExportTemplateRepository()
        templates = repo.get_templates_by_user(user["email"])
        
        return {
            "templates": [template.model_dump() for template in templates],
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export-templates/available-fields")
async def get_available_fields(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtener lista de campos disponibles para templates - SOLO CAMPOS REALES"""
    try:
        from app.models.export_template import AVAILABLE_FIELDS
        
        # Solo devolver campos reales de la base de datos - sin campos calculados
        return {
            "fields": AVAILABLE_FIELDS,
            "categories": {
                "basic": [
                    "numero_factura", "fecha", "cdc", "timbrado", "tipo_documento", 
                    "condicion_venta", "moneda", "tipo_cambio"
                ],
                "emisor": [
                    "ruc_emisor", "nombre_emisor", "direccion_emisor", "telefono_emisor", 
                    "email_emisor", "actividad_economica"
                ],
                "cliente": [
                    "ruc_cliente", "nombre_cliente", "direccion_cliente", "email_cliente", "telefono_cliente"
                ],
                "montos": [
                    "gravado_5", "gravado_10", "iva_5", "iva_10", "total_iva",
                    "monto_exento", "exonerado", "monto_total", 
                    "total_base_gravada", "total_descuento", "anticipo"
                ],
                "productos": [
                    "productos", "productos.codigo", "productos.nombre", 
                    "productos.cantidad", "productos.unidad", "productos.precio_unitario", 
                    "productos.total", "productos.iva", "productos.base_gravada", "productos.monto_iva"
                ],
                "metadata": [
                    "mes_proceso", "created_at"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo campos disponibles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === RUTA DE CAMPOS CALCULADOS ELIMINADA ===
# @app.get("/export-templates/calculated-fields/preview")
# async def preview_calculated_fields(user: Dict[str, Any] = Depends(_get_current_user)):
#     """Preview de campos calculados - ELIMINADO"""
#     return {"error": "Campos calculados eliminados"}

# === RUTAS DE TEMPLATES PREDEFINIDOS ELIMINADAS ===
# Ya no hay templates predefinidos, solo creación personalizada

# @app.post("/export-templates/create-from-preset")
# async def create_template_from_preset(
#     preset_request: dict,
#     user: Dict[str, Any] = Depends(_get_current_user)
# ):
#     """Crear template a partir de un preset inteligente - ELIMINADO"""
#     return {"error": "Templates predefinidos eliminados"}

# === TEMPLATES PREDEFINIDOS ELIMINADOS ===

@app.post("/export-templates")
async def create_export_template(
    template_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Crear un nuevo template de exportación"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.models.export_template import ExportTemplate
        
        # Agregar owner_email
        template_data["owner_email"] = user["email"]
        
        # Crear template
        template = ExportTemplate(**template_data)
        repo = ExportTemplateRepository()
        template_id = repo.create_template(template)
        
        return {
            "success": True,
            "template_id": template_id,
            "message": f"Template '{template.name}' creado exitosamente"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export-templates/{template_id}")
async def get_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Obtener un template específico"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        repo = ExportTemplateRepository()
        template = repo.get_template_by_id(template_id, user["email"])
        
        if not template:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
        return template.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/export-templates/{template_id}")
async def update_export_template(
    template_id: str,
    template_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Actualizar un template existente"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.models.export_template import ExportTemplate
        
        # Agregar owner_email
        template_data["owner_email"] = user["email"]
        
        # Actualizar template
        template = ExportTemplate(**template_data)
        repo = ExportTemplateRepository()
        
        if repo.update_template(template_id, template):
            return {
                "success": True,
                "message": f"Template '{template.name}' actualizado exitosamente"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/export-templates/{template_id}")
async def delete_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Eliminar un template"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        repo = ExportTemplateRepository()
        
        if repo.delete_template(template_id, user["email"]):
            return {
                "success": True,
                "message": "Template eliminado exitosamente"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export-templates/{template_id}/duplicate")
async def duplicate_export_template(
    template_id: str,
    request_data: Dict[str, str],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Duplicar un template existente"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        new_name = request_data.get("name")
        if not new_name:
            raise HTTPException(status_code=400, detail="Nombre requerido para el template duplicado")
        
        repo = ExportTemplateRepository()
        new_template_id = repo.duplicate_template(template_id, new_name, user["email"])
        
        if new_template_id:
            return {
                "success": True,
                "template_id": new_template_id,
                "message": f"Template duplicado como '{new_name}'"
            }
        else:
            raise HTTPException(status_code=404, detail="Template original no encontrado")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export-templates/{template_id}/set-default")
async def set_default_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Establecer un template como por defecto"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        repo = ExportTemplateRepository()
        
        if repo.set_default_template(template_id, user["email"]):
            return {
                "success": True,
                "message": "Template establecido como por defecto"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estableciendo template por defecto {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/custom")
async def export_invoices_with_template(
    export_request: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Exportar facturas usando un template personalizado"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.modules.excel_exporter.template_exporter import ExcelExporter
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        
        template_id = export_request.get("template_id")
        filters = export_request.get("filters", {})
        filename = export_request.get("filename", f"facturas_custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        # Verificar si el plan del usuario permite exportación
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.repositories.user_repository import UserRepository
        
        owner = user.get("email", "").lower()
        user_repo = UserRepository()
        is_admin = user_repo.is_admin(owner)
        
        if not is_admin:
            sub_repo = SubscriptionRepository()
            subscription = await sub_repo.get_user_active_subscription(owner)
            
            # Formatos permitidos (por ahora solo excel)
            requested_format = "excel" if filename.endswith((".xlsx", ".xls")) else "unknown"
            
            if not subscription:
                # Usuario FREE: Permitir solo excel
                if requested_format != "excel":
                     raise HTTPException(status_code=403, detail="Tu plan no permite este formato de exportación.")
            else:
                plan_code = subscription.get("plan_code")
                plan = await sub_repo.get_plan_by_code(plan_code)
                if plan and plan.get("features"):
                    allowed = plan["features"].get("allowed_export_formats", ["excel"])
                    if requested_format not in allowed:
                        raise HTTPException(status_code=403, detail=f"El formato {requested_format} no está permitido en tu plan actual.")
        
        if not template_id:
            raise HTTPException(status_code=400, detail="template_id requerido")
        
        # Obtener template
        template_repo = ExportTemplateRepository()
        template = template_repo.get_template_by_id(template_id, user["email"])
        
        if not template:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
        # Obtener facturas
        invoice_repo = MongoInvoiceRepository()
        invoices_raw = invoice_repo.get_invoices_by_user(user["email"], filters)
        
        if not invoices_raw:
            raise HTTPException(status_code=404, detail="No se encontraron facturas con los filtros especificados")
        
        # Convertir diccionarios a InvoiceData
        invoices = [_mongo_doc_to_invoice_data(invoice) for invoice in invoices_raw]
        
        # Generar Excel
        exporter = ExcelExporter()
        excel_data = exporter.export_invoices(invoices, template)
        
        # Retornar archivo
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        return Response(
            content=excel_data,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exportando con template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# OBSERVABILIDAD - LOGS FRONTEND
# ================================

class FrontendLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    component: Optional[str] = None
    user_email: Optional[str] = None
    request_id: Optional[str] = None
    event_type: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None

class FrontendLogsPayload(BaseModel):
    logs: List[FrontendLogEntry]

@app.post("/logs/frontend")
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

@app.get("/metrics")
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

@app.get("/health")
async def health_check():
    """
    Health check endpoint para Kubernetes y monitoreo
    """
    try:
        # Verificar conexiones críticas
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "service": "cuenly-backend"
        }
        
        # Verificar conexión a MongoDB
        try:
            from app.repositories.user_repository import UserRepository
            user_repo = UserRepository()
            # Intento simple de conexión
            user_repo.collection.database.command("ismaster")
            health_status["mongodb"] = "connected"
        except Exception as e:
            health_status["mongodb"] = f"error: {str(e)}"
            health_status["status"] = "unhealthy"
        
        # Verificar límites de procesamiento
        try:
            health_status["processing_lock"] = "available" if not PROCESSING_LOCK.is_locked() else "locked"
        except:
            health_status["processing_lock"] = "unknown"
        
        status_code = 200 if health_status["status"] == "healthy" else 503
        
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            status_code=503
        )
