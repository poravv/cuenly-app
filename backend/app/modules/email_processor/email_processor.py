import os
import re
import time
import threading
import logging
import queue
import pickle
import email.utils
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config.settings import settings
from app.models.models import EmailConfig, MultiEmailConfig, InvoiceData, ProcessResult
from app.modules.openai_processor.openai_processor import OpenAIProcessor
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.mapping.invoice_mapping import map_invoice


from app.modules.email_processor.errors import OpenAIFatalError, OpenAIRetryableError

from .imap_client import IMAPClient, decode_mime_header
from .link_extractor import extract_links_from_message
from .downloader import download_pdf_from_url
from .storage import save_binary, sanitize_filename, ensure_dirs
from .connection_pool import get_imap_pool
from .config_store import get_enabled_configs


from .dedup import deduplicate_invoices
from .processed_registry import build_key as build_processed_key, was_processed, mark_processed

# NUEVO runner thread-safe (sincroniza con tu API /job/start)
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

    def process_limited_emails(self, limit: int = 10) -> ProcessResult:
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
                email_ids = single.search_emails()
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

    def process_all_emails(self) -> ProcessResult:
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
                    logger.warning(f"⏭️ Omitiendo cuenta {cfg.username} (owner: {cfg.owner_email}) - {ai_check['message']}")
                    skipped_ai_limit += 1
                    continue
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
            
            def process_single_account(cfg: MultiEmailConfig) -> Tuple[bool, ProcessResult, str]:
                """Procesa una cuenta individual y retorna resultado"""
                try:
                    single = EmailProcessor(EmailConfig(
                        host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                        search_criteria=cfg.search_criteria, search_terms=cfg.search_terms or [],
                        auth_type=cfg.auth_type, access_token=cfg.access_token,
                        refresh_token=cfg.refresh_token, token_expiry=cfg.token_expiry
                    ), owner_email=cfg.owner_email)
                    result = single.process_emails()
                    return (True, result, cfg.username)
                except Exception as e:
                    error_msg = f"Error procesando {cfg.username}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    return (False, ProcessResult(success=False, message=str(e), invoice_count=0, invoices=[]), cfg.username)
            
            # Ejecutar en paralelo con ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EmailProc") as executor:
                # Enviar todas las tareas
                future_to_config = {executor.submit(process_single_account, cfg): cfg for cfg in self.email_configs}
                
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


