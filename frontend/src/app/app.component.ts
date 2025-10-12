import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { AuthService } from './services/auth.service';
import { FirebaseService } from './services/firebase.service';
// Analytics services - se auto-inicializan al ser inyectados
import { AnalyticsService } from './services/analytics.service';
import { AnalyticsDebugService } from './services/analytics-debug.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'CuenlyApp';
  authReady = false;
  private sub = new Subscription();

  constructor(
    private auth: AuthService,
    private firebase: FirebaseService,
    private analytics: AnalyticsService,  // Inicializa tracking automático
    private analyticsDebug: AnalyticsDebugService  // Debug tools
  ) {}

  ngOnInit(): void {
    this.sub.add(this.auth.ready$.subscribe(r => {
      this.authReady = r;
      
      // Configurar Analytics cuando hay usuario autenticado
      if (r) {
        this.auth.user$.subscribe(user => {
          if (user) {
            this.firebase.setUserId(user.uid);
            this.firebase.setUserProperties({
              user_email: user.email,
              signup_date: user.metadata.creationTime
            });
            this.firebase.trackLogin('google');
            
            // Trackear que la app se inicializó exitosamente
            this.firebase.logEvent('app_initialized', {
              user_type: 'authenticated',
              timestamp: new Date().toISOString()
            });
          }
        });
      } else {
        // Trackear inicialización sin usuario
        this.firebase.logEvent('app_initialized', {
          user_type: 'anonymous',
          timestamp: new Date().toISOString()
        });
      }
    }));

    // Debug info para desarrollo
    console.log('🔧 Analytics Debug: Use analyticsDebug.test() in console to test Firebase Analytics');
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }
}
