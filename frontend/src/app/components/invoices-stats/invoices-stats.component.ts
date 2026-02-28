import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { environment } from '../../../environments/environment';

interface MonthlyStats {
  year_month: string;
  count: number;
  total_amount: number;
  unique_providers: number;
}

interface MonthStatistics {
  year_month: string;
  total_facturas: number;
  total_monto: number;
  total_iva: number;
  total_iva_5: number;
  total_iva_10: number;
  total_subtotal_5: number;
  total_subtotal_10: number;
  total_exentas: number;
  promedio_factura: number;
  porcentaje_cdc: number;
  porcentaje_timbrado: number;
  xml_nativo: number;
  openai_vision: number;
  total_proveedores: number;
  total_clientes: number;
  primera_factura: string;
  ultima_factura: string;
}

@Component({
  selector: 'app-invoices-stats',
  templateUrl: './invoices-stats.component.html',
  styleUrls: ['./invoices-stats.component.scss']
})
export class InvoicesStatsComponent implements OnInit {
  availableMonths: MonthlyStats[] = [];
  selectedMonth = '';
  selectedMonthStats: MonthStatistics | null = null;

  loadingMonths = false;
  loadingStats = false;
  error: string | null = null;

  constructor(private http: HttpClient) { }

  ngOnInit(): void {
    this.loadMonths();
  }

  loadMonths(): void {
    this.loadingMonths = true;
    this.error = null;

    this.http.get<{ success: boolean; months: MonthlyStats[] }>(`${environment.apiUrl}/invoices/months`).subscribe({
      next: (response) => {
        const months = response?.months || [];
        this.availableMonths = months.sort((a, b) => b.year_month.localeCompare(a.year_month));

        if (this.availableMonths.length > 0) {
          if (!this.selectedMonth || !this.availableMonths.some(month => month.year_month === this.selectedMonth)) {
            this.selectedMonth = this.availableMonths[0].year_month;
          }
          this.loadMonthStats(this.selectedMonth);
        } else {
          this.selectedMonth = '';
          this.selectedMonthStats = null;
        }
      },
      error: () => {
        this.error = 'No se pudieron cargar los meses disponibles.';
      },
      complete: () => {
        this.loadingMonths = false;
      }
    });
  }

  onMonthChange(yearMonth: string): void {
    this.selectedMonth = yearMonth;
    this.loadMonthStats(yearMonth);
  }

  loadMonthStats(yearMonth: string): void {
    if (!yearMonth) {
      this.selectedMonthStats = null;
      return;
    }

    this.loadingStats = true;
    this.error = null;

    this.http.get<{ success: boolean; statistics: MonthStatistics }>(
      `${environment.apiUrl}/invoices/month/${yearMonth}/stats`
    ).subscribe({
      next: (response) => {
        this.selectedMonthStats = response?.statistics || null;
      },
      error: () => {
        this.error = 'No se pudieron cargar las estadísticas del mes seleccionado.';
      },
      complete: () => {
        this.loadingStats = false;
      }
    });
  }

  get totalMesesConDatos(): number {
    return this.availableMonths.length;
  }

  get totalFacturasGlobal(): number {
    return this.availableMonths.reduce((acc, month) => acc + Number(month.count || 0), 0);
  }

  get totalMontoGlobal(): number {
    return this.availableMonths.reduce((acc, month) => acc + Number(month.total_amount || 0), 0);
  }

  get promedioGlobal(): number {
    const totalFacturas = this.totalFacturasGlobal;
    if (!totalFacturas) {
      return 0;
    }
    return this.totalMontoGlobal / totalFacturas;
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('es-PY', {
      style: 'currency',
      currency: 'PYG',
      minimumFractionDigits: 0
    }).format(Number(value || 0));
  }

  formatDate(value: string): string {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString('es-PY', { year: 'numeric', month: '2-digit', day: '2-digit' });
  }

  formatMonthLabel(yearMonth: string): string {
    if (!yearMonth) return '';
    const [year, month] = yearMonth.split('-');
    const parsed = new Date(Number(year), Number(month) - 1, 1);
    if (Number.isNaN(parsed.getTime())) return yearMonth;
    return parsed.toLocaleDateString('es-PY', { month: 'long', year: 'numeric' });
  }

  trackByMonth(index: number, month: MonthlyStats): string {
    return month.year_month;
  }
}

