import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-suspended',
  templateUrl: './suspended.component.html',
  styleUrls: ['./suspended.component.scss']
})
export class SuspendedComponent {
  constructor(private auth: AuthService, private router: Router) {}

  async logout(): Promise<void> {
    await this.auth.signOut();
    // Limpiar bandera local de suspensión
    try { localStorage.removeItem('account_suspended'); } catch {}
    this.router.navigateByUrl('/login');
  }
}

