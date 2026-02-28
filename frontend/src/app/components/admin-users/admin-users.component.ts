import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { ObservabilityService } from '../../services/observability.service';
import { UserService } from '../../services/user.service';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  status: string;
  created_at: string;
  last_login: string;
  is_trial_user?: boolean;
  trial_expires_at?: string;
  ai_invoices_processed?: number;
  ai_invoices_limit?: number;
}

@Component({
  selector: 'app-admin-users',
  templateUrl: './admin-users.component.html',
  styleUrls: ['./admin-users.component.scss']
})
export class AdminUsersComponent implements OnInit {
  loading = true;
  loadingUsers = false;
  users: User[] = [];
  totalUsers = 0;
  currentPage = 1;
  pageSize = 20;
  totalPages = 0;
  userSearchTerm = '';
  private _searchDebounce: any = null;

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService,
    private observability: ObservabilityService,
    private userService: UserService
  ) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loadingUsers = true;
    this.apiService.getAdminUsers(this.currentPage, this.pageSize, this.userSearchTerm).subscribe({
      next: (response) => {
        if (response.success) {
          this.users = response.users;
          this.totalUsers = response.total;
          this.totalPages = response.total_pages;
        }
        this.loadingUsers = false;
        this.loading = false;
      },
      error: () => {
        this.notificationService.error('Error cargando usuarios', 'Error');
        this.loadingUsers = false;
        this.loading = false;
      }
    });
  }

  updateUserRole(user: User, newRole: string): void {
    const roleText = newRole === 'admin' ? 'administrador' : 'usuario';
    const currentUser = this.userService.getCurrentProfile();

    this.notificationService.warning(
      `¿Estás seguro de cambiar el rol de ${user.email} a ${roleText}?`,
      'Confirmar cambio de rol',
      {
        persistent: true,
        action: {
          label: 'Confirmar',
          handler: () => {
            this.observability.warn('Role change attempt', 'AdminUsersComponent', {
              admin_email: currentUser?.email,
              target_user_email: user.email,
              old_role: user.role,
              new_role: newRole,
              action: 'user_role_change_attempt',
              security_event: true,
              audit_trail: true
            });

            this.apiService.updateUserRole(user.email, newRole).subscribe({
              next: (response) => {
                if (response.success) {
                  this.observability.warn('Role changed successfully', 'AdminUsersComponent', {
                    admin_email: currentUser?.email,
                    target_user_email: user.email,
                    old_role: user.role,
                    new_role: newRole,
                    action: 'user_role_changed',
                    security_event: true,
                    audit_trail: true,
                    success: true
                  });
                  user.role = newRole;
                  this.notificationService.success(
                    `Rol actualizado correctamente para ${user.email}`,
                    'Rol actualizado'
                  );
                }
              },
              error: (error) => {
                this.observability.error('Role change failed', error, 'AdminUsersComponent', {
                  admin_email: currentUser?.email,
                  target_user_email: user.email,
                  attempted_role: newRole,
                  action: 'user_role_change_failed',
                  security_event: true,
                  audit_trail: true
                });
                this.notificationService.error(
                  'No se pudo actualizar el rol del usuario',
                  'Error actualizando rol'
                );
              }
            });
          }
        }
      }
    );
  }

  updateUserStatus(user: User, newStatus: string): void {
    const action = newStatus === 'suspended' ? 'suspender' : 'activar';
    const statusText = newStatus === 'suspended' ? 'suspendido' : 'activo';
    const currentUser = this.userService.getCurrentProfile();

    this.observability.warn('User status change attempt', 'AdminUsersComponent', {
      admin_email: currentUser?.email,
      target_user_email: user.email,
      old_status: user.status,
      new_status: newStatus,
      action: 'user_status_change_attempt',
      security_event: true,
      audit_trail: true,
      is_suspension: newStatus === 'suspended'
    });

    const extraNote = newStatus === 'suspended' ? ' Esto cancelará cualquier suscripción activa.' : '';
    this.notificationService.warning(
      `¿Estás seguro de ${action} a ${user.email}?${extraNote}`,
      'Confirmar cambio de estado',
      {
        persistent: true,
        action: {
          label: 'Confirmar',
          handler: () => {
            this.apiService.updateUserStatus(user.email, newStatus).subscribe({
              next: (response) => {
                if (response.success) {
                  user.status = newStatus;
                  this.notificationService.success(
                    `Usuario ${user.email} marcado como ${statusText}`,
                    'Estado actualizado'
                  );
                }
              },
              error: () => {
                this.notificationService.error(
                  'No se pudo actualizar el estado del usuario',
                  'Error actualizando estado'
                );
              }
            });
          }
        }
      }
    );
  }

  goToPage(page: number): void {
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
      this.loadUsers();
    }
  }

  nextPage(): void {
    this.goToPage(this.currentPage + 1);
  }

  prevPage(): void {
    this.goToPage(this.currentPage - 1);
  }

  onUserSearch(): void {
    clearTimeout(this._searchDebounce);
    this._searchDebounce = setTimeout(() => {
      this.currentPage = 1;
      this.loadUsers();
    }, 400);
  }

  isProtectedAdmin(user: User): boolean {
    const currentUser = this.userService.getCurrentProfile();
    return user.email === currentUser?.email;
  }

  trackByEmail(_index: number, user: User): string {
    return user.email;
  }

  getRoleClass(role: string): string {
    return role === 'admin' ? 'badge-admin' : 'badge-user';
  }

  getStatusClass(status: string): string {
    return status === 'active' ? 'badge-active' : 'badge-suspended';
  }

  formatDate(dateString: string): string {
    if (!dateString) return 'Nunca';
    return new Date(dateString).toLocaleDateString('es-ES', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  }

  formatNumber(num: number): string {
    return new Intl.NumberFormat('es-ES').format(num);
  }
}
