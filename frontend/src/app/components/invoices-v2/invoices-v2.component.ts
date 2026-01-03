import { Component, OnInit } from '@angular/core';
import { NotificationService } from '../../services/notification.service';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-invoices-v2',
  templateUrl: './invoices-v2.component.html',
  styleUrls: ['./invoices-v2.component.scss']
})
export class InvoicesV2Component implements OnInit {
  loading = false;
  error: string | null = null;

  // Filtros
  month: string = '';
  search: string = '';
  rucEmisor: string = '';
  rucReceptor: string = '';
  emisorNombre: string = '';

  // Paginación
  page = 1;
  pageSize = 10;
  total = 0;

  headers: any[] = [];
  expanded: { [id: string]: boolean } = {};
  itemsCache: { [id: string]: any[] } = {};
  itemsLoading: { [id: string]: boolean } = {};
  itemsError: { [id: string]: string | null } = {};
  chips: { key: string; label: string; value: string }[] = [];

  // Eliminación
  selectedHeaders: Set<string> = new Set();
  selectAll = false;
  showDeleteConfirm = false;
  deleteLoading = false;
  deleteInfo: any = null;

  constructor(
    private api: ApiService,
    private notificationService: NotificationService
  ) { }

  ngOnInit(): void {
    // Valor por defecto al mes actual en formato YYYY-MM
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    this.month = `${y}-${m}`;
    this.loadHeaders();
  }

  loadHeaders(): void {
    this.loading = true; this.error = null;
    this.selectedHeaders.clear(); // Limpiar selecciones al recargar
    this.updateSelectAll();
    this.updateChips();
    this.api.getV2Headers({
      page: this.page,
      page_size: this.pageSize,
      // Enviar year_month solo si hay mes definido
      year_month: this.month || undefined,
      search: this.search || undefined,
      ruc_emisor: this.rucEmisor || undefined,
      ruc_receptor: this.rucReceptor || undefined,
      emisor_nombre: this.emisorNombre || undefined,
    }).subscribe({
      next: (res) => {
        this.headers = res?.data || [];
        this.total = res?.total || 0;
        this.loading = false;
        this.updateSelectAll(); // Actualizar estado del selectAll después de cargar
      },
      error: (err) => {
        this.error = 'Error cargando cabeceras';
        this.loading = false;
        console.error(err);
      }
    })
  }

  refresh(): void { this.page = 1; this.loadHeaders(); }

  prevPage(): void {
    if (this.page <= 1) return;
    this.page = Math.max(1, this.page - 1);
    this.loadHeaders();
  }

  nextPage(): void {
    const max = this.pageCount();
    if (this.page >= max) return;
    this.page = Math.min(max, this.page + 1);
    this.loadHeaders();
  }

  goToPage(p: number): void {
    const max = this.pageCount();
    if (p < 1 || p > max) return;
    this.page = p;
    this.loadHeaders();
  }

  getPageNumbers(): number[] {
    const totalPages = this.pageCount();
    if (totalPages === 0) return [];
    const windowSize = 10;
    if (totalPages <= windowSize) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    // Ventana móvil centrada en la página actual cuando sea posible
    let start = Math.max(1, this.page - Math.floor(windowSize / 2));
    let end = start + windowSize - 1;
    if (end > totalPages) {
      end = totalPages;
      start = end - windowSize + 1;
    }
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }

  setPageSize(size: number | string): void {
    const n = Number(size);
    if (!n || n < 1) return;
    this.pageSize = n;
    this.page = 1;
    this.loadHeaders();
  }

  toggle(header: any): void {
    const id = header?.id;
    if (!id) { return; }
    if (this.itemsLoading[id]) { return; }
    this.expanded[id] = !this.expanded[id];
    if (this.expanded[id] && !this.itemsCache[id]) {
      this.itemsLoading[id] = true;
      this.itemsError[id] = null;
      this.api.getV2InvoiceById(id).subscribe({
        next: (res) => {
          this.itemsCache[id] = res?.items || [];
          this.itemsLoading[id] = false;
        },
        error: (err) => {
          this.itemsError[id] = 'Error obteniendo detalle v2';
          this.itemsLoading[id] = false;
          console.error('Error obteniendo detalle v2', err);
        }
      })
    }
  }

  pageCount(): number { return Math.ceil((this.total || 0) / this.pageSize); }

  toCurrency(n: number): string {
    try { return new Intl.NumberFormat('es-PY', { style: 'currency', currency: 'PYG', minimumFractionDigits: 0 }).format(n || 0); } catch { return String(n || 0); }
  }

  formatDate(dt: any): string {
    try {
      const d = (typeof dt === 'number') ? new Date(dt * 1000) : new Date(dt);
      return d.toLocaleDateString('es-PY', { year: 'numeric', month: '2-digit', day: '2-digit' });
    } catch { return ''; }
  }

  ivaBadgeClass(iva: any): string {
    const v = Number(iva || 0);
    if (v === 10) return 'badge bg-primary';
    if (v === 5) return 'badge bg-warning text-dark';
    return 'badge bg-secondary';
  }

