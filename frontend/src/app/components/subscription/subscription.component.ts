import { Component, OnInit } from '@angular/core';
import { UserService, UserProfile } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-subscription',
  templateUrl: './subscription.component.html',
  styleUrls: ['./subscription.component.scss']
})
export class SubscriptionComponent implements OnInit {
  userProfile: UserProfile | null = null;
  loading = true;
  selectedPlan: string = 'monthly';
  
  // Alert properties
  showAlertFlag = false;
  alertType: 'success' | 'error' | 'warning' | 'info' = 'info';
  alertMessage = '';
  
  // Processing state
  isProcessing = false;

  plans = [
    {
      id: 'monthly',
      name: 'Plan Mensual',
      price: '$29.99',
      period: '/mes',
      description: 'Perfecto para empezar',
      features: [
        'Procesamiento ilimitado de XML nativos',
        'Procesamiento con IA hasta 1,000 facturas/mes',
        'Exportación de datos a Excel y CSV',
        'Soporte técnico por email',
        'Actualizaciones automáticas',
        'Panel de control completo'
      ],
      highlight: false,
      popular: false
    },
    {
      id: 'yearly',
      name: 'Plan Anual',
      price: '$299.99',
      period: '/año',
      originalPrice: '$359.88',
      description: 'Mejor valor - ¡Ahorra 17%!',
      features: [
        'Procesamiento ilimitado de XML nativos',
        'Procesamiento con IA hasta 15,000 facturas/año',
        'Exportación de datos a Excel y CSV',
        'Soporte técnico prioritario',
        'Actualizaciones automáticas',
        'Panel de control completo',
        'Reportes avanzados',
        'API de integración'
      ],
      highlight: true,
      popular: true
    },
    {
      id: 'enterprise',
      name: 'Plan Empresarial',
      price: 'Personalizado',
      period: '',
      description: 'Para grandes volúmenes',
      features: [
        'Procesamiento ilimitado de XML nativos',
        'Procesamiento con IA ilimitado',
        'Exportación de datos a Excel y CSV',
        'Soporte técnico 24/7',
        'Actualizaciones automáticas',
        'Panel de control completo',
        'Reportes avanzados personalizados',
        'API de integración completa',
        'Implementación dedicada',
        'Capacitación del equipo'
      ],
      highlight: false,
      popular: false
    }
  ];

  constructor(
    private userService: UserService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.authService.user$.subscribe(user => {
      if (user) {
        this.loadUserProfile();
      } else {
        this.router.navigate(['/login']);
      }
    });
  }

  private loadUserProfile(): void {
    this.userService.getUserProfile().subscribe({
      next: (profile) => {
        this.userProfile = profile;
        this.loading = false;
      },
      error: (error) => {
        console.error('Error cargando perfil de usuario:', error);
        this.loading = false;
      }
    });
  }

  selectPlan(planId: string): void {
    this.selectedPlan = planId;
  }

  subscribeToPlan(planId: string): void {
    this.selectedPlan = planId;
    this.subscribe();
  }

  subscribe(): void {
    if (this.isProcessing) return;
    
    this.isProcessing = true;
    console.log('Iniciando suscripción para plan:', this.selectedPlan);
    
    // Simulación de proceso de pago
    setTimeout(() => {
      this.isProcessing = false;
      const planName = this.getPlanName(this.selectedPlan);
      this.showAlert('success', `¡Suscripción exitosa a ${planName}! Ahora tienes acceso completo.`);
    }, 2000);
  }

  private proceedToPayment(planId: string): void {
    // Integración con pasarela de pago (Stripe, PayPal, etc.)
    console.log('Proceeding to payment for plan:', planId);
    
    // Simulación de redirección a pago
    alert(`Redirigiendo a la página de pago para el ${this.getPlanName(planId)}...`);
    
    // Aquí implementarías:
    // 1. Crear sesión de pago con Stripe/PayPal
    // 2. Redirigir al usuario
    // 3. Manejar el callback de éxito/error
  }

  public contactSales(): void {
    this.showAlert('info', 'Contacta con nuestro equipo de ventas: ventas@cuenlyapp.com');
  }

  private getPlanName(planId: string): string {
    const plan = this.plans.find(p => p.id === planId);
    return plan ? plan.name : 'Plan';
  }

  getDaysRemaining(): number {
    return this.userProfile?.trial_days_remaining || 0;
  }

  isTrialExpired(): boolean {
    return this.userProfile?.trial_expired || false;
  }

  getTrialMessage(): string {
    if (this.isTrialExpired()) {
      return 'Tu período de prueba ha expirado. Suscríbete para continuar usando todas las funciones.';
    } else {
      const daysLeft = this.getDaysRemaining();
      return `Te quedan ${daysLeft} días de prueba. Suscríbete ahora y no pierdas acceso a tus datos.`;
    }
  }

  showAlert(type: 'success' | 'error' | 'warning' | 'info', message: string): void {
    this.alertType = type;
    this.alertMessage = message;
    this.showAlertFlag = true;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
      this.hideAlert();
    }, 5000);
  }

  hideAlert(): void {
    this.showAlertFlag = false;
  }
}