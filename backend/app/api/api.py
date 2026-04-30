"""
CuenlyApp API — punto de entrada FastAPI.

Crea la aplicación, configura middleware y monta todos los routers.
La lógica de cada dominio vive en app/api/routers/ y app/api/endpoints/.
"""
import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.utils.observability import observability_logger
from app.middleware.observability_middleware import ObservabilityMiddleware
from app.api.state import invoice_sync  # noqa: F401 — instancia global usada por routers

# ── Logging ──────────────────────────────────────────────────────────────────
observability_logger.setup_logging(level=settings.LOG_LEVEL)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("cuenlyapp_api.log")],
)
logger = logging.getLogger(__name__)

# ── Aplicación ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="CuenlyApp API",
    description="API para procesar facturas desde correo electrónico y almacenarlas en MongoDB",
    version="2.0.0",
)

# ── Rate limiter ─────────────────────────────────────────────────────────────
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.api.rate_limit import limiter, _ENABLED as _RATE_LIMITING_ENABLED

    if _RATE_LIMITING_ENABLED and limiter:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except Exception as _rl_err:
    logger.warning(f"⚠️ Rate limiting no configurado en app: {_rl_err}")

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.cuenly.com",
        "http://localhost:4200",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers existentes (endpoints/) ──────────────────────────────────────────
from app.api.endpoints import (
    pagopar,
    admin_subscriptions,
    subscriptions,
    admin_users,
    admin_plans,
    user_profile,
    queues,
    admin_ai_limits,
    admin_scheduler,
    admin_audit,
    admin_export_templates,
    admin_manage,
)

app.include_router(pagopar.router,                  prefix="/pagopar",                          tags=["Pagopar"])
app.include_router(admin_subscriptions.router,      prefix="/admin/subscriptions",              tags=["Admin Subscriptions"])
app.include_router(subscriptions.router,            prefix="/subscriptions",                    tags=["Subscriptions"])
app.include_router(admin_users.router,              prefix="/admin/users",                      tags=["Admin Users"])
app.include_router(admin_plans.router,              prefix="/admin/plans",                      tags=["Admin Plans"])
app.include_router(user_profile.router,             prefix="/user",                             tags=["User Profile"])
app.include_router(queues.router,                   prefix="/admin/queues",                     tags=["Admin Queues"])
app.include_router(admin_ai_limits.router,          prefix="/admin/ai-limits",                  tags=["Admin AI Limits"])
app.include_router(admin_scheduler.router,          prefix="/admin/scheduler",                  tags=["Admin Scheduler"])
app.include_router(admin_audit.router,              prefix="/admin/audit",                      tags=["Admin Audit"])
app.include_router(admin_export_templates.router,   prefix="/admin/export-templates/system",    tags=["Admin Export Templates"])
app.include_router(admin_manage.router,             prefix="/admin/admins",                     tags=["Admin Management"])

# ── Routers nuevos (routers/) ─────────────────────────────────────────────────
from app.api.routers import (
    user,
    processing,
    uploads,
    email_config,
    invoices,
    export_templates,
    dashboard,
    system,
    plans,
)

app.include_router(user.router,             prefix="", tags=["User"])
app.include_router(processing.router,       prefix="", tags=["Processing"])
app.include_router(uploads.router,          prefix="", tags=["Uploads"])
app.include_router(email_config.router,     prefix="", tags=["Email Config"])
app.include_router(invoices.router,         prefix="", tags=["Invoices"])
app.include_router(export_templates.router, prefix="", tags=["Export Templates"])
app.include_router(dashboard.router,        prefix="", tags=["Dashboard"])
app.include_router(system.router,           prefix="", tags=["System"])
app.include_router(plans.router,            prefix="", tags=["Plans"])


# ── Bootstrap admin ──────────────────────────────────────────────────────────
async def _bootstrap_admin() -> None:
    """Crea el admin inicial en Firestore si la colección está vacía."""
    bootstrap_email = getattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "")
    if not bootstrap_email:
        return
    try:
        from app.repositories.firestore_admin_repository import FirestoreAdminRepository
        repo = FirestoreAdminRepository()
        if repo.has_any_admin():
            logger.debug("Bootstrap admin: ya existe al menos un admin en Firestore, omitiendo")
            return
        success = repo.grant_admin(
            email=bootstrap_email,
            granted_by="bootstrap",
            notes="Admin inicial creado por BOOTSTRAP_ADMIN_EMAIL",
        )
        if success:
            logger.info("Bootstrap admin creado: %s", bootstrap_email)
    except Exception as e:
        logger.warning("Bootstrap admin falló (no crítico): %s", e)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Inicializa servicios cuando arranca el servidor FastAPI."""
    try:
        from app.modules.scheduler import ScheduledTasks
        ScheduledTasks().start_background_scheduler()
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

    await _bootstrap_admin()
