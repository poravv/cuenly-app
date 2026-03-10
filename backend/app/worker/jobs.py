"""
Job Definitions - Funciones ejecutables por el worker RQ.

Cada función aquí puede ser encolada para ejecución asíncrona:

Uso:
    from app.worker.jobs import process_emails_job
    from app.worker.queues import enqueue_job
    
    # Encolar para ejecución asíncrona
    job = enqueue_job(process_emails_job, owner_email="user@example.com")
    
    # O ejecutar directamente (para testing)
    result = process_emails_job(owner_email="user@example.com")
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


def _set_current_job_progress(stage: str, **extra: Any) -> None:
    """
    Actualiza meta de progreso del job RQ actual, si existe.
    """
    try:
        from rq import get_current_job

        current_job = get_current_job()
        if not current_job:
            return

        progress = dict(current_job.meta.get("progress", {}) or {})
        progress.update(
            {
                "stage": stage,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        progress.update(extra or {})
        current_job.meta["progress"] = progress
        current_job.save_meta()
    except Exception:
        return


def process_emails_job(
    owner_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_emails: Optional[int] = None
) -> Dict[str, Any]:
    """
    Job de procesamiento de correos electrónicos.
    
    Procesa todas las cuentas de correo configuradas para un usuario.
    
    Args:
        owner_email: Email del usuario propietario.
        start_date: Fecha inicio (ISO format YYYY-MM-DD).
        end_date: Fecha fin (ISO format YYYY-MM-DD).
        max_emails: Número máximo de correos a procesar.
        
    Returns:
        dict: Resultado del procesamiento con estadísticas.
    """
    logger.info(f"🚀 Iniciando job de procesamiento para {owner_email}")
    logger.info(f"   Rango: {start_date} → {end_date}, max={max_emails}")
    
    try:
        from app.modules.email_processor.config_store import get_enabled_configs
        from app.modules.email_processor.email_processor import MultiEmailProcessor
        from app.models.models import MultiEmailConfig
        
        # Obtener configuraciones de email habilitadas
        configs = get_enabled_configs(include_password=True, owner_email=owner_email)
        
        if not configs:
            logger.warning(f"⚠️ Sin cuentas configuradas para {owner_email}")
            return {
                "success": False,
                "message": "Sin cuentas de correo configuradas",
                "owner_email": owner_email,
                "processed": 0,
                "errors": 0
            }
        
        # Crear configuraciones de email
        email_configs = []
        for cfg in configs:
            try:
                email_configs.append(MultiEmailConfig(**{**cfg, 'owner_email': owner_email}))
            except Exception as e:
                logger.warning(f"Error creando config para {cfg.get('email')}: {e}")
        
        if not email_configs:
            return {
                "success": False,
                "message": "No se pudieron cargar las configuraciones de email",
                "owner_email": owner_email,
                "processed": 0,
                "errors": 0
            }
        
        # Crear procesador
        processor = MultiEmailProcessor(
            email_configs=email_configs,
            owner_email=owner_email
        )
        
        # Ejecutar procesamiento
        result = processor.process_all_emails(
            start_date=start_date,
            end_date=end_date
        )
        
        # Formatear resultado
        if hasattr(result, 'dict'):
            return result.dict()
        elif hasattr(result, '__dict__'):
            return result.__dict__
        else:
            return {
                "success": True,
                "result": result,
                "owner_email": owner_email
            }
            
    except Exception as e:
        logger.error(f"❌ Error en job de procesamiento: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e),
            "owner_email": owner_email,
            "processed": 0,
            "errors": 1
        }


def process_emails_range_job(
    owner_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Job distribuido para procesamiento por rango histórico.

    A diferencia del procesamiento manual "rápido", este flujo:
    - fuerza búsqueda sobre LEÍDOS + NO LEÍDOS (ALL)
    - procesa en fan-out por lotes de 50
    - desactiva el cap por cuenta para recorrer todo el rango
    """
    logger.info(f"🚀 Iniciando job de rango para {owner_email}: {start_date} → {end_date}")
    _set_current_job_progress(
        "starting",
        owner_email=owner_email,
        start_date=start_date,
        end_date=end_date,
    )

    try:
        from app.modules.email_processor.config_store import get_enabled_configs
        from app.modules.email_processor.email_processor import MultiEmailProcessor
        from app.models.models import MultiEmailConfig

        def _parse_date(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            return datetime.strptime(value, "%Y-%m-%d")

        start_dt = _parse_date(start_date)
        end_dt = _parse_date(end_date)

        configs = get_enabled_configs(include_password=True, owner_email=owner_email)
        if not configs:
            logger.warning(f"⚠️ Sin cuentas configuradas para proceso por rango: {owner_email}")
            return {
                "success": False,
                "message": "No hay cuentas de correo configuradas",
                "owner_email": owner_email,
                "invoice_count": 0,
                "invoices": [],
            }

        email_configs = []
        for cfg in configs:
            try:
                email_configs.append(MultiEmailConfig(**{**cfg, "owner_email": owner_email}))
            except Exception as e:
                logger.warning(f"Error creando config para {cfg.get('email')}: {e}")

        if not email_configs:
            return {
                "success": False,
                "message": "No se pudieron cargar las configuraciones de email",
                "owner_email": owner_email,
                "invoice_count": 0,
                "invoices": [],
            }

        processor = MultiEmailProcessor(
            email_configs=email_configs,
            owner_email=owner_email,
        )

        result = processor.process_all_emails(
            start_date=start_dt,
            end_date=end_dt,
            force_search_criteria_all=True,
            fanout_batch_size=50,
            disable_fanout_account_cap=True,
        )

        if hasattr(result, "dict"):
            payload = result.dict()
        elif hasattr(result, "__dict__"):
            payload = result.__dict__
        else:
            payload = {
                "success": True,
                "result": result,
                "owner_email": owner_email,
            }

        _set_current_job_progress(
            "completed",
            owner_email=owner_email,
            queued_count=int(payload.get("queued_count") or 0),
            invoice_count=int(payload.get("invoice_count") or 0),
        )
        return payload
    except Exception as e:
        logger.error(f"❌ Error en job de rango para {owner_email}: {e}", exc_info=True)
        _set_current_job_progress(
            "error",
            owner_email=owner_email,
            error=str(e)[:240],
        )
        return {
            "success": False,
            "message": str(e),
            "owner_email": owner_email,
            "invoice_count": 0,
            "invoices": [],
        }


def process_single_account_job(
    email_address: str,
    owner_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Job de procesamiento para una sola cuenta de correo.
    
    Args:
        email_address: Dirección de correo a procesar.
        owner_email: Email del usuario propietario.
        start_date: Fecha inicio opcional.
        end_date: Fecha fin opcional.
        
    Returns:
        dict: Resultado del procesamiento.
    """
    logger.info(f"🚀 Procesando cuenta individual: {email_address} para {owner_email}")
    
    try:
        from app.modules.email_processor.config_store import get_by_username
        from app.modules.email_processor.email_processor import EmailProcessor
        from app.models.models import EmailConfig
        
        # Obtener configuración específica
        cfg = get_by_username(email_address, include_password=True, owner_email=owner_email)
        
        if not cfg:
            return {
                "success": False,
                "message": f"Cuenta no encontrada: {email_address}",
                "email": email_address
            }
        
        # Crear y ejecutar procesador
        email_cfg = EmailConfig(**cfg)
        processor = EmailProcessor(email_cfg, owner_email=owner_email)
        
        result = processor.process_emails(
            start_date=start_date,
            end_date=end_date
        )
        
        if hasattr(result, 'dict'):
            return result.dict()
        return {"success": True, "result": result}
        
    except Exception as e:
        logger.error(f"❌ Error procesando {email_address}: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e),
            "email": email_address
        }


def process_single_email_from_uid_job(
    email_address: Optional[str] = None,
    owner_email: Optional[str] = None,
    email_uid: Optional[str] = None,
    account_email: Optional[str] = None,
    message_id: Optional[str] = None,
    preclaimed: bool = False,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Job de procesamiento asíncrono para un solo correo (Fan-out).
    Permite escalar el procesamiento de UIDs en múltiples workers.
    """
    # Compatibilidad con payloads antiguos encolados con kwargs distintos.
    if not email_address and account_email:
        email_address = account_email
    if not email_uid and "uid" in kwargs:
        email_uid = str(kwargs.get("uid"))
    if "preclaimed" in kwargs:
        preclaimed = bool(kwargs.get("preclaimed"))

    logger.info(
        f"🚀 Procesando correo individual UID {email_uid} de la cuenta {email_address} "
        f"(owner={owner_email}, message_id={message_id})"
    )
    
    try:
        from app.modules.email_processor.config_store import get_by_username
        from app.modules.email_processor.email_processor import EmailProcessor
        from app.models.models import EmailConfig
        from app.modules.email_processor.errors import SkipEmailKeepUnread
        
        if not email_address or not owner_email or not email_uid:
            return {
                "success": False,
                "message": "Parámetros incompletos para procesar correo individual",
                "email_address": email_address,
                "owner_email": owner_email,
                "email_uid": email_uid,
            }

        cfg = get_by_username(email_address, include_password=True, owner_email=owner_email)
        if not cfg:
            return {"success": False, "message": f"Cuenta no encontrada: {email_address}"}
            
        email_cfg = EmailConfig(**cfg)
        processor = EmailProcessor(email_cfg, owner_email=owner_email)
        
        if not processor.connect():
            return {"success": False, "message": processor.get_last_connect_error_message()}
            
        invoice = processor._process_single_email(email_uid, already_claimed=preclaimed)
        
        if invoice:
            # _store_invoice_v2 is usually called inside process_emails, but we must call it here since we bypassed the loop
            processor._store_invoice_v2(invoice)
            try:
                processor.mark_as_read(email_uid)
            except Exception as e:
                logger.warning(f"No se pudo marcar como leído UID {email_uid}: {e}")
                
            processor.disconnect()
            return {"success": True, "message": f"Factura {getattr(invoice, 'numero_factura', 'N/A')} procesada"}
            
        processor.disconnect()
        return {"success": False, "message": "No se extrajo ninguna factura"}
        
    except SkipEmailKeepUnread as e:
        # Flujo esperado (límite IA / OpenAI no disponible): no debe verse como fallo
        # del job RQ. El estado funcional ya queda reflejado en processed_emails.
        logger.info(
            "🕒 UID %s queda pendiente por IA/disponibilidad (%s). "
            "Job RQ marcado como completado para evitar falso 'fallido'.",
            email_uid,
            str(e),
        )
        try:
            processor.disconnect()
        except Exception:
            pass
        return {
            "success": True,
            "pending_ai": True,
            "message": str(e),
            "email_uid": email_uid,
            "status": "pending_ai",
        }
    except Exception as e:
        logger.error(f"❌ Error procesando UID {email_uid}: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def process_manual_pdf_job(
    owner_email: str,
    pdf_path: str,
    minio_key: str,
    sender: str = "Carga manual",
    date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Job RQ para procesar un PDF subido manualmente.
    Se ejecuta en el worker distribuido (Redis), no en memoria del backend.
    """
    logger.info(f"📄 Procesando PDF manual para {owner_email}: {pdf_path}")
    _set_current_job_progress("starting", owner_email=owner_email)

    try:
        from app.repositories.user_repository import UserRepository
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        from app.modules.mapping.invoice_mapping import map_invoice
        from app.modules.email_processor.storage import cleanup_local_file_if_safe, ensure_local_file
        from app.modules.email_processor.errors import OpenAIFatalError, OpenAIRetryableError
        from app.main import CuenlyApp

        # Garantizar archivo local (descarga de MinIO si corre en otro pod)
        pdf_path = ensure_local_file(pdf_path, minio_key)
        if not pdf_path:
            return {"success": False, "message": "No se pudo acceder al archivo PDF", "invoice_count": 0}

        date_obj = None
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                pass

        email_meta = {"sender": sender}
        if date_obj:
            email_meta["date"] = date_obj

        # Verificar disponibilidad de IA
        ai_block = _check_ai_block(owner_email)
        if ai_block:
            _store_pending_ai(owner_email, sender, date_obj, minio_key, "OPENAI_VISION", ai_block)
            cleanup_local_file_if_safe(pdf_path, minio_key)
            return {"success": True, "message": "PDF registrado como PENDING_AI", "reason_code": _ai_reason_code(ai_block), "invoice_count": 0}

        try:
            invoice_sync = CuenlyApp()
            inv = invoice_sync.openai_processor.extract_invoice_data(pdf_path, email_meta, owner_email=owner_email)
        except (OpenAIFatalError, OpenAIRetryableError) as e:
            _store_pending_ai(owner_email, sender, date_obj, minio_key, "OPENAI_VISION", f"IA_NO_DISPONIBLE: {e}")
            cleanup_local_file_if_safe(pdf_path, minio_key)
            return {"success": True, "message": "PDF registrado como PENDING_AI por indisponibilidad de IA", "reason_code": "ai_unavailable", "invoice_count": 0}

        if not inv:
            cleanup_local_file_if_safe(pdf_path, minio_key)
            return {"success": False, "message": "No se pudo extraer información del PDF", "reason_code": "extraction_failed", "invoice_count": 0}

        if minio_key:
            inv.minio_key = minio_key
        try:
            repo = MongoInvoiceRepository()
            doc = map_invoice(inv, fuente="OPENAI_VISION", minio_key=minio_key or "")
            if owner_email:
                doc.header.owner_email = owner_email
                for it in doc.items:
                    it.owner_email = owner_email
            repo.save_document(doc)
        except Exception as e:
            logger.error(f"❌ Error persistiendo PDF manual: {e}")

        cleanup_local_file_if_safe(pdf_path, minio_key)
        _set_current_job_progress("done", owner_email=owner_email)
        return {"success": True, "message": "PDF procesado correctamente", "invoice_count": 1}

    except Exception as e:
        logger.error(f"❌ Error en job PDF manual: {e}", exc_info=True)
        try:
            from app.modules.email_processor.storage import cleanup_local_file_if_safe
            cleanup_local_file_if_safe(pdf_path, minio_key)
        except Exception:
            pass
        return {"success": False, "message": str(e), "invoice_count": 0}


def process_manual_image_job(
    owner_email: str,
    img_path: str,
    minio_key: str,
    sender: str = "Carga manual (Imagen)",
    date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Job RQ para procesar una imagen subida manualmente.
    """
    logger.info(f"🖼️ Procesando imagen manual para {owner_email}: {img_path}")
    _set_current_job_progress("starting", owner_email=owner_email)

    try:
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        from app.modules.mapping.invoice_mapping import map_invoice
        from app.modules.email_processor.storage import cleanup_local_file_if_safe, ensure_local_file
        from app.modules.email_processor.errors import OpenAIFatalError, OpenAIRetryableError
        from app.main import CuenlyApp

        # Garantizar archivo local (descarga de MinIO si corre en otro pod)
        img_path = ensure_local_file(img_path, minio_key)
        if not img_path:
            return {"success": False, "message": "No se pudo acceder a la imagen", "invoice_count": 0}

        date_obj = None
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                pass

        email_meta = {"sender": sender}
        if date_obj:
            email_meta["date"] = date_obj

        ai_block = _check_ai_block(owner_email)
        if ai_block:
            _store_pending_ai(owner_email, sender, date_obj, minio_key, "OPENAI_VISION_IMAGE", ai_block)
            cleanup_local_file_if_safe(img_path, minio_key)
            return {"success": True, "message": "Imagen registrada como PENDING_AI", "reason_code": _ai_reason_code(ai_block), "invoice_count": 0}

        try:
            invoice_sync = CuenlyApp()
            inv = invoice_sync.openai_processor.extract_invoice_data(img_path, email_meta, owner_email=owner_email)
        except (OpenAIFatalError, OpenAIRetryableError) as e:
            _store_pending_ai(owner_email, sender, date_obj, minio_key, "OPENAI_VISION_IMAGE", f"IA_NO_DISPONIBLE: {e}")
            cleanup_local_file_if_safe(img_path, minio_key)
            return {"success": True, "message": "Imagen registrada como PENDING_AI", "reason_code": "ai_unavailable", "invoice_count": 0}

        if not inv:
            cleanup_local_file_if_safe(img_path, minio_key)
            return {"success": False, "message": "No se pudo extraer factura de la imagen", "reason_code": "extraction_failed", "invoice_count": 0}

        if minio_key:
            inv.minio_key = minio_key
        try:
            repo = MongoInvoiceRepository()
            doc = map_invoice(inv, fuente="OPENAI_VISION_IMAGE", minio_key=minio_key or "")
            if owner_email:
                doc.header.owner_email = owner_email
                for it in doc.items:
                    it.owner_email = owner_email
            repo.save_document(doc)
        except Exception as e:
            logger.error(f"❌ Error persistiendo imagen manual: {e}")

        cleanup_local_file_if_safe(img_path, minio_key)
        _set_current_job_progress("done", owner_email=owner_email)
        return {"success": True, "message": "Imagen procesada y almacenada", "invoice_count": 1}

    except Exception as e:
        logger.error(f"❌ Error en job imagen manual: {e}", exc_info=True)
        try:
            from app.modules.email_processor.storage import cleanup_local_file_if_safe
            cleanup_local_file_if_safe(img_path, minio_key)
        except Exception:
            pass
        return {"success": False, "message": str(e), "invoice_count": 0}


def process_manual_xml_job(
    owner_email: str,
    xml_path: str,
    minio_key: str,
    sender: str = "Carga manual",
    date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Job RQ para procesar un XML subido manualmente.
    """
    logger.info(f"📋 Procesando XML manual para {owner_email}: {xml_path}")
    _set_current_job_progress("starting", owner_email=owner_email)

    try:
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        from app.modules.mapping.invoice_mapping import map_invoice
        from app.modules.email_processor.storage import cleanup_local_file_if_safe, ensure_local_file
        from app.main import CuenlyApp

        # Garantizar archivo local (descarga de MinIO si corre en otro pod)
        xml_path = ensure_local_file(xml_path, minio_key)
        if not xml_path:
            return {"success": False, "message": "No se pudo acceder al archivo XML", "invoice_count": 0}

        date_obj = None
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                pass

        email_meta = {"sender": sender}
        if date_obj:
            email_meta["date"] = date_obj

        try:
            invoice_sync = CuenlyApp()
            inv = invoice_sync.openai_processor.extract_invoice_data_from_xml(xml_path, email_meta, owner_email=owner_email)
        except Exception as e:
            logger.error(f"❌ Error extrayendo XML: {e}")
            inv = None

        if inv:
            if minio_key:
                inv.minio_key = minio_key
            try:
                repo = MongoInvoiceRepository()
                doc = map_invoice(
                    inv,
                    fuente="XML_NATIVO" if getattr(inv, 'cdc', '') else "OPENAI_VISION",
                    minio_key=minio_key or "",
                )
                if owner_email:
                    doc.header.owner_email = owner_email
                    for it in doc.items:
                        it.owner_email = owner_email
                repo.save_document(doc)
            except Exception as e:
                logger.error(f"❌ Error persistiendo XML manual: {e}")
            cleanup_local_file_if_safe(xml_path, minio_key)
            _set_current_job_progress("done", owner_email=owner_email)
            return {"success": True, "message": "Factura XML procesada y almacenada", "invoice_count": 1}

        # XML no extrajo datos → verificar si puede hacer fallback IA
        ai_block = _check_ai_block(owner_email)
        if ai_block:
            _store_pending_ai(owner_email, sender, date_obj, minio_key, "XML_UPLOAD", f"{ai_block} | XML requiere fallback de IA")
            cleanup_local_file_if_safe(xml_path, minio_key)
            return {"success": True, "message": "XML registrado como PENDING_AI", "reason_code": _ai_reason_code(ai_block), "invoice_count": 0}

        cleanup_local_file_if_safe(xml_path, minio_key)
        return {"success": False, "message": "No se pudo extraer información desde el XML", "reason_code": "extraction_failed", "invoice_count": 0}

    except Exception as e:
        logger.error(f"❌ Error en job XML manual: {e}", exc_info=True)
        try:
            from app.modules.email_processor.storage import cleanup_local_file_if_safe
            cleanup_local_file_if_safe(xml_path, minio_key)
        except Exception:
            pass
        return {"success": False, "message": str(e), "invoice_count": 0}


# ── Helpers compartidos para jobs manuales ──────────────────────────────

def _check_ai_block(owner_email: str) -> Optional[str]:
    """Retorna razón de bloqueo IA o None si puede usar IA."""
    try:
        from app.repositories.user_repository import UserRepository
        ai_check = UserRepository().can_use_ai(owner_email)
        if ai_check.get("can_use", False):
            return None
        reason = str(ai_check.get("reason", "")).strip().lower()
        message = str(ai_check.get("message", "No disponible")).strip()
        if reason == "ai_limit_reached":
            return f"LIMITE_IA: {message}"
        return f"IA_NO_DISPONIBLE: {message}"
    except Exception as e:
        logger.warning(f"⚠️ Error verificando IA para {owner_email}: {e}")
        return "IA_NO_DISPONIBLE: No fue posible validar disponibilidad de IA"


def _ai_reason_code(ai_block_reason: Optional[str]) -> Optional[str]:
    if not ai_block_reason:
        return None
    return "ai_limit_reached" if ai_block_reason.startswith("LIMITE_IA:") else "ai_unavailable"


def _store_pending_ai(
    owner_email: str,
    sender: str,
    date_obj: Optional[datetime],
    minio_key: str,
    fuente: str,
    reason: str,
) -> None:
    """Registra upload manual bloqueado por IA en processed_emails + invoice_headers."""
    import uuid as _uuid
    try:
        from app.modules.email_processor.processed_registry import _repo, build_key as build_processed_key
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        from app.modules.mapping.invoice_mapping import map_invoice
        from app.models.models import InvoiceData

        # 1) processed_emails (visibilidad UI)
        try:
            event_uid = f"manual_ai_pending_{_uuid.uuid4().hex}"
            event_key = build_processed_key(event_uid, "manual_upload", owner_email)
            base_reason = (reason or "Pendiente por IA").strip()
            event_reason = f"{base_reason} | Manual: sin reproceso automático"[:500]
            _repo.mark_processed(
                key=event_key, status="pending", reason=event_reason,
                owner_email=owner_email, account_email="manual_upload",
                message_id=f"manual_pending_ai:{event_uid}",
                subject=f"Carga manual pendiente de IA ({fuente})",
                sender=(sender or "Carga manual")[:200],
                email_date=date_obj or datetime.utcnow(),
            )
            _repo._get_collection().update_one(
                {"_id": event_key},
                {"$set": {"manual_upload": True, "fuente": fuente, "minio_key": minio_key or "", "retry_supported": False}},
                upsert=False,
            )
        except Exception as qerr:
            logger.error(f"❌ Error registrando pending manual en processed_emails: {qerr}")

        # 2) invoice_headers (PENDING_AI)
        pending_msg_id = f"manual_pending_ai:{_uuid.uuid4().hex}"
        inv = InvoiceData(
            numero_factura=f"PENDING_AI_{_uuid.uuid4().hex[:10]}",
            ruc_emisor="UNKNOWN",
            nombre_emisor=(sender or "Carga manual")[:100],
            fecha=date_obj or datetime.utcnow(),
            email_origen=owner_email,
            message_id=pending_msg_id,
            status="PENDING_AI",
            processing_error=(reason or "Pendiente por IA")[:500],
            fuente=fuente,
            minio_key=minio_key or "",
        )
        doc = map_invoice(inv, fuente=fuente, minio_key=minio_key or "")
        if owner_email:
            doc.header.owner_email = owner_email
            for it in doc.items:
                it.owner_email = owner_email
        doc.header.status = "PENDING_AI"
        doc.header.processing_error = (reason or "Pendiente por IA")[:500]
        MongoInvoiceRepository().save_document(doc)
        logger.info("🕒 Upload manual PENDING_AI (owner=%s, fuente=%s)", owner_email, fuente)
    except Exception as e:
        logger.error(f"❌ Error guardando PENDING_AI manual: {e}")


def cleanup_old_processed_emails_job(days: int = 30) -> Dict[str, Any]:
    """
    Job de limpieza de registros de correos procesados antiguos.
    
    Args:
        days: Eliminar registros más antiguos que N días.
        
    Returns:
        dict: Resultado de la limpieza.
    """
    logger.info(f"🧹 Iniciando limpieza de correos procesados > {days} días")
    
    try:
        from app.modules.email_processor.processed_registry import ProcessedEmailRegistry
        
        registry = ProcessedEmailRegistry()
        cleaned = registry.cleanup_old_entries(days=days)
        
        return {
            "success": True,
            "cleaned_entries": cleaned,
            "days_threshold": days
        }
        
    except Exception as e:
        logger.error(f"Error en limpieza: {e}")
        return {
            "success": False,
            "message": str(e)
        }


def generate_report_job(
    owner_email: str,
    report_type: str = "monthly",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Job de generación de reportes.
    
    Args:
        owner_email: Email del usuario.
        report_type: Tipo de reporte ("monthly", "weekly", "custom").
        start_date: Fecha inicio para reportes custom.
        end_date: Fecha fin para reportes custom.
        
    Returns:
        dict: Resultado con URL del reporte generado.
    """
    logger.info(f"📊 Generando reporte {report_type} para {owner_email}")
    
    # TODO: Implementar generación de reportes
    return {
        "success": True,
        "message": "Reporte generado",
        "report_type": report_type,
        "owner_email": owner_email
    }
