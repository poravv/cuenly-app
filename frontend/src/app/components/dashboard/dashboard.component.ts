import { Component, OnInit, OnDestroy } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { HttpClient } from '@angular/common/http';
import { forkJoin } from 'rxjs';
import { environment } from '../../../environments/environment';

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
  // Dashboard data
  stats: DashboardStats | null = null;
  monthlyData: MonthlyData[] = [];
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
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.loadData();
  }
  
  ngOnDestroy(): void {
    // Cleanup if needed
  }

  loadData(): void {
    this.loading = true;
    
    // Cargar solo métricas reales disponibles
    forkJoin({
      months: this.http.get<any>(`${this.apiUrl}/invoices/months`),
      mongoStats: this.http.get<any>(`${this.apiUrl}/export/mongodb/stats`),
      headers: this.http.get<any>(`${this.apiUrl}/v2/invoices/headers?page=1&page_size=20`)
    }).subscribe({
      next: (responses) => {
        this.processStatsData(responses);
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading dashboard data:', err);
        this.loadFallbackData();
        this.loading = false;
      }
    });
  }
  
  private processStatsData(responses: any): void {
    // Procesar estadísticas generales desde MongoDB
    if (responses.mongoStats?.success) {
      const mongoStats = responses.mongoStats;
      
      this.stats = {
        total_invoices: mongoStats.total_invoices || 0,
        total_amount: mongoStats.total_amount || 0,
        average_amount: mongoStats.total_invoices > 0 ? (mongoStats.total_amount / mongoStats.total_invoices) : 0
      };
    }
    
    // Procesar datos mensuales reales
    if (responses.months?.success && responses.months.months) {
      this.monthlyData = responses.months.months.slice(0, 6).map((month: MonthSummary) => ({
        year_month: month.year_month,
        invoice_count: month.count,
        total_amount: month.total_amount,
        average_amount: month.count > 0 ? (month.total_amount / month.count) : 0
      }));
    }
    
    // Procesar facturas recientes desde headers (solo para mostrar)
    if (responses.headers?.success && responses.headers.data) {
      
      this.recentInvoices = responses.headers.data.slice(0, 5).map((header: any) => ({
        emisor_nombre: header.emisor?.nombre || 'Sin emisor',
        numero_documento: header.numero_documento || 'N/A',
        fecha_emision: header.fecha_emision || header.fecha,
        monto_total: header.totales?.total || 0
      }));
      
      // Crear top emisores basado en frecuencia en la muestra actual
      const emisoresMap = new Map<string, {count: number, total: number}>();
      responses.headers.data.forEach((header: any) => {
        const emisorNombre = header.emisor?.nombre;
        if (emisorNombre && emisorNombre.trim() !== '') {
          const monto = header.totales?.total || 0;
          
          if (emisoresMap.has(emisorNombre)) {
            const existing = emisoresMap.get(emisorNombre)!;
            existing.count += 1;
            existing.total += monto;
          } else {
            emisoresMap.set(emisorNombre, {count: 1, total: monto});
          }
        }
      });
      
      this.topEmisores = Array.from(emisoresMap.entries())
        .map(([nombre, data]) => ({
          nombre,
          invoice_count: data.count,
          total_amount: data.total
        }))
        .sort((a, b) => b.total_amount - a.total_amount)
        .slice(0, 5);
    }
    
    // Cargar estado del sistema
    this.loadSystemStatus();
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
  }
  
  setPeriod(period: string): void {
    this.currentPeriod = period;
    // Por ahora solo refrescar datos sin filtros específicos
    // TODO: Implementar filtros por período cuando el backend los soporte
    this.loadData();
  }
  
  getCurrentPeriodLabel(): string {
    switch (this.currentPeriod) {
      case 'today': return 'Hoy';
      case 'week': return 'Esta Semana';
      case 'month': return 'Este Mes';
      case 'year': return 'Este Año';
      default: return 'Este Mes';
    }
  }
  
  private loadSystemStatus(): void {
    this.apiService.getStatus().subscribe({
      next: (data) => {
        this.systemStatus = {
          email_configured: data.email_configured || false,
          email_configs_count: data.email_configs_count || 0,
          openai_configured: data.openai_configured || false
        };
      },
      error: (err) => {
        console.error('Error loading system status:', err);
        // Estado por defecto en caso de error
        this.systemStatus = {
          email_configured: false,
          email_configs_count: 0,
          openai_configured: false
        };
      }
    });
  }

  formatCurrency(amount: number): string {
    // Formatear para Paraguay - sin decimales, con separadores de miles
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
  
  formatYearMonth(yearMonth: string): string {
    if (yearMonth.length !== 6) return yearMonth;
    
    const year = yearMonth.substring(0, 4);
    const month = yearMonth.substring(4, 6);
    const monthNames = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];
    
    const monthIndex = parseInt(month, 10) - 1;
    return `${monthNames[monthIndex]} ${year}`;
  }
}
