# Configuración mejorada de logging para observabilidad con Grafana+Loki+Prometheus

import logging
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
import sys
import os

# Context variables para tracing distribuido
request_id: ContextVar[str] = ContextVar('request_id', default='')
user_id: ContextVar[str] = ContextVar('user_id', default='')

class StructuredFormatter(logging.Formatter):
    """
    Formatter que genera logs estructurados en JSON para mejor parsing en Loki
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Crear estructura base del log
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Agregar context de tracing si existe
        req_id = request_id.get('')
        if req_id:
            log_entry['request_id'] = req_id
            
        uid = user_id.get('')
        if uid:
            log_entry['user_id'] = uid
            
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Agregar campos extra del record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'message', 'exc_info', 'exc_text', 
                          'stack_info', 'getMessage']:
                log_entry[key] = value
                
        return json.dumps(log_entry, ensure_ascii=False)

class ObservabilityLogger:
    """
    Logger centralizado para observabilidad mejorada
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)
        
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
        
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
        
    def warn(self, message: str, **kwargs):
        """Alias for warning"""
        self.warning(message, **kwargs)
        
    def error(self, message: str, exc_info=None, **kwargs):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
        
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, extra=kwargs)
        
    def setup_logging(self, level: str = "INFO"):
        """
        Configurar logging estructurado para Kubernetes + Loki
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # Limpiar handlers existentes
        self.logger.handlers.clear()
        
        # Handler para stdout (recogido por Kubernetes)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(StructuredFormatter())
        
        # Configurar logger
        self.logger.addHandler(stdout_handler)
        self.logger.setLevel(log_level)
        
        # Prevenir duplicados
        self.logger.propagate = False
        
    def set_request_context(self, request_id: str, user_email: str = ""):
        """
        Establecer contexto de request para tracing
        """
        request_id_var.set(request_id)
        if user_email:
            user_id_var.set(user_email)
            
    def clear_request_context(self):
        """
        Limpiar contexto de request
        """
        request_id_var.set('')
        user_id_var.set('')
        
    def log_api_request(self, method: str, endpoint: str, user_email: str = "", 
                       request_size: int = 0, **kwargs):
        """
        Log estructurado para requests de API
        """
        self.logger.info(
            f"API Request: {method} {endpoint}",
            extra={
                'event_type': 'api_request',
                'http_method': method,
                'endpoint': endpoint,
                'user_email': user_email,
                'request_size_bytes': request_size,
                **kwargs
            }
        )
        
    def log_api_response(self, method: str, endpoint: str, status_code: int,
                        response_time_ms: float, user_email: str = "", 
                        response_size: int = 0, **kwargs):
        """
        Log estructurado para responses de API
        """
        level = logging.INFO if status_code < 400 else logging.ERROR
        self.logger.log(
            level,
            f"API Response: {method} {endpoint} - {status_code}",
            extra={
                'event_type': 'api_response',
                'http_method': method,
                'endpoint': endpoint,
                'status_code': status_code,
                'response_time_ms': response_time_ms,
                'user_email': user_email,
                'response_size_bytes': response_size,
                **kwargs
            }
        )
        
    def log_business_event(self, event_name: str, user_email: str = "", **kwargs):
        """
        Log para eventos de negocio importantes
        """
        self.logger.info(
            f"Business Event: {event_name}",
            extra={
                'event_type': 'business_event',
                'event_name': event_name,
                'user_email': user_email,
                **kwargs
            }
        )
        
    def log_error(self, error_type: str, error_message: str, user_email: str = "", 
                  **kwargs):
        """
        Log estructurado para errores
        """
        self.logger.error(
            f"Error: {error_type} - {error_message}",
            extra={
                'event_type': 'error',
                'error_type': error_type,
                'error_message': error_message,
                'user_email': user_email,
                **kwargs
            }
        )
        
    def log_performance_metric(self, operation: str, duration_ms: float, 
                             success: bool, user_email: str = "", **kwargs):
        """
        Log para métricas de performance
        """
        self.logger.info(
            f"Performance: {operation} - {duration_ms}ms - {'SUCCESS' if success else 'FAILED'}",
            extra={
                'event_type': 'performance',
                'operation': operation,
                'duration_ms': duration_ms,
                'success': success,
                'user_email': user_email,
                **kwargs
            }
        )

# Variables de contexto global
request_id_var = request_id
user_id_var = user_id

# Logger global
observability_logger = ObservabilityLogger("cuenlyapp")
# Configurar el logger por defecto
observability_logger.setup_logging()