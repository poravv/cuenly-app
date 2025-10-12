"""
Métricas extendidas para Firebase y servicios externos en backend
Integración con Prometheus para monitoreo completo
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Dict, Any, Optional
import time
import logging
from datetime import datetime
import json
from app.utils.observability import ObservabilityLogger

# Métricas de Firebase Authentication
FIREBASE_AUTH_EVENTS = Counter(
    'cuenly_firebase_auth_events_total',
    'Total Firebase authentication events',
    ['event_type', 'success', 'provider']
)

FIREBASE_TOKEN_VALIDATION_DURATION = Histogram(
    'cuenly_firebase_token_validation_duration_seconds',
    'Duration of Firebase token validation',
    ['result']
)

# Métricas de Base de Datos
DATABASE_OPERATIONS = Counter(
    'cuenly_database_operations_total',
    'Total database operations',
    ['operation_type', 'collection', 'success']
)

DATABASE_QUERY_DURATION = Histogram(
    'cuenly_database_query_duration_seconds',
    'Duration of database queries',
    ['collection', 'operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

DATABASE_CONNECTION_POOL = Gauge(
    'cuenly_database_connections_active',
    'Active database connections'
)

# Métricas de OpenAI API
OPENAI_API_CALLS = Counter(
    'cuenly_openai_api_calls_total',
    'Total OpenAI API calls',
    ['model', 'success', 'user_type']
)

OPENAI_API_DURATION = Histogram(
    'cuenly_openai_api_duration_seconds',
    'Duration of OpenAI API calls',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

OPENAI_TOKEN_USAGE = Counter(
    'cuenly_openai_tokens_used_total',
    'Total tokens used in OpenAI API',
    ['model', 'token_type']  # token_type: prompt, completion
)

# Métricas de Email Processing
EMAIL_PROCESSING_DURATION = Histogram(
    'cuenly_email_processing_duration_seconds',
    'Duration of email processing',
    ['user_type', 'success']
)

EMAIL_MESSAGES_PROCESSED = Counter(
    'cuenly_email_messages_processed_total',
    'Total email messages processed',
    ['source', 'has_attachments', 'success']
)

# Métricas de Trial y Suscripciones
TRIAL_EVENTS = Counter(
    'cuenly_trial_events_total',
    'Total trial events',
    ['event_type', 'user_type']  # event_type: started, expired, converted
)

SUBSCRIPTION_EVENTS = Counter(
    'cuenly_subscription_events_total',
    'Total subscription events',
    ['event_type', 'plan_type']  # event_type: created, upgraded, cancelled
)

# Métricas de Sistema
SYSTEM_RESOURCE_USAGE = Gauge(
    'cuenly_system_resource_usage',
    'System resource usage',
    ['resource_type']  # memory, cpu, disk
)

BACKGROUND_JOBS = Gauge(
    'cuenly_background_jobs_active',
    'Active background jobs',
    ['job_type']
)

# Métricas de Seguridad
SECURITY_EVENTS = Counter(
    'cuenly_security_events_total',
    'Total security events',
    ['event_type', 'severity', 'user_type']
)

# Información del sistema
SYSTEM_INFO = Info(
    'cuenly_system_info',
    'System information'
)

class ExtendedMetricsCollector:
    """Colector extendido de métricas para integración con servicios externos"""
    
    def __init__(self):
        self.logger = ObservabilityLogger(__name__)
        
    def record_firebase_auth_event(self, event_type: str, success: bool, 
                                 provider: str = "email", user_email: str = ""):
        """Registra evento de autenticación Firebase"""
        try:
            FIREBASE_AUTH_EVENTS.labels(
                event_type=event_type,
                success=str(success).lower(),
                provider=provider
            ).inc()
            
            self.logger.info(f"Firebase auth event: {event_type}", extra={
                'user_email': user_email,
                'provider': provider,
                'success': success,
                'event_type': 'firebase_auth',
                'metric_type': 'firebase_auth_event'
            })
        except Exception as e:
            self.logger.error(f"Error recording Firebase auth event: {e}")
    
    def record_firebase_token_validation(self, duration: float, success: bool, user_email: str = ""):
        """Registra validación de token Firebase"""
        try:
            result = "success" if success else "failure"
            FIREBASE_TOKEN_VALIDATION_DURATION.labels(result=result).observe(duration)
            
            self.logger.debug(f"Firebase token validation: {duration}s", extra={
                'user_email': user_email,
                'duration': duration,
                'success': success,
                'metric_type': 'firebase_token_validation'
            })
        except Exception as e:
            self.logger.error(f"Error recording Firebase token validation: {e}")
    
    def record_database_operation(self, operation_type: str, collection: str, 
                                success: bool, duration: float = 0, user_email: str = ""):
        """Registra operación de base de datos"""
        try:
            DATABASE_OPERATIONS.labels(
                operation_type=operation_type,
                collection=collection,
                success=str(success).lower()
            ).inc()
            
            if duration > 0:
                DATABASE_QUERY_DURATION.labels(
                    collection=collection,
                    operation=operation_type
                ).observe(duration)
            
            self.logger.debug(f"DB operation: {operation_type} on {collection}", extra={
                'user_email': user_email,
                'operation_type': operation_type,
                'collection': collection,
                'duration': duration,
                'success': success,
                'metric_type': 'database_operation'
            })
        except Exception as e:
            self.logger.error(f"Error recording database operation: {e}")
    
    def record_openai_api_call(self, model: str, success: bool, duration: float, 
                             tokens_used: Dict[str, int], user_type: str = "unknown",
                             user_email: str = ""):
        """Registra llamada a OpenAI API"""
        try:
            OPENAI_API_CALLS.labels(
                model=model,
                success=str(success).lower(),
                user_type=user_type
            ).inc()
            
            OPENAI_API_DURATION.labels(model=model).observe(duration)
            
            # Registrar tokens usados
            for token_type, count in tokens_used.items():
                OPENAI_TOKEN_USAGE.labels(
                    model=model,
                    token_type=token_type
                ).inc(count)
            
            self.logger.info(f"OpenAI API call: {model}", extra={
                'user_email': user_email,
                'model': model,
                'duration': duration,
                'tokens_used': tokens_used,
                'user_type': user_type,
                'success': success,
                'metric_type': 'openai_api_call'
            })
        except Exception as e:
            self.logger.error(f"Error recording OpenAI API call: {e}")
    
    def record_email_processing(self, duration: float, success: bool, 
                              messages_count: int, user_type: str = "unknown",
                              user_email: str = ""):
        """Registra procesamiento de emails"""
        try:
            EMAIL_PROCESSING_DURATION.labels(
                user_type=user_type,
                success=str(success).lower()
            ).observe(duration)
            
            self.logger.info(f"Email processing completed", extra={
                'user_email': user_email,
                'duration': duration,
                'messages_count': messages_count,
                'user_type': user_type,
                'success': success,
                'metric_type': 'email_processing'
            })
        except Exception as e:
            self.logger.error(f"Error recording email processing: {e}")
    
    def record_trial_event(self, event_type: str, user_type: str, user_email: str = ""):
        """Registra evento de trial"""
        try:
            TRIAL_EVENTS.labels(
                event_type=event_type,
                user_type=user_type
            ).inc()
            
            self.logger.warn(f"Trial event: {event_type}", extra={
                'user_email': user_email,
                'event_type': event_type,
                'user_type': user_type,
                'metric_type': 'trial_event',
                'business_event': True
            })
        except Exception as e:
            self.logger.error(f"Error recording trial event: {e}")
    
    def record_subscription_event(self, event_type: str, plan_type: str, user_email: str = ""):
        """Registra evento de suscripción"""
        try:
            SUBSCRIPTION_EVENTS.labels(
                event_type=event_type,
                plan_type=plan_type
            ).inc()
            
            self.logger.info(f"Subscription event: {event_type}", extra={
                'user_email': user_email,
                'event_type': event_type,
                'plan_type': plan_type,
                'metric_type': 'subscription_event',
                'business_event': True
            })
        except Exception as e:
            self.logger.error(f"Error recording subscription event: {e}")
    
    def record_security_event(self, event_type: str, severity: str, user_type: str = "unknown",
                            user_email: str = "", details: Dict[str, Any] = None):
        """Registra evento de seguridad"""
        try:
            SECURITY_EVENTS.labels(
                event_type=event_type,
                severity=severity,
                user_type=user_type
            ).inc()
            
            self.logger.warn(f"Security event: {event_type}", extra={
                'user_email': user_email,
                'event_type': event_type,
                'severity': severity,
                'user_type': user_type,
                'details': details or {},
                'metric_type': 'security_event',
                'security_event': True
            })
        except Exception as e:
            self.logger.error(f"Error recording security event: {e}")
    
    def update_system_resource_usage(self, resource_type: str, value: float):
        """Actualiza uso de recursos del sistema"""
        try:
            SYSTEM_RESOURCE_USAGE.labels(resource_type=resource_type).set(value)
        except Exception as e:
            self.logger.error(f"Error updating system resource usage: {e}")
    
    def update_background_jobs(self, job_type: str, count: int):
        """Actualiza contador de jobs en background"""
        try:
            BACKGROUND_JOBS.labels(job_type=job_type).set(count)
        except Exception as e:
            self.logger.error(f"Error updating background jobs: {e}")
    
    def set_system_info(self, info_dict: Dict[str, str]):
        """Establece información del sistema"""
        try:
            SYSTEM_INFO.info(info_dict)
        except Exception as e:
            self.logger.error(f"Error setting system info: {e}")

# Instancia global
extended_metrics = ExtendedMetricsCollector()

def monitor_firebase_auth(func):
    """Decorator para monitorear autenticación Firebase"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        success = False
        user_email = ""
        
        try:
            result = func(*args, **kwargs)
            success = True
            # Intentar extraer email del resultado si está disponible
            if hasattr(result, 'get'):
                user_email = result.get('email', '')
            return result
        except Exception as e:
            success = False
            raise e
        finally:
            duration = time.time() - start_time
            extended_metrics.record_firebase_token_validation(duration, success, user_email)
    
    return wrapper

def monitor_database_operation(operation_type: str, collection: str):
    """Decorator para monitorear operaciones de base de datos"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            user_email = ""
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration = time.time() - start_time
                extended_metrics.record_database_operation(
                    operation_type, collection, success, duration, user_email
                )
        
        return wrapper
    return decorator

def monitor_openai_call(model: str):
    """Decorator para monitorear llamadas a OpenAI"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            tokens_used = {}
            user_email = ""
            user_type = "unknown"
            
            try:
                result = func(*args, **kwargs)
                success = True
                
                # Intentar extraer información de tokens del resultado
                if isinstance(result, dict):
                    usage = result.get('usage', {})
                    tokens_used = {
                        'prompt': usage.get('prompt_tokens', 0),
                        'completion': usage.get('completion_tokens', 0)
                    }
                
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration = time.time() - start_time
                extended_metrics.record_openai_api_call(
                    model, success, duration, tokens_used, user_type, user_email
                )
        
        return wrapper
    return decorator