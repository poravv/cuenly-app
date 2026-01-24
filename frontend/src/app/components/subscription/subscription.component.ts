import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import { UserService } from '../../services/user.service';
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

  // NUEVO: Estado para iframe de Bancard
  showBancardIframeModal = false;
  bancardFormId = '';
  loadingIframe = false;
  confirmingCard = false;

  // Estado de tarjetas (ya no se usa el check previo)
  hasCards = false;
  showNoCardModal = false;

  // Estado de perfil incompleto
  showIncompleteProfileModal = false;
  missingProfileFields: string[] = [];

  // Datos del comprador para Pagopar (YA NO SE USA - solo para backward compatibility)
  buyerData = {
    tipo_documento: 'CI',
    documento: '',
    ruc: '',
    telefono: '',
    direccion: '',
    razon_social: ''
  };

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService,
    private router: Router,
    private userService: UserService
  ) { }

  ngOnInit(): void {
    this.loadSubscriptionData();
    // Ya no necesitamos checkCards() - el flujo es diferente
  }

  checkCards(): void {
    this.apiService.getCards().subscribe({
      next: (cards) => {
        this.hasCards = cards && cards.length > 0;
      },
      error: () => this.hasCards = false
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadSubscriptionData(): void {
    this.loading = true;

    // Cargar suscripción actual usando NUEVO endpoint
    this.apiService.getMySubscription()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          if (response.success && response.subscription) {
            this.currentSubscription = response.subscription;
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

    // Cargar planes disponibles usando NUEVO endpoint
    this.apiService.getSubscriptionPlans()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (plans: any[]) => {
          this.availablePlans = plans
            .filter((plan: any) => plan.active)
            .map((plan: any) => ({
              _id: plan.code,
              name: plan.name,
              type: this.mapPlanType(plan.name),
              price: plan.amount,
              currency: plan.currency,
              features: this.extractFeatures(plan.description, plan.features),
              monthly_ai_limit: plan.features?.ai_invoices_limit || 0,
              description: plan.description.split('\n')[0],
              is_active: plan.active
            }));
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

    // NUEVO FLUJO: Iniciar catastro de tarjeta directamente
    this.selectedPlanId = planId;
    this.startCardRegistration(planId);
  }

  /**
   * PASO 3: Iniciar catastro de tarjeta
   * Llama a /subscriptions/subscribe para obtener form_id
   */
  startCardRegistration(planCode: string): void {
    this.loadingIframe = true;
    console.log('🎬 Iniciando catastro de tarjeta para plan:', planCode);

    // PASO 1: Verificar perfil completo
    this.userService.checkProfileCompleteness()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (status) => {
          if (!status.is_complete) {
            console.warn('⚠️ Perfil incompleto:', status.missing_fields);
            this.missingProfileFields = status.missing_fields;
            this.showIncompleteProfileModal = true;
            this.loadingIframe = false;
            return;
          }

          // PASO 2: Si está completo, iniciar suscripción
          this.proceedToSubscribe(planCode);
        },
        error: (err) => {
          console.error('❌ Error verificando perfil:', err);
          this.notificationService.error('Error verificando estado del perfil');
          this.loadingIframe = false;
        }
      });
  }

  private proceedToSubscribe(planCode: string): void {
    this.apiService.subscribeToSelectedPlan(planCode)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          console.log('✅ Form ID recibido:', response.form_id);
          this.bancardFormId = response.form_id;
          this.showBancardIframeModal = true; // Mostrar modal con iframe
          this.loadingIframe = false;
        },
        error: (err) => {
          console.error('❌ Error iniciando suscripción:', err);
          this.notificationService.error(
            err.error?.detail || 'Error iniciando el proceso de suscripción'
          );
          this.loadingIframe = false;
        }
      });
  }

  /**
   * PASO 5: Confirmar tarjeta (llamado cuando el usuario completa el iframe)
   */
  onBancardIframeComplete(): void {
    console.log('✅ Usuario completó formulario de Bancard');
    this.showBancardIframeModal = false;
    this.confirmingCard = true;

    this.notificationService.info('Confirmando tarjeta y activando suscripción...');

    this.apiService.confirmSubscriptionCard()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          console.log('✅ Suscripción confirmada:', response);
          this.notificationService.success('¡Suscripción activada exitosamente!');
          this.confirmingCard = false;
          this.loadSubscriptionData(); // Recargar datos
          this.setActiveTab('current'); // Ir a la pestaña de suscripción actual
          this.userService.refreshUserProfile().subscribe(); // Refrescar perfil
        },
        error: (err) => {
          console.error('❌ Error confirmando tarjeta:', err);
          this.notificationService.error(
            err.error?.detail || 'Error confirmando la tarjeta. Por favor, contacta a soporte.'
          );
          this.confirmingCard = false;
        }
      });
  }

  /**
   * Cerrar modal de iframe de Bancard
   */
  closeBancardModal(): void {
    this.showBancardIframeModal = false;
    this.bancardFormId = '';
  }

  // DEPRECATED: Ya no se usa - mantenido para compatibilidad
  goToAddCard(): void {
    this.router.navigate(['/payment-methods'], { queryParams: { return: '/subscription' } });
  }

  closeNoCardModal(): void {
    this.showNoCardModal = false;
  }

  closeIncompleteProfileModal(): void {
    this.showIncompleteProfileModal = false;
  }

  goToProfileAndComplete(): void {
    this.showIncompleteProfileModal = false;
    this.router.navigate(['/profile'], {
      queryParams: {
        returnUrl: this.router.url,
        missingFields: this.missingProfileFields.join(',')
      }
    });
  }

  closePlanChangeModal(): void {
    this.showPlanChangeModal = false;
    this.selectedPlanId = '';
    this.changeReason = '';
    this.confirmChangeAcknowledged = false;
  }

  // DEPRECATED: Ya no se usa el formulario de datos del comprador
  submitPlanChange(): void {
    // Este método ya no se usa - el flujo ahora va directo al iframe
    console.warn('submitPlanChange() está deprecated - usar startCardRegistration()');
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

    this.apiService.cancelMySubscription()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.notificationService.success(response?.message || 'Suscripción cancelada correctamente');
          this.cancelling = false;
          this.showCancelConfirmModal = false;
          this.loadSubscriptionData();
          this.setActiveTab('plans');
          // Refrescar perfil global
          this.userService.refreshUserProfile().subscribe();
        },
        error: (error: any) => {
          console.error('Error cancelling subscription:', error);
          this.notificationService.error('No se pudo cancelar la suscripción');
          this.cancelling = false;
        }
      });
  }
}
