"""
Endpoints de carga manual de archivos (PDF, XML, imagen).
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import time
import logging

from app.api.deps import (
    _get_current_user,
    _get_current_user_with_trial_check,
)
from app.models.models import ProcessResult, InvoiceData, MultiEmailConfig
from app.repositories.user_repository import UserRepository
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.mapping.invoice_mapping import map_invoice
from app.modules.scheduler.processing_lock import PROCESSING_LOCK
from app.modules.scheduler.task_queue import task_queue
from app.modules.email_processor.storage import save_binary, cleanup_local_file_if_safe
from app.modules.email_processor.errors import AIFatalError, AIRetryableError
from app.utils.security import validate_frontend_key
from app.utils.observability import observability_logger
from app.api.state import invoice_sync

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

def _check_upload_size(content: bytes, filename: str = "") -> None:
    if len(content) > _MAX_UPLOAD_BYTES:
        size_mb = len(content) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"El archivo '{filename}' supera el límite de 20MB ({size_mb:.1f}MB recibido)"
        )

# Helpers compartidos con processing.py
from app.api.rate_limit import rate_limit as _rate_limit
from app.api.routers.processing import (
    _get_ai_block_reason,
    _get_ai_reason_code,
    _store_manual_pending_ai,
    _create_completed_task,
)

@router.post("/upload", response_model=ProcessResult)
@_rate_limit("20/minute")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)):
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
    
    pdf_path = ""
    minio_key = ""
    try:
        # Leer contenido
        content = await file.read()
        _check_upload_size(content, file.filename)

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
                ai_block_reason = _get_ai_block_reason(owner)
                if ai_block_reason:
                    _store_manual_pending_ai(
                        owner_email=owner,
                        sender=email_meta.get("sender", "Carga manual"),
                        date_obj=email_meta.get("date"),
                        minio_key=minio_key,
                        fuente="OPENAI_VISION",
                        reason=ai_block_reason,
                    )
                    return ProcessResult(
                        success=True,
                        message="Archivo registrado como PENDING_AI por límite/disponibilidad de IA",
                        invoice_count=0,
                        reason_code=_get_ai_reason_code(ai_block_reason),
                        invoices=[],
                    )

                try:
                    invoice_data = invoice_sync.openai_processor.extract_invoice_data(
                        pdf_path,
                        email_meta,
                        owner_email=owner,
                    )
                except (AIFatalError, AIRetryableError) as e:
                    _store_manual_pending_ai(
                        owner_email=owner,
                        sender=email_meta.get("sender", "Carga manual"),
                        date_obj=email_meta.get("date"),
                        minio_key=minio_key,
                        fuente="OPENAI_VISION",
                        reason=f"IA_NO_DISPONIBLE: {str(e)}",
                    )
                    return ProcessResult(
                        success=True,
                        message="Archivo registrado como PENDING_AI por indisponibilidad temporal de IA",
                        invoice_count=0,
                        reason_code="ai_unavailable",
                        invoices=[],
                    )

                invoices = [invoice_data] if invoice_data else []
                if invoices:
                    try:
                        repo = MongoInvoiceRepository()
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
                    return ProcessResult(
                        success=True,
                        message="Factura procesada y almacenada",
                        invoice_count=1,
                        invoices=invoices,
                    )

                return ProcessResult(
                    success=False,
                    message="No se pudo extraer factura del PDF",
                    invoice_count=0,
                    reason_code="extraction_failed",
                    invoices=[],
                )

        # Ejecutar en threadpool para no bloquear el event loop
        return await run_in_threadpool(_process_sync)
        
    except Exception as e:
        logger.error(f"Error al procesar el archivo: {str(e)}")
        return ProcessResult(
            success=False,
            message=f"Error al procesar el archivo: {str(e)}"
        )
    finally:
        if pdf_path:
            await run_in_threadpool(cleanup_local_file_if_safe, pdf_path, minio_key)

@router.post("/upload-xml", response_model=ProcessResult)
async def upload_xml(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)):
    """
    Sube un archivo XML SIFEN para procesarlo directamente con el parser nativo (fallback OpenAI).
    """
    if not (file.filename.lower().endswith('.xml')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML")

    xml_path = ""
    minio_key = ""
    try:
        # Leer contenido
        content = await file.read()
        _check_upload_size(content, file.filename)

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
                    return ProcessResult(
                        success=True,
                        message="Factura XML procesada y almacenada",
                        invoice_count=1,
                        invoices=invoices,
                    )

                # Si no hubo extracción y además no hay IA disponible para fallback, dejar en pendiente.
                ai_block_reason = _get_ai_block_reason(owner)
                if ai_block_reason:
                    _store_manual_pending_ai(
                        owner_email=owner,
                        sender=email_meta.get("sender", "Carga manual"),
                        date_obj=email_meta.get("date"),
                        minio_key=minio_key,
                        fuente="XML_UPLOAD",
                        reason=f"{ai_block_reason} | XML requiere fallback de IA",
                    )
                    return ProcessResult(
                        success=True,
                        message="XML registrado como PENDING_AI (sin cupo/disponibilidad IA para fallback)",
                        invoice_count=0,
                        reason_code=_get_ai_reason_code(ai_block_reason),
                        invoices=[],
                    )

                return ProcessResult(
                    success=False,
                    message="No se pudo extraer información desde el XML",
                    invoice_count=0,
                    reason_code="extraction_failed",
                    invoices=[],
                )

        # Ejecutar en threadpool
        return await run_in_threadpool(_process_sync)

    except Exception as e:
        logger.error(f"Error al procesar el XML: {str(e)}")
        return ProcessResult(
            success=False,
            message=f"Error al procesar el XML: {str(e)}"
        )
    finally:
        if xml_path:
            await run_in_threadpool(cleanup_local_file_if_safe, xml_path, minio_key)

@router.post("/tasks/upload-pdf")
async def enqueue_upload_pdf(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)):
    """Encola el procesamiento de un PDF manual vía RQ (distribuido) y retorna job_id."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    pdf_path = ""
    pdf_minio_key = ""
    try:
        file_bytes = await file.read()
        _check_upload_size(file_bytes, file.filename)
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                pass

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

        from app.worker.jobs import process_manual_pdf_job
        from app.worker.queues import enqueue_job

        job = enqueue_job(
            process_manual_pdf_job,
            owner_email=owner_email,
            pdf_path=pdf_path,
            minio_key=pdf_minio_key,
            sender=sender or "Carga manual",
            date_str=date if date else None,
            priority='high',
            timeout='10m',
        )
        return {"job_id": job.id}
    except Exception as e:
        if pdf_path:
            cleanup_local_file_if_safe(pdf_path, pdf_minio_key)
        logger.error(f"Error encolando PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-image", response_model=Dict[str, str])
