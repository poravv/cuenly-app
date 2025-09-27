import { Injectable } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivate, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { Observable, combineLatest, filter, map, take } from 'rxjs';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class AuthGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): Observable<boolean | UrlTree> {
    return combineLatest([this.auth.ready$, this.auth.user$]).pipe(
      filter(([ready]) => ready),
      take(1),
      map(([_, user]) => {
        if (!user) {
          return this.router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
        }
        // Si hay bandera local de cuenta suspendida, redirigir a la página correspondiente
        try {
          const suspended = localStorage.getItem('account_suspended') === 'true';
          if (suspended && state.url !== '/suspended') {
            return this.router.createUrlTree(['/suspended']);
          }
        } catch {}
        return true;
      })
    );
  }
}
