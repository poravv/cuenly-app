import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-admin-subscriptions',
  templateUrl: './admin-subscriptions.component.html',
  styleUrls: ['./admin-subscriptions.component.scss']
})
export class AdminSubscriptionsComponent implements OnInit {
  loading = true;
  loadingSubscriptions = false;
  subscriptions: any[] = [];
  totalSubscriptions = 0;
  subscriptionsPage = 1;
  subscriptionsPageSize = 20;
  subscriptionsTotalPages = 0;
  subscriptionsStatusFilter = 'all';
  dateNow = new Date().toISOString();

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadSubscriptions();
  }

  loadSubscriptions(): void {
    this.loadingSubscriptions = true;
    this.apiService.getAdminSubscriptions(
      this.subscriptionsPage, this.subscriptionsPageSize, this.subscriptionsStatusFilter
    ).subscribe({
      next: (response) => {
        if (response.data) {
          this.subscriptions = response.data;
          this.totalSubscriptions = response.total;
          this.subscriptionsTotalPages = response.pages;
        }
        this.loadingSubscriptions = false;
        this.loading = false;
      },
      error: () => {
        this.notificationService.error('Error cargando suscripciones', 'Error');
        this.loadingSubscriptions = false;
        this.loading = false;
      }
    });
  }

  onFilterChange(): void {
    this.subscriptionsPage = 1;
    this.loadSubscriptions();
  }

  onPageChange(page: number): void {
    if (page >= 1 && page <= this.subscriptionsTotalPages) {
      this.subscriptionsPage = page;
      this.loadSubscriptions();
    }
  }

  retryCharge(sub: any): void {
    this.notificationService.warning(
      `¿Reintentar cobro para ${sub.user_email}?`,
      'Confirmar cobro manual',
      {
        persistent: true,
        action: {
          label: 'Cobrar',
          handler: () => {
            this.apiService.retrySubscriptionCharge(sub._id).subscribe({
              next: (res) => {
                if (res.success) {
                  this.notificationService.success('Cobro exitoso', 'Cobro realizado');
                  this.loadSubscriptions();
                } else {
                  this.notificationService.error(res.message || 'Fallo el cobro', 'Error');
                }
              },
              error: (err) => {
                this.notificationService.error('Error al procesar cobro: ' + err.message, 'Error');
              }
            });
          }
        }
      }
    );
  }

  getStatusClass(status: string): string {
    switch (status?.toLowerCase()) {
      case 'active': return 'badge-active';
      case 'past_due': return 'badge-warning';
      case 'cancelled': return 'badge-danger';
      default: return 'badge-muted';
    }
  }

  getStatusLabel(status: string): string {
    switch (status?.toLowerCase()) {
      case 'active': return 'Activa';
      case 'past_due': return 'Vencida';
      case 'cancelled': return 'Cancelada';
      default: return status;
    }
  }

  trackBySub(_index: number, sub: any): string {
    return sub._id || sub.user_email;
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
