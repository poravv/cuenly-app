import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

interface MonthlyStats {
  year_month: string;
  count: number;
  total_amount: number;
  first_date: string;
  last_date: string;
  unique_providers: number;
}

interface MonthStatistics {
  year_month: string;
  fecha_consulta: string;
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
  selector: 'app-invoice-explorer',
  templateUrl: './invoice-explorer.component.html',
  styleUrls: ['./invoice-explorer.component.scss']
})
export class InvoiceExplorerComponent implements OnInit {
  availableMonths: MonthlyStats[] = [];
  selectedMonth: string = '';
  monthStatistics: MonthStatistics | null = null;
  loading = false;
  error: string | null = null;

  // v2 headers + items
  v2Headers: any[] = [];
  v2Total: number = 0;
  v2Page: number = 1;
  v2PageSize: number = 20;
  v2Header: any | null = null;
  v2Items: any[] = [];
  expandedInvoiceId: string | null = null;

  // Descargas de Excel eliminadas

  constructor(private http: HttpClient, private api: ApiService, private notificationService: NotificationService) { }

  ngOnInit(): void {
    this.loadAvailableMonths();
  }

  async loadAvailableMonths(): Promise<void> {
    try {
      this.loading = true;
      this.error = null;

      const response = await this.http.get<{ success: boolean, months: MonthlyStats[] }>
        (`${environment.apiUrl}/invoices/months`).toPromise();

      if (response?.success) {
        this.availableMonths = response.months;
        console.log('📅 Meses disponibles cargados:', this.availableMonths.length);
      } else {
        this.error = 'No se pudieron cargar los meses disponibles';
      }
    } catch (error) {
      console.error('Error cargando meses:', error);
      this.error = 'Error conectando con el servidor';
    } finally {
      this.loading = false;
    }
  }

  async selectMonth(yearMonth: string): Promise<void> {
    if (this.selectedMonth === yearMonth) return;

    this.selectedMonth = yearMonth;
    this.monthStatistics = null;
    this.v2Headers = [];
    this.v2Items = [];
    this.v2Header = null;
    this.expandedInvoiceId = null;

    if (!yearMonth) return;

    try {
      this.loading = true;
      this.error = null;

      const response = await this.http.get<{ success: boolean, statistics: MonthStatistics }>
        (`${environment.apiUrl}/invoices/month/${yearMonth}/stats`).toPromise();

      if (response?.success) {
        this.monthStatistics = response.statistics;
        console.log('📊 Estadísticas del mes cargadas:', this.monthStatistics);
      } else {
        this.error = 'No se pudieron cargar las estadísticas del mes';
      }
    } catch (error) {
      console.error('Error cargando estadísticas:', error);
      this.error = 'Error obteniendo estadísticas del mes';
      // Cargar headers v2 para el mes seleccionado
      this.loadV2Headers(yearMonth);
    } finally {
      this.loading = false;
    }
  }

  loadV2Headers(yearMonth?: string): void {
    const ym = yearMonth || this.selectedMonth;
    this.api.getV2Headers({ page: this.v2Page, page_size: this.v2PageSize, year_month: ym }).subscribe({
      next: (res) => {
        this.v2Headers = res?.data || [];
        this.v2Total = res?.total || 0;
      },
      error: (err) => {
        console.error('Error cargando headers v2:', err);
      }
    });
  }

  viewV2Invoice(headerId: string): void {
    // Si ya está expandido, colapsar
    if (this.expandedInvoiceId === headerId) {
      this.expandedInvoiceId = null;
      this.v2Header = null;
      this.v2Items = [];
      return;
    }

    // Expandir nuevo
    this.expandedInvoiceId = headerId;
    this.v2Header = null;
    this.v2Items = [];

    this.api.getV2InvoiceById(headerId).subscribe({
      next: (res) => {
        if (this.expandedInvoiceId === headerId) { // Verificar que siga siendo el seleccionado
          this.v2Header = res?.header || null;
          this.v2Items = res?.items || [];
        }
      },
      error: (err) => {
        console.error('Error obteniendo invoice v2:', err);
      }
    });
  }

  // Métodos de descarga de Excel removidos

  formatCurrency(amount: number): string {
    return new Intl.NumberFormat('es-PY', {
      style: 'currency',
      currency: 'PYG',
      minimumFractionDigits: 0
    }).format(amount);
  }

  formatDate(dateString: string): string {
    if (!dateString) return '-';

    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('es-PY', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  }

  getQualityColor(percentage: number): string {
    if (percentage >= 80) return 'success';
    if (percentage >= 60) return 'warning';
    return 'danger';
  }

  refreshData(): void {
    this.loadAvailableMonths();
    if (this.selectedMonth) {
      this.selectMonth(this.selectedMonth);
    }
  }

  clearSelection(): void {
    this.selectedMonth = '';
    this.monthStatistics = null;
    this.error = null;
  }

  trackByMonth(index: number, month: MonthlyStats): string {
    return month.year_month;
  }

  formatMonthName(yearMonth: string): string {
    if (!yearMonth) return '';

    try {
      const [year, month] = yearMonth.split('-');
      const date = new Date(parseInt(year), parseInt(month) - 1, 1);

      return date.toLocaleDateString('es-PY', {
        year: 'numeric',
        month: 'long'
      });
    } catch {
      return yearMonth;
    }
  }

  downloadInvoice(headerId: string, event: Event): void {
    event.stopPropagation();
    if (!headerId) return;

    this.notificationService.info('Descargando archivo...', 'Procesando');

    // Descargar con autenticación y abrir en nueva pestaña
    this.api.downloadInvoiceFile(headerId).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => window.URL.revokeObjectURL(url), 60000);
      },
      error: (err) => {
        console.error('Error descarga:', err);
        if (err.status === 404) {
          this.notificationService.error('Archivo no disponible en almacenamiento', 'Error');
        } else {
          this.notificationService.error('Error al descargar archivo', 'Error');
        }
      }
    });
  }
}
