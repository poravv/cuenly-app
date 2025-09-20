import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Router } from '@angular/router';

@Injectable()
export class TrialInterceptor implements HttpInterceptor {
  
  constructor(private router: Router) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        // Verificar si es error de trial expirado (HTTP 402)
        if (error.status === 402) {
          // Mostrar mensaje de error o redirigir a página de upgrade
          this.handleTrialExpired(error);
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
    // Implementar notificación toast aquí
    // Por ahora usamos alert simple
    alert(message + '\n\nContacta al administrador para continuar usando el sistema.');
  }

  private showAILimitNotification(message: string): void {
    // Notificación específica para límite de IA
    alert(message + '\n\n💡 Tip: Puedes seguir procesando facturas XML de forma ilimitada usando el procesador nativo SIFEN.');
  }
}