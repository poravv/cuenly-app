/**
 * Servicio de métricas extendido para Firebase y otras plataformas
 * Compatible con la configuración actual de Firebase
 */

import { Injectable } from '@angular/core';
import { ObservabilityService } from './observability.service';
import { UserService } from './user.service';
import { environment } from '../../environments/environment';

interface PerformanceMetric {
  name: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  success: boolean;
  metadata?: any;
}

@Injectable({
  providedIn: 'root'
})
export class ExtendedMetricsService {
  
  private performanceMetrics: Map<string, PerformanceMetric> = new Map();
  private sessionId: string;
  private sessionStartTime: number;

  constructor(
    private observability: ObservabilityService,
    private userService: UserService
  ) {
    this.sessionId = this.generateSessionId();
    this.sessionStartTime = Date.now();
    this.initializeMetrics();
  }

  private generateSessionId(): string {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private initializeMetrics(): void {
    // Log session started
    this.observability.info('User session started', 'ExtendedMetricsService', {
      event_type: 'session_started',
      session_id: this.sessionId,
      user_agent: navigator.userAgent,
      screen_resolution: `${screen.width}x${screen.height}`,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      language: navigator.language,
      platform: navigator.platform
    });

    // Monitor page visibility changes
    document.addEventListener('visibilitychange', () => {
      this.logVisibilityChange();
    });

    // Monitor online/offline status
    window.addEventListener('online', () => this.logConnectivityChange(true));
    window.addEventListener('offline', () => this.logConnectivityChange(false));

    // Log session end on page unload
    window.addEventListener('beforeunload', () => {
      this.logSessionEnd();
    });
  }

  /**
   * Métricas de Firebase Authentication (usando eventos existentes)
   */
  logFirebaseAuthEvent(eventType: 'login' | 'logout' | 'token_refresh' | 'auth_error', userEmail?: string, metadata?: any): void {
    const currentUser = this.userService.getCurrentProfile();
    
    this.observability.info(`Firebase auth: ${eventType}`, 'ExtendedMetricsService', {
      event_type: 'firebase_auth_event',
      firebase_event_type: eventType,
      user_email: userEmail || currentUser?.email,
      session_id: this.sessionId,
      metadata: metadata,
      security_event: true
    });
  }

  /**
   * Métricas de Performance Web Vitals
   */
  measureWebVitals(): void {
    // Largest Contentful Paint (LCP)
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === 'largest-contentful-paint') {
            this.observability.info('Web Vitals - LCP', 'ExtendedMetricsService', {
              event_type: 'web_vitals',
              metric_name: 'largest_contentful_paint',
              value: entry.startTime,
              session_id: this.sessionId,
              url: window.location.pathname
            });
          }
        }
      });
      
      try {
        observer.observe({ entryTypes: ['largest-contentful-paint'] });
      } catch (e) {
        // Browser doesn't support this metric
      }
    }

    // Navigation timing
    setTimeout(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      if (navigation) {
        this.observability.info('Page load performance', 'ExtendedMetricsService', {
          event_type: 'page_performance',
          dns_lookup: navigation.domainLookupEnd - navigation.domainLookupStart,
          tcp_connect: navigation.connectEnd - navigation.connectStart,
          request_time: navigation.responseEnd - navigation.requestStart,
          dom_loading: navigation.domContentLoadedEventEnd - navigation.fetchStart,
          page_load: navigation.loadEventEnd - navigation.fetchStart,
          session_id: this.sessionId,
          url: window.location.pathname
        });
      }
    }, 0);
  }

  /**
   * Monitoreo de errores JavaScript
   */
  initErrorTracking(): void {
    window.addEventListener('error', (event) => {
      const currentUser = this.userService.getCurrentProfile();
      
      this.observability.error('JavaScript error', event.error, 'ExtendedMetricsService', {
        event_type: 'javascript_error',
        error_message: event.message,
        filename: event.filename,
        line_number: event.lineno,
        column_number: event.colno,
        user_email: currentUser?.email,
        session_id: this.sessionId,
        url: window.location.href,
        user_agent: navigator.userAgent
      });
    });

    window.addEventListener('unhandledrejection', (event) => {
      const currentUser = this.userService.getCurrentProfile();
      
      this.observability.error('Unhandled promise rejection', new Error(event.reason), 'ExtendedMetricsService', {
        event_type: 'unhandled_promise_rejection',
        reason: event.reason,
        user_email: currentUser?.email,
        session_id: this.sessionId,
        url: window.location.href
      });
    });
  }

  /**
   * Métricas de uso de recursos
   */
  logResourceUsage(): void {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      
      this.observability.debug('Memory usage', 'ExtendedMetricsService', {
        event_type: 'resource_usage',
        used_memory_mb: Math.round(memory.usedJSHeapSize / 1048576),
        total_memory_mb: Math.round(memory.totalJSHeapSize / 1048576),
        memory_limit_mb: Math.round(memory.jsHeapSizeLimit / 1048576),
        session_id: this.sessionId
      });
    }

    // Network information (si está disponible)
    if ('connection' in navigator) {
      const connection = (navigator as any).connection;
      
      this.observability.debug('Network information', 'ExtendedMetricsService', {
        event_type: 'network_info',
        effective_type: connection.effectiveType,
        downlink: connection.downlink,
        rtt: connection.rtt,
        save_data: connection.saveData,
        session_id: this.sessionId
      });
    }
  }

  /**
   * Métricas específicas de Cuenly
   */
  logCuenlyBusinessEvents = {
    invoiceProcessingStarted: (emailCount: number) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.info('Invoice processing started', 'ExtendedMetricsService', {
        event_type: 'cuenly_invoice_processing_started',
        email_count: emailCount,
        user_email: currentUser?.email,
        user_type: currentUser?.is_trial ? 'trial' : 'premium',
        session_id: this.sessionId,
        business_event: true
      });
    },

    invoiceProcessingCompleted: (invoiceCount: number, duration: number, success: boolean) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.info('Invoice processing completed', 'ExtendedMetricsService', {
        event_type: 'cuenly_invoice_processing_completed',
        invoice_count: invoiceCount,
        duration_ms: duration,
        success: success,
        user_email: currentUser?.email,
        user_type: currentUser?.is_trial ? 'trial' : 'premium',
        session_id: this.sessionId,
        business_event: true
      });
    },

    featureUsage: (featureName: string, metadata?: any) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.info(`Feature used: ${featureName}`, 'ExtendedMetricsService', {
        event_type: 'cuenly_feature_usage',
        feature_name: featureName,
        user_email: currentUser?.email,
        user_role: currentUser?.role,
        is_trial: currentUser?.is_trial,
        session_id: this.sessionId,
        metadata: metadata,
        business_event: true
      });
    },

    trialEvent: (eventType: 'trial_started' | 'trial_expired' | 'trial_extended', daysRemaining?: number) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.warn(`Trial event: ${eventType}`, 'ExtendedMetricsService', {
        event_type: 'cuenly_trial_event',
        trial_event_type: eventType,
        days_remaining: daysRemaining,
        user_email: currentUser?.email,
        session_id: this.sessionId,
        business_event: true,
        security_event: eventType === 'trial_expired'
      });
    },

    subscriptionEvent: (eventType: string, oldPlan?: string, newPlan?: string) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.info(`Subscription event: ${eventType}`, 'ExtendedMetricsService', {
        event_type: 'cuenly_subscription_event',
        subscription_event_type: eventType,
        old_plan: oldPlan,
        new_plan: newPlan,
        user_email: currentUser?.email,
        session_id: this.sessionId,
        business_event: true
      });
    },

    apiCallPerformance: (endpoint: string, method: string, duration: number, success: boolean, statusCode?: number) => {
      const currentUser = this.userService.getCurrentProfile();
      this.observability.debug(`API performance: ${method} ${endpoint}`, 'ExtendedMetricsService', {
        event_type: 'cuenly_api_performance',
        endpoint: endpoint,
        method: method,
        duration_ms: duration,
        success: success,
        status_code: statusCode,
        user_email: currentUser?.email,
        session_id: this.sessionId
      });
    }
  };

  private logVisibilityChange(): void {
    const currentUser = this.userService.getCurrentProfile();
    
    this.observability.debug(`Page visibility: ${document.visibilityState}`, 'ExtendedMetricsService', {
      event_type: 'page_visibility_change',
      visibility_state: document.visibilityState,
      user_email: currentUser?.email,
      session_id: this.sessionId,
      url: window.location.pathname
    });
  }

  private logConnectivityChange(isOnline: boolean): void {
    const currentUser = this.userService.getCurrentProfile();
    
    this.observability.info(`Connectivity changed: ${isOnline ? 'online' : 'offline'}`, 'ExtendedMetricsService', {
      event_type: 'connectivity_change',
      is_online: isOnline,
      user_email: currentUser?.email,
      session_id: this.sessionId
    });
  }

  private logSessionEnd(): void {
    const currentUser = this.userService.getCurrentProfile();
    const sessionDuration = Date.now() - this.sessionStartTime;
    
    this.observability.info('User session ended', 'ExtendedMetricsService', {
      event_type: 'session_ended',
      session_id: this.sessionId,
      session_duration_ms: sessionDuration,
      user_email: currentUser?.email,
      page_views: this.getPageViewCount(),
      business_event: true
    });
  }

  private getPageViewCount(): number {
    // Simple contador basado en navigation entries
    return performance.getEntriesByType('navigation').length;
  }

  /**
   * Métricas de Google Analytics (si está configurado)
   */
  logGoogleAnalyticsEvent(eventName: string, parameters: any): void {
    // Si tienes Google Analytics configurado
    if (typeof gtag !== 'undefined') {
      gtag('event', eventName, parameters);
    }

    // También log en nuestro sistema
    const currentUser = this.userService.getCurrentProfile();
    this.observability.info(`GA event: ${eventName}`, 'ExtendedMetricsService', {
      event_type: 'google_analytics_event',
      ga_event_name: eventName,
      ga_parameters: parameters,
      user_email: currentUser?.email,
      session_id: this.sessionId
    });
  }
}

