import { Component, OnInit } from '@angular/core';
import { UserService, UserProfile } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-trial-banner',
  template: `
    <div *ngIf="userProfile && userProfile.is_trial" 
         class="alert border-0 rounded-0 mb-0 d-flex align-items-center justify-content-between"
         [class.alert-danger]="userProfile.trial_expired || userProfile.ai_limit_reached"
         [class.alert-warning]="!userProfile.trial_expired && !userProfile.ai_limit_reached">
      <div class="d-flex align-items-center">
        <i class="bi bi-clock-history me-2" *ngIf="!userProfile.trial_expired"></i>
        <i class="bi bi-exclamation-triangle me-2" *ngIf="userProfile.trial_expired || userProfile.ai_limit_reached"></i>
        
        <!-- Trial expirado -->
        <span *ngIf="userProfile.trial_expired">
          <strong>Período de prueba expirado.</strong> Contacta al administrador para continuar.
        </span>
        
        <!-- IA límite alcanzado pero trial válido -->
        <span *ngIf="!userProfile.trial_expired && userProfile.ai_limit_reached">
          <strong>Límite de IA alcanzado:</strong> {{ userProfile.ai_invoices_processed }}/{{ userProfile.ai_invoices_limit }} facturas con IA. 
          Aún puedes procesar XMLs nativos ilimitadamente.
        </span>
        
        <!-- Trial válido con límites normales -->
        <span *ngIf="!userProfile.trial_expired && !userProfile.ai_limit_reached">
          <strong>Período de prueba:</strong> {{ userProfile.trial_days_remaining }} días | 
          <strong>IA:</strong> {{ userProfile.ai_invoices_processed }}/{{ userProfile.ai_invoices_limit }} facturas | 
          <strong>XML nativo:</strong> ilimitado
        </span>
      </div>
      <small class="text-muted" *ngIf="userProfile.trial_expires_at && !userProfile.trial_expired">
        Expira: {{ formatDate(userProfile.trial_expires_at) }}
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
        // Reaccionar a actualizaciones globales del perfil
        this.userService.userProfile$.subscribe(p => {
          if (p) {
            this.userProfile = p;
            console.log('🔄 TrialBanner: Perfil actualizado', p);
          }
        });
      } else {
        this.userProfile = null;
      }
    });
    
    // Actualización periódica para asegurar consistencia
    setInterval(() => {
      if (this.userProfile?.is_trial) {
        this.userService.refreshUserProfile().subscribe({
          next: (profile) => {
            console.log('🔄 TrialBanner: Refresh periódico', profile);
          },
          error: (error) => {
            console.warn('⚠️ Error en refresh periódico:', error);
          }
        });
      }
    }, 30000); // Cada 30 segundos si es usuario de prueba
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
