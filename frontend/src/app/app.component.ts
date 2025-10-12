import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { AuthService } from './services/auth.service';
import { FirebaseService } from './services/firebase.service';
import { AnalyticsService } from './services/analytics.service';

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
    private analytics: AnalyticsService  // Inicializa tracking automático
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
          }
        });
      }
    }));
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }
}
