/**
 * Servicio de métricas de Firebase para observabilidad
 * Captura eventos de autenticación, performance y analytics
 */

import { Injectable } from '@angular/core';
import { ObservabilityService } from './observability.service';

// Interfaces locales para evitar dependencias de Firebase
interface FirebaseUser {
  uid?: string;
  email?: string;
  displayName?: string;
  emailVerified?: boolean;
  providerData?: any[];
  metadata?: {
    creationTime?: string;
    lastSignInTime?: string;
  };
}

@Injectable({
  providedIn: 'root'
})
export class FirebaseMetricsService {
  
  constructor(
    private observability: ObservabilityService
  ) {
    this.initializeFirebaseMetrics();
  }

  private initializeFirebaseMetrics(): void {
    // Placeholder para inicialización - se puede conectar con Firebase cuando esté configurado
    this.observability.debug('FirebaseMetricsService initialized', 'FirebaseMetricsService');
  }

  /**
   * Log eventos de autenticación de Firebase
   */
  logFirebaseAuth(eventType: string, user: FirebaseUser | null): void {
    this.observability.info(`Firebase auth event: ${eventType}`, 'FirebaseMetricsService', {
      event_type: 'firebase_auth_event',
      firebase_event: eventType,
      user_uid: user?.uid,
      user_email: user?.email,
      user_display_name: user?.displayName,
      user_email_verified: user?.emailVerified,
      auth_provider: user?.providerData?.[0]?.providerId,
      creation_time: user?.metadata?.creationTime,
      last_sign_in: user?.metadata?.lastSignInTime,
      security_event: true
    });
  }

  /**
   * Métricas de performance simuladas (sin Firebase Performance)
   */
  measureFirebasePerformance(operationName: string, fn: () => Promise<any>): Promise<any> {
    const startTime = performance.now();
    
    return fn()
      .then(result => {
        const duration = performance.now() - startTime;
        
        // Log en nuestro sistema
        this.observability.info(`Performance measurement: ${operationName}`, 'FirebaseMetricsService', {
          event_type: 'performance_measurement',
          operation: operationName,
          duration_ms: duration,
          success: true
        });
        
        return result;
      })
      .catch(error => {
        const duration = performance.now() - startTime;
        
        // Log error
        this.observability.error(`Performance measurement error: ${operationName}`, error, 'FirebaseMetricsService', {
          event_type: 'performance_measurement_error',
          operation: operationName,
          duration_ms: duration
        });
        
        throw error;
      });
  }

  /**
   * Eventos de negocio personalizados (sin Firebase Analytics)
   */
  logBusinessEvent(eventName: string, parameters: any, userEmail?: string): void {
    // Log en nuestro sistema
    this.observability.info(`Business event: ${eventName}`, 'FirebaseMetricsService', {
      event_type: 'business_event',
      business_event: eventName,
      user_email: userEmail,
      parameters: parameters,
      app_version: '2.0.0',
      timestamp: Date.now()
    });
  }

  /**
   * Métricas específicas de Cuenly para Firebase Analytics
   */
  logCuenlyEvents = {
    invoiceProcessed: (count: number, userEmail: string, isTrialUser: boolean) => {
      this.logBusinessEvent('invoice_processed', {
        invoice_count: count,
        user_type: isTrialUser ? 'trial' : 'premium',
        success: true
      }, userEmail);
    },

    trialExpired: (userEmail: string) => {
      this.logBusinessEvent('trial_expired', {
        user_email: userEmail
      }, userEmail);
    },

    subscriptionChanged: (userEmail: string, oldPlan: string, newPlan: string) => {
      this.logBusinessEvent('subscription_changed', {
        old_plan: oldPlan,
        new_plan: newPlan
      }, userEmail);
    },

    featureUsed: (featureName: string, userEmail: string) => {
      this.logBusinessEvent('feature_used', {
        feature_name: featureName
      }, userEmail);
    },

    errorOccurred: (errorType: string, errorMessage: string, userEmail?: string) => {
      this.logBusinessEvent('error_occurred', {
        error_type: errorType,
        error_message: errorMessage
      }, userEmail);
    },

    exportCompleted: (exportType: string, recordCount: number, userEmail: string) => {
      this.logBusinessEvent('export_completed', {
        export_type: exportType,
        record_count: recordCount
      }, userEmail);
    }
  };
}

/**
 * Decorator para medir performance automáticamente (sin Firebase)
 */
export function MeasureFirebasePerformance(operationName: string) {
  return function (target: any, propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value;

    descriptor.value = function (...args: any[]) {
      const firebaseMetrics = (this as any).firebaseMetrics as FirebaseMetricsService;
      
      if (firebaseMetrics && typeof method === 'function') {
        if (method.constructor.name === 'AsyncFunction') {
          return firebaseMetrics.measureFirebasePerformance(
            `${target.constructor.name}.${operationName || propertyName}`,
            () => method.apply(this, args)
          );
        } else {
          const startTime = performance.now();
          
          try {
            const result = method.apply(this, args);
            const duration = performance.now() - startTime;
            console.log(`Performance: ${operationName || propertyName} - ${duration}ms`);
            return result;
          } catch (error) {
            const duration = performance.now() - startTime;
            console.error(`Performance error: ${operationName || propertyName} - ${duration}ms`);
            throw error;
          }
        }
      }
      
      return method.apply(this, args);
    };

    return descriptor;
  };
}