  condBadgeClass(cond: any): string {
    const c = String(cond || '').toUpperCase();
    return c.includes('CRED') ? 'badge bg-warning text-dark' : 'badge bg-success';
  }

  updateChips(): void {
    const chips: { key: string; label: string; value: string }[] = [];
    if (this.month) chips.push({ key: 'month', label: 'Mes', value: this.month });
    if (this.search) chips.push({ key: 'search', label: 'Texto', value: this.search });
    if (this.emisorNombre) chips.push({ key: 'emisorNombre', label: 'Emisor', value: this.emisorNombre });
    if (this.rucEmisor) chips.push({ key: 'rucEmisor', label: 'RUC Emisor', value: this.rucEmisor });
    if (this.rucReceptor) chips.push({ key: 'rucReceptor', label: 'RUC Receptor', value: this.rucReceptor });
    this.chips = chips;
  }

  removeChip(key: string): void {
    switch (key) {
      case 'month': this.month = ''; break;
      case 'search': this.search = ''; break;
      case 'emisorNombre': this.emisorNombre = ''; break;
      case 'rucEmisor': this.rucEmisor = ''; break;
      case 'rucReceptor': this.rucReceptor = ''; break;
    }
    this.refresh();
  }

  trackByHeaderId(index: number, h: any): any {
    return h?.id || h?._id || index;
  }

  // Métodos de selección
  toggleSelection(headerId: string): void {
    if (this.selectedHeaders.has(headerId)) {
      this.selectedHeaders.delete(headerId);
    } else {
      this.selectedHeaders.add(headerId);
    }
    this.updateSelectAll();
  }

  toggleSelectAll(): void {
    if (this.selectAll) {
      this.selectedHeaders.clear();
    } else {
      this.headers.forEach(h => this.selectedHeaders.add(h.id));
    }
    this.updateSelectAll();
  }

  updateSelectAll(): void {
    this.selectAll = this.headers.length > 0 && this.selectedHeaders.size === this.headers.length;
  }

  // Métodos de eliminación
  deleteSelected(): void {
    if (this.selectedHeaders.size === 0) return;

    const headerIds = Array.from(this.selectedHeaders);
    this.deleteLoading = true;

    if (headerIds.length === 1) {
      // Eliminación individual
      this.api.getV2DeleteInfo(headerIds[0]).subscribe({
        next: (info) => {
          this.deleteInfo = info;
          this.showDeleteConfirm = true;
          this.deleteLoading = false;
        },
        error: (err) => {
          this.error = 'Error obteniendo información de eliminación';
          this.deleteLoading = false;
          console.error(err);
        }
      });
    } else {
      // Eliminación en lote
      this.api.getV2BulkDeleteInfo(headerIds).subscribe({
        next: (info) => {
          this.deleteInfo = info;
          this.showDeleteConfirm = true;
          this.deleteLoading = false;
        },
        error: (err) => {
          this.error = 'Error obteniendo información de eliminación en lote';
          this.deleteLoading = false;
          console.error(err);
        }
      });
    }
  }

  confirmDelete(): void {
    if (!this.deleteInfo || this.selectedHeaders.size === 0) return;

    const headerIds = Array.from(this.selectedHeaders);
    this.deleteLoading = true;

    if (headerIds.length === 1) {
      // Eliminación individual
      this.api.deleteV2Invoice(headerIds[0]).subscribe({
        next: (result) => {
          this.showDeleteConfirm = false;
          this.selectedHeaders.clear();
          this.deleteInfo = null;
          this.deleteLoading = false;
          this.loadHeaders(); // Recargar lista
          this.error = null;
        },
        error: (err) => {
          this.error = 'Error eliminando factura';
          this.deleteLoading = false;
          console.error(err);
        }
      });
    } else {
      // Eliminación en lote
      this.api.deleteV2InvoicesBulk(headerIds).subscribe({
        next: (result) => {
          this.showDeleteConfirm = false;
          this.selectedHeaders.clear();
          this.deleteInfo = null;
          this.deleteLoading = false;
          this.loadHeaders(); // Recargar lista
          this.error = null;
        },
        error: (err) => {
          this.error = 'Error eliminando facturas en lote';
          this.deleteLoading = false;
          console.error(err);
        }
      });
    }
  }

  cancelDelete(): void {
    this.showDeleteConfirm = false;
    this.deleteInfo = null;
    this.deleteLoading = false;
  }

  isSelected(headerId: string): boolean {
    return this.selectedHeaders.has(headerId);
  }

  get hasSelection(): boolean {
    return this.selectedHeaders.size > 0;
  }

  downloadInvoice(headerId: string, event: Event): void {
    if (event) {
      event.stopPropagation();
    }
    if (!headerId) return;

    this.notificationService.info('Generando enlace...', 'Procesando');

    this.api.downloadInvoice(headerId).subscribe({
      next: (res) => {
        if (res.success && res.download_url) {
          window.open(res.download_url, '_blank');
        } else {
          this.notificationService.error(res.message || 'El archivo no está disponible', 'Error de Descarga');
        }
      },
      error: (err) => {
        console.error("Error descarga:", err);
        this.notificationService.error('Error al conectar con el servidor', 'Error de Conexión');
      }
    });
  }
}
