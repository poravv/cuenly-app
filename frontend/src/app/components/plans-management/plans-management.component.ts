import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

interface Plan {
  name: string;
  code: string;
  description: string;
  price: number;
  currency: string;
  billing_period: string;
  features: {
    ai_invoices_limit: number;
    email_processing: boolean;
    export_formats: string[];
    api_access: boolean;
    priority_support: boolean;
    custom_templates: boolean;
  };
  status: string;
  is_popular: boolean;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
}

interface SubscriptionStats {
  total_subscriptions: number;
  active_subscriptions: number;
  total_revenue: number;
  plan_stats: Array<{
    _id: string;
    plan_name: string;
    total_subscriptions: number;
    active_subscriptions: number;
    total_revenue: number;
    avg_price: number;
  }>;
}

interface User {
  email: string;
  name: string;
  role: string;
  status: string;
  created_at: string;
  is_trial_user: boolean;
}

@Component({
  selector: 'app-plans-management',
  templateUrl: './plans-management.component.html',
  styleUrls: ['./plans-management.component.scss']
})
export class PlansManagementComponent implements OnInit {
  activeTab: string = 'plans';
  loading: boolean = false;
  
  // Plans data
  plans: Plan[] = [];
  loadingPlans: boolean = false;
  
  // Subscription stats
  subscriptionStats: SubscriptionStats | null = null;
  loadingStats: boolean = false;
  
  // Plan form
  showPlanForm: boolean = false;
  editingPlan: Plan | null = null;
  planForm = {
    name: '',
    code: '',
    description: '',
    price: 0,
    currency: 'USD',
    billing_period: 'monthly',
    features: {
      ai_invoices_limit: 50,
      email_processing: true,
      export_formats: ['excel', 'csv'],
      api_access: false,
      priority_support: false,
      custom_templates: false
    },
    status: 'active',
    is_popular: false,
    sort_order: 0
  };
  
  // User assignment
  showUserAssignment: boolean = false;
  users: User[] = [];
  loadingUsers: boolean = false;
  selectedUser: string = '';
  selectedPlan: string = '';
  
  // Available features for form
  availableExportFormats = [
    { value: 'excel', label: 'Excel' },
    { value: 'csv', label: 'CSV' },
    { value: 'json', label: 'JSON' },
    { value: 'pdf', label: 'PDF' }
  ];
  
  billingPeriods = [
    { value: 'monthly', label: 'Mensual' },
    { value: 'yearly', label: 'Anual' },
    { value: 'one_time', label: 'Pago único' }
  ];
  
