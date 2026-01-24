import os
import time
import logging
from typing import List, Tuple, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config.settings import settings
from app.models.models import EmailConfig, MultiEmailConfig, InvoiceData, ProcessResult
from app.modules.openai_processor.openai_processor import OpenAIProcessor

from .single_processor import EmailProcessor
from .config_store import get_enabled_configs
from .dedup import deduplicate_invoices
from .storage import ensure_dirs
from app.modules.scheduler.job_runner import ScheduledJobRunner

logger = logging.getLogger(__name__)


# =========================
#  MultiEmailProcessor
# =========================
class MultiEmailProcessor:
    """
    Orquestador multi-cuenta. Mantiene la funcionalidad anterior pero delega
    en EmailProcessor para cada cuenta. Incluye job programado.
    """
    def __init__(self, email_configs: List[MultiEmailConfig] = None, owner_email: Optional[str] = None):
        if email_configs is None:
            try:
                configs_data = get_enabled_configs(include_password=True)
            except Exception as e:
                logger.error(f"Error cargando configuraciones de correo desde MongoDB: {e}")
                configs_data = []
            self.email_configs = [MultiEmailConfig(**cfg) for cfg in configs_data]
        else:
            self.email_configs = email_configs

        self.openai_processor = OpenAIProcessor()
        self.owner_email = (owner_email or '').lower() if owner_email else ''

        ensure_dirs()

        # Scheduler moderno (ScheduledJobRunner)
        self._scheduler: Optional[ScheduledJobRunner] = None

        logger.info(f"✅ MultiEmailProcessor inicializado con {len(self.email_configs)} cuentas de correo")

    def process_all(self) -> Dict[str, Any]:
        """Método breve para un endpoint /run-once (compat)."""
        res = self.process_all_emails()
        return res.dict() if hasattr(res, "dict") else {
            "success": res.success, "message": res.message, "invoice_count": res.invoice_count
        }

    def _remove_duplicate_invoices(self, invoices: List[InvoiceData]) -> List[InvoiceData]:
        return deduplicate_invoices(invoices)

    def process_limited_emails(self, limit: int = 10, ignore_date_filter: bool = False, 
                                start_date: Optional[str] = None, end_date: Optional[str] = None) -> ProcessResult:
        """Procesa un número limitado de correos para procesamiento manual"""
        logger.info(f"🔄 Iniciando procesamiento manual limitado a {limit} facturas")
        
        all_invoices: List[InvoiceData] = []
        success_count = 0
        errors: List[str] = []
        total_processed = 0
        remaining_emails = 0
        
        if not self.email_configs:
            return ProcessResult(
                success=False,
                message="No hay cuentas de correo configuradas",
                invoice_count=0,
                invoices=[]
            )
        
        # ✅ FILTRAR USUARIOS QUE ALCANZARON LÍMITE DE IA
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        filtered_configs = []
        
        for cfg in self.email_configs:
            if cfg.owner_email:
                ai_check = user_repo.can_use_ai(cfg.owner_email)
                if not ai_check['can_use']:
                    logger.warning(f"⏭️ Omitiendo cuenta {cfg.username} (owner: {cfg.owner_email}) - {ai_check['message']}")
                    errors.append(f"Cuenta {cfg.username}: {ai_check['message']}")
                    continue
            filtered_configs.append(cfg)
        
        if not filtered_configs:
            return ProcessResult(
                success=False,
                message="No hay cuentas con acceso a IA disponible. Todos los usuarios han alcanzado su límite.",
                invoice_count=0,
                invoices=[]
            )
        
        self.email_configs = filtered_configs

        for idx, cfg in enumerate(self.email_configs):
            if total_processed >= limit:
                break
                
            logger.info(f"Procesando cuenta {idx + 1}/{len(self.email_configs)}: {cfg.username}")
            
            try:
                # Crear procesador para esta cuenta
                single = EmailProcessor(EmailConfig(
                    host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                    search_criteria=cfg.search_criteria, search_terms=cfg.search_terms or [],
                    auth_type=cfg.auth_type, access_token=cfg.access_token,
                    refresh_token=cfg.refresh_token, token_expiry=cfg.token_expiry
                ), owner_email=cfg.owner_email)
                
                # Conectar y buscar correos
                if not single.connect():
                    errors.append(f"Error conectando a {cfg.username}")
                    continue
                
                # Buscar correos disponibles
                # Aplicar límite de IA estricto en la selección de correos a procesar
                current_limit = limit
                if hasattr(self, 'max_ai_process') and self.max_ai_process is not None:
                     current_limit = min(limit, self.max_ai_process)
                     logger.info(f"🔒 Aplicando límite estricto de IA para cuenta {cfg.username}: máx {self.max_ai_process} correos")

                # Si el límite es 0, no procesar nada (salvo que sea XML puro, pero por seguridad paramos)
                if current_limit <= 0:
                    logger.warning(f"🛑 Cuenta {cfg.username} omitida: Límite de IA alcanzado o 0 restante.")
                    continue

                email_ids = single.search_emails(ignore_date_filter=ignore_date_filter, start_date=start_date, end_date=end_date)
                if not email_ids:
                    single.disconnect()
                    continue
                
                # Calcular cuántos correos procesar de esta cuenta
                emails_to_process = min(len(email_ids), limit - total_processed)
                remaining_emails += len(email_ids) - emails_to_process
                
                logger.info(f"📮 Encontrados {len(email_ids)} correos, procesando {emails_to_process}")
                
                # Procesar solo los correos necesarios
                account_invoices = []
                for i in range(emails_to_process):
                    try:
                        invoice = single._process_single_email(email_ids[i])
                        if invoice:
                            single._store_invoice_v2(invoice)
                            account_invoices.append(invoice)
                            total_processed += 1
                            logger.info(f"✅ Factura {total_processed}/{limit}: {invoice.numero_factura}")
                        
                        # Marcar como leído
                        try:
                            single.mark_as_read(email_ids[i])
                        except:
                            logger.warning(f"⚠️ No se pudo marcar correo como leído")
                            
                    except Exception as e:
                        logger.error(f"Error procesando correo individual: {e}")
                
                single.disconnect()
                all_invoices.extend(account_invoices)
                success_count += 1
                
            except Exception as e:
                errors.append(f"Error en cuenta {cfg.username}: {str(e)}")
                logger.error(f"❌ Error procesando cuenta {cfg.username}: {e}")

        # Preparar mensaje de resultado
        message_parts = [f"Procesamiento manual completado: {total_processed} facturas procesadas"]
        if remaining_emails > 0:
            message_parts.append(f"Quedan {remaining_emails} correos más por procesar")
        if errors:
            message_parts.append(f"Errores en {len(errors)} cuentas")
            
        return ProcessResult(
            success=True,
            message=". ".join(message_parts),
            invoice_count=total_processed,
            invoices=all_invoices
        )

    def process_all_emails(self, start_date=None, end_date=None) -> ProcessResult:
        # Refrescar configuración en cada corrida para reflejar cambios dinámicos desde el frontend
        # Usar check_trial=True para que automáticamente filtre usuarios con trial expirado
        try:
            configs_data = get_enabled_configs(include_password=True, check_trial=True)
            self.email_configs = [MultiEmailConfig(**cfg) for cfg in configs_data]
        except Exception as e:
            logger.warning(f"No se pudo refrescar configuraciones desde MongoDB: {e}")
        
        # ✅ FILTRAR USUARIOS QUE ALCANZARON LÍMITE DE IA
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        filtered_configs = []
        skipped_ai_limit = 0
        
        for cfg in self.email_configs:
            if cfg.owner_email:
                ai_check = user_repo.can_use_ai(cfg.owner_email)
                if not ai_check['can_use']:
                    # Si la razón es límite alcanzado, pero es procesamiento XML, podríamos permitirlo.
                    # PERO, el requerimiento es blindar el límite.
                    logger.warning(f"⏭️ Omitiendo cuenta {cfg.username} (owner: {cfg.owner_email}) - {ai_check['message']}")
                    skipped_ai_limit += 1
                    continue
                
                # Calcular límite restante para limitar el lote
                trial_info = user_repo.get_trial_info(cfg.owner_email)
                if not trial_info.get('is_trial_user', False) and trial_info.get('ai_invoices_limit', 0) == -1:
                    # Ilimitado
                    pass
                else:
                    limit_total = trial_info.get('ai_invoices_limit', 50)
                    used = trial_info.get('ai_invoices_processed', 0)
                    remaining = max(0, limit_total - used)
                    
                    if remaining == 0:
                        logger.warning(f"⏭️ Omitiendo cuenta {cfg.username} - Cupo IA agotado ({used}/{limit_total})")
                        skipped_ai_limit += 1
                        continue
                    
                    # Guardar remaining en la config para uso posterior si fuera necesario
                    cfg.ai_remaining = remaining

            filtered_configs.append(cfg)
        
        self.email_configs = filtered_configs
        
        all_invoices: List[InvoiceData] = []
        success_count = 0
        errors: List[str] = []
        
        logger.info(f"Iniciando procesamiento de {len(self.email_configs)} cuentas de correo (filtradas por trial válido y límite IA)")
        if skipped_ai_limit > 0:
            logger.info(f"⏭️ {skipped_ai_limit} cuentas omitidas por límite de IA alcanzado")

        if not self.email_configs:
            return ProcessResult(
                success=False,
                message="No hay cuentas de correo configuradas con acceso válido. Usuarios con trial expirado o límite de IA alcanzado han sido omitidos.",
                invoice_count=0,
                invoices=[]
            )

        # ✅ PROCESAMIENTO PARALELO OPTIMIZADO
        use_parallel = getattr(settings, 'ENABLE_PARALLEL_PROCESSING', True)
        max_workers = getattr(settings, 'MAX_CONCURRENT_ACCOUNTS', 10)
        
        if use_parallel and len(self.email_configs) > 1:
            logger.info(f"🚀 Procesamiento paralelo habilitado: {max_workers} cuentas simultáneas")
            
            def process_single_account(cfg: MultiEmailConfig, limit_override: Optional[int] = None) -> Tuple[bool, ProcessResult, str]:
                """Procesa una cuenta individual y retorna resultado"""
                try:
                    single = EmailProcessor(EmailConfig(
                        host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                        search_criteria=cfg.search_criteria, search_terms=cfg.search_terms or [],
                        auth_type=cfg.auth_type, access_token=cfg.access_token,
                        refresh_token=cfg.refresh_token, token_expiry=cfg.token_expiry
                    ), owner_email=cfg.owner_email)
                    
                    # Pasar límite estricto y fechas si existen
                    result = single.process_emails(max_ai_process=limit_override, start_date=start_date, end_date=end_date)
                    return (True, result, cfg.username)
                except Exception as e:
                    error_msg = f"Error procesando {cfg.username}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    return (False, ProcessResult(success=False, message=str(e), invoice_count=0, invoices=[]), cfg.username)
            
            # Ejecutar en paralelo con ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EmailProc") as executor:
                # Enviar todas las tareas (pasando remaining si existe)
                future_to_config = {}
                for cfg in self.email_configs:
                    limit_override = getattr(cfg, 'ai_remaining', None)
                    future = executor.submit(process_single_account, cfg, limit_override)
                    future_to_config[future] = cfg
                
                # Procesar resultados a medida que completan
                for idx, future in enumerate(as_completed(future_to_config), 1):
                    cfg = future_to_config[future]
                    try:
                        is_success, result, username = future.result(timeout=300)  # 5 min timeout por cuenta
                        
                        logger.info(f"✅ Completada cuenta {idx}/{len(self.email_configs)}: {username}")
                        
                        if is_success and result.success:
                            success_count += 1
                            # Validar facturas
                            valid_invoices = []
                            for invoice in result.invoices:
                                if isinstance(invoice, str):
                                    logger.error(f"❌ Factura inválida (string): {invoice[:100]}...")
                                    continue
                                elif hasattr(invoice, '__dict__'):
                                    valid_invoices.append(invoice)
                                else:
                                    logger.error(f"❌ Factura de tipo inválido: {type(invoice)}")
                                    continue
                            
                            all_invoices.extend(valid_invoices)
                            logger.info(f"✅ Cuenta {username}: {len(valid_invoices)} facturas válidas procesadas")
                        else:
                            errors.append(f"Error en {username}: {result.message}")
                            logger.error(f"❌ Error en cuenta {username}: {result.message}")
                            
                    except TimeoutError:
                        errors.append(f"Timeout en {cfg.username}: procesamiento tomó más de 300 segundos")
                        logger.error(f"❌ Timeout al procesar cuenta {cfg.username}")
                    except Exception as e:
                        errors.append(f"Error en {cfg.username}: {str(e)}")
                        logger.error(f"❌ Error al procesar cuenta {cfg.username}: {str(e)}")
        else:
            # Procesamiento secuencial (fallback o configuración deshabilitada)
            logger.info(f"📋 Procesamiento secuencial: {len(self.email_configs)} cuentas")
            
            for idx, cfg in enumerate(self.email_configs):
                logger.info(f"Procesando cuenta {idx + 1}/{len(self.email_configs)}: {cfg.username}")
                
                if idx > 0:
                    time.sleep(2)  # Pausa entre cuentas
                
                try:
                    single = EmailProcessor(EmailConfig(
                        host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                        search_criteria=cfg.search_criteria, search_terms=cfg.search_terms or [],
                        auth_type=cfg.auth_type, access_token=cfg.access_token,
                        refresh_token=cfg.refresh_token, token_expiry=cfg.token_expiry
                    ), owner_email=cfg.owner_email)
                    
                    r = single.process_emails()
                    
                    if r.success:
                        success_count += 1
                        valid_invoices = [inv for inv in r.invoices if hasattr(inv, '__dict__')]
                        all_invoices.extend(valid_invoices)
                        logger.info(f"✅ Cuenta {cfg.username}: {len(valid_invoices)} facturas")
                    else:
                        errors.append(f"Error en {cfg.username}: {r.message}")
                        logger.error(f"❌ {cfg.username}: {r.message}")
                        
                except Exception as e:
                    errors.append(f"Error en {cfg.username}: {str(e)}")
                    logger.error(f"❌ Error en {cfg.username}: {str(e)}")

        if all_invoices:
            unique = self._remove_duplicate_invoices(all_invoices)
            logger.info(f"Facturas únicas después de eliminar duplicados: {len(unique)} (originales: {len(all_invoices)})")
            # La persistencia ya se realizó por-correo en _store_invoice_v2; evitar doble guardado
            all_invoices = unique

        if success_count == len(self.email_configs):
            message = f"Procesamiento exitoso de {len(self.email_configs)} cuentas. {len(all_invoices)} facturas encontradas."
        elif success_count > 0:
            message = f"Procesamiento parcial: {success_count}/{len(self.email_configs)} cuentas exitosas. {len(all_invoices)} facturas encontradas."
        else:
            message = f"Fallo en todas las cuentas. Errores: {'; '.join(errors)}"

        # Adjuntar información de export a MongoDB si está disponible
        try:
            if 'message_suffix' in locals() and message_suffix:
                message += message_suffix
        except Exception:
            pass

        # Excel deshabilitado

        return ProcessResult(
            success=success_count > 0,
            message=message,
            invoice_count=len(all_invoices),
            invoices=all_invoices
        )

    # ------------------------------------------
    # Scheduler Moderno (ScheduledJobRunner)
    # ------------------------------------------
    def start_scheduled_job(self):
        """
        Mantiene el nombre que espera tu API.
        Inicia un runner que ejecuta process_all_emails() cada X minutos.
        """
        try:
            interval = settings.JOB_INTERVAL_MINUTES
        except Exception:
            interval = 60

        if self._scheduler and self._scheduler.is_running:
            # ya está corriendo; no lo dupliques
            logger.info("start_scheduled_job: ya en ejecución")
            return {"ok": True, "message": "El job ya está en ejecución."}

        self._scheduler = ScheduledJobRunner(
            interval_minutes=interval,
            target=self.process_all_emails
        )
        self._scheduler.start()
        logger.info(f"start_scheduled_job: iniciado (cada {interval} min)")
        return {"ok": True, "message": f"Job iniciado. Intervalo: {interval} minutos."}

    def stop_scheduled_job(self):
        """
        Detiene el job programado si está en ejecución.
        """
        if self._scheduler and self._scheduler.is_running:
            self._scheduler.stop()
            logger.info("stop_scheduled_job: detenido")
            return {"ok": True, "message": "Job detenido."}
        logger.info("stop_scheduled_job: no había job en ejecución")
        return {"ok": True, "message": "No había job en ejecución."}

    def scheduled_job_status(self):
        """
        Snapshot simple del runner moderno (opcional para /job/status).
        """
        # Si el hilo murió inesperadamente, reflejarlo como detenido
        if self._scheduler and not self._scheduler.is_alive():
            logger.warning("Scheduler thread no está vivo; marcando como detenido.")
            try:
                self._scheduler.stop()
            except Exception:
                pass

        if not self._scheduler or not self._scheduler.is_running:
            return {
                "running": False,
                "next_run": None,
                "last_run": None,
                "interval_minutes": settings.JOB_INTERVAL_MINUTES,
                "last_result": None
            }
        return {
            "running": True,
            "next_run": self._scheduler.next_run,
            "last_run": self._scheduler.last_run,
            "interval_minutes": settings.JOB_INTERVAL_MINUTES,
            "last_result": getattr(self._scheduler, "last_result", None)
        }

    def set_interval_minutes(self, minutes: int):
        try:
            minutes = max(1, int(minutes))
        except Exception:
            minutes = settings.JOB_INTERVAL_MINUTES
        settings.JOB_INTERVAL_MINUTES = minutes
        if self._scheduler and self._scheduler.is_running:
            # actualizar intervalo en caliente
            self._scheduler.interval_minutes = minutes
        return {"ok": True, "interval_minutes": minutes}
