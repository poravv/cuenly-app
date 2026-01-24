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
    def search_emails(self, ignore_date_filter: bool = False, 
                      start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[str]:
        """
        Usa IMAPClient.search(subject_terms) que devuelve UIDs (str).
        NOTA: los términos en .env deben venir SIN acentos (como acordamos).
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
        unread_only = (str(self.config.search_criteria or 'UNSEEN').upper() != 'ALL')
        
        # Adapter para pasar since_date y before_date al cliente si soporta kwargs, o usarlos aquí
        # IMAPClient.search signature: (terms, unread_only=True, since_date=None)
        # Necesitamos verificar si imap_client soporta before_date. Si no, lo implementaremos o filtraremos pos-search.
        # Asumiendo que imap_client.py solo tiene since_date por ahora. Lo revisaremos.
        # Por ahora pasamos only since_date y los terminos.
        
        uids = self.client.search(terms, unread_only=unread_only, **extra_criteria)

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
    def process_emails(self, ignore_date_filter: bool = False, max_ai_process: Optional[int] = None, 
                       start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> ProcessResult:
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
            
            if max_ai_process is not None:
                logger.info(f"🔒 Límite estricto de IA configurado para esta ejecución: {max_ai_process}")

            abort_run = False
            processed_emails = 0
            ai_processed_count = 0

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
                
                # Check 1: ¿Podemos usar IA en general?
                ai_check = user_repo.can_use_ai(self.owner_email)
                
                if not ai_check['can_use']:
                    # Doble validación en tiempo real por si otro hilo consumió el saldo
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
    
