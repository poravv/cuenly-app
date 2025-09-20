# Módulo de monitoreo para CuenlyApp
from .health_checker import AdvancedHealthChecker

def get_health_checker():
    """Retorna una instancia del health checker avanzado"""
    return AdvancedHealthChecker()

__all__ = ['AdvancedHealthChecker', 'get_health_checker']