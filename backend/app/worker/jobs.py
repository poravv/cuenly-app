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
            return {"success": False, "message": "No se pudo conectar a la cuenta IMAP"}
            
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
        logger.info(f"🛑 Omitido por límite de IA (UID {email_uid}). Manteniendo en cola de fallidos de RQ para posible reintento.")
        # Re-raise para que RQ mueva el job a FailedQueue y el usuario pueda verlo/reencolarlo
        raise e
    except Exception as e:
        logger.error(f"❌ Error procesando UID {email_uid}: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


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
