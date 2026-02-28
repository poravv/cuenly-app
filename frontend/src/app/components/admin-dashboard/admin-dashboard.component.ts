import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

interface UserStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  trial_users: number;
}

interface InvoiceStats {
  total_invoices: number;
  total_items: number;
  monthly_invoices: Array<{
    _id: string;
    count: number;
    total_amount: number;
    xml_nativo: number;
    openai_vision: number;
  }>;
  daily_invoices: Array<{ _id: string; count: number }>;
  user_invoices: Array<{ _id: string; count: number; total_amount: number }>;
  source_totals: { xml_nativo: number; openai_vision: number; total_amount: number };
}

interface QueueStats {
  workers_online: number;
  queues: {
    high:    { queued: number; started: number; failed: number };
    default: { queued: number; started: number; failed: number };
    low:     { queued: number; started: number; failed: number };
  };
}

@Component({
  selector: 'app-admin-dashboard',
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.scss']
})
export class AdminDashboardComponent implements OnInit {

  // Estados de carga
  loading = true;
  loadingQueueStats = false;
  loadingFilteredStats = false;

  // Toggle de sección avanzada
  showAdvancedStats = false;

  // Datos principales
  userStats: UserStats = {
    total_users: 0,
    active_users: 0,
    admin_users: 0,
    trial_users: 0
  };

  invoiceStats: InvoiceStats = {
    total_invoices: 0,
    total_items: 0,
    monthly_invoices: [],
    daily_invoices: [],
    user_invoices: [],
    source_totals: { xml_nativo: 0, openai_vision: 0, total_amount: 0 }
  };

  queueStats: QueueStats | null = null;

  // Lista de usuarios (para el selector del filtro)
  users: any[] = [];

  // Filtros de estadísticas avanzadas
  statsFilters = {
    start_date: '',
    end_date: '',
    user_email: ''
  };

  // Resultado de estadísticas filtradas
  filteredStats: any = null;

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  // =====================================
  // CARGA DE DATOS PRINCIPAL
  // =====================================

  loadData(): void {
    this.loading = true;
    this.loadStats();
    this.loadUsers();
  }

  loadStats(): void {
    this.apiService.getAdminStats().subscribe({
      next: (response) => {
        if (response.success) {
          this.userStats    = response.user_stats;
          this.invoiceStats = response.invoice_stats;
        }
        this.loading = false;
      },
      error: () => {
        this.notificationService.error('Error cargando estadísticas', 'Error');
        this.loading = false;
      }
    });
    this.loadQueueStats();
  }

  loadQueueStats(): void {
    this.loadingQueueStats = true;
    this.apiService.getQueueStats().subscribe({
      next: (response) => {
        if (response.success) {
          this.queueStats = response;
        }
        this.loadingQueueStats = false;
      },
      error: () => {
        this.loadingQueueStats = false;
      }
    });
  }

  /**
   * Carga la lista de usuarios sólo para poblar el selector de filtros.
   * No requiere paginación completa: se trae la primera página grande.
   */
  loadUsers(): void {
    this.apiService.getAdminUsers(1, 200, '').subscribe({
      next: (response) => {
        if (response.success) {
          this.users = response.users;
        }
      },
      error: () => {
        // Error no crítico: el selector simplemente queda vacío
      }
    });
  }

  // =====================================
  // ESTADÍSTICAS FILTRADAS (AVANZADAS)
  // =====================================

  async loadFilteredStats(): Promise<void> {
    this.loadingFilteredStats = true;
    try {
      const filters: any = {};
      if (this.statsFilters.start_date) filters.start_date = this.statsFilters.start_date;
      if (this.statsFilters.end_date)   filters.end_date   = this.statsFilters.end_date;
      if (this.statsFilters.user_email) filters.user_email = this.statsFilters.user_email;

      const response = await this.apiService.getFilteredStats(filters).toPromise();
      if (response.success) {
        this.filteredStats = response;
        this.notificationService.info(
          'Estadísticas actualizadas con los filtros aplicados',
          'Filtros aplicados'
        );
      }
    } catch {
      this.notificationService.error(
        'No se pudieron cargar las estadísticas filtradas',
        'Error cargando estadísticas'
      );
    } finally {
      this.loadingFilteredStats = false;
    }
  }

