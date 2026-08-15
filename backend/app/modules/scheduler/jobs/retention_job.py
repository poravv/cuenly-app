"""
Job de retención de datos: Elimina archivos físicos de MinIO antiguos (> 1 año).
Preserva la información procesada en la base de datos MongoDB.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config.settings import settings
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.email_processor.storage import get_minio_client

logger = logging.getLogger(__name__)

class DataRetentionJob:
    """Job para purgar archivos originales de MinIO según la política de retención."""

    def __init__(self):
        self.repo = MongoInvoiceRepository()
        self.minio_client = None
        if settings.MINIO_ACCESS_KEY:
            try:
                self.minio_client = get_minio_client()
            except RuntimeError as e:
                logger.error(f"❌ Cliente MinIO no disponible: {e}")

    async def run(self, days: int = 365):
        """
        Ejecuta la purga de archivos.
        Args:
            days: Antigüedad en días para considerar un archivo como 'expirado'.
        """
        if not self.minio_client:
            logger.warning("⚠️ MinIO no configurado. Abortando job de retención.")
            return

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        logger.info(f"🧹 Iniciando purga de archivos anteriores a {cutoff_date.isoformat()}")

        try:
            # Buscar facturas antiguas que aún tengan minio_key
            # Usamos el repositorio para acceder a la colección de headers
            headers_col = self.repo._headers()
            query = {
                "date": {"$lt": cutoff_date},
                "minio_key": {"$ne": "", "$exists": True}
            }
            
            expired_invoices = list(headers_col.find(query, {"_id": 1, "minio_key": 1, "owner_email": 1, "date": 1}))
            
            if not expired_invoices:
                logger.info("✅ No se encontraron archivos para purgar.")
                return

            logger.info(f"📂 Encontradas {len(expired_invoices)} facturas expiradas.")
            
            purged_count = 0
            error_count = 0

            for inv in expired_invoices:
                invoice_id = inv["_id"]
                minio_key = inv["minio_key"]
                
                try:
                    # 1. Borrar de MinIO
                    self.minio_client.remove_object(settings.MINIO_BUCKET, minio_key)
                    
                    # 2. Limpiar minio_key en MongoDB (Mantenemos la metadata de la factura)
                    headers_col.update_one(
                        {"_id": invoice_id},
                        {"$set": {"minio_key": "", "purged_at": datetime.utcnow()}}
                    )
                    
                    purged_count += 1
                    if purged_count % 50 == 0:
                        logger.info(f"... purgados {purged_count} archivos")
                        
                except Exception as e:
                    logger.error(f"❌ Error purgando factura {invoice_id} ({minio_key}): {e}")
                    error_count += 1

            logger.info(f"✨ Purga completada: {purged_count} archivos eliminados, {error_count} errores.")

        except Exception as e:
            logger.error(f"❌ Error fatal en DataRetentionJob: {e}")

async def run_retention_job():
    """Función helper para ejecutar el job."""
    job = DataRetentionJob()
    await job.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_retention_job())
