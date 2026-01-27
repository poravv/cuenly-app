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
        from app.modules.email_processor.config_store import get_email_config
        from app.modules.email_processor.email_processor import EmailProcessor
        from app.models.models import EmailConfig
        
        # Obtener configuración específica
        cfg = get_email_config(email_address, include_password=True)
        
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
