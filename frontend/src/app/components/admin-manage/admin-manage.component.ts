import {
  Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef
} from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import { AdminUser } from '../../models/admin.model';

@Component({
  selector: 'app-admin-manage',
  templateUrl: './admin-manage.component.html',
  styleUrls: ['./admin-manage.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminManageComponent implements OnInit, OnDestroy {
  admins: AdminUser[] = [];
  loading = false;
  error = false;
  newAdminEmail = '';
  addingAdmin = false;
  addError = '';
  confirmRevokeEmail: string | null = null;
  revoking = false;

  private destroy$ = new Subject<void>();

  constructor(
    private apiService: ApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadAdmins();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadAdmins(): void {
    this.loading = true;
    this.error = false;
    this.apiService.getAdminList()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.admins = res.admins || [];
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.error = true;
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  addAdmin(): void {
    const email = this.newAdminEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      this.addError = 'Ingresá un email válido';
      return;
    }
    this.addingAdmin = true;
    this.addError = '';
    this.apiService.grantAdmin(email)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.newAdminEmail = '';
          this.addingAdmin = false;
          this.loadAdmins();
        },
        error: (err: any) => {
          this.addError = err?.error?.detail || 'Error al agregar admin';
          this.addingAdmin = false;
          this.cdr.markForCheck();
        }
      });
  }

  confirmRevoke(email: string): void {
    this.confirmRevokeEmail = email;
    this.cdr.markForCheck();
  }

  cancelRevoke(): void {
    this.confirmRevokeEmail = null;
    this.cdr.markForCheck();
  }

  revokeAdmin(email: string): void {
    this.revoking = true;
    this.apiService.revokeAdmin(email)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.confirmRevokeEmail = null;
          this.revoking = false;
          this.loadAdmins();
        },
        error: (err: any) => {
          this.addError = err?.error?.detail || 'Error al revocar admin';
          this.confirmRevokeEmail = null;
          this.revoking = false;
          this.cdr.markForCheck();
        }
      });
  }

  trackByEmail(_: number, admin: AdminUser): string {
    return admin.email;
  }
}
