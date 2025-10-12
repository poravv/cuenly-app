// Servicio de logging centralizado para frontend con integración a backend

import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { environment } from '../../environments/environment';

export interface LogLevel {
  DEBUG: 0;
  INFO: 1;
  WARN: 2;
  ERROR: 3;
}

export interface FrontendLogEntry {
  timestamp: string;
  level: string;
  message: string;
  component?: string;
  user_email?: string;
  request_id?: string;
  event_type?: string;
  extra_data?: any;
  stack_trace?: string;
  url?: string;
  user_agent?: string;
}

export interface PerformanceMetric {
  operation: string;
  duration_ms: number;
  success: boolean;
  component?: string;
  user_email?: string;
  extra_data?: any;
}

@Injectable({
  providedIn: 'root'
})
export class ObservabilityService {
  private readonly apiUrl = environment.apiUrl;
  private readonly logLevel = environment.production ? 1 : 0; // INFO in prod, DEBUG in dev
  private sessionId = this.generateSessionId();
  private logBuffer: FrontendLogEntry[] = [];
  private isOnline$ = new BehaviorSubject<boolean>(navigator.onLine);
  
  private readonly LOG_LEVELS: LogLevel = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3
  };

  constructor(private http: HttpClient) {
    // Detectar cambios de conectividad
    window.addEventListener('online', () => this.isOnline$.next(true));
    window.addEventListener('offline', () => this.isOnline$.next(false));
    
    // Flush logs periódicamente
    setInterval(() => this.flushLogs(), 10000);
    
    // Flush logs antes de cerrar la página
    window.addEventListener('beforeunload', () => this.flushLogs());
  }

  private generateSessionId(): string {
    return 'frontend-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
  }

  private shouldLog(level: string): boolean {
    const numericLevel = this.LOG_LEVELS[level as keyof LogLevel];
    return numericLevel >= this.logLevel;
  }

  private createLogEntry(
    level: string, 
    message: string, 
    component?: string, 
    extraData?: any,
    eventType?: string
  ): FrontendLogEntry {
    const logEntry: FrontendLogEntry = {
      timestamp: new Date().toISOString(),
      level: level,
      message: message,
      component: component,
      request_id: this.sessionId,
      url: window.location.href,
      user_agent: navigator.userAgent,
      event_type: eventType
    };

    // Agregar user email si está disponible
    const userEmail = this.getCurrentUserEmail();
    if (userEmail) {
      logEntry.user_email = userEmail;
    }

    // Agregar datos extra si existen
    if (extraData) {
      logEntry.extra_data = extraData;
    }

    // Agregar stack trace para errores
    if (level === 'ERROR' && extraData instanceof Error) {
      logEntry.stack_trace = extraData.stack;
    }

    return logEntry;
  }

  private getCurrentUserEmail(): string {
    // Obtener email del usuario actual desde localStorage o servicio de auth
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user.email || '';
      }
    } catch (e) {
      // Silenciar error
    }
    return '';
  }

  private addToBuffer(logEntry: FrontendLogEntry): void {
    this.logBuffer.push(logEntry);
    
    // Mantener buffer size razonable
    if (this.logBuffer.length > 100) {
      this.logBuffer = this.logBuffer.slice(-50);
    }

    // Log inmediato para errores críticos
    if (logEntry.level === 'ERROR' && this.isOnline$.value) {
      this.sendLogsToBackend([logEntry]);
    }
  }

  private flushLogs(): void {
    if (this.logBuffer.length > 0 && this.isOnline$.value) {
      const logsToSend = [...this.logBuffer];
      this.logBuffer = [];
      this.sendLogsToBackend(logsToSend);
    }
  }

  private sendLogsToBackend(logs: FrontendLogEntry[]): void {
    if (!this.apiUrl || logs.length === 0) return;

    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'X-Frontend-Key': environment.frontendApiKey
    });

    this.http.post(`${this.apiUrl}/logs/frontend`, { logs }, { headers })
      .subscribe({
        next: () => {
          // Logs enviados exitosamente
        },
        error: (error) => {
          // Re-agregar logs al buffer si falla el envío
          this.logBuffer.unshift(...logs);
          console.warn('Failed to send logs to backend:', error);
        }
      });
  }

  // Métodos públicos de logging
  debug(message: string, component?: string, extraData?: any): void {
    if (this.shouldLog('DEBUG')) {
      console.log(`[DEBUG] ${component || 'App'}: ${message}`, extraData);
      const logEntry = this.createLogEntry('DEBUG', message, component, extraData);
      this.addToBuffer(logEntry);
    }
  }

  info(message: string, component?: string, extraData?: any): void {
    if (this.shouldLog('INFO')) {
      console.info(`[INFO] ${component || 'App'}: ${message}`, extraData);
      const logEntry = this.createLogEntry('INFO', message, component, extraData);
      this.addToBuffer(logEntry);
    }
  }

  warn(message: string, component?: string, extraData?: any): void {
    if (this.shouldLog('WARN')) {
      console.warn(`[WARN] ${component || 'App'}: ${message}`, extraData);
      const logEntry = this.createLogEntry('WARN', message, component, extraData);
      this.addToBuffer(logEntry);
    }
  }

  error(message: string, error?: Error, component?: string, extraData?: any): void {
    if (this.shouldLog('ERROR')) {
      console.error(`[ERROR] ${component || 'App'}: ${message}`, error, extraData);
      const logEntry = this.createLogEntry('ERROR', message, component, error || extraData, 'frontend_error');
      this.addToBuffer(logEntry);
    }
  }

  // Logging de eventos de negocio específicos
  logUserAction(action: string, component: string, extraData?: any): void {
    this.info(`User action: ${action}`, component, { ...extraData, event_type: 'user_action' });
  }

  logApiCall(method: string, endpoint: string, responseTime?: number, success?: boolean, extraData?: any): void {
    const level = success === false ? 'WARN' : 'INFO';
    const message = `API Call: ${method} ${endpoint}${responseTime ? ` (${responseTime}ms)` : ''}`;
    
    const logEntry = this.createLogEntry(level, message, 'ApiService', {
      ...extraData,
      http_method: method,
      endpoint: endpoint,
      response_time_ms: responseTime,
      success: success
    }, 'api_call');
    
    this.addToBuffer(logEntry);
  }

  logPerformance(operation: string, durationMs: number, component: string, success: boolean = true, extraData?: any): void {
    const metric: PerformanceMetric = {
      operation,
      duration_ms: durationMs,
      success,
      component,
      user_email: this.getCurrentUserEmail(),
      extra_data: extraData
    };

    this.info(`Performance: ${operation} - ${durationMs}ms`, component, {
      ...metric,
      event_type: 'performance_metric'
    });
  }

  logPageView(pageName: string, loadTime?: number): void {
    this.info(`Page view: ${pageName}`, 'Router', {
      page_name: pageName,
      load_time_ms: loadTime,
      event_type: 'page_view'
    });
  }

  // Métricas de rendimiento automáticas
  measureOperation<T>(operation: string, component: string, fn: () => T): T;
  measureOperation<T>(operation: string, component: string, fn: () => Promise<T>): Promise<T>;
  measureOperation<T>(operation: string, component: string, fn: () => T | Promise<T>): T | Promise<T> {
    const startTime = performance.now();
    
    try {
      const result = fn();
      
      if (result instanceof Promise) {
        return result
          .then(res => {
            const duration = performance.now() - startTime;
            this.logPerformance(operation, duration, component, true);
            return res;
          })
          .catch(error => {
            const duration = performance.now() - startTime;
            this.logPerformance(operation, duration, component, false, { error: error.message });
            throw error;
          });
      } else {
        const duration = performance.now() - startTime;
        this.logPerformance(operation, duration, component, true);
        return result;
      }
    } catch (error) {
      const duration = performance.now() - startTime;
      this.logPerformance(operation, duration, component, false, { error: (error as Error).message });
      throw error;
    }
  }
}