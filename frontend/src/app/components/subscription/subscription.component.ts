import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

interface SubscriptionPlan {
  _id: string;
  name: string;
  type: 'free' | 'basic' | 'premium' | 'enterprise';
  price: number;
  currency: string;
  features: string[];
  monthly_ai_limit: number;
  description: string;
  is_active: boolean;
}

interface UserSubscription {
  _id: string;
  user_id: string;
  plan_id: string;
  plan_name: string;
  status: 'active' | 'inactive' | 'pending';
  start_date: string;
  end_date: string | null;
  created_at: string;
  monthly_ai_limit: number;
  current_ai_usage: number;
}

interface SubscriptionHistory {
  _id: string;
  plan_name: string;
  status: string;
  start_date: string;
  end_date: string | null;
  created_at: string;
}

interface PlanChangeRequest {
  new_plan_id: string;
  reason?: string;
}

@Component({
  selector: 'app-subscription',
  templateUrl: './subscription.component.html',
  styleUrls: ['./subscription.component.scss']
})
export class SubscriptionComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
  
  // Estado de carga
  loading = false;
  
  // Datos de suscripción
  currentSubscription: UserSubscription | null = null;
  subscriptionHistory: SubscriptionHistory[] = [];
  availablePlans: SubscriptionPlan[] = [];
  
  // UI Estado
  activeTab = 'current'; // 'current', 'history', 'plans'
  showPlanChangeModal = false;
  showCancelConfirmModal = false;
  selectedPlanId = '';
  changeReason = '';
  cancelling = false;
  confirmChangeAcknowledged = false;
  
  // Estado de envío
  submittingPlanChange = false;

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadSubscriptionData();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadSubscriptionData(): void {
    this.loading = true;
    
    // Cargar suscripción actual
    this.apiService.getUserSubscription()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          if (response.success && response.data) {
            // Los datos ya vienen en el formato correcto
            this.currentSubscription = response.data;
          } else {
            this.currentSubscription = null;
          }
          this.loading = false;
        },
        error: (error: any) => {
          console.error('Error loading subscription:', error);
          this.notificationService.error('Error al cargar la suscripción');
          this.loading = false;
        }
      });

    // Cargar historial
    this.apiService.getUserSubscriptionHistory()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.subscriptionHistory = response.success ? response.data : [];
        },
        error: (error: any) => {
          console.error('Error loading subscription history:', error);
        }
      });

    // Cargar planes disponibles
    this.apiService.getSubscriptionPlans()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          if (response.success && response.data) {
            this.availablePlans = response.data
              .filter((plan: any) => plan.status === 'active')
              .map((plan: any) => ({
                _id: plan.code, // Usamos el código como ID
                name: plan.name,
                type: this.mapPlanType(plan.name), // Mapear tipo basado en el nombre
                price: plan.price,
                currency: plan.currency,
                features: this.extractFeatures(plan.description, plan.features),
                monthly_ai_limit: plan.features?.ai_invoices_limit || 0,
                description: plan.description.split('\n')[0], // Primera línea como descripción
                is_active: plan.status === 'active'
              }));
          }
        },
        error: (error: any) => {
          console.error('Error loading plans:', error);
        }
      });
  }

  setActiveTab(tab: string): void {
    this.activeTab = tab;
  }

  get usagePercentage(): number {
    if (!this.currentSubscription || this.currentSubscription.monthly_ai_limit === 0) {
      return 0;
    }
    return Math.min((this.currentSubscription.current_ai_usage / this.currentSubscription.monthly_ai_limit) * 100, 100);
  }

  get remainingUsage(): number {
    if (!this.currentSubscription) return 0;
    return Math.max(this.currentSubscription.monthly_ai_limit - this.currentSubscription.current_ai_usage, 0);
  }

  isCurrentPlan(planId: string): boolean {
    return this.currentSubscription?.plan_id === planId;
  }

  openPlanChangeModal(planId: string): void {
    if (this.isCurrentPlan(planId)) {
      this.notificationService.info('Ya tienes este plan activo');
      return;
    }
    
    this.selectedPlanId = planId;
    this.changeReason = '';
    this.confirmChangeAcknowledged = false;
    this.showPlanChangeModal = true;
  }

  closePlanChangeModal(): void {
    this.showPlanChangeModal = false;
    this.selectedPlanId = '';
    this.changeReason = '';
    this.confirmChangeAcknowledged = false;
  }

  submitPlanChange(): void {
    if (!this.selectedPlanId) {
      this.notificationService.error('Selecciona un plan válido');
      return;
    }
    if (!this.confirmChangeAcknowledged) {
      this.notificationService.warning('Debes confirmar que entiendes las implicaciones del cambio de plan');
      return;
    }

    this.submittingPlanChange = true;
    
    this.apiService.requestPlanChange(this.selectedPlanId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.notificationService.success('Solicitud de cambio de plan enviada correctamente');
          this.closePlanChangeModal();
          this.submittingPlanChange = false;
          // Recargar datos
          this.loadSubscriptionData();
        },
        error: (error: any) => {
          console.error('Error requesting plan change:', error);
          this.notificationService.error('Error al enviar la solicitud de cambio de plan');
          this.submittingPlanChange = false;
        }
      });
  }

  get selectedPlan(): SubscriptionPlan | undefined {
    return this.availablePlans.find(p => p._id === this.selectedPlanId);
  }

  getStatusBadgeClass(status: string): string {
    switch (status) {
      case 'active':
        return 'badge-success';
      case 'inactive':
        return 'badge-secondary';
      case 'pending':
        return 'badge-warning';
      case 'cancelled':
        return 'badge-danger';
      default:
        return 'badge-secondary';
    }
  }

  getStatusText(status: string): string {
    switch (status) {
      case 'active':
        return 'Activo';
      case 'inactive':
        return 'Inactivo';
      case 'pending':
        return 'Pendiente';
      case 'cancelled':
        return 'Cancelado';
      default:
        return status;
    }
  }

  getPlanTypeClass(type: string): string {
    switch (type) {
      case 'free':
        return 'plan-free';
      case 'basic':
        return 'plan-basic';
      case 'premium':
        return 'plan-premium';
      case 'enterprise':
        return 'plan-enterprise';
      default:
        return 'plan-default';
    }
  }

  getPlanTypeName(type: string): string {
    switch (type) {
      case 'free':
        return 'Gratuito';
      case 'basic':
        return 'Básico';
      case 'premium':
        return 'Premium';
      case 'enterprise':
        return 'Empresarial';
      default:
        return type;
    }
  }

  formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  }

  formatPrice(price: number, currency: string): string {
    if (price === 0) return 'Gratis';
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: currency || 'USD'
    }).format(price);
  }

  goBack(): void {
    this.router.navigate(['/']);
  }

  private mapPlanType(planName: string): 'free' | 'basic' | 'premium' | 'enterprise' {
    const name = planName.toLowerCase();
    if (name.includes('básico') || name.includes('basico')) return 'basic';
    if (name.includes('pro') || name.includes('premium')) return 'premium';
    if (name.includes('empresa') || name.includes('enterprise')) return 'enterprise';
    return 'free';
  }

  private extractFeatures(description: string, backendFeatures: any): string[] {
    const features: string[] = [];
    
    // Extraer características de la descripción
    const lines = description.split('\n').filter(line => line.trim());
    lines.forEach(line => {
      if (line.trim()) {
        features.push(line.trim());
      }
    });

    // Agregar características del backend
    if (backendFeatures) {
      if (backendFeatures.ai_invoices_limit) {
        features.push(`Procesamiento IA: ${backendFeatures.ai_invoices_limit} facturas/mes`);
      }
      if (backendFeatures.email_processing) {
        features.push('Procesamiento de correos automático');
      }
      if (backendFeatures.export_formats && Array.isArray(backendFeatures.export_formats)) {
        features.push(`Exportación: ${backendFeatures.export_formats.join(', ').toUpperCase()}`);
      }
      if (backendFeatures.api_access) {
        features.push('Acceso completo a API');
      }
      if (backendFeatures.priority_support) {
        features.push('Soporte prioritario');
      }
      if (backendFeatures.custom_templates) {
        features.push('Plantillas personalizadas');
      }
    }

    return features;
  }

  openCancelConfirmModal(): void {
    if (!this.currentSubscription) return;
    this.showCancelConfirmModal = true;
  }

  closeCancelConfirmModal(): void {
    this.showCancelConfirmModal = false;
  }

  confirmCancel(): void {
    if (this.cancelling) return;
    this.cancelling = true;
    this.apiService.cancelUserSubscription()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.notificationService.success(response?.message || 'Suscripción cancelada correctamente');
          this.cancelling = false;
          this.showCancelConfirmModal = false;
          this.loadSubscriptionData();
          this.setActiveTab('plans');
        },
        error: (error: any) => {
          console.error('Error cancelling subscription:', error);
          this.notificationService.error('No se pudo cancelar la suscripción');
          this.cancelling = false;
        }
      });
  }
}
