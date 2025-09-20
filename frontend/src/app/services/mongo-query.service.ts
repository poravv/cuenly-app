import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface MonthSummary {
  year_month: string;
  count: number;
  total_amount: number;
  unique_providers: number;
  first_date: string;
  last_date: string;
}

export interface MonthStatistics {
  year_month: string;
  total_facturas: number;
  total_monto: number;
  total_iva: number;
  total_proveedores: number;
  total_clientes: number;
  promedio_factura: number;
  primera_factura: string;
  ultima_factura: string;
  porcentaje_cdc: number;
  porcentaje_timbrado: number;
  xml_nativo: number;
  openai_vision: number;
  fecha_consulta: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class MongoQueryService {
  private apiUrl = `${environment.apiUrl}/api/mongo`;
  private loadingSubject = new BehaviorSubject<boolean>(false);
  private errorSubject = new BehaviorSubject<string | null>(null);

  constructor(private http: HttpClient) {}

  // Observable states
  get loading$(): Observable<boolean> {
    return this.loadingSubject.asObservable();
  }

  get error$(): Observable<string | null> {
    return this.errorSubject.asObservable();
  }

  /**
   * Get available months with summary data
   */
  getAvailableMonths(): Observable<MonthSummary[]> {
    this.setLoading(true);
    this.clearError();

    return this.http.get<ApiResponse<MonthSummary[]>>(`${this.apiUrl}/months`)
      .pipe(
        map(response => {
          this.setLoading(false);
          if (response.success) {
            return response.data;
          } else {
            throw new Error(response.error || 'Error al obtener meses disponibles');
          }
        }),
        catchError(error => {
          this.setLoading(false);
          this.setError(this.formatError(error));
          throw error;
        })
      );
  }

  /**
   * Get detailed statistics for a specific month
   */
  getMonthStatistics(yearMonth: string): Observable<MonthStatistics> {
    this.setLoading(true);
    this.clearError();

    const params = new HttpParams().set('year_month', yearMonth);
    
    return this.http.get<ApiResponse<MonthStatistics>>(`${this.apiUrl}/month-stats`, { params })
      .pipe(
        map(response => {
          this.setLoading(false);
          if (response.success) {
            return response.data;
          } else {
            throw new Error(response.error || 'Error al obtener estadísticas del mes');
          }
        }),
        catchError(error => {
          this.setLoading(false);
          this.setError(this.formatError(error));
          throw error;
        })
      );
  }

  // Excel removido: sin endpoints de descarga

  /**
   * Search invoices with filters
   */
  searchInvoices(filters: any): Observable<any[]> {
    this.setLoading(true);
    this.clearError();

    let params = new HttpParams();
    Object.keys(filters).forEach(key => {
      if (filters[key] !== null && filters[key] !== undefined && filters[key] !== '') {
        params = params.set(key, filters[key]);
      }
    });

    return this.http.get<ApiResponse<any[]>>(`${this.apiUrl}/search`, { params })
      .pipe(
        map(response => {
          this.setLoading(false);
          if (response.success) {
            return response.data;
          } else {
            throw new Error(response.error || 'Error en la búsqueda');
          }
        }),
        catchError(error => {
          this.setLoading(false);
          this.setError(this.formatError(error));
          throw error;
        })
      );
  }

  /**
   * Test MongoDB connection
   */
  testConnection(): Observable<boolean> {
    return this.http.get<ApiResponse<any>>(`${this.apiUrl}/test-connection`)
      .pipe(
        map(response => response.success),
        catchError(() => {
          return [false];
        })
      );
  }

  /**
   * Utility methods
   */
  private setLoading(loading: boolean): void {
    this.loadingSubject.next(loading);
  }

  private setError(error: string | null): void {
    this.errorSubject.next(error);
  }

  private clearError(): void {
    this.errorSubject.next(null);
  }

  private formatError(error: any): string {
    if (error.error && error.error.message) {
      return error.error.message;
    }
    if (error.message) {
      return error.message;
    }
    if (typeof error === 'string') {
      return error;
    }
    return 'Error desconocido en la comunicación con el servidor';
  }

  /**
   * Download utility - trigger file download in browser
   */
  downloadFile(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  /**
   * Format currency for display
   */
  formatCurrency(amount: number): string {
    return new Intl.NumberFormat('es-PY', {
      style: 'currency',
      currency: 'PYG',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount || 0);
  }

  /**
   * Format date for display
   */
  formatDate(dateString: string): string {
    if (!dateString) return '-';
    
    try {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('es-PY', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      }).format(date);
    } catch {
      return dateString;
    }
  }

  /**
   * Format month name from YYYY-MM format
   */
  formatMonthName(yearMonth: string): string {
    if (!yearMonth || !yearMonth.includes('-')) return yearMonth;
    
    try {
      const [year, month] = yearMonth.split('-');
      const date = new Date(parseInt(year), parseInt(month) - 1, 1);
      
      return new Intl.DateTimeFormat('es-PY', {
        year: 'numeric',
        month: 'long'
      }).format(date);
    } catch {
      return yearMonth;
    }
  }
}
