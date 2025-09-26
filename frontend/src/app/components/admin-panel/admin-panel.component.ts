import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';

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
  
  // Tabs
  activeTab = 'stats'; // 'stats', 'users', 'plans'
  
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

  constructor(private apiService: ApiService) {}

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
    if (!confirm(`¿Estás seguro de cambiar el rol de ${user.email} a ${newRole}?`)) {
      return;
    }

    this.apiService.updateUserRole(user.email, newRole).subscribe({
      next: (response) => {
        if (response.success) {
          user.role = newRole;
          this.showSuccess(response.message);
          this.loadStats(); // Recargar stats
        }
      },
      error: (error) => {
        console.error('Error updating role:', error);
        this.showError('Error actualizando rol');
      }
    });
  }

  updateUserStatus(user: User, newStatus: string): void {
    const action = newStatus === 'suspended' ? 'suspender' : 'activar';
    if (!confirm(`¿Estás seguro de ${action} a ${user.email}?`)) {
      return;
    }

    this.apiService.updateUserStatus(user.email, newStatus).subscribe({
      next: (response) => {
        if (response.success) {
          user.status = newStatus;
          this.showSuccess(response.message);
          this.loadStats(); // Recargar stats
        }
      },
      error: (error) => {
        console.error('Error updating status:', error);
        this.showError('Error actualizando estado');
      }
    });
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

  // Mensajes de alerta simples
  showSuccess(message: string): void {
    alert('✅ ' + message);
  }

  showError(message: string): void {
    alert('❌ ' + message);
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
      }
    } catch (error) {
      console.error('Error loading filtered stats:', error);
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
}