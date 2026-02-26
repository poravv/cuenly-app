import os
import re
import time
import threading
import logging
import queue
import pickle
import email.utils
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config.settings import settings
from app.models.models import EmailConfig, MultiEmailConfig, InvoiceData, ProcessResult
from app.modules.openai_processor.openai_processor import OpenAIProcessor
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.mapping.invoice_mapping import map_invoice


from app.modules.email_processor.errors import OpenAIFatalError, OpenAIRetryableError, SkipEmailKeepUnread

from .imap_client import IMAPClient, decode_mime_header
from .link_extractor import extract_links_from_message
from .downloader import download_pdf_from_url
from .storage import save_binary, sanitize_filename, ensure_dirs, cleanup_local_file_if_safe
from .connection_pool import get_imap_pool
from .config_store import get_enabled_configs


from .dedup import deduplicate_invoices
from .processed_registry import (
    build_key as build_processed_key,
    claim_for_processing,
    was_processed_by_message_id,
    set_message_id,
    _repo,
)

logger = logging.getLogger(__name__)

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
                    search_synonyms=first.get("search_synonyms") or {},
                    fallback_sender_match=bool(first.get("fallback_sender_match", False)),
                    fallback_attachment_match=bool(first.get("fallback_attachment_match", False)),
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
        
        start_conn = time.time()
        logger.info(f"⏱️ Solicitando conexión IMAP al pool para {self.config.username}")
        self.current_connection = self.connection_pool.get_connection(self.config)
        elapsed_conn = time.time() - start_conn
        if self.current_connection:
            # IMPORTANT: Sincronizar la conexión real con el cliente IMAP interno
            self.client.conn = self.current_connection.connection
            
            # 🚀 CRÍTICO: Asegurar que el mailbox esté seleccionado (Estado SELECTED)
            # Tras obtener una conexión del pool (estado AUTH), comandos como SEARCH/FETCH fallan
            try:
                self.client.conn.select(self.client.mailbox or "INBOX")
            except Exception as e:
                logger.warning(f"⚠️ Error al seleccionar mailbox {self.client.mailbox} en conexión del pool: {e}")
                # Si falla select, la conexión podría estar corrupta, mejor no usarla
                # Pero por ahora lo dejamos pasar o el pool la marcará muerta después
                
            logger.info(f"🔄 Conexión IMAP obtenida del pool para {self.config.username} en {elapsed_conn:.2f}s")
            return True
        
        logger.error(f"❌ No se pudo obtener conexión IMAP para {self.config.username} (espera {elapsed_conn:.2f}s)")
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

    def _mark_email_processed(self, email_id: str, status: str = "success", message_id: str = None, 
                              reason: str = None, subject: str = None) -> None:
        try:
            # Pass explicit arguments to the new Mongo repository method
            # status can be: success, skipped_ai_limit, error, xml, pdf, pending
            from app.modules.email_processor.processed_registry import _repo
            _repo.mark_processed(
                key=self._email_key(email_id),
                status=status,
                reason=reason,
                owner_email=self.owner_email,
                account_email=self.config.username,
                message_id=message_id,
                subject=subject
            )
        except Exception as e:
            logger.debug(f"Registro de correo procesado falló ({email_id}): {e}")

    def _get_imap_connection(self):
        """Obtiene la conexión IMAP actual."""
        if self.current_connection:
            return self.current_connection.connection
        return None

    # --------- Search logic ---------
    def search_emails(self, ignore_date_filter: bool = False, 
                      start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
                      search_criteria_override: Optional[str] = None) -> List[dict]:
        """
        Usa IMAPClient.search(...) con matcher robusto (acentos/sinonimos/fallback opcional).
        Filtra correos por fecha de registro del usuario (o start_date param) y opcionalmente end_date.
        """
        if not self.client.conn:
            if not self.connect():
                return []

        terms = self.config.search_terms or []
        if not terms:
            logger.info("No se configuraron términos de búsqueda. Se devolverá lista vacía.")
            return []

        # Obtener fecha de inicio de procesamiento para este usuario (si no se pasó explícita)
        since_date = None
        
        # 1. Prioridad: Fecha explícita pasada como parámetro (Job filtering)
        if start_date:
            since_date = start_date
            logger.info(f"📅 Filtro de fecha explícito (Job): SINCE {since_date.date()}")
        
        # 2. Si no hay fecha explícita, usar fecha de configuración del usuario
        # Verificar si debe aplicar filtro de fecha (configurable)
        elif not ignore_date_filter and self.owner_email:
            try:
                from app.repositories.user_repository import UserRepository
                # Evitar import circular
                from app.config.settings import settings
                if not settings.EMAIL_PROCESS_ALL_DATES:
                    user_repo = UserRepository()
                    stored_date = user_repo.get_email_processing_start_date(self.owner_email)
                    if stored_date:
                        since_date = stored_date
                        logger.info(f"📅 Filtro de fecha usuario: SINCE {since_date.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.info(f"📮 Procesando TODOS los correos sin restricción (EMAIL_PROCESS_ALL_DATES=true)")
            except Exception as e:
                logger.warning(f"No se pudo obtener fecha de inicio para {self.owner_email}: {e}")
        
        # Construir criterios adicionales
        extra_criteria = {}
        if since_date:
            extra_criteria['since_date'] = since_date
            
        if end_date:
            # IMAP BEFORE excluye la fecha, sumamos 1 día para incluirlo
            target_end = end_date + timedelta(days=1)
            extra_criteria['before_date'] = target_end
            logger.info(f"📅 Filtro de fecha fin explícito (Job): BEFORE {target_end.date()}")

        # Pasamos la lista de términos directamente al nuevo IMAPClient.search()
        effective_search_criteria = str(search_criteria_override or self.config.search_criteria or 'UNSEEN').upper()
        unread_only = (effective_search_criteria != 'ALL')
        logger.info(
            "Criterio IMAP aplicado: %s (%s)",
            "UNSEEN" if unread_only else "ALL",
            self.config.username
        )
        
        # Adapter para pasar since_date y before_date al cliente si soporta kwargs, o usarlos aquí
        # IMAPClient.search signature: (terms, unread_only=True, since_date=None)
        # Necesitamos verificar si imap_client soporta before_date. Si no, lo implementaremos o filtraremos pos-search.
        # Asumiendo que imap_client.py solo tiene since_date por ahora. Lo revisaremos.
        # Por ahora pasamos only since_date y los terminos.
        
        uids = self.client.search(
            terms,
            unread_only=unread_only,
            search_synonyms=getattr(self.config, "search_synonyms", None),
            fallback_sender_match=bool(getattr(self.config, "fallback_sender_match", False)),
            fallback_attachment_match=bool(getattr(self.config, "fallback_attachment_match", False)),
            **extra_criteria,
        )

        logger.info(f"Se encontraron {len(uids)} correos combinando términos: {terms}" + 
                   (f" rango {since_date.date() if since_date else 'Start'} - {end_date.date() if end_date else 'End'}" if (since_date or end_date) else " (sin restricción)"))
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

        real_message_id = message.get("Message-ID", "")
        if real_message_id:
            real_message_id = real_message_id.strip()

        meta = {"subject": subject, "sender": sender, "date": dt, "message_id": email_id, "rfc822_message_id": real_message_id}
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
    def process_emails(self, max_ai_process: Optional[int] = None,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
                       fan_out: bool = False,
                       ignore_date_filter: bool = False,
                       max_discovery_emails: Optional[int] = None,
                       search_criteria_override: Optional[str] = None,
                       respect_fanout_account_cap: bool = True,
                       discovery_batch_size_override: Optional[int] = None) -> ProcessResult:
        """
        Punto de entrada principal para procesar correos de la cuenta.
        - fan_out=True: Descubrimiento rápido y encolado a RQ (High Performance).
        - fan_out=False: Procesamiento secuencial local (Legacy/Direct).
        """
        import gc
        from app.config.settings import settings
        
        result = ProcessResult(success=False, message="", invoice_count=0, invoices=[])
        
        if not self.client.conn and not self.connect():
            result.message = f"No se pudo conectar a la cuenta {self.config.username}"
            return result

        try:
            # 1. Búsqueda de UIDs y metadatos base
            # search_emails devuelve una lista de diccionarios: [{"uid": "...", "subject": "...", ...}]
            email_info = self.search_emails(
                ignore_date_filter=ignore_date_filter,
                start_date=start_date,
                end_date=end_date,
                search_criteria_override=search_criteria_override
            )
            if not email_info:
                self.disconnect()
                result.success = True
                result.message = f"No hay correos nuevos para procesar en {self.config.username}"
                return result

            # Caps para discovery de fan-out: por cuenta y/o por llamada (global restante).
            discovery_cap_candidates = []
            if respect_fanout_account_cap:
                fanout_account_cap = int(getattr(settings, "FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 0) or 0)
                if fanout_account_cap > 0:
                    discovery_cap_candidates.append(fanout_account_cap)

            if max_discovery_emails is not None:
                try:
                    discovery_cap_candidates.append(max(0, int(max_discovery_emails)))
                except Exception:
                    discovery_cap_candidates.append(0)

            if discovery_cap_candidates:
                effective_cap = min(discovery_cap_candidates)
                if effective_cap <= 0:
                    self.disconnect()
                    result.success = True
                    result.message = "Límite de descubrimiento alcanzado; no se encolaron correos."
                    return result

                if len(email_info) > effective_cap:
                    logger.info(
                        f"🔒 Limitando discovery de {len(email_info)} a {effective_cap} "
                        f"para {self.config.username} (cap por cuenta/global)"
                    )
                    email_info = email_info[:effective_cap]

            total_emails = len(email_info)
            # Extraer solo los UIDs para el control de flujo
            email_ids = [item['uid'] for item in email_info]
            # Mappear metadatos para acceso rápido durante Fan-out/Discovery
            meta_map = {item['uid']: item for item in email_info}
            
            logger.info(f"🔍 [Discovery] {total_emails} correos encontrados para {self.config.username}")

            from app.modules.email_processor.processed_registry import _repo
            coll = _repo._get_collection()

            # CASO A: FAN-OUT (Async) - Recomendado para performance
            if fan_out or getattr(settings, 'ENABLE_EMAIL_FANOUT', False):
                logger.info(f"🚀 Iniciando Fan-out para {total_emails} correos en {self.config.username}")
                items_queued = 0
                skipped_existing = 0
                requeued_errors = 0
                
                try:
                    from app.worker.queues import enqueue_job
                    from app.worker.jobs import process_single_email_from_uid_job
                    
                    # Batch configurable para discovery masivo
                    effective_discovery_batch_size = (
                        discovery_batch_size_override
                        if discovery_batch_size_override is not None
                        else getattr(settings, "FANOUT_DISCOVERY_BATCH_SIZE", 250)
                    )
                    discovery_batch_size = max(1, int(effective_discovery_batch_size or 250))

                    for i in range(0, total_emails, discovery_batch_size):
                        batch_info = email_info[i:i+discovery_batch_size]
                        batch_ids = [item['uid'] for item in batch_info]
                        
                        # Optimización: Obtener todos los existentes en este batch con UNA sola consulta
                        batch_keys = [self._email_key(eid) for eid in batch_ids]
                        existing_docs = list(coll.find({"_id": {"$in": batch_keys}}, {"_id": 1, "status": 1}))
                        existing_map = {
                            doc["_id"]: str(doc.get("status", "")).lower()
                            for doc in existing_docs
                        }
                        
                        for info in batch_info:
                            eid = info['uid']
                            key = self._email_key(eid)

                            prev_status = existing_map.get(key)
                            if prev_status and not _repo.is_retryable_status(prev_status):
                                skipped_existing += 1
                                continue

                            # 1. Registro/actualización rápida en pending
                            pending_reason = "Descubierto en escaneo (Pendiente de procesamiento)"
                            if prev_status:
                                pending_reason = (
                                    f"Reencolado automático por fan-out (estado previo: {prev_status})"
                                )
                                requeued_errors += 1

                            claimed = _repo.claim_for_processing(
                                key=key,
                                reason=pending_reason,
                                owner_email=self.owner_email,
                                account_email=self.config.username,
                                subject=info.get('subject'),
                                sender=info.get('sender'),
                                email_date=info.get('date'),
                            )
                            if not claimed:
                                skipped_existing += 1
                                continue

                            # 2. Encolar a RQ
                            enqueue_job(
                                process_single_email_from_uid_job,
                                self.config.username,
                                self.owner_email,
                                eid,
                                preclaimed=True,
                                priority='default'
                            )
                            items_queued += 1
                        
                        logger.info(
                            f"⏳ Progreso Fan-out {self.config.username}: "
                            f"encolados={items_queued}, omitidos_existentes={skipped_existing}, "
                            f"reencolados_error={requeued_errors}, analizados={min(i + len(batch_info), total_emails)}/{total_emails}"
                        )
                            
                    self.disconnect()
                    result.message = (
                        f"Fan-out exitoso: {items_queued} correos encolados "
                        f"(omitidos existentes: {skipped_existing}, reencolados por error: {requeued_errors})."
                    )
                    result.success = True
                    result.invoice_count = items_queued
                    return result
                    
                except Exception as fanout_err:
                    logger.error(f"❌ Error en sincronización por rango/fan-out: {fanout_err}. Intentando procesamiento local.")

            # CASO B: Procesamiento Regular (Síncrono/Local)
            # Evitamos pre-marcar "pending" para no bloquear la reserva atómica de _process_single_email.
            logger.info("🔒 Discovery local sin pre-registro: la reserva se hace al iniciar cada procesamiento.")

            # Configuración para procesamiento local (fallback si fan-out falla)
            batch_size = getattr(settings, 'EMAIL_BATCH_SIZE', 50)
            batch_delay = getattr(settings, 'EMAIL_BATCH_DELAY', 3)  # 3 segundos entre lotes
            email_delay = getattr(settings, 'EMAIL_PROCESSING_DELAY', 0.5)  # 0.5 segundos entre correos
            
            logger.info(f"🔄 Procesando {total_emails} correos en lotes de {batch_size} (local/sincrónico)")
            
            if max_ai_process is not None:
                logger.info(f"🔒 Límite estricto de IA configurado para esta ejecución: {max_ai_process}")

            abort_run = False
            processed_emails = 0
            ai_processed_count = 0
            
            # Límite de procesamiento por run (para ser "lento y con calma")
            process_limit = 50 
            new_processed_in_this_run = 0

            # Procesar en lotes pequeños con pausas (Local / Síncrono)
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
                    
                    # Verificar límite de procesamiento por run
                    if new_processed_in_this_run >= process_limit:
                        logger.info(f"🛑 Límite de procesamiento por run ({process_limit}) alcanzado. El resto se procesará en el siguiente ciclo.")
                        abort_run = True
                        break

                    invoice = None
                    try:
                        processed_emails += 1
                        new_processed_in_this_run += 1
                        logger.debug(f"🔍 Procesando correo {i+1}/{len(batch_ids)} del lote {batch_num}")
                        
                        # Procesar un correo (ya incluye validación de límite IA)
                        # Validar límite de IA antes de procesar
                        if max_ai_process is not None and ai_processed_count >= max_ai_process:
                             logger.warning(f"🛑 Límite estricto de IA ({max_ai_process}) alcanzado durante procesamiento. Deteniendo lote.")
                             abort_run = True
                             break

                        invoice = self._process_single_email(eid)
                        
                        # Si se procesó una factura usando IA (XML fallback o PDF/Imagen), incrementar contador local
                        # Nota: _process_single_email devuelve la factura si fue exitoso.
                        # Tendríamos que saber si usó IA. Por ahora asumimos que si retornó factura y no fue XML nativo 100%, usó IA.
                        # Una mejor aproximación es verificar el contador de uso real, pero aquí es un contador de seguridad del bucle.
                        # Dado que _process_single_email verifica can_use_ai internamente también, tenemos doble check.
                        if invoice and getattr(invoice, 'ai_used', False): # Necesitamos que InvoiceData o el proceso marque si usó IA
                            ai_processed_count += 1

                        
                        if invoice:
                            # Almacenar inmediatamente
                            self._store_invoice_v2(invoice)
                            batch_invoices.append(invoice)
                            result.invoice_count += 1
                            logger.debug(f"✅ Factura procesada: {invoice.numero_factura}")
                    except OpenAIFatalError as e:
                        logger.warning(
                            f"⚠️ Error FATAL de OpenAI en correo {eid}: {e}. "
                            "Se mantiene NO LEÍDO para reintento controlado."
                        )
                    except OpenAIRetryableError as e:
                        logger.warning(f"⚠️ Error transitorio de OpenAI en correo {eid}: {e}. Se omitirá este correo en esta corrida.")
                        # No marcar como leído para reintentar luego
                    except SkipEmailKeepUnread:
                         logger.info(f"🛑 Correo {eid} omitido y preservado como NO LEÍDO (SkipEmailKeepUnread signal).")
                         # NO llamar a mark_as_read
                    except Exception as e:
                        logger.error(f"❌ Error procesando correo {eid}: {e}")
                        try:
                            self.mark_as_read(eid)
                        except: pass
                    finally:
                        # LOGICA FINAL DE PAUSA
                        # Nota: mark_as_read se movió a los bloques except/try específicos arriba 
                        # o condicionado, ya que el 'finally' incondicional rompía el requerimiento
                        
                        # Si fue exitoso (invoice present), marcar leido aqui por seguridad si no se hizo antes
                        try:
                            if invoice:
                                self.mark_as_read(eid)
                                logger.debug(f"📧 Correo {eid} marcado como leído (success)")
                        except: pass

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

    def _process_single_email(self, email_id: str, already_claimed: bool = False):
        """
        Procesa un solo correo y retorna la factura extraída.
        Versión optimizada para uso en lotes.
        """
        key = self._email_key(email_id)
        temp_files_to_cleanup: List[Tuple[str, str]] = []
        real_msg_id: Optional[str] = None
        metadata: Dict[str, Any] = {}
        if not already_claimed:
            if not claim_for_processing(
                key=key,
                owner_email=self.owner_email,
                account_email=self.config.username,
                reason="Reserva para procesamiento individual",
            ):
                logger.info(f"⏭️ Correo {email_id} ya estaba reservado/procesado; se omite para evitar duplicados.")
                return None

        try:
            # 🚀 OPTIMIZACIÓN: Fetch Message-ID antes de bajar todo el correo
            real_msg_id = self.client.fetch_rfc822_message_id(email_id)
            if real_msg_id:
                set_message_id(key, real_msg_id)

            if real_msg_id and was_processed_by_message_id(real_msg_id, self.owner_email, exclude_key=key):
                logger.info(f"⏭️ Correo con Message-ID {real_msg_id} (UID {email_id}) ya procesado globalmente; se omite.")
                self._mark_email_processed(email_id, "skipped_duplicate_msgid", message_id=real_msg_id, reason="Correo duplicado detectado por Message-ID")
                return None

            metadata, attachments = self.get_email_content(email_id)
            if not metadata:
                # FALLBACK: Intentar recuperar metadatos capturados en el discovery phase de la DB
                logger.warning(f"⚠️ get_email_content falló para UID {email_id}. Intentando fallback desde DB...")
                db_meta = _repo._get_collection().find_one({"_id": key})
                if db_meta and db_meta.get("subject"):
                    logger.info(f"✅ Fallback exitoso: Usando metadatos de DB para UID {email_id}")
                    metadata = {
                        "subject": db_meta.get("subject"),
                        "sender": db_meta.get("sender", "Desconocido (IMAP Fetch Error)"),
                        "date": db_meta.get("email_date"),
                        "message_id": email_id,
                        "rfc822_message_id": real_msg_id or db_meta.get("message_id")
                    }
                    attachments = [] # Obviamente no hay adjuntos si el fetch falló
                else:
                    logger.error(f"❌ Falló fallback de metadatos para UID {email_id}. Marcar como error de metadatos.")
                    self._mark_email_processed(email_id, "missing_metadata", reason="No se pudieron extraer metadatos del correo ni del historial.")
                    return None

            # Si llegamos aquí con metadata de fallback pero sin adjuntos (porque falló el fetch)
            if not attachments:
                 logger.error(f"❌ Correo UID {email_id} ({metadata.get('subject')}) no pudo bajarse (FETCH error).")
                 self._mark_email_processed(email_id, "error", message_id=real_msg_id, reason="Error de conexión al bajar contenido del correo (FETCH)")
                 self._store_failed_invoice(email_id, "Error de comunicación IMAP al bajar el contenido", metadata)
                 return None

            # ✅ VALIDACIÓN INTELIGENTE DE LÍMITE IA
            if self.owner_email:
                has_xml = any(
                    (a.get("filename") or "").lower().endswith(".xml") or 
                    a.get("content_type", "").lower() in ("text/xml", "application/xml", "application/x-invoice+xml") 
                    for a in attachments
                )

                # Si NO hay XML, asumimos que necesitaremos IA (PDF/Imagen/Links)
                if not has_xml:
                    from app.repositories.user_repository import UserRepository
                    user_repo = UserRepository()
                    ai_check = user_repo.can_use_ai(self.owner_email)
                    
                    if not ai_check['can_use']:
                        logger.warning(f"⚠️ Límite de IA alcanzado para {self.owner_email} y no hay XML: {ai_check['message']}")
                        logger.info(f"⏭️ Omitiendo correo {email_id} y dejándolo como NO LEÍDO (esperando cupo al mes siguiente)")
                        
                        # Guardar constancia pero NO marcar leído
                        self._mark_email_processed(email_id, "skipped_ai_limit_unread", reason="Límite mensual de IA alcanzado (Pausado)")
                        # Store a minimal invoice record with PENDING_AI status
                        self._store_failed_invoice(email_id, "Límite de IA alcanzado y sin XML", metadata, status="PENDING_AI")
                        
                        # Lanzar excepción especial para que el bucle sepa no marcarlo como leído
                        raise SkipEmailKeepUnread("Límite de IA alcanzado y sin XML")

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
                    if xml_path:
                        temp_files_to_cleanup.append((xml_path, xml_storage.minio_key))
                    # Guardamos referencia para asignar después
                    xml_minio_key = xml_storage.minio_key
                    
                elif is_pdf:
                    pdf_storage = save_binary(
                        content, fname, force_pdf=True,
                        owner_email=self.owner_email,
                        date_obj=metadata.get("date")
                    )
                    pdf_path = pdf_storage.local_path
                    if pdf_path:
                        temp_files_to_cleanup.append((pdf_path, pdf_storage.minio_key))
                    pdf_minio_key = pdf_storage.minio_key
            
            # Procesar con prioridad: XML > PDF > Enlaces
            # XML primero
            if xml_path:
                inv = self.openai_processor.extract_invoice_data_from_xml(xml_path, email_meta_for_ai, owner_email=self.owner_email)
                if inv:
                    if 'xml_minio_key' in locals() and xml_minio_key:
                        inv.minio_key = xml_minio_key
                    self._mark_email_processed(email_id, "xml", message_id=real_msg_id, reason="Factura extraída de XML adjunto")
                    return inv

            # PDF si no hay XML o falló
            if pdf_path:
                inv = self.openai_processor.extract_invoice_data(pdf_path, email_meta_for_ai, owner_email=self.owner_email)
                if inv:
                    if 'pdf_minio_key' in locals() and pdf_minio_key:
                         inv.minio_key = pdf_minio_key
                    self._mark_email_processed(email_id, "pdf", message_id=real_msg_id, reason="Factura extraída de PDF/Imagen adjunta usando IA")
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
                        temp_files_to_cleanup.append((downloaded_path, storage_result.minio_key))

                        if downloaded_path.lower().endswith(".xml"):
                            inv = self.openai_processor.extract_invoice_data_from_xml(downloaded_path, email_meta_for_ai, owner_email=self.owner_email)
                        elif downloaded_path.lower().endswith(".pdf"):
                            inv = self.openai_processor.extract_invoice_data(downloaded_path, email_meta_for_ai, owner_email=self.owner_email)
                        else:
                            continue
                        if inv:
                            if storage_result.minio_key: # Use storage_result's minio_key for downloaded link
                                inv.minio_key = storage_result.minio_key
                            self._mark_email_processed(email_id, "link_pdf", message_id=real_msg_id, reason="Factura extraída de enlace (URL) en el cuerpo")
                            return inv
                    except (OpenAIFatalError, OpenAIRetryableError):
                        raise
                    except Exception as e:
                        logger.warning(f"⚠️ Error procesando link PDF de {email_id}: {e}")

            # Si llega aquí, significa que falló de todos los métodos posibles
            logger.error(f"❌ Correo UID {email_id} carece de datos válidos (solo contenía links rotos o adjuntos inservibles)")
            self._mark_email_processed(email_id, "error", message_id=real_msg_id, reason="No se encontraron adjuntos válidos ni enlaces procesables")
            # Guardar registro en MongoDB con status FAILED para poder ver en dashboard
            self._store_failed_invoice(email_id, "No se pudo extraer factura del correo", metadata)
            return None

        except OpenAIFatalError as e:
            reason = f"OpenAI no disponible (fatal): {str(e)[:350]}"
            self._mark_email_processed(
                email_id,
                "pending_ai_unread",
                message_id=real_msg_id,
                reason=reason,
            )
            self._store_failed_invoice(email_id, reason, metadata or {}, status="PENDING_AI")
            logger.warning(
                f"⚠️ Correo {email_id} pasa a PENDING_AI por error fatal de OpenAI; "
                "se preserva NO LEÍDO para reintento."
            )
            raise SkipEmailKeepUnread(reason)
        except OpenAIRetryableError as e:
            reason = f"OpenAI temporalmente no disponible: {str(e)[:350]}"
            self._mark_email_processed(
                email_id,
                "pending_ai_unread",
                message_id=real_msg_id,
                reason=reason,
            )
            self._store_failed_invoice(email_id, reason, metadata or {}, status="PENDING_AI")
            logger.warning(
                f"⚠️ Correo {email_id} pasa a PENDING_AI por error transitorio de OpenAI; "
                "se preserva NO LEÍDO para reintento."
            )
            raise SkipEmailKeepUnread(reason)
        except Exception as e:
            logger.error(f"❌ Error en _process_single_email para {email_id}: {e}")
            self._mark_email_processed(email_id, "error")
            return None
        finally:
            for temp_path, minio_key in temp_files_to_cleanup:
                cleanup_local_file_if_safe(temp_path, minio_key)

    def _store_invoice_v2(self, invoice, status: str = "DONE", error: str = None):
        """
        Almacena una factura inmediatamente en el esquema v2 con el status indicado.
        status: DONE | FAILED | PENDING_AI | PROCESSING
        """
        try:
            from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
            from app.modules.mapping.invoice_mapping import map_invoice
            
            repo = MongoInvoiceRepository()
            
            # Asignar status y error al invoice antes de mapear
            if hasattr(invoice, 'status'):
                invoice.status = status
            if error and hasattr(invoice, 'processing_error'):
                invoice.processing_error = error

            doc = map_invoice(
                invoice,
                fuente="EMAIL_BATCH_PROCESSOR",
                minio_key=(getattr(invoice, "minio_key", "") or ""),
            )
            
            # Asignar owner_email si está disponible
            if hasattr(self, 'owner_email') and self.owner_email:
                try:
                    doc.header.owner_email = self.owner_email
                    for item in doc.items:
                        item.owner_email = self.owner_email
                except Exception:
                    pass
            
            repo.save_document(doc)
            logger.info(f"✅ Factura guardada con status={status}")
            
            # 🚀 FEATURE B2B: Webhooks Outbound
            if status == "DONE" and hasattr(self, 'owner_email') and self.owner_email:
                try:
                    from app.services.webhook_service import WebhookService
                    webhook_svc = WebhookService()
                    
                    # Convertimos a diccionario para enviarlo como JSON
                    # Módulos como datetime se gestionan en el payload_str del WebhookService
                    payload = invoice.to_dict() if hasattr(invoice, 'to_dict') else doc.dict()
                    
                    webhook_svc.send_invoice_notification(self.owner_email, payload)
                except Exception as wh_err:
                    logger.error(f"Error al disparar webhook: {wh_err}")
            
        except Exception as e:
            logger.error(f"❌ Error almacenando factura v2 (status={status}): {e}")
            # No re-lanzar la excepción para no detener el procesamiento del lote

    def _store_failed_invoice(self, email_id: str, error_msg: str, metadata: dict, status: str = "FAILED"):
        """
        Guarda un registro minimal en MongoDB con status=FAILED para tracking en dashboard.
        """
        if not getattr(settings, "STORE_FAILED_INVOICE_HEADERS", False):
            logger.info(
                "ℹ️ STORE_FAILED_INVOICE_HEADERS=false: omitiendo persistencia de ERR_* para UID %s",
                str(email_id),
            )
            return

        try:
            from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
            from app.models.models import InvoiceData
            from datetime import timezone

            repo = MongoInvoiceRepository()
            from app.modules.mapping.invoice_mapping import map_invoice

            # Crear InvoiceData mínima solo para tracking
            inv = InvoiceData(
                numero_factura=f"ERR_{email_id[:8]}",
                ruc_emisor="UNKNOWN",
                nombre_emisor=str(metadata.get("sender", "Unknown sender"))[:100],
                fecha=metadata.get("date"),
                email_origen=str(metadata.get("sender", "")),
                message_id=str(email_id),
                status=status,
                processing_error=str(error_msg)[:500],
                fuente="EMAIL_BATCH_PROCESSOR",
            )
            if self.owner_email:
                inv.email_origen = self.owner_email

            doc = map_invoice(
                inv,
                fuente="EMAIL_BATCH_PROCESSOR",
                minio_key=(getattr(inv, "minio_key", "") or ""),
            )
            if self.owner_email:
                doc.header.owner_email = self.owner_email
                for item in doc.items:
                    item.owner_email = self.owner_email
            doc.header.status = status
            doc.header.processing_error = str(error_msg)[:500]

            repo.save_document(doc)
            logger.info(f"⚠️ Registro FAILED guardado para correo {email_id[:8]}")
        except Exception as e:
            logger.debug(f"No se pudo guardar registro FAILED: {e}")
    


    # ------------- EmailProcessor solo para single processing -------------
    # Los jobs programados ahora se manejan por MultiEmailProcessor.start_scheduled_job()
    
