import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Router } from '@angular/router';
import { NotificationService } from '../services/notification.service';

@Injectable()
export class TrialInterceptor implements HttpInterceptor {
  
  constructor(private router: Router, private notificationService: NotificationService) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        // Verificar si es error de trial expirado (HTTP 402)
        if (error.status === 402) {
          // Mostrar mensaje de error o redirigir a página de upgrade
          this.handleTrialExpired(error);
        }
        // Verificar si el usuario está suspendido (HTTP 403)
        if (error.status === 403) {
          const detail = (error?.error && (error.error.detail || error.error.message)) || error.message || 'Acceso denegado';
          // Si parece ser el mensaje de suspensión, mostrar notificación clara
          if ((detail || '').toLowerCase().includes('suspendid')) {
            this.notificationService.error(
              'Tu cuenta está suspendida. Contacta al administrador.',
              'Cuenta suspendida',
              { duration: 12000 }
            );
            try { localStorage.setItem('account_suspended', 'true'); } catch {}
            // Redirigir a la página de cuenta suspendida
            this.router.navigateByUrl('/suspended');
          }
        }
        return throwError(() => error);
      })
    );
  }

  private handleTrialExpired(error: HttpErrorResponse): void {
    const message = error.error?.detail || 'Tu período de prueba ha expirado';
    
    // Diferenciar entre trial expirado y límite de IA alcanzado
    if (message.includes('límite de') && message.includes('facturas con IA')) {
      this.showAILimitNotification(message);
    } else {
      this.showTrialExpiredNotification(message);
    }
  }

  private showTrialExpiredNotification(message: string): void {
    this.notificationService.error(
      message + '\n\nContacta al administrador para continuar usando el sistema.',
      'Período de prueba expirado',
      { duration: 12000 }
    );
  }

  private showAILimitNotification(message: string): void {
    this.notificationService.warning(
      message + '\n\n💡 Tip: Puedes seguir procesando facturas XML de forma ilimitada usando el procesador nativo SIFEN.',
      'Límite de IA alcanzado',
      { duration: 12000 }
    );
  }
}
