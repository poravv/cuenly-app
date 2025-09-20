import { Injectable } from '@angular/core';
import { HttpEvent, HttpHandler, HttpInterceptor, HttpRequest, HttpErrorResponse } from '@angular/common/http';
import { Observable, from, throwError } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private auth: AuthService, private router: Router) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Evitar adjuntar token a llamadas absolutas a terceros si fuera necesario
    const isRelative = !/^https?:\/\//i.test(req.url);

    if (!isRelative) {
      return next.handle(req);
    }

    return from(this.auth.getIdToken()).pipe(
      switchMap(token => {
        const reqToSend = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
        return next.handle(reqToSend).pipe(
          catchError((err: any) => {
            if (err instanceof HttpErrorResponse && err.status === 401) {
              this.router.navigateByUrl('/login');
            }
            return throwError(() => err);
          })
        );
      })
    );
  }
}
