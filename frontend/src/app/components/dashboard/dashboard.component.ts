import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { HttpClient } from '@angular/common/http';
import { forkJoin } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ObservabilityService } from '../../services/observability.service';
import { UserService } from '../../services/user.service';
import { ChartConfiguration, ChartData, ChartEvent, ChartType } from 'chart.js';
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
  invoice_count: number;
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
  _id?: string;
  emisor?: {
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
export class DashboardComponent implements OnInit, OnDestroy {
  @ViewChild(BaseChartDirective) chart: BaseChartDirective | undefined;

  // Chart Configuration - Monthly Trend
  public lineChartData: ChartConfiguration['data'] = {
    datasets: [],
    labels: []
  };
  public lineChartOptions: ChartConfiguration['options'] = {
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
  currentPeriod = 'month';
  Math = Math;

  private apiUrl = environment.apiUrl;

  constructor(
    private apiService: ApiService,
    private http: HttpClient,
    private observability: ObservabilityService,
    private userService: UserService
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
  }

  ngOnDestroy(): void {
    // Cleanup if needed
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

          this.loading = false;
        },
        error: (err) => {
          console.error('Error loading dashboard data', err);
          this.loading = false;
          this.observability.error('Error loading dashboard data', err, 'DashboardComponent', { context: 'loadDashboardData' });
          this.loadFallbackData();
        }
      });

    } catch (error) {
      console.error('Unexpected error', error);
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
  }

  formatCurrency(amount: number): string {
    // Formatear para Paraguay - sin decimales, con separadores de miles
    if (amount === undefined || amount === null) return '0 ₲';

    if (amount >= 1000000000) {
      // Más de mil millones
      return (amount / 1000000000).toFixed(1) + 'B ₲';
    } else if (amount >= 1000000) {
      // Más de un millón
      return (amount / 1000000).toFixed(1) + 'M ₲';
    } else if (amount >= 1000) {
      // Más de mil
      return (amount / 1000).toFixed(0) + 'K ₲';
    }

    // Formato estándar paraguayo con separadores de miles
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
}
