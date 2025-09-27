"""
Scheduler para tareas automáticas del sistema CuenlyApp
Maneja el reseteo mensual automático de límites de IA
"""

import schedule
import time
import threading
from datetime import datetime
import logging
from app.modules.monthly_reset_service import MonthlyResetService

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
            # Programar el reseteo para ejecutarse diariamente a las 00:01
            # pero solo se ejecutará el día 1 de cada mes (lógica interna)
            schedule.every().day.at("00:01").do(self._check_and_execute_monthly_reset)
            
            # Iniciar el hilo de background
            self.scheduler_thread = threading.Thread(
                target=self._run_scheduler, 
                daemon=True,
                name="AI-Limits-Scheduler"
            )
            self.scheduler_thread.start()
            self.running = True
            
            logger.info("✅ Scheduler de límites IA iniciado correctamente")
            logger.info("📅 Verificación diaria a las 00:01 - Reseteo automático el día 1 de cada mes")
            
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
        """Verifica si es día 1 del mes y ejecuta el reseteo mensual"""
        try:
            # Solo ejecutar el día 1 de cada mes
            if not self.should_run_today():
                logger.debug(f"📅 Verificación diaria: No es día 1, saltando reseteo (día {datetime.now().day})")
                return
            
            logger.info("🚀 Es día 1 del mes - Iniciando reseteo mensual automático de límites IA")
            
            result = self.monthly_reset_service.reset_monthly_limits()
            
            if result["success"]:
                logger.info(f"✅ Reseteo mensual completado: {result['users_reset']} usuarios reseteados")
            else:
                logger.error(f"❌ Error en reseteo mensual: {result.get('error', 'Error desconocido')}")
                
        except Exception as e:
            logger.error(f"❌ Excepción durante reseteo mensual: {str(e)}")
    
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
        """Verifica si el reseteo debería ejecutarse hoy"""
        today = datetime.now()
        # El reseteo se ejecuta el día 1 de cada mes
        return today.day == 1
    
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