  // =====================================
  // CALCULOS DERIVADOS — COLAS RQ
  // =====================================

  getTotalQueued(): number {
    if (!this.queueStats) return 0;
    return (this.queueStats.queues.high?.queued    || 0)
         + (this.queueStats.queues.default?.queued || 0)
         + (this.queueStats.queues.low?.queued     || 0);
  }

  getTotalFailed(): number {
    if (!this.queueStats) return 0;
    return (this.queueStats.queues.high?.failed    || 0)
         + (this.queueStats.queues.default?.failed || 0)
         + (this.queueStats.queues.low?.failed     || 0);
  }

  // =====================================
  // CALCULOS DERIVADOS — GRÁFICOS
  // =====================================

  getTopUsers(): Array<{ email: string; count: number; total: number }> {
    return this.invoiceStats.user_invoices.slice(0, 5).map(item => ({
      email: item._id,
      count: item.count,
      total: item.total_amount
    }));
  }

  getRecentMonths(): Array<{
    month: string;
    count: number;
    total: number;
    xml_nativo: number;
    openai_vision: number;
  }> {
    return this.invoiceStats.monthly_invoices.slice(-6).map(item => ({
      month:         item._id,
      count:         item.count,
      total:         item.total_amount,
      xml_nativo:    item.xml_nativo    || 0,
      openai_vision: item.openai_vision || 0
    }));
  }

  getMaxMonthCount(): number {
    const months = this.getRecentMonths();
    if (!months.length) return 1;
    return Math.max(...months.map(m => m.count), 1);
  }

  getSourcePercent(value: number): number {
    const total = (this.invoiceStats.source_totals?.xml_nativo    || 0)
                + (this.invoiceStats.source_totals?.openai_vision || 0);
    if (!total) return 0;
    return Math.round((value / total) * 100);
  }

  // =====================================
  // CALCULOS DERIVADOS — GRÁFICOS FILTRADOS
  // =====================================

  getMaxDailyCount(): number {
    if (!this.filteredStats?.stats?.daily_breakdown) return 1;
    return Math.max(
      ...this.filteredStats.stats.daily_breakdown.map((d: any) => d.count),
      1
    );
  }

  getMaxHourlyCount(): number {
    if (!this.filteredStats?.stats?.hourly_breakdown) return 1;
    return Math.max(
      ...this.filteredStats.stats.hourly_breakdown.map((h: any) => h.count),
      1
    );
  }

  /**
   * Calcula la altura porcentual de una barra con un mínimo del 5 % para visibilidad.
   */
  getBarHeight(value: number, maxValue: number): number {
    if (maxValue === 0) return 0;
    return Math.max((value / maxValue) * 100, 5);
  }

  // =====================================
  // FORMATEO
  // =====================================

  formatDate(dateString: string): string {
    if (!dateString) return 'Nunca';
    return new Date(dateString).toLocaleDateString('es-ES', {
      year:   'numeric',
      month:  '2-digit',
      day:    '2-digit',
      hour:   '2-digit',
      minute: '2-digit'
    });
  }

  formatNumber(num: number): string {
    return new Intl.NumberFormat('es-ES').format(num);
  }

  formatCurrency(amount: number): string {
    return new Intl.NumberFormat('es-ES', {
      style:                 'currency',
      currency:              'PYG',
      minimumFractionDigits: 0
    }).format(amount);
  }

  formatShortDate(dateStr: string): string {
    try {
      return new Date(dateStr).toLocaleDateString('es-ES', {
        month: '2-digit',
        day:   '2-digit'
      });
    } catch {
      return dateStr;
    }
  }

  // =====================================
  // TRACK BY — RENDIMIENTO *ngFor
  // =====================================

  trackByEmail(_index: number, user: any): string {
    return user.email;
  }
}
