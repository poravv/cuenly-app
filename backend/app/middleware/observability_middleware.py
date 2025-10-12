# Middleware de observabilidad para FastAPI

import time
import uuid
from typing import Callable, Dict, Any
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
import json

from app.utils.observability import observability_logger, request_id_var, user_id_var
from app.utils.metrics import metrics_collector

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura automáticamente métricas de requests para observabilidad
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generar ID único para el request
        req_id = str(uuid.uuid4())
        
        # Obtener información del request
        start_time = time.time()
        method = request.method
        url = str(request.url)
        path = request.url.path
        user_agent = request.headers.get("user-agent", "")
        content_length = request.headers.get("content-length", 0)
        
        try:
            content_length = int(content_length) if content_length else 0
        except:
            content_length = 0
            
        # Extraer user email si está disponible (de headers de auth)
        user_email = ""
        auth_header = request.headers.get("authorization", "")
        if auth_header and hasattr(request, 'state') and hasattr(request.state, 'user'):
            user_email = getattr(request.state.user, 'email', '')
        
        # Establecer contexto de tracing
        request_id_var.set(req_id)
        user_id_var.set(user_email)
        
        # Log del request entrante
        observability_logger.log_api_request(
            method=method,
            endpoint=path,
            user_email=user_email,
            request_size=content_length,
            user_agent=user_agent,
            remote_ip=request.client.host if request.client else "unknown"
        )
        
        # Procesar request
        try:
            response = await call_next(request)
            
            # Calcular tiempo de respuesta
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Obtener tamaño de respuesta
            response_size = 0
            if hasattr(response, 'headers'):
                content_length_header = response.headers.get("content-length")
                if content_length_header:
                    try:
                        response_size = int(content_length_header)
                    except:
                        pass
            
            # Log del response
            observability_logger.log_api_response(
                method=method,
                endpoint=path,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                user_email=user_email,
                response_size=response_size
            )
            
            # Registrar métricas en Prometheus
            metrics_collector.record_request_duration(
                method=method,
                endpoint=path,
                status_code=response.status_code,
                duration=response_time_ms / 1000  # Convertir a segundos
            )
            
            # Agregar headers de tracing
            response.headers["X-Request-ID"] = req_id
            if response_time_ms > 1000:  # Log slow requests
                observability_logger.log_performance_metric(
                    operation=f"{method} {path}",
                    duration_ms=response_time_ms,
                    success=response.status_code < 400,
                    user_email=user_email,
                    slow_request=True
                )
            
            return response
            
        except Exception as e:
            # Log de errores
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            observability_logger.log_error(
                error_type="request_processing_error",
                error_message=str(e),
                user_email=user_email,
                endpoint=path,
                method=method,
                response_time_ms=response_time_ms
            )
            
            raise e
        finally:
            # Limpiar contexto
            observability_logger.clear_request_context()

def log_endpoint_performance(endpoint_name: str):
    """
    Decorator para logging automático de performance en endpoints específicos
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise e
            finally:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                observability_logger.log_performance_metric(
                    operation=endpoint_name,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error if error else None
                )
        
        return wrapper
    return decorator

class BusinessEventLogger:
    """
    Logger especializado para eventos de negocio
    """
    
    @staticmethod
    def log_invoice_processing_started(user_email: str, email_count: int):
        observability_logger.log_business_event(
            "invoice_processing_started",
            user_email=user_email,
            email_count=email_count
        )
        # Registrar métrica
        metrics_collector.record_invoice_processing("started", "regular")
    
    @staticmethod
    def log_invoice_processing_completed(user_email: str, invoices_processed: int, 
                                       processing_time_ms: float, success: bool):
        observability_logger.log_business_event(
            "invoice_processing_completed",
            user_email=user_email,
            invoices_processed=invoices_processed,
            processing_time_ms=processing_time_ms,
            success=success
        )
        # Registrar métricas
        status = "success" if success else "error"
        metrics_collector.record_invoice_processing(status, "regular")
    
    @staticmethod
    def log_trial_expiration_attempt(user_email: str, action: str):
        observability_logger.log_business_event(
            "trial_expiration_attempt",
            user_email=user_email,
            attempted_action=action,
            security_event=True
        )
        # Registrar métricas
        metrics_collector.record_trial_expiration("blocked_access")
    
    @staticmethod
    def log_user_authentication(user_email: str, success: bool, method: str = "firebase"):
        observability_logger.log_business_event(
            "user_authentication",
            user_email=user_email,
            success=success,
            auth_method=method,
            security_event=True
        )
        # Registrar métricas
        result = "success" if success else "failure"
        metrics_collector.record_authentication_event("login", result)
    
    @staticmethod
    def log_subscription_event(user_email: str, event_type: str, plan_id: str = ""):
        observability_logger.log_business_event(
            "subscription_event",
            user_email=user_email,
            subscription_event_type=event_type,
            plan_id=plan_id
        )
    
    @staticmethod
    def log_automation_job_event(user_email: str, action: str, success: bool, 
                                interval_minutes: int = 0):
        observability_logger.log_business_event(
            "automation_job_event",
            user_email=user_email,
            job_action=action,
            success=success,
            interval_minutes=interval_minutes
        )