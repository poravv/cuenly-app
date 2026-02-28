import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { UserService } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-queue-events',
  templateUrl: './queue-events.component.html',
  styleUrls: [],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class QueueEventsComponent implements OnInit, OnDestroy {
  events: any[] = [];
  loading: boolean = false;
  error: string | null = null;
  retryingId: string | null = null;
  lastRefresh: Date | null = null;

  // Estado de la conexión SSE
  sseConnected: boolean = false;
  sseError: boolean = false;

  // Pagination and filtering
  currentPage: number = 1;
  pageSize: number = 20;
  totalItems: number = 0;
  totalPages: number = 0;
  selectedStatus: string = 'all';

  private eventSource: EventSource | null = null;

  statusOptions = [
    { value: 'all', label: 'Todos' },
    { value: 'pending', label: 'Pendiente' },
    { value: 'processing', label: 'Procesando' },
    { value: 'pending_ai_unread', label: 'Pendiente IA' },
    { value: 'failed', label: 'Fallido' },
    { value: 'error', label: 'Error' },
    { value: 'skipped_ai_limit', label: 'Límite IA' },
    { value: 'missing_metadata', label: 'Sin Metadatos' }
  ];

  constructor(
    private userService: UserService,
    private authService: AuthService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    // Carga inicial vía HTTP para respuesta inmediata
    this.loadEvents();
    // Luego conectar SSE para actualizaciones en tiempo real
    this.connectSSE();
  }

  ngOnDestroy(): void {
    this.disconnectSSE();
  }

  /** Conecta el EventSource SSE con el token JWT como query param. */
  private connectSSE(): void {
    this.disconnectSSE();

    this.authService.getIdToken().then(token => {
      if (!token) {
        // Sin token no podemos conectar SSE; el botón manual sirve como fallback
        return;
      }

      const params = new URLSearchParams({
        token: token,
        status: this.selectedStatus,
        page_size: String(this.pageSize)
      });

      const url = `/api/user/queue-events/stream?${params.toString()}`;
      this.eventSource = new EventSource(url);

      this.eventSource.onopen = () => {
        this.sseConnected = true;
        this.sseError = false;
        this.cdr.markForCheck();
      };

      this.eventSource.addEventListener('queue-update', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.success) {
            // Solo actualizar página 1 desde SSE; otras páginas requieren carga manual
            if (this.currentPage === 1) {
              this.events = data.events || [];
              if (data.pagination) {
                this.totalItems = data.pagination.total;
                this.totalPages = data.pagination.pages;
              }
              this.lastRefresh = new Date();
            }
            this.sseConnected = true;
            this.sseError = false;
            this.cdr.markForCheck();
          }
        } catch (e) {
          // Ignorar errores de parseo individuales
        }
      });

      this.eventSource.addEventListener('heartbeat', () => {
        this.sseConnected = true;
        this.sseError = false;
        this.cdr.markForCheck();
      });

      this.eventSource.addEventListener('error', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.error) {
            this.error = `Error SSE: ${data.error}`;
            this.cdr.markForCheck();
          }
        } catch (e) {
          // Ignorar si no es JSON
        }
      });

      this.eventSource.onerror = () => {
        // EventSource auto-reconecta nativamente; solo actualizamos el indicador
        this.sseConnected = false;
        this.sseError = true;
        this.cdr.markForCheck();
      };
    }).catch(() => {
      // No bloquear la UI si no se puede obtener el token
    });
  }

  /** Cierra la conexión SSE activa. */
  private disconnectSSE(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.sseConnected = false;
    }
  }

  loadEvents(): void {
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();

    this.userService.getQueueEvents(this.currentPage, this.pageSize, this.selectedStatus).subscribe({
      next: (response) => {
        if (response && response.success) {
          this.events = response.events || [];
          if (response.pagination) {
            this.totalItems = response.pagination.total;
            this.totalPages = response.pagination.pages;
          }
        } else {
          this.error = 'No se pudieron cargar los eventos de la cola.';
        }
        this.loading = false;
        this.lastRefresh = new Date();
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Ocurrió un error al cargar la cola de procesamiento.';
        this.loading = false;
        this.lastRefresh = new Date();
        this.cdr.markForCheck();
      }
    });
  }

  onPageChange(page: number): void {
    if (page >= 1 && page <= this.totalPages && page !== this.currentPage) {
      this.currentPage = page;
      this.loadEvents();
    }
  }

  onStatusChange(status: string): void {
    this.selectedStatus = status;
    this.currentPage = 1;
    this.loadEvents();
    // Reconectar SSE con el nuevo filtro de estado
    this.connectSSE();
  }

  refresh(): void {
    this.loadEvents();
  }

  /** trackBy para evitar que Angular destruya y reconstruya filas existentes */
  trackByEventId(_: number, event: any): string {
    return event._id || String(_);
  }

  getStatusBadgeClass(status: string, event?: any): string {
    if (status === 'pending' && (event?.manual_upload || event?.account_email === 'manual_upload')) {
      return 'bg-info text-dark';
    }
    switch (status) {
      case 'pending': return 'bg-warning text-dark';
      case 'processing': return 'bg-primary';
      case 'pending_ai_unread': return 'bg-warning text-dark';
      case 'skipped_ai_limit':
      case 'skipped_ai_limit_unread': return 'bg-info text-dark';
      case 'failed':
      case 'error': return 'bg-danger';
      case 'missing_metadata': return 'bg-secondary';
      default: return 'bg-secondary';
    }
  }

  getStatusText(status: string, event?: any): string {
    if (status === 'pending' && (event?.manual_upload || event?.account_email === 'manual_upload')) {
      return 'Pendiente IA (Manual)';
    }
    switch (status) {
      case 'pending': return 'Pendiente';
      case 'processing': return 'Procesando';
      case 'pending_ai_unread': return 'Pendiente IA';
      case 'skipped_ai_limit':
      case 'skipped_ai_limit_unread': return 'En Pausa (Límite IA)';
      case 'failed':
      case 'error': return 'Fallido';
      case 'missing_metadata': return 'Metadatos Faltantes';
      default: return status;
    }
  }

  retryEvent(event: any): void {
    if (!event._id) return;
    this.retryingId = event._id;
    this.userService.retryQueueEvent(event._id).subscribe({
      next: (res) => {
        this.retryingId = null;
        if (res.success) {
          event.status = 'pending';
          event.reason = 'Reintento manual encolado';
        }
        this.cdr.markForCheck();
      },
      error: () => {
        this.retryingId = null;
        this.cdr.markForCheck();
        alert('Hubo un error al intentar reencolar este evento.');
      }
    });
  }

  canRetry(event: any): boolean {
    if (!event) return false;
    if (typeof event.can_retry === 'boolean') return event.can_retry;
    const status = String(event.status || '').toLowerCase();
    const isManual = !!event.manual_upload || event.account_email === 'manual_upload';
    const retryableStatuses = ['skipped_ai_limit', 'skipped_ai_limit_unread', 'pending_ai_unread', 'failed', 'error', 'missing_metadata'];
    return retryableStatuses.includes(status) && !isManual;
  }
}
