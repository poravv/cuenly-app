
import logging
import re
from pymongo import MongoClient
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_failed_records():
    """
    Elimina registros 'ERR_*' de invoice_headers y resetea su estado en processed_emails.
    Usa el formato de ID correcto para el processed_registry.
    """
    client = MongoClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]
    
    headers_coll = db.invoice_headers
    processed_coll = db.processed_emails
    
    # 1. Identificar registros ERR_
    query_err = {"numero_documento": {"$regex": "^ERR_"}}
    failed_docs = list(headers_coll.find(query_err))
    
    if not failed_docs:
        logger.info("✅ No se encontraron registros 'ERR_' para limpiar en invoice_headers.")
        
        # Opcional: buscar por status 'error' en processed_emails directamente
        # En caso de que no llegara a guardarse el header ERR_
        query_repo_err = {"status": "error"}
        failed_registry = list(processed_coll.find(query_repo_err))
        if failed_registry:
            logger.info(f"🔍 Encontrados {len(failed_registry)} registros con status 'error' en processed_emails.")
            res = processed_coll.delete_many(query_repo_err)
            logger.info(f"🗑 Eliminados {res.deleted_count} registros de error del registry.")
        return

    logger.info(f"🔍 Encontrados {len(failed_docs)} registros ERR_ en invoice_headers.")
    
    deleted_headers = 0
    deleted_registry = 0
    
    for doc in failed_docs:
        header_id = doc.get("_id") # Formato owner:UID
        owner = doc.get("owner_email")
        email_id = doc.get("message_id")
        
        # Eliminar del header
        headers_coll.delete_one({"_id": header_id})
        deleted_headers += 1
        
        # El ID en processed_emails suele ser "owner::account::UID"
        # Pero es más seguro buscar por owner_email y message_id
        if owner and email_id:
            res = processed_coll.delete_many({
                "owner_email": owner,
                "message_id": email_id
            })
            deleted_registry += res.deleted_count
            
    # Resetear cualquier otro 'error' remanente
    res_error = processed_coll.delete_many({"status": "error"})
    deleted_registry += res_error.deleted_count
            
    logger.info(f"🗑 Eliminados {deleted_headers} headers de facturas fallidas.")
    logger.info(f"🔄 Eliminados {deleted_registry} registros del registry de correos (reset completo).")
    logger.info("✅ Limpieza completada. Los correos serán re-procesados en el próximo escaneo.")

if __name__ == "__main__":
    cleanup_failed_records()