async def upload_image(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)):
    """Sube una imagen (JPG/PNG) para procesarla como factura vía RQ (distribuido)."""
    allowed_exts = ('.jpg', '.jpeg', '.png', '.webp')
    if not (file.filename.lower().endswith(allowed_exts)):
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes (JPG, PNG, WEBP)")

    img_path = ""
    img_minio_key = ""
    try:
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                pass

        file_bytes = await file.read()
        _check_upload_size(file_bytes, file.filename)
        owner_email = (user.get('email') or '').lower()

        img_storage = await run_in_threadpool(
            save_binary,
            content=file_bytes,
            filename=file.filename,
            owner_email=owner_email,
            date_obj=date_obj
        )
        img_path = img_storage.local_path
        img_minio_key = img_storage.minio_key

        from app.worker.jobs import process_manual_image_job
        from app.worker.queues import enqueue_job

        job = enqueue_job(
            process_manual_image_job,
            owner_email=owner_email,
            img_path=img_path,
            minio_key=img_minio_key,
            sender=sender or "Carga manual (Imagen)",
            date_str=date if date else None,
            priority='high',
            timeout='10m',
        )
        return {"job_id": job.id}

    except Exception as e:
        if img_path:
            cleanup_local_file_if_safe(img_path, img_minio_key)
        logger.error(f"Error al procesar imagen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")




@router.post("/tasks/upload-xml")
async def enqueue_upload_xml(
    file: UploadFile = File(...),
    sender: Optional[str] = Form(None),
    date: Optional[str] = Form(None)
    , user: Dict[str, Any] = Depends(_get_current_user_with_trial_check)):
    """Encola el procesamiento de un XML manual vía RQ (distribuido) y retorna job_id."""
    if not file.filename.lower().endswith('.xml'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML")

    xml_path = ""
    xml_minio_key = ""
    try:
        file_bytes = await file.read()
        _check_upload_size(file_bytes, file.filename)
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                logger.warning(f"Formato de fecha incorrecto: {date}")

        owner_email = (user.get('email') or '').lower()
        xml_storage = save_binary(
            file_bytes,
            file.filename,
            owner_email=owner_email,
            date_obj=date_obj
        )
        xml_path = xml_storage.local_path
        xml_minio_key = xml_storage.minio_key

        from app.worker.jobs import process_manual_xml_job
        from app.worker.queues import enqueue_job

        job = enqueue_job(
            process_manual_xml_job,
            owner_email=owner_email,
            xml_path=xml_path,
            minio_key=xml_minio_key,
            sender=sender or "Carga manual",
            date_str=date if date else None,
            priority='high',
            timeout='10m',
        )
        return {"job_id": job.id}
    except Exception as e:
        if xml_path:
            cleanup_local_file_if_safe(xml_path, xml_minio_key)
        logger.error(f"Error al encolar XML: {e}")
        raise HTTPException(status_code=500, detail=str(e))

