import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

interface QueueStats {
  workers_online: number;
  queues: {
    high:    { queued: number; started: number; failed: number };
    default: { queued: number; started: number; failed: number };
    low:     { queued: number; started: number; failed: number };
  };
}

interface SchedulerStatus {
  scheduler: { running: boolean; jobs_count: number };
  next_reset_date: string;
  should_run_today: boolean;
}

interface ResetStats {
  active_subscriptions: number;
  resetted_this_month: number;
}

@Component({
  selector: 'app-admin-system',
  templateUrl: './admin-system.component.html',
  styleUrls: ['./admin-system.component.scss']
})
export class AdminSystemComponent implements OnInit {
  // Queue
  queueStats: QueueStats | null = null;
  loadingQueueStats = false;

  // AI Limits
  loadingSchedulerStatus = false;
  loadingResetStats = false;
  loadingMonthlyReset = false;
  loadingUserReset = false;
  schedulerStatus: SchedulerStatus | null = null;
  resetStats: ResetStats | null = null;
  selectedUserForReset = '';

  // Users for dropdown
  users: any[] = [];

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadQueueStats();
    this.loadAiLimitsData();
    this.loadUsers();
  }

  // Queue stats
  loadQueueStats(): void {
    this.loadingQueueStats = true;
    this.apiService.getQueueStats().subscribe({
      next: (response) => {
        if (response.success) {
          this.queueStats = response;
        }
        this.loadingQueueStats = false;
      },
      error: () => { this.loadingQueueStats = false; }
    });
  }

  getTotalQueued(): number {
    if (!this.queueStats) return 0;
    return (this.queueStats.queues.high?.queued || 0)
         + (this.queueStats.queues.default?.queued || 0)
         + (this.queueStats.queues.low?.queued || 0);
  }

  getTotalFailed(): number {
    if (!this.queueStats) return 0;
    return (this.queueStats.queues.high?.failed || 0)
         + (this.queueStats.queues.default?.failed || 0)
         + (this.queueStats.queues.low?.failed || 0);
  }

  getTotalStarted(): number {
    if (!this.queueStats) return 0;
    return (this.queueStats.queues.high?.started || 0)
         + (this.queueStats.queues.default?.started || 0)
         + (this.queueStats.queues.low?.started || 0);
  }

  // AI Limits
  async loadAiLimitsData(): Promise<void> {
    await Promise.all([
      this.loadSchedulerStatus(),
      this.loadResetStats()
    ]);
  }

  async loadSchedulerStatus(): Promise<void> {
    this.loadingSchedulerStatus = true;
    try {
      const response = await this.apiService.getSchedulerStatus().toPromise();
      if (response.success) {
        this.schedulerStatus = response.data;
      }
    } catch {
      this.notificationService.error('No se pudo cargar el estado del scheduler', 'Error');
    } finally {
      this.loadingSchedulerStatus = false;
    }
  }

  async loadResetStats(): Promise<void> {
    this.loadingResetStats = true;
    try {
      const response = await this.apiService.getResetStats().toPromise();
      if (response.success) {
        this.resetStats = response.data;
      }
    } catch {
      this.notificationService.error('No se pudieron cargar las estadísticas de reseteo', 'Error');
    } finally {
      this.loadingResetStats = false;
    }
  }

  loadUsers(): void {
    this.apiService.getAdminUsers(1, 100, '').subscribe({
      next: (response) => {
        if (response.success) {
          this.users = response.users;
        }
      }
    });
  }

  async executeMonthlyReset(): Promise<void> {
    this.notificationService.warning(
      '¿Estás seguro de ejecutar el reseteo mensual? Esta acción reseteará los límites de IA de todos los usuarios con planes activos.',
      'Confirmar reseteo mensual',
      {
        persistent: true,
        action: {
          label: 'Ejecutar Reseteo',
          handler: async () => {
            this.loadingMonthlyReset = true;
            try {
              const response = await this.apiService.executeMonthlyReset().toPromise();
              if (response.success) {
                this.notificationService.success(
                  `Reseteo mensual completado: ${response.data.users_reset} usuarios reseteados`,
                  'Reseteo exitoso'
                );
                await this.loadResetStats();
              }
            } catch {
              this.notificationService.error('No se pudo ejecutar el reseteo mensual', 'Error');
            } finally {
              this.loadingMonthlyReset = false;
            }
          }
        }
      }
    );
  }

  async resetUserLimits(): Promise<void> {
    if (!this.selectedUserForReset) {
      this.notificationService.warning('Por favor selecciona un usuario para resetear', 'Usuario requerido');
      return;
    }

    const selectedUser = this.users.find((u: any) => u.email === this.selectedUserForReset);
    const userName = selectedUser?.name || this.selectedUserForReset;

    this.notificationService.warning(
      `¿Estás seguro de resetear los límites de IA de ${userName}?`,
      'Confirmar reseteo individual',
      {
        persistent: true,
        action: {
          label: 'Resetear Usuario',
          handler: async () => {
            this.loadingUserReset = true;
            try {
              const response = await this.apiService.resetUserAiLimits(this.selectedUserForReset).toPromise();
              if (response.success) {
                this.notificationService.success(
                  `Límites de IA reseteados correctamente para ${userName}`,
                  'Usuario reseteado'
                );
                this.selectedUserForReset = '';
              }
            } catch {
              this.notificationService.error('No se pudieron resetear los límites del usuario', 'Error');
            } finally {
              this.loadingUserReset = false;
            }
          }
        }
      }
    );
  }

  trackByEmail(_index: number, user: any): string {
    return user.email;
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
