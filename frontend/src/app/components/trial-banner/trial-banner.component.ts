import { Component, OnInit } from '@angular/core';
import { UserService, UserProfile } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-trial-banner',
  template: `
    <div *ngIf="userProfile && userProfile.trial.is_trial_user" 
         class="alert border-0 rounded-0 mb-0 d-flex align-items-center justify-content-between"
         [class.alert-danger]="userProfile.trial.trial_expired || userProfile.trial.ai_limit_reached"
         [class.alert-warning]="!userProfile.trial.trial_expired && !userProfile.trial.ai_limit_reached">
      <div class="d-flex align-items-center">
        <i class="bi bi-clock-history me-2" *ngIf="!userProfile.trial.trial_expired"></i>
        <i class="bi bi-exclamation-triangle me-2" *ngIf="userProfile.trial.trial_expired || userProfile.trial.ai_limit_reached"></i>
        
        <!-- Trial expirado -->
        <span *ngIf="userProfile.trial.trial_expired">
          <strong>Período de prueba expirado.</strong> Contacta al administrador para continuar.
        </span>
        
        <!-- IA límite alcanzado pero trial válido -->
        <span *ngIf="!userProfile.trial.trial_expired && userProfile.trial.ai_limit_reached">
          <strong>Límite de IA alcanzado:</strong> {{ userProfile.trial.ai_invoices_processed }}/{{ userProfile.trial.ai_invoices_limit }} facturas con IA. 
          Aún puedes procesar XMLs nativos ilimitadamente.
        </span>
        
        <!-- Trial válido con límites normales -->
        <span *ngIf="!userProfile.trial.trial_expired && !userProfile.trial.ai_limit_reached">
          <strong>Período de prueba:</strong> {{ userProfile.trial.days_remaining }} días | 
          <strong>IA:</strong> {{ userProfile.trial.ai_invoices_processed }}/{{ userProfile.trial.ai_invoices_limit }} facturas | 
          <strong>XML nativo:</strong> ilimitado
        </span>
      </div>
      <small class="text-muted" *ngIf="userProfile.trial.trial_expires_at && !userProfile.trial.trial_expired">
        Expira: {{ formatDate(userProfile.trial.trial_expires_at) }}
      </small>
    </div>
  `,
  styles: [`
    .alert {
      font-size: 0.9rem;
    }
  `]
})
export class TrialBannerComponent implements OnInit {
  userProfile: UserProfile | null = null;

  constructor(
    private userService: UserService,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    // Solo cargar si el usuario está autenticado
    this.authService.user$.subscribe(user => {
      if (user) {
        this.loadUserProfile();
      } else {
        this.userProfile = null;
      }
    });
  }

  private loadUserProfile(): void {
    this.userService.getUserProfile().subscribe({
      next: (profile) => {
        this.userProfile = profile;
      },
      error: (error) => {
        console.error('Error cargando perfil de usuario:', error);
      }
    });
  }

  formatDate(dateString: string): string {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  }
}