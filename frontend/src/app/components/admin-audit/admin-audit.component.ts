import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-admin-audit',
  templateUrl: './admin-audit.component.html',
  styleUrls: ['./admin-audit.component.scss']
})
export class AdminAuditComponent implements OnInit {
  loading = true;
  loadingAudit = false;
  auditLogs: any[] = [];
  auditPage = 1;
  auditPageSize = 30;
  auditTotalPages = 0;
  auditTotal = 0;
  auditActionFilter = '';

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadAuditLogs();
  }

  loadAuditLogs(): void {
    this.loadingAudit = true;
    this.apiService.getAuditLogs(this.auditPage, this.auditPageSize, this.auditActionFilter || undefined).subscribe({
      next: (response) => {
        if (response.success) {
          this.auditLogs = response.logs;
          this.auditTotal = response.total;
          this.auditTotalPages = response.total_pages;
        }
        this.loadingAudit = false;
        this.loading = false;
      },
      error: () => {
        this.notificationService.error('Error cargando log de auditoría', 'Error');
        this.loadingAudit = false;
        this.loading = false;
      }
    });
  }

  onPageChange(page: number): void {
    if (page >= 1 && page <= this.auditTotalPages) {
      this.auditPage = page;
      this.loadAuditLogs();
    }
  }

  onFilterChange(): void {
    this.auditPage = 1;
    this.loadAuditLogs();
  }

  trackByAuditId(_index: number, log: any): string {
    return log.id;
  }

  getActionLabel(action: string): string {
    const labels: Record<string, string> = {
      'user_role_changed': 'Cambio de rol',
      'user_suspended': 'Usuario suspendido',
      'user_activated': 'Usuario activado',
      'monthly_ai_reset': 'Reset mensual IA',
      'user_ai_reset': 'Reset IA individual',
    };
    return labels[action] || action;
  }

  getActionClass(action: string): string {
    if (action.includes('suspended') || action.includes('cancelled')) return 'badge-danger';
    if (action.includes('activated') || action.includes('reset')) return 'badge-active';
    if (action.includes('role')) return 'badge-info';
    return 'badge-muted';
  }

  formatDate(dateString: string): string {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('es-ES', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  }

  formatNumber(num: number): string {
    return new Intl.NumberFormat('es-ES').format(num);
  }
}
