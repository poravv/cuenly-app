import os
import logging
import time
import signal
import threading
from typing import List, Dict, Any, Optional
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config.settings import settings
from app.models.models import InvoiceData, ProcessResult, EmailConfig, JobStatus
from app.modules.email_processor.email_processor import MultiEmailProcessor, EmailProcessor
from app.modules.openai_processor.openai_processor import OpenAIProcessor
from app.modules.scheduler.processing_lock import PROCESSING_LOCK
from app.core.redis_client import get_redis_client

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cuenlyapp.log")
    ]
)

logger = logging.getLogger(__name__)

def _now():
    """Fecha/hora actual en la zona configurada."""
    try:
        tz = ZoneInfo(getattr(settings, "TIMEZONE", "UTC"))
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)

class CuenlyApp:
    def __init__(self):
        """Inicializa el sistema de sincronización de facturas usando OpenAI."""
        # Crear directorios necesarios
        try:
            from app.modules.email_processor.storage import ensure_dirs
            ensure_dirs()
        except Exception:
            os.makedirs(settings.TEMP_PDF_DIR, exist_ok=True)
        # Directorio de Excel eliminado del flujo
        
        # Inicializar componentes
        # Usar MultiEmailProcessor si hay múltiples configuraciones de correo (desde MongoDB)
        try:
            from app.modules.email_processor.config_store import get_enabled_configs
            email_configs = get_enabled_configs(include_password=True)
        except Exception as e:
            logger.warning(f"No se pudieron cargar configuraciones de correo desde MongoDB: {e}")
            email_configs = []

        # Siempre usar MultiEmailProcessor para compatibilidad con jobs programados
        self.email_processor = MultiEmailProcessor()
        if len(email_configs) > 1:
            logger.info(f"Usando MultiEmailProcessor con {len(email_configs)} cuentas de correo")
        elif len(email_configs) == 1:
            logger.info("Usando MultiEmailProcessor para una sola cuenta de correo")
        else:
            logger.info("No hay cuentas configuradas aún. MultiEmailProcessor inicializado sin cuentas")
        
        self.openai_processor = OpenAIProcessor()
        
        # Persistencia unificada en esquema v2 (invoice_headers/items) mediante MongoInvoiceRepository
        # El exportador documental legacy (facturas_completas) ha sido deshabilitado
        self.mongodb_exporter = None
        
        # Guardar referencia a últimas facturas procesadas
        self._last_processed_invoices: List[InvoiceData] = []
        
        # Estado del job
        self._job_status = JobStatus(
            running=False,
            interval_minutes=settings.JOB_INTERVAL_MINUTES,
            next_run=None,
            last_run=None,
            last_result=None
        )
        self._job_enabled_key = "cuenly:job:enabled"
        self._job_owner_key = "cuenly:job:owner"
        self._job_owner_ttl_seconds = int(os.getenv("JOB_OWNER_TTL_SECONDS", "120"))
        self._pod_id = os.getenv("HOSTNAME", "local")
        
        
        # Estado por defecto seguro del job: desactivado.
        # Solo se restaura al boot si JOB_RESTORE_ON_BOOT=true.
        try:
            redis_client = get_redis_client()
            raw_enabled = redis_client.get(self._job_enabled_key)
            normalized_enabled = self._decode_redis_str(raw_enabled)
            if normalized_enabled is not None:
                normalized_enabled = normalized_enabled.lower()

            # Si no existe la clave, se fuerza explícitamente a false.
            if normalized_enabled is None:
                redis_client.set(self._job_enabled_key, "false")
                redis_client.delete(self._job_owner_key)
                normalized_enabled = "false"

            if settings.JOB_RESTORE_ON_BOOT and normalized_enabled == "true":
                if email_configs:
                    logger.info("🔄 Restaurando job programado desde estado persistente (JOB_RESTORE_ON_BOOT=true)...")
                    self.start_scheduled_job(restore=True)
                else:
                    logger.info("ℹ️ Se encontró job enabled=true pero no hay cuentas configuradas. Forzando enabled=false.")
                    redis_client.set(self._job_enabled_key, "false")
                    redis_client.delete(self._job_owner_key)
            elif normalized_enabled == "true":
                logger.info("ℹ️ Job persistido como enabled=true, pero JOB_RESTORE_ON_BOOT=false. Forzando enabled=false en arranque.")
                redis_client.set(self._job_enabled_key, "false")
                redis_client.delete(self._job_owner_key)
        except Exception as e:
            logger.warning(f"No se pudo restaurar estado de job desde Redis: {e}")
        
        logger.info("Sistema CuenlyApp inicializado correctamente")

    @staticmethod
    def _decode_redis_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return str(value, "utf-8").strip()
        return str(value).strip()

    def _redis_bool(self, value: Any, default: bool = False) -> bool:
        parsed = self._decode_redis_str(value)
        if parsed is None:
            return default
        return parsed.lower() in ("1", "true", "yes", "on")

    def _should_local_scheduler_continue(self) -> bool:
        """
        Verifica ownership global del scheduler para entornos con pods replicados.
        """
        try:
            redis_client = get_redis_client()
            enabled = self._redis_bool(redis_client.get(self._job_enabled_key), default=False)
            owner = self._decode_redis_str(redis_client.get(self._job_owner_key))
            if not enabled:
                return False
            if owner and owner != self._pod_id:
                return False
            if owner == self._pod_id:
                try:
                    redis_client.expire(self._job_owner_key, self._job_owner_ttl_seconds)
                except Exception:
                    pass
            return True
        except Exception:
            # En caso de falla temporal de Redis, no forzar stop inmediato.
            return True
    
    def process_emails(self) -> ProcessResult:
        """
        Procesa correos electrónicos para extraer facturas con timeout de seguridad.
        
        Returns:
            ProcessResult: Resultado del procesamiento.
        """
        logger.info("🚀 Iniciando procesamiento de correos con watchdog de seguridad")
        
        # Registrar inicio del procesamiento
        self._job_status.last_run = _now().isoformat()
        
        # Usar watchdog para evitar cuelgues indefinidos
        import queue
        result_queue = queue.Queue()
        
        def process_with_timeout():
            try:
                # Procesar correos serializadamente para evitar colisiones
                with PROCESSING_LOCK:
                    if hasattr(self.email_processor, 'process_all_emails'):
                        result = self.email_processor.process_all_emails()
                    else:
                        result = self.email_processor.process_emails()
                
                result_queue.put(('success', result))
                
            except Exception as e:
                logger.error(f"❌ Error en procesamiento: {e}")
                result_queue.put(('error', str(e)))
        
        # Ejecutar procesamiento en thread separado con timeout global
        process_thread = threading.Thread(target=process_with_timeout, daemon=True)
        process_thread.start()
        
        # Timeout global de 10 minutos para todo el procesamiento
        process_thread.join(timeout=600)
        
        if process_thread.is_alive():
            logger.error("❌ TIMEOUT GLOBAL: El procesamiento tomó más de 10 minutos. Abortando...")
            result = ProcessResult(
                success=False,
                message="Timeout global: El procesamiento fue abortado por seguridad (>10 min)",
                invoice_count=0,
                invoices=[]
            )
        else:
            # Obtener resultado del thread
            try:
                result_type, result_data = result_queue.get_nowait()
                if result_type == 'success':
                    result = result_data
                    
                    # Persistencia se realiza directamente durante el procesamiento vía repositorio v2
                    
                else:
                    result = ProcessResult(
                        success=False,
                        message=f"Error en procesamiento: {result_data}",
                        invoice_count=0,
                        invoices=[]
                    )
            except queue.Empty:
                result = ProcessResult(
                    success=False,
                    message="Error: No se pudo obtener resultado del procesamiento",
                    invoice_count=0,
                    invoices=[]
                )
        
        # Actualizar estado del job
        self._job_status.last_result = result
        
        return result

    def process_pdf(self, pdf_path: str, metadata: Dict[str, Any] = None) -> InvoiceData:
        """
        Procesa un archivo PDF para extraer datos de factura.
        
        Args:
            pdf_path: Ruta al archivo PDF.
            metadata: Metadatos adicionales.
            
        Returns:
            InvoiceData: Datos extraídos de la factura.
        """
        logger.info(f"Procesando PDF: {pdf_path}")
        # Serializar extracción para mantener coherencia con export posterior
        with PROCESSING_LOCK:
            invoice_data = self.openai_processor.extract_invoice_data(pdf_path, metadata)
            
            # Persistencia se realiza directamente vía repositorio v2 durante el flujo de EmailProcessor
            
            return invoice_data
    
    def start_scheduled_job(self, restore: bool = False) -> JobStatus:
        """
        Inicia el trabajo programado para procesar correos periódicamente.
        
        Returns:
            JobStatus: Estado actual del trabajo.
        """
        try:
            redis_client = get_redis_client()
            redis_enabled = self._redis_bool(redis_client.get(self._job_enabled_key), default=False)
            owner = self._decode_redis_str(redis_client.get(self._job_owner_key))

            # Si globalmente estaba apagado y quedó owner viejo, limpiar para evitar estado atascado.
            if not redis_enabled and owner:
                redis_client.delete(self._job_owner_key)
                owner = None

            # Si ya está habilitado globalmente y otro pod es dueño, no iniciar aquí.
            if redis_enabled and owner and owner != self._pod_id:
                logger.info(
                    "Job ya activo globalmente en otro pod (%s). Este pod (%s) no iniciará scheduler local.",
                    owner, self._pod_id
                )
                self._job_status.running = True
                return self._job_status

            # Intentar reclamar ownership si no existe dueño
            if not owner:
                claimed = bool(
                    redis_client.set(
                        self._job_owner_key,
                        self._pod_id,
                        nx=True,
                        ex=self._job_owner_ttl_seconds
                    )
                )
                if claimed:
                    owner = self._pod_id
                else:
                    owner = self._decode_redis_str(redis_client.get(self._job_owner_key))

            if owner and owner != self._pod_id:
                redis_client.set(self._job_enabled_key, "true")
                logger.info(
                    "Ownership del scheduler ya tomado por %s. Este pod (%s) no iniciará scheduler local.",
                    owner, self._pod_id
                )
                self._job_status.running = True
                return self._job_status

            # Este pod es owner
            if not self._job_status.running:
                self.email_processor.start_scheduled_job(
                    should_continue=self._should_local_scheduler_continue
                )
                self._job_status.running = True
                self._job_status.next_run = self._calculate_next_run()

            redis_client.set(self._job_enabled_key, "true")
            redis_client.set(self._job_owner_key, self._pod_id, ex=self._job_owner_ttl_seconds)
            logger.info(
                "Job programado iniciado por pod owner=%s. Próxima ejecución: %s",
                self._pod_id,
                self._job_status.next_run
            )
        except Exception as e:
            logger.warning(f"No se pudo coordinar start de job en Redis: {e}")
            if not self._job_status.running:
                self.email_processor.start_scheduled_job(
                    should_continue=self._should_local_scheduler_continue
                )
                self._job_status.running = True
                self._job_status.next_run = self._calculate_next_run()

        return self._job_status
    
    def stop_scheduled_job(self) -> JobStatus:
        """
        Detiene el trabajo programado.
        
        Returns:
            JobStatus: Estado actual del trabajo.
        """
        # Detener scheduler local si está corriendo en este pod
        if self._job_status.running:
            self.email_processor.stop_scheduled_job()
            logger.info("Job programado local detenido")

        self._job_status.running = False
        self._job_status.next_run = None
        self._job_status.next_run_ts = None

        # Persistir estado global SIEMPRE, incluso si el request llegó a un pod no-owner
        try:
            redis_client = get_redis_client()
            redis_client.set(self._job_enabled_key, "false")
            redis_client.delete(self._job_owner_key)
        except Exception as e:
            logger.warning(f"No se pudo persistir estado stop de job en Redis: {e}")

        return self._job_status
    
    def get_job_status(self) -> JobStatus:
        """
        Obtiene el estado actual del trabajo programado.
        
        Returns:
            JobStatus: Estado actual del trabajo.
        """
        # 1. Verificar fuente de verdad en Redis para entornos multi-pod
        redis_enabled = False
        redis_owner = None
        try:
            redis_client = get_redis_client()
            redis_enabled = self._redis_bool(redis_client.get(self._job_enabled_key), default=False)
            redis_owner = self._decode_redis_str(redis_client.get(self._job_owner_key))
            if not redis_enabled:
                # Si globalmente está apagado, forzar stop local (si aplica)
                if getattr(self._job_status, 'running', False) or (
                    hasattr(self.email_processor, 'scheduled_job_status')
                    and self.email_processor.scheduled_job_status().get('running', False)
                ):
                    try:
                        if hasattr(self.email_processor, 'stop_scheduled_job'):
                            self.email_processor.stop_scheduled_job()
                    except Exception:
                        pass
                self._job_status.running = False
                self._job_status.next_run = None
                self._job_status.next_run_ts = None
        except Exception as e:
            logger.warning(f"No se pudo verificar estado de Redis en get_job_status: {e}")
            
        # 2. VERIFICAR SI HAY CUALQUIER PROCESAMIENTO ACTIVO (Global flag)
        try:
            from app.modules.scheduler.task_queue import task_queue
            active_tasks = 0
            with task_queue._lock:
                for job in task_queue._jobs.values():
                    if job.get('status') in ('running', 'queued', 'pending'): active_tasks += 1
            self._job_status.is_processing = (active_tasks > 0)
        except Exception as e:
            logger.warning(f"No se pudo verificar task_queue en get_job_status: {e}")

        # 3. Preferir estado real reportado por el scheduler si está disponible
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(getattr(settings, "TIMEZONE", "UTC"))
        except Exception:
            from datetime import timezone
            tz = timezone.utc

        local_running = False
        if hasattr(self.email_processor, 'scheduled_job_status'):
            sched = self.email_processor.scheduled_job_status()
            if isinstance(sched, dict) and sched:
                local_running = bool(sched.get('running', False))

                # Auto-heal: si el job está habilitado globalmente pero no hay owner,
                # este pod puede reclamar ownership y arrancar scheduler local.
                if redis_enabled and not redis_owner and not local_running:
                    try:
                        redis_client = get_redis_client()
                        claimed = bool(
                            redis_client.set(
                                self._job_owner_key,
                                self._pod_id,
                                nx=True,
                                ex=self._job_owner_ttl_seconds
                            )
                        )
                        if claimed:
                            self.email_processor.start_scheduled_job(
                                should_continue=self._should_local_scheduler_continue
                            )
                            local_running = True
                            logger.info("Auto-heal scheduler: ownership reclamado por pod %s", self._pod_id)
                    except Exception as e:
                        logger.warning(f"No se pudo ejecutar auto-heal del scheduler: {e}")

                self._job_status.running = bool(redis_enabled or local_running)
                
                def _to_iso(v):
                    try:
                        if v is None: return None
                        if isinstance(v, (int, float)):
                            return datetime.fromtimestamp(v, tz).isoformat()
                        dt = datetime.fromisoformat(str(v))
                        if dt.tzinfo is None: dt = dt.replace(tzinfo=tz)
                        else: dt = dt.astimezone(tz)
                        return dt.isoformat()
                    except Exception: return None

                next_iso = _to_iso(sched.get('next_run'))
                last_iso = _to_iso(sched.get('last_run'))
                self._job_status.next_run = next_iso
                self._job_status.last_run = last_iso

                try:
                    nr = sched.get('next_run')
                    if isinstance(nr, (int, float)): self._job_status.next_run_ts = int(nr)
                    elif next_iso: self._job_status.next_run_ts = int(datetime.fromisoformat(next_iso).timestamp())
                except Exception: pass

                try:
                    lr = sched.get('last_run')
                    if isinstance(lr, (int, float)): self._job_status.last_run_ts = int(lr)
                    elif last_iso: self._job_status.last_run_ts = int(datetime.fromisoformat(last_iso).timestamp())
                except Exception: pass

                self._job_status.interval_minutes = int(sched.get('interval_minutes', self._job_status.interval_minutes))
                self._job_status.last_result = sched.get('last_result')
            else:
                self._job_status.running = bool(redis_enabled)
                if self._job_status.running:
                    next_iso = self._calculate_next_run()
                    self._job_status.next_run = next_iso
                    try:
                        self._job_status.next_run_ts = int(datetime.fromisoformat(next_iso).timestamp()) if next_iso else None
                    except Exception: pass

        # 4. Watchdog: si está running pero el siguiente run está muy vencido, marcar como detenido
        try:
            now_ts = int(_now().timestamp())
            interval_sec = max(60, int(self._job_status.interval_minutes) * 60)
            if local_running and self._job_status.running and self._job_status.next_run_ts:
                drift = now_ts - self._job_status.next_run_ts
                if drift > interval_sec * 2:
                    logger.warning(f"Job scheduler zombie detectado. Drift: {drift}s")
                    try:
                        if hasattr(self.email_processor, 'stop_scheduled_job'):
                            self.email_processor.stop_scheduled_job()
                    except Exception: pass
                    self._job_status.running = False
                    self._job_status.next_run = None
                    self._job_status.next_run_ts = None
        except Exception: pass
        
        return self._job_status

    def update_job_interval(self, minutes: int) -> JobStatus:
        try:
            minutes = max(1, int(minutes))
        except Exception:
            minutes = self._job_status.interval_minutes

        # delegar al procesador subyacente
        if hasattr(self.email_processor, 'set_interval_minutes'):
            self.email_processor.set_interval_minutes(minutes)
        # actualizar estado interno
        self._job_status.interval_minutes = minutes
        return self.get_job_status()
    
    def _calculate_next_run(self) -> str:
        """
        Calcula el tiempo de la próxima ejecución del job.
        
        Returns:
            str: Tiempo de la próxima ejecución en formato ISO.
        """
        # Estimación simple basada en el intervalo actualmente reportado por el job
        now = _now()
        next_run = now.replace(second=0, microsecond=0)
        
        # Añadir los minutos del intervalo (preferir el estado interno si existe)
        from datetime import timedelta
        interval = getattr(self._job_status, 'interval_minutes', None) or settings.JOB_INTERVAL_MINUTES
        try:
            interval = max(1, int(interval))
        except Exception:
            interval = settings.JOB_INTERVAL_MINUTES
        next_run += timedelta(minutes=interval)
        
        return next_run.isoformat()

