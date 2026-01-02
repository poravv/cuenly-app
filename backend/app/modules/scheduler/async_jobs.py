import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pymongo import MongoClient, ASCENDING
from app.config.settings import settings

logger = logging.getLogger(__name__)

class AsyncJobManager:
    """
    Gestor de trabajos asíncronos persistentes en MongoDB.
    Permite encolar tareas pesadas (como sync histórico) y procesarlas en background.
    """
    def __init__(self):
        self._client = None
        self._db_name = settings.MONGODB_DATABASE
        self._conn_str = settings.MONGODB_URL
        self._listening = False
        self._thread = None
        # Registro de funciones handlers
        self._handlers: Dict[str, Callable] = {}

    def _get_collection(self):
        if not self._client:
            self._client = MongoClient(self._conn_str)
        return self._client[self._db_name].jobs

    def register_handler(self, job_type: str, handler: Callable):
        """Registra una función para manejar un tipo de trabajo."""
        self._handlers[job_type] = handler

    def enqueue_job(self, job_type: str, payload: Dict[str, Any], owner_email: Optional[str] = None) -> str:
        """Encola un nuevo trabajo."""
        try:
            job = {
                "job_type": job_type,
                "payload": payload,
                "owner_email": owner_email,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "attempts": 0
            }
            result = self._get_collection().insert_one(job)
            logger.info(f"Job {job_type} encolado para {owner_email} (ID: {result.inserted_id})")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error encolando job {job_type}: {e}")
            return ""

    def start_worker(self):
        """Inicia el worker thread."""
        if self._listening:
            return
        self._listening = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="AsyncJobWorker")
        self._thread.start()
        logger.info("🚀 AsyncJobWorker iniciado")

    def stop_worker(self):
        self._listening = False
        if self._thread:
            self._thread.join(timeout=5)

    def _worker_loop(self):
        coll = self._get_collection()
        # Asegurar índice
        try:
            coll.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
        except:
            pass

        while self._listening:
            try:
                # Buscar job pendiente (FIFO)
                job = coll.find_one_and_update(
                    {"status": "pending"},
                    {"$set": {"status": "processing", "started_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
                    sort=[("created_at", ASCENDING)]
                )

                if not job:
                    time.sleep(5)  # Backoff si no hay trabajos
                    continue

                job_id = job["_id"]
                job_type = job["job_type"]
                payload = job.get("payload", {})
                
                logger.info(f"🔄 Procesando job {job_id} ({job_type})")

                handler = self._handlers.get(job_type)
                if not handler:
                    logger.error(f"❌ No handler for job_type: {job_type}")
                    coll.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": "No handler", "updated_at": datetime.utcnow()}})
                    continue

                try:
                    # Ejecutar handler
                    handler(payload)
                    coll.update_one(
                        {"_id": job_id}, 
                        {"$set": {"status": "completed", "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
                    )
                    logger.info(f"✅ Job {job_id} completado")
                    
                except Exception as ex:
                    logger.error(f"❌ Error ejecutando job {job_id}: {ex}")
                    coll.update_one(
                        {"_id": job_id}, 
                        {"$set": {"status": "failed", "error": str(ex), "updated_at": datetime.utcnow()}}
                    )

            except Exception as e:
                logger.error(f"Error en worker loop: {e}")
                time.sleep(5)

# Singleton global
async_job_manager = AsyncJobManager()