  currencies = [
    { value: 'USD', label: 'USD' },
    { value: 'EUR', label: 'EUR' },
    { value: 'PYG', label: 'PYG' }
  ];

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadPlans();
    this.loadSubscriptionStats();
  }

  setActiveTab(tab: string): void {
    this.activeTab = tab;
    if (tab === 'assign' && this.users.length === 0) {
      this.loadUsers();
    }
  }

  // =====================================
  // PLANS MANAGEMENT
  // =====================================

  async loadPlans(): Promise<void> {
    this.loadingPlans = true;
    try {
      const response = await this.apiService.get('/admin/plans?include_inactive=true');
      if (response.success) {
        this.plans = response.data || [];
      }
    } catch (error) {
      console.error('Error loading plans:', error);
    } finally {
      this.loadingPlans = false;
    }
  }

  async loadSubscriptionStats(): Promise<void> {
    this.loadingStats = true;
    try {
      const response = await this.apiService.get('/admin/subscriptions/stats');
      if (response.success) {
        this.subscriptionStats = response.data;
      }
    } catch (error) {
      console.error('Error loading subscription stats:', error);
    } finally {
      this.loadingStats = false;
    }
  }

  showCreatePlanForm(): void {
    this.editingPlan = null;
    this.resetPlanForm();
    this.showPlanForm = true;
  }

  editPlan(plan: Plan): void {
    this.editingPlan = plan;
    this.planForm = { ...plan };
    this.showPlanForm = true;
  }

  resetPlanForm(): void {
    this.planForm = {
      name: '',
      code: '',
      description: '',
      price: 0,
      currency: 'USD',
      billing_period: 'monthly',
      features: {
        ai_invoices_limit: 50,
        email_processing: true,
        export_formats: ['excel', 'csv'],
        api_access: false,
        priority_support: false,
        custom_templates: false
      },
      status: 'active',
      is_popular: false,
      sort_order: 0
    };
  }

  async savePlan(): Promise<void> {
    if (!this.planForm.name || !this.planForm.code) {
      this.notificationService.warning('Nombre y código son obligatorios', 'Validación');
      return;
    }

    try {
      let response;
      if (this.editingPlan) {
        response = await this.apiService.put(`/admin/plans/${this.editingPlan.code}`, this.planForm);
      } else {
        response = await this.apiService.post('/admin/plans', this.planForm);
      }

      if (response.success) {
        this.showPlanForm = false;
        this.loadPlans();
        this.notificationService.success(response.message, 'Plan guardado');
      }
    } catch (error: any) {
      console.error('Error saving plan:', error);
      this.notificationService.error('Error guardando plan: ' + (error.error?.detail || error.message));
    }
  }

  async deletePlan(plan: Plan): Promise<void> {
    if (!confirm(`¿Estás seguro de eliminar el plan "${plan.name}"?`)) {
      return;
    }

    try {
      const response = await this.apiService.delete(`/admin/plans/${plan.code}`);
      if (response.success) {
        this.loadPlans();
        this.notificationService.success(response.message, 'Plan eliminado');
      }
    } catch (error: any) {
      console.error('Error deleting plan:', error);
      this.notificationService.error('Error eliminando plan: ' + (error.error?.detail || error.message));
    }
  }

  cancelPlanForm(): void {
    this.showPlanForm = false;
    this.editingPlan = null;
    this.resetPlanForm();
  }

  // =====================================
  // USER ASSIGNMENT
  // =====================================

  async loadUsers(): Promise<void> {
    this.loadingUsers = true;
    try {
      const response = await this.apiService.get('/admin/users');
      if (response.success) {
        // Usar la propiedad 'users' que es la que devuelve el backend
        this.users = response.users || [];
      }
    } catch (error) {
      console.error('Error loading users:', error);
    } finally {
      this.loadingUsers = false;
    }
  }

  async assignPlanToUser(): Promise<void> {
    if (!this.selectedUser || !this.selectedPlan) {
      this.notificationService.warning('Selecciona un usuario y un plan', 'Validación');
      return;
    }

    try {
      const response = await this.apiService.post('/admin/subscriptions', {
        user_email: this.selectedUser,
        plan_code: this.selectedPlan,
        payment_method: 'manual'
      });

      if (response.success) {
        this.notificationService.success(response.message, 'Plan asignado');
        this.selectedUser = '';
        this.selectedPlan = '';
        this.loadSubscriptionStats();
      }
    } catch (error: any) {
      console.error('Error assigning plan:', error);
      this.notificationService.error('Error asignando plan: ' + (error.error?.detail || error.message));
    }
  }

  // =====================================
  // UTILITY METHODS
  // =====================================

  formatCurrency(amount: number, currency: string): string {
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: currency
    }).format(amount);
  }

  formatNumber(num: number): string {
    return new Intl.NumberFormat('es-ES').format(num);
  }

  getBillingPeriodLabel(period: string): string {
    const found = this.billingPeriods.find(p => p.value === period);
    return found ? found.label : period;
  }

  getStatusClass(status: string): string {
    switch (status) {
      case 'active': return 'badge-success';
      case 'inactive': return 'badge-warning';
      case 'deprecated': return 'badge-danger';
      default: return 'badge-secondary';
    }
  }

  toggleExportFormat(format: string): void {
    const formats = this.planForm.features.export_formats;
    const index = formats.indexOf(format);
    if (index > -1) {
      formats.splice(index, 1);
    } else {
      formats.push(format);
    }
  }

  isExportFormatSelected(format: string): boolean {
    return this.planForm.features.export_formats.includes(format);
  }
}