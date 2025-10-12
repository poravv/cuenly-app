import { Injectable } from '@angular/core';
import { initializeApp } from 'firebase/app';
import { getAnalytics, Analytics, logEvent, setUserId, setUserProperties } from 'firebase/analytics';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class FirebaseService {
  private analytics: Analytics | null = null;
  private app: any;

  constructor() {
    this.initializeFirebase();
  }

  private initializeFirebase(): void {
    try {
      // Inicializar Firebase App
      this.app = initializeApp(environment.firebase);
      
      // Inicializar Analytics solo en producción y si está disponible
      if (environment.production && environment.firebase.measurementId) {
        this.analytics = getAnalytics(this.app);
        console.log('✅ Firebase Analytics inicializado');
      } else {
        console.log('⚠️ Firebase Analytics deshabilitado en desarrollo');
      }
    } catch (error) {
      console.error('❌ Error inicializando Firebase:', error);
    }
  }

  /**
   * Registra un evento personalizado en Firebase Analytics
   */
  logEvent(eventName: string, parameters?: { [key: string]: any }): void {
    if (!this.analytics) {
      console.log(`📊 [DEV] Analytics Event: ${eventName}`, parameters);
      return;
    }

    try {
      logEvent(this.analytics, eventName, parameters);
      console.log(`📊 Analytics Event logged: ${eventName}`, parameters);
    } catch (error) {
      console.error('❌ Error logging analytics event:', error);
    }
  }

  /**
   * Configura el ID del usuario para Analytics
   */
  setUserId(userId: string): void {
    if (!this.analytics) {
      console.log(`👤 [DEV] User ID set: ${userId}`);
      return;
    }

    try {
      setUserId(this.analytics, userId);
      console.log(`👤 Analytics User ID set: ${userId}`);
    } catch (error) {
      console.error('❌ Error setting user ID:', error);
    }
  }

  /**
   * Configura propiedades del usuario para Analytics
   */
  setUserProperties(properties: { [key: string]: any }): void {
    if (!this.analytics) {
      console.log('👤 [DEV] User properties set:', properties);
      return;
    }

    try {
      setUserProperties(this.analytics, properties);
      console.log('👤 Analytics User properties set:', properties);
    } catch (error) {
      console.error('❌ Error setting user properties:', error);
    }
  }

  // Eventos de negocio específicos
  trackLogin(method: string = 'firebase'): void {
    this.logEvent('login', { method });
  }

  trackLogout(): void {
    this.logEvent('logout');
  }

  trackPageView(pageName: string): void {
    this.logEvent('page_view', { page_name: pageName });
  }

  trackFeatureUsed(featureName: string, metadata?: { [key: string]: any }): void {
    this.logEvent('feature_used', {
      feature_name: featureName,
      ...metadata
    });
  }

  trackButtonClick(buttonName: string, context?: string): void {
    this.logEvent('button_click', {
      button_name: buttonName,
      context: context || 'unknown'
    });
  }

  trackError(errorType: string, errorMessage: string, component?: string): void {
    this.logEvent('app_error', {
      error_type: errorType,
      error_message: errorMessage,
      component: component || 'unknown'
    });
  }
}