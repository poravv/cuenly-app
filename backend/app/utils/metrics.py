"""
Métricas personalizadas para Prometheus
Proporciona métricas específicas de negocio para monitoreo con Grafana
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_client.multiprocess import MultiProcessCollector
from typing import Dict, Any
import time
import logging
from app.utils.observability import ObservabilityLogger

# Registry para métricas personalizadas
REGISTRY = CollectorRegistry()

# Métricas de negocio
ACTIVE_USERS_GAUGE = Gauge(
    'cuenly_active_users_total',
    'Number of currently active users',
    ['subscription_type'],
    registry=REGISTRY
)

INVOICES_PROCESSED_COUNTER = Counter(
    'cuenly_invoices_processed_total',
    'Total number of invoices processed',
    ['status', 'user_type'],
    registry=REGISTRY
)

TRIAL_EXPIRATION_COUNTER = Counter(
    'cuenly_trial_expiration_events_total',
    'Total number of trial expiration events',
    ['action_taken'],
    registry=REGISTRY
)

REQUEST_DURATION_HISTOGRAM = Histogram(
    'cuenly_request_duration_seconds',
    'Duration of HTTP requests in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY
)

API_KEY_VALIDATIONS_COUNTER = Counter(
    'cuenly_api_key_validations_total',
    'Total number of API key validations',
    ['result', 'key_type'],
    registry=REGISTRY
)

AUTHENTICATION_EVENTS_COUNTER = Counter(
    'cuenly_authentication_events_total',
    'Total number of authentication events',
    ['event_type', 'result'],
    registry=REGISTRY
)

SUBSCRIPTION_EVENTS_COUNTER = Counter(
    'cuenly_subscription_events_total',
    'Total number of subscription events',
    ['event_type', 'subscription_type'],
    registry=REGISTRY
)

ERROR_COUNTER = Counter(
    'cuenly_errors_total',
    'Total number of application errors',
    ['error_type', 'severity'],
    registry=REGISTRY
)

class MetricsCollector:
    """Colector de métricas de negocio para Cuenly"""
    
    def __init__(self):
        # Usar el logger global de observabilidad para evitar problemas de inicialización
        from app.utils.observability import observability_logger
        self.logger = observability_logger
        
    def record_user_activity(self, user_id: str, subscription_type: str):
        """Registra actividad de usuario"""
        try:
            ACTIVE_USERS_GAUGE.labels(subscription_type=subscription_type).inc()
            self.logger.info(f"Recorded user activity for {user_id}", extra={
                'user_id': user_id,
                'subscription_type': subscription_type,
                'metric_type': 'user_activity'
            })
        except Exception as e:
            self.logger.error(f"Error recording user activity: {e}")
    
    def record_invoice_processing(self, status: str, user_type: str):
        """Registra procesamiento de factura"""
        try:
            INVOICES_PROCESSED_COUNTER.labels(
                status=status,
                user_type=user_type
            ).inc()
            self.logger.info(f"Recorded invoice processing: {status}", extra={
                'status': status,
                'user_type': user_type,
                'metric_type': 'invoice_processing'
            })
        except Exception as e:
            self.logger.error(f"Error recording invoice processing: {e}")
    
    def record_trial_expiration(self, action_taken: str):
        """Registra evento de expiración de trial"""
        try:
            TRIAL_EXPIRATION_COUNTER.labels(action_taken=action_taken).inc()
            self.logger.info(f"Recorded trial expiration: {action_taken}", extra={
                'action_taken': action_taken,
                'metric_type': 'trial_expiration'
            })
        except Exception as e:
            self.logger.error(f"Error recording trial expiration: {e}")
    
    def record_request_duration(self, method: str, endpoint: str, status_code: int, duration: float):
        """Registra duración de request HTTP"""
        try:
            REQUEST_DURATION_HISTOGRAM.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).observe(duration)
            self.logger.debug(f"Recorded request duration: {duration}s", extra={
                'method': method,
                'endpoint': endpoint,
                'status_code': status_code,
                'duration': duration,
                'metric_type': 'request_duration'
            })
        except Exception as e:
            self.logger.error(f"Error recording request duration: {e}")
    
    def record_api_key_validation(self, result: str, key_type: str = "frontend"):
        """Registra validación de API key"""
        try:
            API_KEY_VALIDATIONS_COUNTER.labels(
                result=result,
                key_type=key_type
            ).inc()
            self.logger.info(f"Recorded API key validation: {result}", extra={
                'result': result,
                'key_type': key_type,
                'metric_type': 'api_key_validation'
            })
        except Exception as e:
            self.logger.error(f"Error recording API key validation: {e}")
    
    def record_authentication_event(self, event_type: str, result: str):
        """Registra evento de autenticación"""
        try:
            AUTHENTICATION_EVENTS_COUNTER.labels(
                event_type=event_type,
                result=result
            ).inc()
            self.logger.info(f"Recorded auth event: {event_type} - {result}", extra={
                'event_type': event_type,
                'result': result,
                'metric_type': 'authentication'
            })
        except Exception as e:
            self.logger.error(f"Error recording authentication event: {e}")
    
    def record_subscription_event(self, event_type: str, subscription_type: str):
        """Registra evento de suscripción"""
        try:
            SUBSCRIPTION_EVENTS_COUNTER.labels(
                event_type=event_type,
                subscription_type=subscription_type
            ).inc()
            self.logger.info(f"Recorded subscription event: {event_type}", extra={
                'event_type': event_type,
                'subscription_type': subscription_type,
                'metric_type': 'subscription'
            })
        except Exception as e:
            self.logger.error(f"Error recording subscription event: {e}")
    
    def record_error(self, error_type: str, severity: str = "error"):
        """Registra error de aplicación"""
        try:
            ERROR_COUNTER.labels(
                error_type=error_type,
                severity=severity
            ).inc()
            self.logger.error(f"Recorded application error: {error_type}", extra={
                'error_type': error_type,
                'severity': severity,
                'metric_type': 'application_error'
            })
        except Exception as e:
            self.logger.error(f"Error recording application error: {e}")
    
    def get_metrics_output(self) -> str:
        """Obtiene salida de métricas en formato Prometheus"""
        try:
            return generate_latest(REGISTRY).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error generating metrics output: {e}")
            return ""

# Instancia global del colector
metrics_collector = MetricsCollector()

def time_request(method: str, endpoint: str, status_code: int):
    """Decorator para medir duración de requests"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics_collector.record_request_duration(method, endpoint, status_code, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.record_request_duration(method, endpoint, 500, duration)
                raise
        return wrapper
    return decorator