/**
 * Decorator para medir performance de métodos
 */
export function MeasurePerformance(metricName?: string) {
  return function (target: any, propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value;
    const measurementName = metricName || `${target.constructor.name}.${propertyName}`;

    descriptor.value = function (...args: any[]) {
      const extendedMetrics = (this as any).extendedMetrics as ExtendedMetricsService;
      const startTime = performance.now();
      
      try {
        const result = method.apply(this, args);
        
        // Handle both sync and async methods
        if (result && typeof result.then === 'function') {
          return result
            .then((res: any) => {
              const duration = performance.now() - startTime;
              if (extendedMetrics) {
                extendedMetrics.logCuenlyBusinessEvents.apiCallPerformance(
                  measurementName, 'METHOD', duration, true
                );
              }
              return res;
            })
            .catch((error: any) => {
              const duration = performance.now() - startTime;
              if (extendedMetrics) {
                extendedMetrics.logCuenlyBusinessEvents.apiCallPerformance(
                  measurementName, 'METHOD', duration, false
                );
              }
              throw error;
            });
        } else {
          const duration = performance.now() - startTime;
          if (extendedMetrics) {
            extendedMetrics.logCuenlyBusinessEvents.apiCallPerformance(
              measurementName, 'METHOD', duration, true
            );
          }
          return result;
        }
      } catch (error) {
        const duration = performance.now() - startTime;
        if (extendedMetrics) {
          extendedMetrics.logCuenlyBusinessEvents.apiCallPerformance(
            measurementName, 'METHOD', duration, false
          );
        }
        throw error;
      }
    };

    return descriptor;
  };
}

// Declaración global para gtag (Google Analytics)
declare global {
  function gtag(...args: any[]): void;
}