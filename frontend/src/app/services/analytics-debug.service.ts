import { Injectable } from '@angular/core';
import { FirebaseService } from './firebase.service';

@Injectable({
  providedIn: 'root'
})
export class AnalyticsDebugService {
  
  constructor(private firebase: FirebaseService) {
    // Hacer accesible globalmente para debugging en producción
    (window as any).analyticsDebug = this;
  }

  /**
   * Función para probar Analytics desde la consola del navegador
   * Uso: analyticsDebug.test()
   */
  test(): void {
    console.log('🧪 Testing Firebase Analytics...');
    
    // Test eventos básicos
    this.firebase.logEvent('debug_test', {
      timestamp: new Date().toISOString(),
      user_agent: navigator.userAgent,
      url: window.location.href
    });
    
    this.firebase.trackPageView('debug_test_page');
    this.firebase.trackFeatureUsed('debug_test_feature', { test: true });
    
    console.log('✅ Test events sent. Check Firebase Console in ~30 minutes.');
  }

  /**
   * Información del estado actual
   */
  info(): void {
    console.log('📊 Firebase Analytics Debug Info:');
    console.log('- Production mode:', (window as any).environment?.production || 'unknown');
    console.log('- Measurement ID:', (window as any).environment?.firebase?.measurementId || 'unknown');
    console.log('- Current URL:', window.location.href);
    console.log('- User Agent:', navigator.userAgent);
    
    // Verificar si gtag existe
    if (typeof (window as any).gtag !== 'undefined') {
      console.log('✅ gtag found - Analytics should be working');
    } else {
      console.log('❌ gtag not found - Analytics not initialized');
    }
  }

  /**
   * Forzar eventos de prueba
   */
  forceEvents(): void {
    console.log('🚀 Forcing multiple test events...');
    
    for (let i = 1; i <= 5; i++) {
      this.firebase.logEvent(`test_event_${i}`, {
        test_number: i,
        timestamp: Date.now(),
        forced: true
      });
    }
    
    console.log('✅ 5 test events sent');
  }
}