def main():
    """Función principal para ejecutar desde línea de comandos."""
    parser = argparse.ArgumentParser(description="CuenlyApp: Sincronización de facturas desde correo")
    parser.add_argument("--process", action="store_true", help="Procesar correos")
    parser.add_argument("--start-job", action="store_true", help="Iniciar job programado")
    parser.add_argument("--stop-job", action="store_true", help="Detener job programado")
    parser.add_argument("--status", action="store_true", help="Mostrar estado")
    
    args = parser.parse_args()
    
    cuenlyapp = CuenlyApp()
    
    if args.process:
        result = cuenlyapp.process_emails()
        print(f"Resultado: {result.success}")
        print(f"Mensaje: {result.message}")
        print(f"Facturas procesadas: {result.invoice_count}")
    
    elif args.start_job:
        status = cuenlyapp.start_scheduled_job()
        print(f"Job iniciado: {status.running}")
        print(f"Próxima ejecución: {status.next_run}")
        
        # Mantener proceso vivo
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Deteniendo job...")
            cuenlyapp.stop_scheduled_job()
    
    elif args.stop_job:
        status = cuenlyapp.stop_scheduled_job()
        print(f"Job detenido: {not status.running}")
    
    elif args.status:
        status = cuenlyapp.get_job_status()
        print(f"Job activo: {status.running}")
        print(f"Próxima ejecución: {status.next_run}")
        print(f"Última ejecución: {status.last_run}")
        if status.last_result:
            print(f"Último resultado: {status.last_result.message}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
