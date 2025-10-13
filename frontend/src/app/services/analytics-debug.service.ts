import { Injectable } from '@angular/core';
import { FirebaseService } from './firebase.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AnalyticsDebugService {
  
  constructor(private firebase: FirebaseService) {
    // Hacer accesible globalmente para debugging en producción
    (window as any).analyticsDebug = this;
    this.logStartupInfo();
  }

  /**
   * Información de inicio automática
   */
  private logStartupInfo(): void {
    console.log('🔧 Analytics Debug Service initialized');
    console.log('- Environment production:', environment.production);
    console.log('- Measurement ID:', environment.firebase?.measurementId);
    console.log('- Current URL:', window.location.href);
    
    // Test automático al iniciar
    setTimeout(() => {
      this.testBasicEvents();
    }, 2000);
  }

  /**
   * Test completo de Analytics - usa: analyticsDebug.fullTest()
   */
  fullTest(): void {
    console.log('🧪 === FIREBASE ANALYTICS FULL TEST ===');
    
    // 1. Verificar configuración
    this.checkConfiguration();
    
    // 2. Test básico de eventos
    this.testBasicEvents();
    
    // 3. Test eventos con datos
    this.testEventsWithData();
    
    // 4. Instrucciones para DebugView
    this.debugViewInstructions();
  }

  /**
   * Verificar configuración - usa: analyticsDebug.checkConfig()
   */
  checkConfiguration(): void {
    console.log('🔍 === CONFIGURATION CHECK ===');
    console.log('✓ Environment details:', {
      production: environment.production,
      measurementId: environment.firebase?.measurementId,
      projectId: environment.firebase?.projectId,
      currentUrl: window.location.href,
      userAgent: navigator.userAgent.substring(0, 50) + '...'
    });

    // Verificar gtag
    if (typeof (window as any).gtag !== 'undefined') {
      console.log('✅ gtag is available - Analytics should be working');
      
      // Test gtag directamente
      try {
        (window as any).gtag('event', 'debug_test_gtag', {
          test_source: 'direct_gtag_call',
          timestamp: Date.now()
        });
        console.log('✅ Direct gtag call successful');
      } catch (error) {
        console.log('❌ Direct gtag call failed:', error);
      }
    } else {
      console.log('❌ gtag not found - Analytics NOT initialized');
    }
  }

  /**
   * Test básico de eventos
   */
  testBasicEvents(): void {
    console.log('📊 === BASIC EVENTS TEST ===');
    
    // Eventos simples
    this.firebase.logEvent('debug_test_basic');
    this.firebase.logEvent('debug_startup', {
      timestamp: new Date().toISOString(),
      url: window.location.href
    });
    
    console.log('✅ Basic events sent: debug_test_basic, debug_startup');
  }

  /**
   * Test eventos con datos complejos
   */
  testEventsWithData(): void {
    console.log('📈 === EVENTS WITH DATA TEST ===');
    
    // Test page view
    this.firebase.trackPageView('debug_test_page');
    
    // Test feature usage
    this.firebase.trackFeatureUsed('debug_test_feature', {
      test_value: 123,
      test_string: 'debug_mode'
    });
    
    // Test button click
    this.firebase.trackButtonClick('debug_test_button', 'debug_context');
    
    console.log('✅ Complex events sent: page_view, feature_used, button_click');
  }

  /**
   * Información para activar DebugView
   */
  debugViewInstructions(): void {
    console.log('� === DEBUG VIEW ACTIVATION ===');
    console.log('Para ver eventos en TIEMPO REAL:');
    console.log('');
    console.log('1. Ve a Firebase Console > Analytics > DebugView');
    console.log('2. Agrega ?debug_mode=true a tu URL:');
    console.log(`   ${window.location.href}${window.location.href.includes('?') ? '&' : '?'}debug_mode=true`);
    console.log('3. Recarga la página');
    console.log('4. Los eventos aparecerán INMEDIATAMENTE en DebugView');
  }

  /**
   * Activar debug mode automáticamente
   */
  activateDebugMode(): void {
    const url = window.location.href;
    const separator = url.includes('?') ? '&' : '?';
    const newUrl = `${url}${separator}debug_mode=true`;
    
    console.log('🔄 Activating debug mode...');
    window.location.href = newUrl;
  }

  /**
   * Enviar ráfaga de eventos para testing
   */
  sendBurst(): void {
    console.log('🚀 === SENDING EVENT BURST ===');
    
    for (let i = 1; i <= 10; i++) {
      setTimeout(() => {
        this.firebase.logEvent(`debug_burst_${i}`, {
          burst_number: i,
          timestamp: Date.now()
        });
      }, i * 100);
    }
    
    console.log('✅ Burst of 10 events queued');
  }

  /**
   * Información del estado actual
   */
  info(): void {
    console.log('📋 === ANALYTICS DEBUG INFO ===');
    console.log('Available methods:');
    console.log('• analyticsDebug.fullTest() - Complete test');
    console.log('• analyticsDebug.sendBurst() - Send 10 test events');
    console.log('• analyticsDebug.activateDebugMode() - Enable debug mode');
    console.log('');
    console.log('Current status:');
    console.log('- Production mode:', environment.production);
    console.log('- Measurement ID:', environment.firebase?.measurementId);
    console.log('- gtag available:', typeof (window as any).gtag !== 'undefined');
  }

  /**
   * Función heredada para compatibilidad
   */
  test(): void {
    this.fullTest();
  }

  /**
   * Función heredada para compatibilidad
   */
  forceEvents(): void {
    this.sendBurst();
  }
}