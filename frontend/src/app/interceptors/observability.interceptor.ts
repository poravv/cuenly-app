/**
 * Interceptor HTTP para observabilidad automática
 * Captura automáticamente todas las llamadas API para logging centralizado
 */

import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent, HttpResponse, HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { ObservabilityService } from '../services/observability.service';
import { UserService } from '../services/user.service';

@Injectable()
export class ObservabilityInterceptor implements HttpInterceptor {

  constructor(
    private observability: ObservabilityService,
    private userService: UserService
  ) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    const startTime = performance.now();
    const currentUser = this.userService.getCurrentProfile();
    
    // Extraer información del request
    const requestInfo = {
      method: req.method,
      url: req.urlWithParams,
      endpoint: req.url.replace(/\?.*$/, ''), // URL sin parámetros
      user_email: currentUser?.email,
      user_role: currentUser?.role,
      is_trial: currentUser?.is_trial,
      has_frontend_key: req.headers.has('X-Frontend-Key'),
      request_size: this.getRequestSize(req.body)
    };

    // Log del request iniciado (solo en modo debug)
    this.observability.debug(`API Request: ${req.method} ${req.url}`, 'HttpInterceptor', {
      ...requestInfo,
      event_type: 'api_request_start'
    });
    
    return next.handle(req).pipe(
      tap((event) => {
        if (event instanceof HttpResponse) {
          const duration = performance.now() - startTime;
          
          // Log de respuesta exitosa
          this.observability.logApiCall(
            req.method,
            requestInfo.endpoint,
            duration,
            true,
            {
              status_code: event.status,
              user_email: requestInfo.user_email,
              user_role: requestInfo.user_role,
              is_trial: requestInfo.is_trial,
              response_size: this.getResponseSize(event.body),
              request_size: requestInfo.request_size,
              endpoint_category: this.categorizeEndpoint(req.url)
            }
          );

          // Log eventos de negocio específicos basados en endpoint
          this.logBusinessEvents(req, event, duration, requestInfo);
        }
      }),
      catchError((error: HttpErrorResponse) => {
        const duration = performance.now() - startTime;
        
        // Log de error en API call
        this.observability.logApiCall(
          req.method,
          requestInfo.endpoint,
          duration,
          false,
          {
            status_code: error.status,
            error_message: error.message,
            error_type: this.getErrorType(error),
            user_email: requestInfo.user_email,
            user_role: requestInfo.user_role,
            is_trial: requestInfo.is_trial,
            request_size: requestInfo.request_size,
            endpoint_category: this.categorizeEndpoint(req.url)
          }
        );

        // Log errores específicos por tipo
        this.logSpecificErrors(error, requestInfo);

        // Re-throw el error
        throw error;
      })
    );
  }

  private getRequestSize(body: any): number {
    if (!body) return 0;
    try {
      return new Blob([typeof body === 'string' ? body : JSON.stringify(body)]).size;
    } catch {
      return 0;
    }
  }

  private getResponseSize(body: any): number {
    if (!body) return 0;
    try {
      return new Blob([typeof body === 'string' ? body : JSON.stringify(body)]).size;
    } catch {
      return 0;
    }
  }

  private categorizeEndpoint(url: string): string {
    if (url.includes('/process')) return 'invoice_processing';
    if (url.includes('/job')) return 'job_management';
    if (url.includes('/user')) return 'user_management';
    if (url.includes('/invoice')) return 'invoice_data';
    if (url.includes('/export')) return 'data_export';
    if (url.includes('/template')) return 'template_management';
    if (url.includes('/subscription')) return 'subscription';
    if (url.includes('/admin')) return 'admin';
    if (url.includes('/status') || url.includes('/health')) return 'system_status';
    return 'other';
  }

  private getErrorType(error: HttpErrorResponse): string {
    if (error.status === 401) return 'authentication_error';
    if (error.status === 403) return 'authorization_error';
    if (error.status === 404) return 'not_found_error';
    if (error.status === 429) return 'rate_limit_error';
    if (error.status >= 500) return 'server_error';
    if (error.status >= 400) return 'client_error';
    return 'network_error';
  }

  private logBusinessEvents(req: HttpRequest<any>, response: HttpResponse<any>, duration: number, requestInfo: any): void {
    const url = req.url;
    
    // Procesamiento de facturas
    if (req.method === 'POST' && url.includes('/process')) {
      this.observability.info('Invoice processing completed', 'HttpInterceptor', {
        event_type: 'invoice_processing_completed',
        user_email: requestInfo.user_email,
        duration_ms: duration,
        success: response.status === 200,
        endpoint_category: 'invoice_processing'
      });
    }

    // Job management
    if (url.includes('/job/start') && req.method === 'POST') {
      this.observability.info('Scheduled job started', 'HttpInterceptor', {
        event_type: 'scheduled_job_started',
        user_email: requestInfo.user_email,
        endpoint_category: 'job_management'
      });
    }

    if (url.includes('/job/stop') && req.method === 'POST') {
      this.observability.info('Scheduled job stopped', 'HttpInterceptor', {
        event_type: 'scheduled_job_stopped',
        user_email: requestInfo.user_email,
        endpoint_category: 'job_management'
      });
    }

    // Export operations
    if (url.includes('/export') && req.method === 'POST') {
      this.observability.info('Data export completed', 'HttpInterceptor', {
        event_type: 'data_export_completed',
        user_email: requestInfo.user_email,
        duration_ms: duration,
        endpoint_category: 'data_export'
      });
    }

    // User profile updates
    if (url.includes('/user/profile') && req.method === 'GET') {
      const profile = response.body;
      if (profile) {
        this.observability.debug('User profile accessed', 'HttpInterceptor', {
          event_type: 'user_profile_accessed',
          user_email: requestInfo.user_email,
          profile_status: profile.status,
          is_trial: profile.is_trial,
          trial_expired: profile.trial_expired
        });
      }
    }

    // Subscription changes
    if (url.includes('/subscription') && req.method === 'POST') {
      this.observability.info('Subscription change requested', 'HttpInterceptor', {
        event_type: 'subscription_change_requested',
        user_email: requestInfo.user_email,
        endpoint_category: 'subscription'
      });
    }
  }

  private logSpecificErrors(error: HttpErrorResponse, requestInfo: any): void {
    const errorMessage = error.error?.detail || error.error?.message || error.message;

    // Trial expirado
    if (errorMessage?.includes('TRIAL_EXPIRED')) {
      this.observability.warn('Trial expired action blocked', 'HttpInterceptor', {
        event_type: 'trial_expired_blocked',
        user_email: requestInfo.user_email,
        attempted_endpoint: requestInfo.endpoint,
        security_event: true
      });
    }

    // Errores de autenticación
    if (error.status === 401) {
      this.observability.warn('Authentication failed', 'HttpInterceptor', {
        event_type: 'authentication_failed',
        user_email: requestInfo.user_email,
        endpoint: requestInfo.endpoint,
        security_event: true
      });
    }

    // Errores de autorización
    if (error.status === 403) {
      this.observability.warn('Authorization failed', 'HttpInterceptor', {
        event_type: 'authorization_failed',
        user_email: requestInfo.user_email,
        endpoint: requestInfo.endpoint,
        security_event: true
      });
    }

    // Rate limiting
    if (error.status === 429) {
      this.observability.warn('Rate limit exceeded', 'HttpInterceptor', {
        event_type: 'rate_limit_exceeded',
        user_email: requestInfo.user_email,
        endpoint: requestInfo.endpoint,
        security_event: true
      });
    }

    // Errores de servidor (críticos)
    if (error.status >= 500) {
      this.observability.error('Server error occurred', error, 'HttpInterceptor', {
        event_type: 'server_error',
        user_email: requestInfo.user_email,
        endpoint: requestInfo.endpoint,
        status_code: error.status,
        critical_error: true
      });
    }
  }
}