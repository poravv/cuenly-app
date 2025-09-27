import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

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

interface UserStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  trial_users: number;
}

interface InvoiceStats {
  total_invoices: number;
  total_items: number;
  monthly_invoices: Array<{_id: string; count: number; total_amount: number}>;
  daily_invoices: Array<{_id: string; count: number}>;
  user_invoices: Array<{_id: string; count: number; total_amount: number}>;
}

interface SchedulerStatus {
  scheduler: {
    running: boolean;
    jobs_count: number;
  };
  next_reset_date: string;
  should_run_today: boolean;
}

interface ResetStats {
  active_subscriptions: number;
  resetted_this_month: number;
}

@Component({
  selector: 'app-admin-panel',
  templateUrl: './admin-panel.component.html',
  styleUrls: ['./admin-panel.component.scss']
})
export class AdminPanelComponent implements OnInit {
  // Estados
  loading = true;
  loadingUsers = false;
  loadingFilteredStats = false;
  
  // AI Limits
  loadingSchedulerStatus = false;
  loadingResetStats = false;
  loadingMonthlyReset = false;
  loadingUserReset = false;
  schedulerStatus: SchedulerStatus | null = null;
  resetStats: ResetStats | null = null;
  selectedUserForReset = '';
  
  // Tabs
  activeTab = 'stats'; // 'stats', 'users', 'plans', 'ai-limits'
  
  // Users
  users: User[] = [];
  totalUsers = 0;
  currentPage = 1;
  pageSize = 20;
  totalPages = 0;
  
  // Filtros de estadísticas
  statsFilters = {
    start_date: '',
    end_date: '',
    user_email: ''
  };
  
  // Estadísticas filtradas
  filteredStats: any = null;
  selectedUser: User | null = null;
  
  // Stats
  userStats: UserStats = { total_users: 0, active_users: 0, admin_users: 0, trial_users: 0 };
  invoiceStats: InvoiceStats = { 
    total_invoices: 0, 
    total_items: 0, 
    monthly_invoices: [], 
    daily_invoices: [], 
    user_invoices: [] 
  };
  
