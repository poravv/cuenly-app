import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { combineLatest, Subscription } from 'rxjs';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent implements OnInit, OnDestroy {
  loading = false;
  error: string | null = null;
  private returnUrl: string | null = null;
  info: string | null = null;
  private sub = new Subscription();

  constructor(private auth: AuthService, private router: Router, private route: ActivatedRoute) {}

  ngOnInit(): void {
    const ret = this.route.snapshot.queryParamMap.get('returnUrl');
    this.returnUrl = ret && ret !== '/login' ? ret : null;
    // Si ya está autenticado, mostrar aviso y redirigir automáticamente
    this.sub.add(
      combineLatest([this.auth.ready$, this.auth.user$]).subscribe(([ready, user]) => {
        if (ready && user) {
          this.info = 'Ya estabas autenticado, redirigiendo…';
          setTimeout(() => this.router.navigateByUrl(this.returnUrl || '/'), 600);
        }
      })
    );
  }

  async signInGoogle() {
    this.loading = true; this.error = null;
    try {
      await this.auth.signInWithGoogle();
      this.info = 'Autenticación exitosa. ¡Tienes 15 días de uso gratuito!';
      setTimeout(() => {
        this.router.navigateByUrl(this.returnUrl || '/');
      }, 1500);
    } catch (e: any) {
      this.error = e?.message || 'Error al iniciar sesión';
    } finally {
      this.loading = false;
    }
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }
}
