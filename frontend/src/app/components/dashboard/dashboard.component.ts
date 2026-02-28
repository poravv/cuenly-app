import { Component, OnInit, ViewChild } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { HttpClient } from '@angular/common/http';
import { forkJoin, finalize } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ObservabilityService } from '../../services/observability.service';
import { UserService } from '../../services/user.service';
import { ChartConfiguration, ChartData, ChartEvent, ChartType, ChartOptions } from 'chart.js';
import { BaseChartDirective } from 'ng2-charts';

interface DashboardStats {
  total_invoices: number;
  total_amount: number;
  average_amount: number;
}

interface MonthSummary {
  year_month: string;
  count: number;
  total_amount: number;
  unique_providers: number;
  first_date: string;
  last_date: string;
}

interface MonthlyData {
  year_month: string;
  invoice_count?: number;
  count?: number;
  total_amount: number;
  average_amount: number;
}

interface TopEmisor {
  nome?: string;
  nombre?: string;
  invoice_count: number;
  total_amount: number;
}

interface RecentInvoice {
  emisor_nombre?: string;
  numero_documento?: string;
  fecha_emision?: string;
  monto_total?: number;
  id?: string;
  _id?: string;
  emisor?: string | {
    nombre?: string;
  };
  totales?: {
    total?: number;
  };
  fecha?: string;
}