# =========================
#  EmailProcessor (single)
# =========================
class EmailProcessor:
    """
    Procesador de correos para una cuenta IMAP específica.
    Separa responsabilidades: IMAP, parseo, guardado adjuntos, links y envío a OpenAI.
    """
    def __init__(self, config: EmailConfig = None, owner_email: Optional[str] = None):
        self.owner_email = (owner_email or '').lower() if owner_email else ''
        
        if config is None:
            # Obtener primera configuración habilitada desde MongoDB
            try:
                configs = get_enabled_configs(include_password=True)
            except Exception as e:
                logger.error(f"Error obteniendo configuraciones IMAP desde MongoDB: {e}")
                configs = []
            if configs:
                first = configs[0]
                self.config = EmailConfig(
                    host=first.get("host"),
                    port=int(first.get("port", 993)),
                    username=first.get("username"),
                    password=first.get("password", ""),
                    search_criteria=first.get("search_criteria", "UNSEEN"),
                    search_terms=first.get("search_terms") or [],
                    auth_type=first.get("auth_type", "password"),
                    access_token=first.get("access_token"),
                    refresh_token=first.get("refresh_token"),
                    token_expiry=first.get("token_expiry")
                )
            else:
                raise ValueError("No hay configuraciones de correo habilitadas en la base de datos")
        else:
            self.config = config

        # Usar pool de conexiones en lugar de cliente directo
        self.connection_pool = get_imap_pool()
        self.current_connection = None
        
        # Detectar tipo de autenticación OAuth vs password
        auth_type = getattr(self.config, 'auth_type', 'password')
        access_token = getattr(self.config, 'access_token', None) if auth_type == 'oauth2' else None
        
        # Mantener cliente legacy para compatibilidad (puede removerse después)
        self.client = IMAPClient(
            host=self.config.host, 
            port=self.config.port,
            username=self.config.username, 
            password=self.config.password or "", 
            mailbox="INBOX",
            auth_type=auth_type,
            access_token=access_token
        )
        self.openai_processor = OpenAIProcessor()
        # Estado para scheduler legacy
        self._last_run_iso: Optional[str] = None

        ensure_dirs()
        auth_method = "OAuth2" if auth_type == "oauth2" else "password"
        logger.info(f"✅ EmailProcessor inicializado con pool de conexiones para {self.config.username} (auth={auth_method})")

    # --------- IMAP high-level con pool ---------
    def connect(self) -> bool:
        """Obtiene conexión del pool o crea una nueva."""
        if self.current_connection and self.current_connection.test_connection():
            return True
        
        self.current_connection = self.connection_pool.get_connection(self.config)
        if self.current_connection:
            logger.info(f"🔄 Conexión IMAP obtenida del pool para {self.config.username}")
            return True
        
        logger.error(f"❌ No se pudo obtener conexión IMAP para {self.config.username}")
        return False

    def disconnect(self):
        """Devuelve conexión al pool en lugar de cerrarla."""
        if self.current_connection:
            if self.connection_pool.return_connection(self.current_connection):
                logger.debug(f"↩️ Conexión devuelta al pool para {self.config.username}")
            else:
                logger.warning(f"⚠️ No se pudo devolver conexión al pool para {self.config.username}")
            self.current_connection = None

    def mark_as_read(self, email_uid: str) -> bool:
        """Marca un correo como leído por UID usando el cliente IMAP subyacente."""
        try:
            # Asegurar que exista conexión en el cliente legacy
            if not self.client.conn:
                # Si no hay conexión establecida, intenta conectar
                self.client.connect()
            return self.client.mark_seen(email_uid)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo marcar correo {email_uid} como leído: {e}")
            return False

    def _email_key(self, email_id: str) -> str:
        return build_processed_key(email_id, getattr(self.config, "username", ""), self.owner_email)

    def _mark_email_processed(self, email_id: str, status: str = "success") -> None:
        try:
            # Pass explicit arguments to the new Mongo repository method
            # status can be: success, skipped_ai_limit, error, xml, pdf
            # reason is inferred from status usually, or passed if we change signature
            from app.modules.email_processor.processed_registry import _repo
            _repo.mark_processed(
                key=self._email_key(email_id),
                status=status,
                owner_email=self.owner_email,
                account_email=self.config.username
            )
        except Exception as e:
            logger.debug(f"Registro de correo procesado falló ({email_id}): {e}")

    def _get_imap_connection(self):
        """Obtiene la conexión IMAP actual."""
        if self.current_connection:
            return self.current_connection.connection
        return None

    # --------- Search logic ---------
    def search_emails(self, ignore_date_filter: bool = False) -> List[str]:
        """
        Usa IMAPClient.search(subject_terms) que devuelve UIDs (str).
        NOTA: los términos en .env deben venir SIN acentos (como acordamos).
        Filtra correos por fecha de registro del usuario, a menos que ignore_date_filter=True.
        """
        if not self.client.conn:
            if not self.connect():
                return []

        terms = self.config.search_terms or []
        if not terms:
            logger.info("No se configuraron términos de búsqueda. Se devolverá lista vacía.")
            return []

        # Obtener fecha de inicio de procesamiento para este usuario
        # Filtro de fecha de procesamiento configurable
        start_date = None
        
        # Verificar si debe aplicar filtro de fecha (configurable)
        from app.config.settings import settings
        if not ignore_date_filter and not settings.EMAIL_PROCESS_ALL_DATES and self.owner_email:
            try:
                from app.repositories.user_repository import UserRepository
                user_repo = UserRepository()
                start_date = user_repo.get_email_processing_start_date(self.owner_email)
                if start_date:
                    logger.info(f"📅 Filtrando correos desde: {start_date.strftime('%Y-%m-%d %H:%M:%S')} para usuario {self.owner_email}")
            except Exception as e:
                logger.warning(f"No se pudo obtener fecha de inicio para {self.owner_email}: {e}")
        else:
            logger.info(f"📮 Procesando TODOS los correos sin restricción de fecha (EMAIL_PROCESS_ALL_DATES=true)")
        
        # Pasamos la lista de términos directamente al nuevo IMAPClient.search()
        unread_only = (str(self.config.search_criteria or 'UNSEEN').upper() != 'ALL')
        uids = self.client.search(terms, unread_only=unread_only, since_date=start_date)

        logger.info(f"Se encontraron {len(uids)} correos combinando términos: {terms}" + 
                   (f" desde {start_date.strftime('%Y-%m-%d')}" if start_date else " (sin restricción de fecha)"))
        return uids

    # --------- Fetch + parse ---------
    def get_email_content(self, email_id: str) -> Tuple[dict, list]:
        """
        Extrae subject/sender/date + adjuntos PDF/XML y links candidatos.
        """
        if not self.client.conn and not self.connect():
            return {}, []
        message = self.client.fetch_message(email_id)
        if not message:
            return {}, []

        subject = decode_mime_header(message.get("Subject", ""))
        sender = decode_mime_header(message.get("From", ""))
        date_str = message.get("Date", "")

        dt = None
        if date_str:
            import email as pyemail
            try:
                dt = email.utils.parsedate_to_datetime(date_str)
            except Exception as e:
                logger.warning(f"⚠️ Error al parsear fecha '{date_str}': {e}")

        meta = {"subject": subject, "sender": sender, "date": dt, "message_id": email_id}
        attachments = []
        links = extract_links_from_message(message)

        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = part.get_filename()
            if not filename:
                continue
            filename = decode_mime_header(filename).strip()
            ctype = (part.get_content_type() or "").lower()
            content = part.get_payload(decode=True)

            is_pdf = filename.lower().endswith(".pdf") or ctype == "application/pdf"
            is_xml = filename.lower().endswith(".xml") or ctype in (
                "text/xml", "application/xml", "application/x-iso20022+xml", "application/x-invoice+xml"
            )
            if is_pdf or is_xml:
                logger.info(f"📎 Adjunto detectado: {filename} ({ctype})")
                attachments.append({
                    "filename": filename,
                    "content": content,
                    "content_type": ctype
                })

        meta["links"] = links
        logger.info(f"📬 Correo {email_id} - Asunto: '{subject}' - Adjuntos: {len(attachments)} - Enlaces: {len(links)}")
        return meta, attachments

    # --------- Core processing ---------
    def process_emails(self, ignore_date_filter: bool = False) -> ProcessResult:
        """
        Procesamiento optimizado por lotes para evitar problemas de memoria.
        Procesa correos en lotes pequeños, almacenando y liberando memoria inmediatamente.
        """
        import gc
        from app.config.settings import settings
        
        result = ProcessResult(success=True, message="Procesamiento completado", invoice_count=0, invoices=[])
        try:
            if not self.connect():
                return ProcessResult(success=False, message="Error al conectar al servidor de correo")

            email_ids = self.search_emails(ignore_date_filter=ignore_date_filter)
            if not email_ids:
                self.disconnect()
                return ProcessResult(success=True, message="No se encontraron correos con facturas", invoice_count=0)

            total_emails = len(email_ids)
            # Configuración para procesamiento suave multiusuario
            batch_size = getattr(settings, 'EMAIL_BATCH_SIZE', 5)  # Reducido a 5 correos por lote para ser más suave
            batch_delay = getattr(settings, 'EMAIL_BATCH_DELAY', 3)  # 3 segundos entre lotes
            email_delay = getattr(settings, 'EMAIL_PROCESSING_DELAY', 0.5)  # 0.5 segundos entre correos
            
            logger.info(f"🔄 Procesando {total_emails} correos en lotes de {batch_size} (multiusuario suave)")
            logger.info(f"⏱️ Configuración: {batch_delay}s entre lotes, {email_delay}s entre correos")

            abort_run = False
            processed_emails = 0

            # Procesar en lotes pequeños con pausas
            for batch_start in range(0, total_emails, batch_size):
                if abort_run:
                    break
                    
                batch_end = min(batch_start + batch_size, total_emails)
                batch_ids = email_ids[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (total_emails + batch_size - 1) // batch_size
                
                logger.info(f"📦 Procesando lote {batch_num}/{total_batches} ({len(batch_ids)} correos)")
                
                # Pausa entre lotes para ser multiusuario-friendly
                if batch_num > 1:
                    logger.info(f"⏳ Pausa de {batch_delay}s entre lotes para procesamiento multiusuario suave...")
                    time.sleep(batch_delay)
                
                # Procesar correos del lote
                batch_invoices = []
                for i, eid in enumerate(batch_ids):
                    if abort_run:
                        break
                    invoice = None
                    try:
                        processed_emails += 1
                        logger.debug(f"🔍 Procesando correo {i+1}/{len(batch_ids)} del lote {batch_num}")
                        
                        # Procesar un correo (ya incluye validación de límite IA)
                        invoice = self._process_single_email(eid)
                        
                        if invoice:
                            # Almacenar inmediatamente
                            self._store_invoice_v2(invoice)
                            batch_invoices.append(invoice)
                            result.invoice_count += 1
                            logger.debug(f"✅ Factura procesada: {invoice.numero_factura}")
                    except OpenAIFatalError as e:
                        logger.error(f"❌ Error FATAL de OpenAI en correo {eid}: {e}. Se omite y se continúa con el siguiente.")
                    except OpenAIRetryableError as e:
                        logger.warning(f"⚠️ Error transitorio de OpenAI en correo {eid}: {e}. Se omitirá este correo en esta corrida.")
                    except Exception as e:
                        logger.error(f"❌ Error procesando correo {eid}: {e}")
                    finally:
                        # Marcar como leído inmediatamente después de procesar (o fallar) para evitar reprocesos infinitos
                        try:
                            self.mark_as_read(eid)
                            logger.debug(f"📧 Correo {eid} marcado como leído")
                        except Exception as mark_err:
                            logger.warning(f"⚠️ No se pudo marcar correo {eid} como leído: {mark_err}")

                        # Pausa suave entre correos para procesamiento multiusuario
                        if i < len(batch_ids) - 1 and not abort_run:  # No pausar después del último correo del lote
                            time.sleep(email_delay)

                        invoice = None
                
                # Agregar facturas del lote al resultado
                result.invoices.extend(batch_invoices)
                
                # Liberar memoria del lote
                del batch_invoices
                gc.collect()
                
                logger.info(f"✅ Lote {batch_num} completado. Total procesadas: {result.invoice_count}")

            result.message = f"Procesamiento por lotes completado: {result.invoice_count} facturas de {processed_emails} correos procesados"
            
            self.disconnect()
            return result

        except Exception as e:
            logger.error(f"❌ Error en procesamiento por lotes: {e}")
            self.disconnect()
            return ProcessResult(success=False, message=f"Error en procesamiento por lotes: {str(e)}")

    def _process_single_email(self, email_id: str):
        """
        Procesa un solo correo y retorna la factura extraída.
        Versión optimizada para uso en lotes.
        """
        key = self._email_key(email_id)

        if was_processed(key):
            logger.info(f"⏭️ Correo {email_id} ya estaba procesado; se omite para evitar duplicados.")
            return None

        try:
            # ✅ VALIDAR LÍMITE DE IA ANTES DE PROCESAR
            if self.owner_email:
                from app.repositories.user_repository import UserRepository
                user_repo = UserRepository()
                ai_check = user_repo.can_use_ai(self.owner_email)
                
                if not ai_check['can_use']:
                    logger.warning(f"⚠️ Límite de IA alcanzado para {self.owner_email}: {ai_check['message']}")
                    logger.info(f"⏭️ Omitiendo correo {email_id} - usuario sin acceso a IA (se guardará como skipped_ai_limit)")
                    # Marcar como leído para no reprocesarlo inmediatamente
                    try:
                        self.mark_as_read(email_id)
                    except:
                        pass
                    # IMPORTANTE: Marcar como 'skipped_ai_limit' para que was_processed() devuelva False (permitiendo reintento)
                    # pero quede constancia en BD.
                    self._mark_email_processed(email_id, "skipped_ai_limit")
                    return None
            
            metadata, attachments = self.get_email_content(email_id)
            if not metadata:
                self._mark_email_processed(email_id, "missing_metadata")
                return None

            email_meta_for_ai = {
                "sender": metadata.get("sender", ""),
                "subject": metadata.get("subject", ""),
                "date": metadata.get("date")
            }

            xml_path = None
            pdf_path = None

            # Adjuntos: XML prioridad, luego PDF
            for att in attachments:
                fname = (att.get("filename") or "").lower()
                ctype = (att.get("content_type") or "").lower()
                content = att.get("content") or b""
                is_pdf = fname.endswith(".pdf") or ctype == "application/pdf"
                is_xml = fname.endswith(".xml") or ctype in (
                    "text/xml", "application/xml", "application/x-iso20022+xml", "application/x-invoice+xml"
                )
                
                # Usar owner_email y date para MinIO structure
                if is_xml:
                    xml_storage = save_binary(
                        content, fname, 
                        owner_email=self.owner_email, 
                        date_obj=metadata.get("date")
                    )
                    xml_path = xml_storage.local_path
                    # Guardamos referencia para asignar después
                    xml_minio_key = xml_storage.minio_key
                    
                elif is_pdf:
                    pdf_storage = save_binary(
                        content, fname, force_pdf=True,
                        owner_email=self.owner_email,
                        date_obj=metadata.get("date")
                    )
                    pdf_path = pdf_storage.local_path
                    pdf_minio_key = pdf_storage.minio_key
            
            # Procesar con prioridad: XML > PDF > Enlaces
            # XML primero
            if xml_path:
                inv = self.openai_processor.extract_invoice_data_from_xml(xml_path, email_meta_for_ai, owner_email=self.owner_email)
                if inv:
                    if 'xml_minio_key' in locals() and xml_minio_key:
                        inv.minio_key = xml_minio_key
                    self._mark_email_processed(email_id, "xml")
                    return inv

            # PDF si no hay XML o falló
            if pdf_path:
                inv = self.openai_processor.extract_invoice_data(pdf_path, email_meta_for_ai, owner_email=self.owner_email)
                if inv:
                    if 'pdf_minio_key' in locals() and pdf_minio_key:
                         inv.minio_key = pdf_minio_key
                    self._mark_email_processed(email_id, "pdf")
                    return inv

            # Enlaces como último recurso
            if metadata.get("links"):
                for link in metadata["links"]:
                    try:
                        # download_pdf_from_url ahora retorna StoragePath (porque save_binary lo hace)
                        storage_result = download_pdf_from_url(link)
                        
                        # Manejar si devuelve objeto o string vacío (fallo)
                        if not storage_result or not hasattr(storage_result, "local_path"):
                             continue
                             
                        downloaded_path = storage_result.local_path
                        if not downloaded_path:
                             continue

                        if downloaded_path.lower().endswith(".xml"):
                            inv = self.openai_processor.extract_invoice_data_from_xml(downloaded_path, email_meta_for_ai, owner_email=self.owner_email)
                        elif downloaded_path.lower().endswith(".pdf"):
                            inv = self.openai_processor.extract_invoice_data(downloaded_path, email_meta_for_ai, owner_email=self.owner_email)
                        else:
                            continue
                            
                        if inv:
                            if storage_result.minio_key:
                                inv.minio_key = storage_result.minio_key
                            self._mark_email_processed(email_id, "link")
                            return inv
                    except Exception as e:
                        logger.error(f"Error procesando enlace {link}: {e}")
                        continue

            # Si llegamos aquí, no se pudo extraer la factura
            self._mark_email_processed(email_id, "no_invoice")
            return None

        except OpenAIFatalError as e:
            self._mark_email_processed(email_id, "openai_fatal")
            logger.error(f"❌ Error fatal al procesar correo {email_id}: {e}")
            raise
        except OpenAIRetryableError as e:
            logger.warning(f"⚠️ Error transitorio al procesar correo {email_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error en _process_single_email para {email_id}: {e}")
            self._mark_email_processed(email_id, "error")
            return None

    def _store_invoice_v2(self, invoice):
        """
        Almacena una factura inmediatamente en el esquema v2.
        """
        try:
            from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
            from app.modules.mapping.invoice_mapping import map_invoice
            
            repo = MongoInvoiceRepository()
            doc = map_invoice(invoice, fuente="EMAIL_BATCH_PROCESSOR")
            
            # Asignar owner_email si está disponible
            if hasattr(self, 'owner_email') and self.owner_email:
                try:
                    doc.header.owner_email = self.owner_email
                    for item in doc.items:
                        item.owner_email = self.owner_email
                except Exception:
                    pass
            
            repo.save_document(doc)
            
        except Exception as e:
            logger.error(f"❌ Error almacenando factura v2: {e}")
            # No re-lanzar la excepción para no detener el procesamiento del lote
    


    # ------------- EmailProcessor solo para single processing -------------
    # Los jobs programados ahora se manejan por MultiEmailProcessor.start_scheduled_job()
    
