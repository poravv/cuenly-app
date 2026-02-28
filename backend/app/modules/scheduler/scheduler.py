"""
Scheduler para tareas automáticas del sistema CuenlyApp
Maneja el reseteo mensual automático de límites de IA y cobros recurrentes
"""

import schedule
import time
import threading
from datetime import datetime
import logging
from app.modules.monthly_reset_service import MonthlyResetService
from app.modules.scheduler.jobs.subscription_billing_job import run_billing_job
from app.modules.scheduler.jobs.retention_job import run_retention_job
import asyncio

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduledTasks:
    """Manejador de tareas programadas automáticas"""
    
    def __init__(self):
        self.monthly_reset_service = MonthlyResetService()
        self.scheduler_thread = None
        self.running = False
    
    def start_background_scheduler(self):
        """Inicia el scheduler en un hilo de background"""
        try:
            # Reseteo de límites IA por aniversario: ejecuta diario,
            # el servicio filtra internamente por billing_day de cada usuario
            schedule.every().day.at("00:01").do(self._check_and_execute_monthly_reset)
            
            # Programar cobros recurrentes de suscripciones diariamente a las 00:00
            schedule.every().day.at("00:00").do(lambda: asyncio.run(run_billing_job()))
            
            # Programar purga de archivos antiguos diariamente a las 03:00
            schedule.every().day.at("03:00").do(lambda: asyncio.run(run_retention_job()))
            
            # Iniciar el hilo de background
            self.scheduler_thread = threading.Thread(
                target=self._run_scheduler, 
                daemon=True,
                name="Scheduler-Thread"
            )
            self.scheduler_thread.start()
            self.running = True
            
            logger.info("✅ Scheduler iniciado correctamente")
            logger.info("📅 Reseteo de límites IA a las 00:01 (diario, filtra por aniversario)")
            logger.info("💳 Cobros recurrentes de suscripciones a las 00:00 (diario)")
            logger.info("🧹 Purga de archivos antiguos a las 03:00 (diario)")
            
        except Exception as e:
            logger.error(f"❌ Error iniciando scheduler: {str(e)}")
            raise
    
    def _run_scheduler(self):
        """Bucle principal del scheduler que se ejecuta en background"""
        logger.info("🔄 Hilo de scheduler iniciado en background")
        
        while True:
            try:
                # Verificar si hay jobs pendientes cada minuto
                schedule.run_pending()
                time.sleep(60)  # Revisar cada minuto
                
            except Exception as e:
                logger.error(f"❌ Error en el bucle del scheduler: {str(e)}")
                time.sleep(300)  # Esperar 5 minutos antes de reintentar
    
    def _check_and_execute_monthly_reset(self):
        """
        Ejecuta el reseteo de límites IA como fallback diario.
        El servicio filtra internamente: solo resetea usuarios cuyo
        billing_day coincide con hoy y que no fueron reseteados ya
        por el billing job.
        """
        try:
            logger.info(f"🔄 Ejecutando reseteo fallback por aniversario (día {datetime.now().day})")

            result = self.monthly_reset_service.reset_monthly_limits()

            if result["success"]:
                logger.info(
                    f"✅ Reseteo fallback: {result.get('users_reset', 0)} reseteados, "
                    f"{result.get('skipped', 0)} ya reseteados por billing"
                )
            else:
                logger.error(f"❌ Error en reseteo fallback: {result.get('error', 'Error desconocido')}")

        except Exception as e:
            logger.error(f"❌ Excepción durante reseteo fallback: {str(e)}")
    
    def get_status(self):
        """Obtiene el estado actual del scheduler"""
        try:
            jobs = schedule.jobs
            next_run = None
            
            if jobs:
                # Obtener el próximo job programado
                next_run = min(job.next_run for job in jobs) if jobs else None
            
            return {
                "running": self.running and (self.scheduler_thread and self.scheduler_thread.is_alive()),
                "jobs_count": len(jobs),
                "next_run": next_run.isoformat() if next_run else None,
                "thread_alive": self.scheduler_thread.is_alive() if self.scheduler_thread else False
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo estado del scheduler: {str(e)}")
            return {
                "running": False,
                "jobs_count": 0,
                "next_run": None,
                "thread_alive": False,
                "error": str(e)
            }
    
    def should_run_today(self):
        """Siempre True — el filtro por aniversario es interno al servicio."""
        return True
    
    def execute_manual_reset(self):
        """Ejecuta el reseteo mensual manualmente (sin verificar fecha)"""
        try:
            logger.info("🔧 Ejecutando reseteo mensual MANUAL (ignorando fecha)")
            
            result = self.monthly_reset_service.reset_monthly_limits()
            
            if result["success"]:
                logger.info(f"✅ Reseteo manual completado: {result['users_reset']} usuarios reseteados")
                return {
                    "success": True,
                    "users_reset": result.get("users_reset", 0),
                    "message": "Reseteo manual ejecutado correctamente"
                }
            else:
                error_msg = result.get('error', 'Error desconocido')
                logger.error(f"❌ Error en reseteo manual: {error_msg}")
                return {
                    "success": False,
                    "users_reset": 0,
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = f"Excepción durante reseteo manual: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "users_reset": 0,
                "error": error_msg
            }
    
    def stop_scheduler(self):
        """Detiene el scheduler (para testing o shutdown)"""
        try:
            schedule.clear()
            self.running = False
            logger.info("🛑 Scheduler detenido")
            
        except Exception as e:
            logger.error(f"❌ Error deteniendo scheduler: {str(e)}")


# Instancia global del scheduler
scheduler_instance = None


def get_scheduler_instance():
    """Obtiene la instancia global del scheduler"""
    global scheduler_instance
    if scheduler_instance is None:
        scheduler_instance = ScheduledTasks()
    return scheduler_instance