#!/usr/bin/env python
"""
CuenlyApp Worker - Entry point para el worker de RQ.

Este proceso separado ejecuta los jobs encolados desde la API.
Debe iniciarse como un proceso independiente.

Uso local:
    python worker.py

Uso con Docker:
    docker-compose up worker

El worker escucha tres colas en orden de prioridad:
1. high - Jobs urgentes (procesamiento manual, webhooks)
2. default - Jobs normales (procesamiento automático)
3. low - Jobs de baja prioridad (limpieza, reportes)
"""
import os
import sys
import logging
from uuid import uuid4
from datetime import datetime

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("cuenly.worker")


def _build_worker_name() -> str:
    """
    Genera un nombre de worker único por instancia para evitar
    colisiones durante rollouts (dos pods vivos al mismo tiempo).
    """
    pod_name = os.getenv("POD_NAME", "").strip()
    host_name = os.getenv("HOSTNAME", "").strip()
    node = pod_name or host_name or f"pid{os.getpid()}"
    suffix = uuid4().hex[:8]
    return f"cuenly-worker-{node}-{suffix}"


def main():
    """Inicia el worker de RQ."""
    logger.info("=" * 60)
    logger.info("🔧 CuenlyApp Worker - Iniciando...")
    logger.info(f"   Hora: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    try:
        from rq import Worker, Queue
        from app.core.redis_client import get_redis_client
        
        # Obtener conexión Redis RAW (RQ necesita bytes, no strings decodificados)
        redis_conn = get_redis_client(decode_responses=False)
        logger.info("✅ Conexión Redis (RAW) establecida")
        
        # Crear colas en orden de prioridad
        queues = [
            Queue('high', connection=redis_conn),
            Queue('default', connection=redis_conn),
            Queue('low', connection=redis_conn)
        ]
        
        logger.info(f"📋 Colas configuradas: {[q.name for q in queues]}")
        
        # Crear y ejecutar worker
        worker = Worker(
            queues=queues,
            connection=redis_conn,
            name=_build_worker_name()
        )
        
        logger.info(f"👷 Worker '{worker.name}' listo para procesar jobs")
        logger.info("   Presiona Ctrl+C para detener")
        logger.info("-" * 60)
        
        # Iniciar procesamiento
        worker.work(with_scheduler=True)
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Worker detenido por el usuario")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Error fatal en worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