interface SystemStatus {
  email_configured: boolean;
  email_configs_count: number;
  openai_configured: boolean;
}

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {
  @ViewChild(BaseChartDirective) chart: BaseChartDirective | undefined;

  // Chart Configuration - Monthly Trend
  public lineChartData: ChartConfiguration['data'] = {
    datasets: [],
    labels: []
  };
  public lineChartOptions: ChartConfiguration['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    elements: {
      line: {
        tension: 0.4
      }
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0,0,0,0.05)'
        },
        ticks: {
          callback: (value) => {
            return new Intl.NumberFormat('es-PY', {
              notation: 'compact',
              compactDisplay: 'short',
              style: 'currency',
              currency: 'PYG'
            }).format(Number(value));
          }
        }
      },
      x: {
        grid: {
          display: false
        }
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('es-PY', {
                style: 'currency',
                currency: 'PYG',
                minimumFractionDigits: 0
              }).format(context.parsed.y);
            }
            return label;
          }
        }
      }
    }
  };
  public lineChartType: ChartType = 'line';

  // Chart Configuration - Top Emisores
  public doughnutChartData: ChartData<'doughnut'> = {
    labels: [],
    datasets: []
  };
  public doughnutChartType: ChartType = 'doughnut';
  public doughnutChartOptions: ChartConfiguration['options'] = {
    responsive: true,
    plugins: {
      legend: { position: 'bottom' }
    }
  };

  // Dashboard data
  stats: DashboardStats | null = null;
  monthlyData: MonthlyData[] = [];
  rawMonthlyData: MonthlyData[] = []; // Store full data to filter locally
  chartPeriod: '3m' | '6m' | 'year' | 'all' = '6m';

  topEmisores: TopEmisor[] = [];
  recentInvoices: RecentInvoice[] = [];
  systemStatus: SystemStatus | null = null;

  // UI state
  loading = false;
  processing = false;
  lastDashboardUpdate: Date | null = null;
  hasLoadedData = false;
  currentPeriod = 'month';
  Math = Math;
  canDownload: boolean = true;

  private apiUrl = environment.apiUrl;

  constructor(
    private api: ApiService,
    private http: HttpClient,
    private observability: ObservabilityService,
    private userService: UserService,
    private notificationService: NotificationService,
    private titleService: Title,
  ) { }

  ngOnInit(): void {
    // Log page view
    this.observability.logPageView('Dashboard');

    // Log user access
    const currentUser = this.userService.getCurrentProfile();
    this.observability.logUserAction('dashboard_accessed', 'DashboardComponent', {
      user_email: currentUser?.email,
      user_role: currentUser?.role,
    });

    this.loadDashboardData();
    this.checkSubscriptionPermissions();
  }

  checkSubscriptionPermissions(): void {
    this.api.getMySubscription().subscribe({
      next: (res) => {
        if (res.success && res.subscription) {
          const planCode = res.subscription.plan_code;
          this.canDownload = planCode !== 'basic';
        } else {
          this.canDownload = false;
        }
      },
      error: () => {
        this.canDownload = false;
      }
    });
  }

  async loadDashboardData(): Promise<void> {
    try {
      this.loading = true;

      const stats$ = this.http.get<{ success: boolean, stats: DashboardStats }>(`${this.apiUrl}/dashboard/stats`);
      const monthly$ = this.http.get<{ success: boolean, monthly_data: MonthlyData[] }>(`${this.apiUrl}/dashboard/monthly-stats`);
      const topEmisors$ = this.http.get<{ success: boolean, top_emisores: TopEmisor[] }>(`${this.apiUrl}/dashboard/top-emisores`);
      const recent$ = this.http.get<{ success: boolean, invoices: RecentInvoice[] }>(`${this.apiUrl}/dashboard/recent-invoices`);
      const status$ = this.http.get<{ success: boolean, status: SystemStatus }>(`${this.apiUrl}/dashboard/system-status`);

      forkJoin([stats$, monthly$, topEmisors$, recent$, status$]).subscribe({
        next: ([statsRes, monthlyRes, topRes, recentRes, statusRes]) => {
          if (statsRes.success) this.stats = statsRes.stats;
          if (monthlyRes.success) {
            this.rawMonthlyData = monthlyRes.monthly_data;
            this.processStatsData();
          }
          if (topRes.success) {
            this.topEmisores = topRes.top_emisores;
            this.processEmisorData();
          }
          if (recentRes.success) this.recentInvoices = recentRes.invoices;
          if (statusRes.success) this.systemStatus = statusRes.status;
          this.lastDashboardUpdate = new Date();
          this.hasLoadedData = true;

          this.loading = false;
        },
        error: (err) => {
          this.loading = false;
          this.observability.error('Error loading dashboard data', err, 'DashboardComponent', { context: 'loadDashboardData' });
          this.loadFallbackData();
        }
      });

    } catch (error) {
      this.loading = false;
    }
  }

  processStatsData(): void {
    if (!this.rawMonthlyData) return;
    this.updateChartPeriod(this.chartPeriod);
  }

  updateChartPeriod(period: '3m' | '6m' | 'year' | 'all'): void {
    this.chartPeriod = period;
    if (!this.rawMonthlyData) return;

    // Sort ascending by date
    let sortedData = [...this.rawMonthlyData].sort((a, b) => a.year_month.localeCompare(b.year_month));

    // Filter
    let dataToDisplay: MonthlyData[] = [];
    if (period === '3m') {
      dataToDisplay = sortedData.slice(-3);
    } else if (period === '6m') {
      dataToDisplay = sortedData.slice(-6);
    } else if (period === 'year') {
      dataToDisplay = sortedData.slice(-12);
    } else {
      dataToDisplay = sortedData;
    }

    this.monthlyData = dataToDisplay;

    // Recalcular stats para los top cards basado en el filtro
    if (this.monthlyData.length > 0) {
      const total_invoices = this.monthlyData.reduce((sum, d) => sum + (d.count || d.invoice_count || 0), 0);
      const total_amount = this.monthlyData.reduce((sum, d) => sum + d.total_amount, 0);
      const average_amount = total_invoices > 0 ? total_amount / total_invoices : 0;

      this.stats = {
        total_invoices,
        total_amount,
        average_amount
      };
    } else {
      this.stats = { total_invoices: 0, total_amount: 0, average_amount: 0 };
    }

    this.lineChartData = {
      labels: this.monthlyData.map(d => this.formatYearMonthShort(d.year_month)),
      datasets: [
        {
          data: this.monthlyData.map(d => d.total_amount),
          label: 'Inversión',
          fill: true,
          tension: 0.4,
          borderColor: '#4e73df',
          backgroundColor: 'rgba(78, 115, 223, 0.05)',
          pointBackgroundColor: '#4e73df',
          pointBorderColor: '#fff',
          pointHoverBackgroundColor: '#fff',
          pointHoverBorderColor: '#4e73df'
        }
      ]
    };

    if (this.chart) {
      this.chart.update();
    }
  }

  processEmisorData(): void {
    if (!this.topEmisores) return;
    const top5 = this.topEmisores.slice(0, 5);
    this.doughnutChartData = {
      labels: top5.map(e => (e.nome || e.nombre || 'Desconocido').substring(0, 15)),
      datasets: [
        {
          data: top5.map(e => e.total_amount),
          backgroundColor: [
            '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b'
          ],
          hoverBackgroundColor: [
            '#2e59d9', '#17a673', '#2c9faf', '#dda20a', '#be2617'
          ],
          hoverBorderColor: "rgba(234, 236, 244, 1)",
        }
      ]
    };
  }

  private loadFallbackData(): void {
    // Datos de respaldo en caso de error
    this.stats = {
      total_invoices: 0,
      total_amount: 0,
      average_amount: 0
    };
    this.monthlyData = [];
    this.topEmisores = [];
    this.recentInvoices = [];
    // Estado por defecto
    this.systemStatus = {
      email_configured: false,
      email_configs_count: 0,
      openai_configured: false
    };
    this.lastDashboardUpdate = new Date();
    this.hasLoadedData = true;
  }

  /**
   * Procesar correos de forma inmediata desde el Dashboard
   * Quick Win #1: Reducir navegación de 3 clicks a 1 click
   */
  processNow(): void {
    if (this.processing) {
      return;
    }

    if (!this.systemStatus?.email_configured) {
      this.notificationService.warning(
        'Primero debes configurar una cuenta de correo',
        'Configuración Requerida'
      );
      return;
    }

    this.processing = true;
    this.observability.logUserAction('process_now_clicked', 'DashboardComponent', {
      email_configs: this.systemStatus.email_configs_count
    });

    this.notificationService.info(
      'Procesando correos. Esto puede tardar unos segundos.',
      'Procesamiento Iniciado'
    );

    this.api.processEmails(false).pipe(
      finalize(() => {
        this.processing = false;
      })
    ).subscribe({
      next: (result) => {
        if (!result.success) {
          this.notificationService.warning(
            result.message || 'No se pudieron procesar los correos',
            'Advertencia'
          );
          this.refreshDashboardAfterProcessing(400);
          return;
        }

        const processedInvoices = result.invoice_count ?? result.invoices?.length ?? 0;
        if (processedInvoices > 0) {
          this.notificationService.success(
            `Se procesaron ${processedInvoices} factura(s) exitosamente`,
            'Proceso Completado'
          );
          this.refreshDashboardAfterProcessing(800);
          return;
        }

        this.notificationService.info(
          'El procesamiento finalizó, pero no se encontraron facturas nuevas.',
          'Sin Novedades'
        );
        this.refreshDashboardAfterProcessing(400);
      },
      error: (error) => {
        const errorMessage = error.error?.message || error.message || 'Error al procesar correos';
        this.notificationService.error(errorMessage, 'Error de Procesamiento');

        this.observability.error('Error processing emails from dashboard', error, 'DashboardComponent', {
          context: 'processNow'
        });
      }
    });
  }

  private refreshDashboardAfterProcessing(delayMs: number = 500): void {
    window.setTimeout(() => {
      this.loadDashboardData();
    }, delayMs);
  }

  getLastUpdatedLabel(): string {
    if (!this.lastDashboardUpdate) {
      return 'Sin datos';
    }

    const diffSeconds = Math.floor((Date.now() - this.lastDashboardUpdate.getTime()) / 1000);
    if (diffSeconds < 10) {
      return 'Justo ahora';
    }
    if (diffSeconds < 60) {
      return `Hace ${diffSeconds}s`;
    }

    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) {
      return `Hace ${diffMinutes} min`;
    }

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `Hace ${diffHours} h`;
    }

    return this.formatDate(this.lastDashboardUpdate.toISOString());
  }

  isInitialLoading(): boolean {
    return this.loading && !this.hasLoadedData;
  }

  isRefreshingData(): boolean {
    return this.loading && this.hasLoadedData;
  }

  formatCurrency(amount: number): string {
    // Formatear para Paraguay - sin decimales, con separadores de miles
    if (amount === undefined || amount === null) return '0 ₲';

    // Formato estándar paraguayo con separadores de miles SIEMPRE (sin 'M' ni 'K')
    return new Intl.NumberFormat('es-PY', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount) + ' ₲';
  }

  formatDate(dateString: string): string {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('es-PY', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
      }).format(date);
    } catch (error) {
      return 'N/A';
    }
  }

  formatYearMonthShort(yearMonth: string): string {
    if (!yearMonth || yearMonth.length < 6) return yearMonth;
    // yearMonth format: YYYY-MM or YYYYMM
    let year, month;

    if (yearMonth.includes('-')) {
      const parts = yearMonth.split('-');
      year = parts[0];
      month = parts[1];
    } else {
      year = yearMonth.substring(0, 4);
      month = yearMonth.substring(4, 6);
    }

    const monthNames = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const monthIndex = parseInt(month, 10) - 1;

    if (monthIndex >= 0 && monthIndex < 12) {
      return `${monthNames[monthIndex]} '${year.substring(2, 4)}`;
    }

    return yearMonth;
  }

  downloadInvoice(id: string | undefined, event: Event): void {
    if (event) {
      event.stopPropagation();
    }

    // Si no hay ID, notificar
    if (!id) {
      this.notificationService.warning('No se puede descargar: ID no encontrado', 'Aviso');
      return;
    }

    if (!this.canDownload) {
      this.notificationService.warning('Tu plan actual no permite la descarga de archivos originales.', 'Plan Limitado');
      return;
    }

    this.notificationService.info('Generando enlace...', 'Procesando');

    // Obtener URL presignada de MinIO y abrir en nueva pestaña
    this.api.downloadInvoice(id).subscribe({
      next: (res) => {
        if (res.success && res.download_url) {
          window.open(res.download_url, '_blank');
        } else {
          this.notificationService.error(res.message || 'El archivo no está disponible', 'Error de Descarga');
        }
      },
      error: (err) => {
        this.notificationService.error('Error al conectar con el servidor', 'Error de Conexión');
      }
    });
  }
}
