import { Injectable } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivate, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { Observable, combineLatest, filter, map, take } from 'rxjs';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class LoginGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): Observable<boolean | UrlTree> {
    // Permitimos acceder a /login siempre, el propio componente hará redirect con aviso si ya hay sesión
    return combineLatest([this.auth.ready$, this.auth.user$]).pipe(
      filter(([ready]) => ready),
      take(1),
      map(() => true)
    );
  }
}