  // Modals
  showUserModal = false;

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.loading = true;
    this.loadStats();
    this.loadUsers();
  }

  loadStats(): void {
    this.apiService.getAdminStats().subscribe({
      next: (response) => {
        if (response.success) {
          this.userStats = response.user_stats;
          this.invoiceStats = response.invoice_stats;
        }
      },
      error: (error) => {
        console.error('Error loading stats:', error);
        this.showError('Error cargando estadísticas');
      }
    });
  }

  loadUsers(): void {
    this.loadingUsers = true;
    this.apiService.getAdminUsers(this.currentPage, this.pageSize).subscribe({
      next: (response) => {
        if (response.success) {
          this.users = response.users;
          this.totalUsers = response.total;
          this.totalPages = response.total_pages;
        }
        this.loadingUsers = false;
        this.loading = false;
      },
      error: (error) => {
        console.error('Error loading users:', error);
        this.showError('Error cargando usuarios');
        this.loadingUsers = false;
        this.loading = false;
      }
    });
  }

  // Gestión de usuarios
  updateUserRole(user: User, newRole: string): void {
    const roleText = newRole === 'admin' ? 'administrador' : 'usuario';
    
    this.notificationService.warning(
      `¿Estás seguro de cambiar el rol de ${user.email} a ${roleText}?`,
      'Confirmar cambio de rol',
      {
        persistent: true,
        action: {
          label: 'Confirmar',
          handler: () => {
            this.apiService.updateUserRole(user.email, newRole).subscribe({
              next: (response) => {
                if (response.success) {
                  user.role = newRole;
                  this.notificationService.success(
                    `Rol actualizado correctamente para ${user.email}`,
                    'Rol actualizado'
                  );
                  this.loadStats(); // Recargar stats
                }
              },
              error: (error) => {
                console.error('Error updating role:', error);
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
    
    this.notificationService.warning(
      `¿Estás seguro de ${action} a ${user.email}?`,
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
                  this.loadStats(); // Recargar stats
                }
              },
              error: (error) => {
                console.error('Error updating status:', error);
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

  // Paginación
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

  // Tabs
  setActiveTab(tab: string): void {
    this.activeTab = tab;
  }

  // Mensajes de notificación
  showSuccess(message: string): void {
    this.notificationService.success(message, 'Operación exitosa');
  }

  showError(message: string): void {
    this.notificationService.error(message, 'Error en operación');
  }

  // Utileries
  formatDate(dateString: string): string {
    if (!dateString) return 'Nunca';
    return new Date(dateString).toLocaleDateString('es-ES', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  formatNumber(num: number): string {
    return new Intl.NumberFormat('es-ES').format(num);
  }

  formatCurrency(amount: number): string {
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: 'PYG',
      minimumFractionDigits: 0
    }).format(amount);
  }

  getRoleClass(role: string): string {
    return role === 'admin' ? 'badge-admin' : 'badge-user';
  }

  getStatusClass(status: string): string {
    return status === 'active' ? 'badge-active' : 'badge-suspended';
  }

  // Métodos para obtener datos para mostrar
  getTopUsers(): Array<{email: string, count: number, total: number}> {
    return this.invoiceStats.user_invoices.slice(0, 5).map(item => ({
      email: item._id,
      count: item.count,
      total: item.total_amount
    }));
  }

  getRecentMonths(): Array<{month: string, count: number, total: number}> {
    return this.invoiceStats.monthly_invoices.slice(-6).map(item => ({
      month: item._id,
      count: item.count,
      total: item.total_amount
    }));
  }

  // =====================================
  // MÉTODOS PARA ESTADÍSTICAS FILTRADAS
  // =====================================

  async loadFilteredStats(): Promise<void> {
    this.loadingFilteredStats = true;
    try {
      const filters: any = {};
      if (this.statsFilters.start_date) filters.start_date = this.statsFilters.start_date;
      if (this.statsFilters.end_date) filters.end_date = this.statsFilters.end_date;
      if (this.statsFilters.user_email) filters.user_email = this.statsFilters.user_email;

      const response = await this.apiService.getFilteredStats(filters).toPromise();
      if (response.success) {
        this.filteredStats = response;
        this.notificationService.info(
          'Estadísticas actualizadas con los filtros aplicados',
          'Filtros aplicados'
        );
      }
    } catch (error) {
      console.error('Error loading filtered stats:', error);
      this.notificationService.error(
        'No se pudieron cargar las estadísticas filtradas',
        'Error cargando estadísticas'
      );
    } finally {
      this.loadingFilteredStats = false;
    }
  }

  getMaxDailyCount(): number {
    if (!this.filteredStats?.stats?.daily_breakdown) return 1;
    return Math.max(...this.filteredStats.stats.daily_breakdown.map((d: any) => d.count));
  }

  getMaxHourlyCount(): number {
    if (!this.filteredStats?.stats?.hourly_breakdown) return 1;
    return Math.max(...this.filteredStats.stats.hourly_breakdown.map((h: any) => h.count));
  }

  getBarHeight(value: number, maxValue: number): number {
    if (maxValue === 0) return 0;
    return Math.max((value / maxValue) * 100, 5); // Mínimo 5% para visibilidad
  }

  formatShortDate(dateStr: string): string {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('es-ES', { 
        month: '2-digit', 
        day: '2-digit' 
      });
    } catch {
      return dateStr;
    }
  }

  // =====================================
  // MÉTODOS PARA LÍMITES DE IA
  // =====================================

  async loadAiLimitsData(): Promise<void> {
    await Promise.all([
      this.loadSchedulerStatus(),
      this.loadResetStats()
    ]);
  }

  async loadSchedulerStatus(): Promise<void> {
    this.loadingSchedulerStatus = true;
    try {
      const response = await this.apiService.getSchedulerStatus().toPromise();
      if (response.success) {
        this.schedulerStatus = response.data;
      }
    } catch (error) {
      console.error('Error loading scheduler status:', error);
      this.notificationService.error(
        'No se pudo cargar el estado del scheduler',
        'Error cargando scheduler'
      );
    } finally {
      this.loadingSchedulerStatus = false;
    }
  }

  async loadResetStats(): Promise<void> {
    this.loadingResetStats = true;
    try {
      const response = await this.apiService.getResetStats().toPromise();
      if (response.success) {
        this.resetStats = response.data;
      }
    } catch (error) {
      console.error('Error loading reset stats:', error);
      this.notificationService.error(
        'No se pudieron cargar las estadísticas de reseteo',
        'Error cargando estadísticas'
      );
    } finally {
      this.loadingResetStats = false;
    }
  }

  async executeMonthlyReset(): Promise<void> {
    this.notificationService.warning(
      '¿Estás seguro de ejecutar el reseteo mensual? Esta acción reseteará los límites de IA de todos los usuarios con planes activos.',
      'Confirmar reseteo mensual',
      {
        persistent: true,
        action: {
          label: 'Ejecutar Reseteo',
          handler: async () => {
            this.loadingMonthlyReset = true;
            try {
              const response = await this.apiService.executeMonthlyReset().toPromise();
              if (response.success) {
                this.notificationService.success(
                  `Reseteo mensual completado: ${response.data.users_reset} usuarios reseteados`,
                  'Reseteo exitoso'
                );
                // Recargar estadísticas
                await this.loadResetStats();
              }
            } catch (error) {
              console.error('Error executing monthly reset:', error);
              this.notificationService.error(
                'No se pudo ejecutar el reseteo mensual',
                'Error en reseteo'
              );
            } finally {
              this.loadingMonthlyReset = false;
            }
          }
        }
      }
    );
  }

  async resetUserLimits(): Promise<void> {
    if (!this.selectedUserForReset) {
      this.notificationService.warning(
        'Por favor selecciona un usuario para resetear',
        'Usuario requerido'
      );
      return;
    }

    const selectedUser = this.users.find(u => u.email === this.selectedUserForReset);
    const userName = selectedUser?.name || this.selectedUserForReset;

    this.notificationService.warning(
      `¿Estás seguro de resetear los límites de IA de ${userName}?`,
      'Confirmar reseteo individual',
      {
        persistent: true,
        action: {
          label: 'Resetear Usuario',
          handler: async () => {
            this.loadingUserReset = true;
            try {
              const response = await this.apiService.resetUserAiLimits(this.selectedUserForReset).toPromise();
              if (response.success) {
                this.notificationService.success(
                  `Límites de IA reseteados correctamente para ${userName}`,
                  'Usuario reseteado'
                );
                // Limpiar selección
                this.selectedUserForReset = '';
                // Recargar usuarios para mostrar cambios
                await this.loadUsers();
              }
            } catch (error) {
              console.error('Error resetting user limits:', error);
              this.notificationService.error(
                'No se pudieron resetear los límites del usuario',
                'Error en reseteo'
              );
            } finally {
              this.loadingUserReset = false;
            }
          }
        }
      }
    );
  }
}