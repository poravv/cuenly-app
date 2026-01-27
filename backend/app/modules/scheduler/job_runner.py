import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ScheduledJobRunner:
    """
    Ejecuta 'target' cada 'interval_minutes' en un hilo daemon.
    No depende de 'schedule'.
    """
    def __init__(self, interval_minutes: int, target: Callable[[], object], 
                 start_date=None, end_date=None, stop_after_range: bool = False):
        self.interval_minutes = max(1, int(interval_minutes or 1))
        self.target = target
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._next_run_ts: Optional[float] = None
        self._last_run_ts: Optional[float] = None
        self._last_result: Optional[object] = None
        
        # Configuración de fechas
        self.start_date = start_date
        self.end_date = end_date
        self.stop_after_range = stop_after_range

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def next_run(self) -> Optional[float]:
        return self._next_run_ts

    @property
    def last_run(self) -> Optional[float]:
        return self._last_run_ts

    @property
    def last_result(self) -> Optional[object]:
        return self._last_result

    def _loop(self):
        logger.info(f"Scheduler iniciado (cada {self.interval_minutes} min)")
        self._next_run_ts = time.time()  # primera corrida inmediata
        while not self._stop.is_set():
            now = time.time()
            if self._next_run_ts is not None and now >= self._next_run_ts:
                try:
                    self._last_run_ts = now
                    
                    # Ejecutar target pasando fechas si se requieren
                    # Detectar si target acepta argumentos (muy básico, asumimos kwargs)
                    try:
                        self._last_result = self.target(start_date=self.start_date, end_date=self.end_date)
                    except TypeError:
                        # Fallback por si la función no acepta argumentos
                        self._last_result = self.target()
                        
                    # Si es un job de rango único (stop_after_range), detenerse después de una ejecución exitosa
                    if self.stop_after_range:
                        logger.info("Job de rango de fechas completado. Deteniendo scheduler automáticamente.")
                        self.stop()
                        return

                except Exception as e:
                    logger.exception(f"Error ejecutando job programado: {e}")
                finally:
                    self._next_run_ts = time.time() + self.interval_minutes * 60
            time.sleep(1)
        logger.info("Scheduler detenido")

    def start(self):
        if self._running:
            logger.warning("Scheduler ya está en ejecución")
            return
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._running = False
        self._thread = None
        self._next_run_ts = None
