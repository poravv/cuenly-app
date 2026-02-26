import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot, Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { map, catchError, switchMap, take } from 'rxjs/operators';
import { UserService } from '../services/user.service';
import { NotificationService } from '../services/notification.service';

@Injectable({
    providedIn: 'root'
})
export class ProfileGuard implements CanActivate {

    constructor(
        private userService: UserService,
        private router: Router,
        private notificationService: NotificationService
    ) { }

    canActivate(
        route: ActivatedRouteSnapshot,
        state: RouterStateSnapshot
    ): Observable<boolean> {
        return this.userService.checkProfileCompleteness().pipe(
            map(status => {
                if (status.is_complete) {
                    return true;
                } else {
                    // Si faltan campos
                    const missing = status.missing_fields.map(f => this.mapFieldToFriendlyName(f)).join(', ');
                    this.notificationService.warning(`Por favor completa tu perfil para continuar: ${missing}`);

                    // Redirigir a perfil con query params para volver después
                    this.router.navigate(['/cuenta/perfil'], {
                        queryParams: {
                            returnUrl: state.url,
                            missingFields: status.missing_fields.join(',')
                        }
                    });
                    return false;
                }
            }),
            catchError(error => {
                console.error('Error checking profile completeness in guard:', error);
                // En caso de error, permitir el paso pero loguear, o bloquear?
                // Mejor bloquear por seguridad si es un fallo de red, pero si el endpoint no existe...
                // Asumiremos false para obligar a verificar
                return of(false);
            })
        );
    }

    private mapFieldToFriendlyName(field: string): string {
        const map: { [key: string]: string } = {
            'name': 'Nombre',
            'phone': 'Teléfono',
            'ruc': 'RUC/CI',
            'address': 'Dirección',
            'city': 'Ciudad'
        };
        return map[field] || field;
    }
}
