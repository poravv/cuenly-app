# 🧩 Especificaciones Técnicas de Componentes

## Componentes Compartidos (Shared Components)

### 1. QuickEmailSetupModal

**Ubicación:** `frontend/src/app/components/shared/quick-email-setup/`

**Propósito:** Modal inteligente para configuración rápida de correo en 3 pasos, sin salir del contexto actual.

#### Props/Inputs

```typescript
interface QuickEmailSetupConfig {
  // Configuración
  showOnInit?: boolean;              // Mostrar automáticamente al cargar
  allowDismiss?: boolean;            // Permitir cerrar sin completar
  onComplete?: (config: EmailConfig) => void;  // Callback al completar
  
  // Comportamiento
  autoDetectProvider?: boolean;      // Auto-detectar Gmail/Outlook
  runTestConnection?: boolean;       // Test automático al ingresar credenciales
  showAdvanced?: boolean;            // Mostrar opciones avanzadas
  
  // Valores por defecto
  defaultSearchTerms?: string[];     // Pre-fill términos de búsqueda
  defaultProvider?: 'gmail' | 'outlook' | 'custom';
}
```

#### Estructura del Componente

```typescript
@Component({
  selector: 'app-quick-email-setup',
  templateUrl: './quick-email-setup.component.html',
  styleUrls: ['./quick-email-setup.component.scss']
})
export class QuickEmailSetupComponent implements OnInit, OnDestroy {
  
  // Estado del wizard
  currentStep: 1 | 2 | 3 = 1;
  totalSteps = 3;
  
  // Configuración
  config: Partial<EmailConfig> = {
    search_terms: ['factura', 'invoice', 'comprobante'],
    use_ssl: true,
    port: 993
  };
  
  // Estado de validación
  isValidating = false;
  validationResult: {
    email?: ValidationError;
    password?: ValidationError;
    connection?: ValidationError;
  } = {};
  
  // Test de conexión
  isTestingConnection = false;
  connectionTestResult?: EmailTestResult;
  
  // Estados UI
  loading = false;
  error: string | null = null;
  
  // Providers configurados
  providers = [
    {
      id: 'gmail',
      name: 'Gmail',
      icon: 'google.svg',
      host: 'imap.gmail.com',
      port: 993,
      ssl: true,
      helpUrl: 'https://support.google.com/accounts/answer/185833'
    },
    {
      id: 'outlook',
      name: 'Outlook',
      icon: 'bi-microsoft',
      host: 'imap-mail.outlook.com',
      port: 993,
      ssl: true,
      helpUrl: 'https://support.microsoft.com/en-us/account-billing/'
    },
    {
      id: 'custom',
      name: 'Otro proveedor',
      icon: 'bi-envelope-at',
      host: '',
      port: 993,
      ssl: true
    }
  ];
  
  selectedProvider?: typeof this.providers[0];
  
  constructor(
    private api: ApiService,
    private notification: NotificationService,
    private emailService: EmailConfigService
  ) {}
  
  ngOnInit(): void {
    this.loadFromLocalStorage();
  }
  
  // ============= Step 1: Selección de Proveedor =============
  
  selectProvider(provider: typeof this.providers[0]): void {
    this.selectedProvider = provider;
    
    // Auto-fill configuración
    this.config.provider = provider.id;
    this.config.host = provider.host;
    this.config.port = provider.port;
    this.config.use_ssl = provider.ssl;
    
    // Avanzar automáticamente
    if (provider.id !== 'custom') {
      this.nextStep();
    }
  }
  
  detectProviderFromEmail(email: string): void {
    const domain = email.split('@')[1]?.toLowerCase();
    
    if (domain?.includes('gmail')) {
      const gmail = this.providers.find(p => p.id === 'gmail');
      if (gmail) this.selectProvider(gmail);
    } else if (domain?.includes('outlook') || domain?.includes('hotmail')) {
      const outlook = this.providers.find(p => p.id === 'outlook');
      if (outlook) this.selectProvider(outlook);
    }
  }
  
  // ============= Step 2: Credenciales =============
  
  onEmailInput(email: string): void {
    this.config.username = email;
    
    // Auto-detectar al escribir
    if (email.includes('@')) {
      this.detectProviderFromEmail(email);
    }
    
    // Validar formato
    this.validateEmail(email);
  }
  
  validateEmail(email: string): void {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    
    if (!emailRegex.test(email)) {
      this.validationResult.email = {
        valid: false,
        message: 'Formato de email inválido'
      };
    } else {
      this.validationResult.email = { valid: true };
    }
  }
  
  onPasswordInput(password: string): void {
    this.config.password = password;
    
    // Auto-test si está configurado
    if (this.config.username && password.length > 8 && this.selectedProvider) {
      this.debouncedTestConnection();
    }
  }
  
  // Debounced para no hacer requests en cada keystroke
  private _testConnectionTimeout?: any;
  debouncedTestConnection(): void {
    if (this._testConnectionTimeout) {
      clearTimeout(this._testConnectionTimeout);
    }
    
    this._testConnectionTimeout = setTimeout(() => {
      this.testConnection();
    }, 1000);
  }
  
  async testConnection(): Promise<void> {
    if (!this.config.username || !this.config.password || !this.config.host) {
      return;
    }
    
    this.isTestingConnection = true;
    this.connectionTestResult = undefined;
    
    try {
      const result = await this.api.testEmailConnection({
        host: this.config.host!,
        port: this.config.port!,
        username: this.config.username,
        password: this.config.password,
        use_ssl: this.config.use_ssl!
      }).toPromise();
      
      this.connectionTestResult = result;
      
      if (result.success) {
        this.notification.success(
          `Conexión exitosa. Encontrados ${result.emails_found || 0} correos`,
          'Test exitoso'
        );
      } else {
        this.notification.error(result.message || 'Error al conectar', 'Test fallido');
      }
    } catch (error: any) {
      this.connectionTestResult = {
        success: false,
        message: error.message || 'Error de conexión'
      };
      this.notification.error('No se pudo conectar al servidor', 'Error');
    } finally {
      this.isTestingConnection = false;
    }
  }
  
  // ============= Step 3: Confirmación =============
  
  async saveAndProcess(): Promise<void> {
    this.loading = true;
    this.error = null;
    
    try {
      // 1. Guardar configuración
      const savedConfig = await this.api.createEmailConfig(this.config).toPromise();
      
      this.notification.success('Cuenta de correo configurada', 'Éxito');
      
      // 2. Iniciar procesamiento inmediatamente
      await this.api.processEmails().toPromise();
      
      this.notification.success(
        'Procesamiento iniciado. Te notificaremos cuando termine.',
        'En Proceso'
      );
      
      // 3. Cerrar modal y emitir evento
      this.onComplete?.emit(savedConfig);
      this.close();
      
    } catch (error: any) {
      this.error = error.message || 'Error al guardar configuración';
      this.notification.error(this.error, 'Error');
    } finally {
      this.loading = false;
    }
  }
  
  saveOnly(): void {
    // Solo guardar sin procesar
    this.api.createEmailConfig(this.config).subscribe({
      next: (config) => {
        this.notification.success('Configuración guardada', 'Éxito');
        this.onComplete?.emit(config);
        this.close();
      },
      error: (err) => {
        this.notification.error(err.message, 'Error');
      }
    });
  }
  
  // ============= Navegación del Wizard =============
  
  nextStep(): void {
    if (this.currentStep < this.totalSteps) {
      this.currentStep++;
      this.saveToLocalStorage();
    }
  }
  
  prevStep(): void {
    if (this.currentStep > 1) {
      this.currentStep--;
    }
  }
  
  canGoNext(): boolean {
    switch (this.currentStep) {
      case 1:
        return !!this.selectedProvider;
      case 2:
        return !!this.config.username && 
               !!this.config.password && 
               !!this.connectionTestResult?.success;
      case 3:
        return true;
      default:
        return false;
    }
  }
  
  // ============= Persistencia Local =============
  
  saveToLocalStorage(): void {
    const data = {
      step: this.currentStep,
      config: this.config,
      provider: this.selectedProvider?.id
    };
    localStorage.setItem('cuenly_quick_setup', JSON.stringify(data));
  }
  
  loadFromLocalStorage(): void {
    const stored = localStorage.getItem('cuenly_quick_setup');
    if (stored) {
      try {
        const data = JSON.parse(stored);
        this.currentStep = data.step || 1;
        this.config = { ...this.config, ...data.config };
        if (data.provider) {
          this.selectedProvider = this.providers.find(p => p.id === data.provider);
        }
      } catch (e) {
        console.error('Error loading from localStorage', e);
      }
    }
  }
  
  clearLocalStorage(): void {
    localStorage.removeItem('cuenly_quick_setup');
  }
  
  // ============= Lifecycle =============
  
  close(): void {
    this.clearLocalStorage();
    // Emit close event or use modal service
  }
  
  ngOnDestroy(): void {
    if (this._testConnectionTimeout) {
      clearTimeout(this._testConnectionTimeout);
    }
  }
}
```

#### Template HTML

```html
<!-- quick-email-setup.component.html -->
<div class="modal-backdrop" (click)="allowDismiss && close()">
  <div class="modal-content" (click)="$event.stopPropagation()">
    
    <!-- Header -->
    <div class="modal-header">
      <h2 class="modal-title">
        <i class="bi bi-envelope-at icon-gradient"></i>
        Configuración Rápida de Correo
      </h2>
      <button class="btn-close" (click)="close()" *ngIf="allowDismiss">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
    
    <!-- Progress Stepper -->
    <div class="stepper">
      <div class="stepper-item" 
           *ngFor="let step of [1, 2, 3]"
           [class.active]="currentStep === step"
           [class.completed]="currentStep > step">
        <div class="stepper-circle">
          <i class="bi bi-check" *ngIf="currentStep > step"></i>
          <span *ngIf="currentStep <= step">{{ step }}</span>
        </div>
        <div class="stepper-label">
          <span *ngIf="step === 1">Proveedor</span>
          <span *ngIf="step === 2">Credenciales</span>
          <span *ngIf="step === 3">Confirmar</span>
        </div>
      </div>
    </div>
    
    <!-- Body -->
    <div class="modal-body">
      
      <!-- Step 1: Seleccionar Proveedor -->
      <div class="step-content" *ngIf="currentStep === 1" @fadeIn>
        <h3 class="step-title">Selecciona tu proveedor de correo</h3>
        <p class="step-description">
          Elige el servicio que usas para recibir tus facturas
        </p>
        
        <div class="provider-grid">
          <div class="provider-card" 
               *ngFor="let provider of providers"
               [class.selected]="selectedProvider?.id === provider.id"
               (click)="selectProvider(provider)">
            <div class="provider-icon">
              <img *ngIf="provider.icon.includes('.')" 
                   [src]="'assets/' + provider.icon" 
                   [alt]="provider.name">
              <i *ngIf="!provider.icon.includes('.')" 
                 [class]="provider.icon"></i>
            </div>
            <div class="provider-name">{{ provider.name }}</div>
            <i class="bi bi-check-circle-fill check-icon" 
               *ngIf="selectedProvider?.id === provider.id"></i>
          </div>
        </div>
        
        <div class="help-text" *ngIf="selectedProvider">
          <i class="bi bi-info-circle"></i>
          Configurarás tu cuenta de <strong>{{ selectedProvider.name }}</strong>
        </div>
      </div>
      
      <!-- Step 2: Credenciales -->
      <div class="step-content" *ngIf="currentStep === 2" @fadeIn>
        <h3 class="step-title">Ingresa tus credenciales</h3>
        <p class="step-description">
          Tu información está segura y encriptada
        </p>
        
        <form class="credentials-form">
          
          <!-- Email -->
          <div class="form-group">
            <label for="email">
              <i class="bi bi-envelope"></i>
              Correo Electrónico
            </label>
            <input 
              type="email" 
              id="email"
              class="form-control"
              [(ngModel)]="config.username"
              (ngModelChange)="onEmailInput($event)"
              [class.valid]="validationResult.email?.valid"
              [class.invalid]="validationResult.email?.valid === false"
              placeholder="tu-email@ejemplo.com"
              autocomplete="email"
              required>
            <div class="validation-message error" 
                 *ngIf="validationResult.email?.valid === false">
              {{ validationResult.email.message }}
            </div>
          </div>
          
          <!-- Password -->
          <div class="form-group">
            <label for="password">
              <i class="bi bi-key"></i>
              Contraseña de Aplicación
            </label>
            <div class="password-input-wrapper">
              <input 
                [type]="showPassword ? 'text' : 'password'"
                id="password"
                class="form-control"
                [(ngModel)]="config.password"
                (ngModelChange)="onPasswordInput($event)"
                placeholder="••••••••••••"
                autocomplete="new-password"
                required>
              <button 
                type="button"
                class="btn-toggle-password"
                (click)="showPassword = !showPassword">
                <i [class]="showPassword ? 'bi-eye-slash' : 'bi-eye'"></i>
              </button>
            </div>
            
            <div class="help-link" *ngIf="selectedProvider?.helpUrl">
              <a [href]="selectedProvider.helpUrl" target="_blank">
                <i class="bi bi-question-circle"></i>
                ¿Cómo crear una contraseña de aplicación?
              </a>
            </div>
          </div>
          
          <!-- Test Connection -->
          <div class="connection-test">
            <button 
              type="button"
              class="btn btn-outline-primary"
              (click)="testConnection()"
              [disabled]="isTestingConnection || !config.username || !config.password">
              <span *ngIf="!isTestingConnection">
                <i class="bi bi-wifi"></i>
                Probar Conexión
              </span>
              <span *ngIf="isTestingConnection">
                <span class="spinner"></span>
                Probando...
              </span>
            </button>
            
            <div class="test-result success" 
                 *ngIf="connectionTestResult?.success" 
                 @slideInUp>
              <i class="bi bi-check-circle-fill"></i>
              <div>
                <strong>Conexión exitosa</strong>
                <p>Encontrados {{ connectionTestResult.emails_found }} correos</p>
              </div>
            </div>
            
            <div class="test-result error" 
                 *ngIf="connectionTestResult && !connectionTestResult.success"
                 @slideInUp>
              <i class="bi bi-x-circle-fill"></i>
              <div>
                <strong>Error de conexión</strong>
                <p>{{ connectionTestResult.message }}</p>
              </div>
            </div>
          </div>
          
        </form>
      </div>
      
      <!-- Step 3: Confirmación y Acción -->
      <div class="step-content" *ngIf="currentStep === 3" @fadeIn>
        <div class="success-icon">
          <i class="bi bi-check-circle-fill"></i>
        </div>
        
        <h3 class="step-title text-center">¡Todo listo!</h3>
        <p class="step-description text-center">
          Tu cuenta está configurada y lista para usar
        </p>
        
        <div class="summary-card">
          <div class="summary-item">
            <i class="bi bi-envelope-at"></i>
            <div>
              <div class="summary-label">Cuenta</div>
              <div class="summary-value">{{ config.username }}</div>
            </div>
          </div>
          <div class="summary-item">
            <i class="bi bi-server"></i>
            <div>
              <div class="summary-label">Servidor</div>
              <div class="summary-value">{{ config.host }}</div>
            </div>
          </div>
          <div class="summary-item">
            <i class="bi bi-search"></i>
            <div>
              <div class="summary-label">Términos de búsqueda</div>
              <div class="summary-value">
                {{ config.search_terms?.join(', ') }}
              </div>
            </div>
          </div>
        </div>
        
        <div class="action-section">
          <h4>¿Qué deseas hacer ahora?</h4>
          
          <button 
            class="btn btn-primary btn-lg btn-block"
            (click)="saveAndProcess()"
            [disabled]="loading">
            <i class="bi bi-rocket-takeoff"></i>
            Guardar y Procesar Facturas Ahora
          </button>
          
          <button 
            class="btn btn-secondary btn-block"
            (click)="saveOnly()"
            [disabled]="loading">
            <i class="bi bi-bookmark"></i>
            Solo Guardar Configuración
          </button>
          
          <div class="loading-state" *ngIf="loading">
            <span class="spinner"></span>
            Guardando configuración...
          </div>
          
          <div class="error-message" *ngIf="error">
            <i class="bi bi-exclamation-triangle"></i>
            {{ error }}
          </div>
        </div>
      </div>
      
    </div>
    
    <!-- Footer Navigation -->
    <div class="modal-footer" *ngIf="currentStep < 3">
      <button 
        class="btn btn-ghost"
        (click)="prevStep()"
        [disabled]="currentStep === 1">
        <i class="bi bi-arrow-left"></i>
        Atrás
      </button>
      
      <button 
        class="btn btn-primary"
        (click)="nextStep()"
        [disabled]="!canGoNext()">
        Continuar
        <i class="bi bi-arrow-right"></i>
      </button>
    </div>
    
  </div>
</div>
```

#### Estilos SCSS

```scss
// quick-email-setup.component.scss

.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.modal-content {
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  animation: slideInUp 0.3s ease;
}

// Header
.modal-header {
  padding: 24px;
  border-bottom: 1px solid #E5E7EB;
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  .modal-title {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    
    .icon-gradient {
      background: linear-gradient(135deg, #4F46E5, #818CF8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-size: 1.75rem;
    }
  }
  
  .btn-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #6B7280;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.2s;
    
    &:hover {
      background: #F3F4F6;
      color: #111827;
    }
  }
}

// Stepper
.stepper {
  display: flex;
  justify-content: space-between;
  padding: 32px 48px;
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 20%;
    right: 20%;
    height: 2px;
    background: #E5E7EB;
    z-index: 0;
  }
  
  .stepper-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    position: relative;
    z-index: 1;
    
    .stepper-circle {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: white;
      border: 2px solid #E5E7EB;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      color: #9CA3AF;
      transition: all 0.3s ease;
    }
    
    .stepper-label {
      font-size: 0.875rem;
      color: #6B7280;
      font-weight: 500;
    }
    
    &.active {
      .stepper-circle {
        background: #4F46E5;
        border-color: #4F46E5;
        color: white;
        box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
      }
      
      .stepper-label {
        color: #4F46E5;
        font-weight: 600;
      }
    }
    
    &.completed {
      .stepper-circle {
        background: #10B981;
        border-color: #10B981;
        color: white;
      }
      
      .stepper-label {
        color: #10B981;
      }
    }
  }
}

// Body
.modal-body {
  padding: 24px;
  min-height: 300px;
}

.step-content {
  animation: fadeIn 0.3s ease;
  
  .step-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: #111827;
  }
  
  .step-description {
    color: #6B7280;
    margin-bottom: 24px;
  }
}

// Provider Selection
.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
  
  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
}

.provider-card {
  border: 2px solid #E5E7EB;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  
  &:hover {
    border-color: #4F46E5;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.1);
    transform: translateY(-2px);
  }
  
  &.selected {
    border-color: #4F46E5;
    background: rgba(79, 70, 229, 0.05);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
    
    .check-icon {
      opacity: 1;
    }
  }
  
  .provider-icon {
    font-size: 2.5rem;
    margin-bottom: 12px;
    color: #4F46E5;
    
    img {
      width: 40px;
      height: 40px;
    }
  }
  
  .provider-name {
    font-weight: 600;
    color: #374151;
  }
  
  .check-icon {
    position: absolute;
    top: 8px;
    right: 8px;
    color: #10B981;
    font-size: 1.25rem;
    opacity: 0;
    transition: opacity 0.2s;
  }
}

// Form
.credentials-form {
  .form-group {
    margin-bottom: 20px;
    
    label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
      color: #374151;
      margin-bottom: 8px;
      font-size: 0.875rem;
    }
    
    .form-control {
      width: 100%;
      padding: 12px 16px;
      border: 2px solid #E5E7EB;
      border-radius: 8px;
      font-size: 1rem;
      transition: all 0.2s;
      
      &:focus {
        outline: none;
        border-color: #4F46E5;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
      }
      
      &.valid {
        border-color: #10B981;
      }
      
      &.invalid {
        border-color: #EF4444;
      }
    }
    
    .validation-message {
      margin-top: 8px;
      font-size: 0.875rem;
      
      &.error {
        color: #EF4444;
      }
    }
  }
  
  .password-input-wrapper {
    position: relative;
    
    .btn-toggle-password {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: #6B7280;
      cursor: pointer;
      padding: 4px;
      
      &:hover {
        color: #111827;
      }
    }
  }
  
  .help-link {
    margin-top: 8px;
    
    a {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 0.875rem;
      color: #4F46E5;
      text-decoration: none;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
}

// Connection Test
.connection-test {
  margin-top: 24px;
  
  .test-result {
    margin-top: 16px;
    padding: 16px;
    border-radius: 8px;
    display: flex;
    align-items: start;
    gap: 12px;
    animation: slideInUp 0.3s ease;
    
    i {
      font-size: 1.5rem;
      flex-shrink: 0;
    }
    
    strong {
      display: block;
      margin-bottom: 4px;
    }
    
    p {
      margin: 0;
      font-size: 0.875rem;
    }
    
    &.success {
      background: #ECFDF5;
      border: 1px solid #10B981;
      color: #065F46;
      
      i {
        color: #10B981;
      }
    }
    
    &.error {
      background: #FEF2F2;
      border: 1px solid #EF4444;
      color: #991B1B;
      
      i {
        color: #EF4444;
      }
    }
  }
}

// Summary & Actions
.success-icon {
  text-align: center;
  margin-bottom: 24px;
  
  i {
    font-size: 4rem;
    color: #10B981;
    animation: scaleIn 0.4s ease;
  }
}

.summary-card {
  background: #F9FAFB;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  
  .summary-item {
    display: flex;
    align-items: start;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid #E5E7EB;
    
    &:last-child {
      border-bottom: none;
    }
    
    i {
      font-size: 1.25rem;
      color: #4F46E5;
      flex-shrink: 0;
    }
    
    .summary-label {
      font-size: 0.75rem;
      color: #6B7280;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    
    .summary-value {
      font-weight: 500;
      color: #111827;
    }
  }
}

.action-section {
  h4 {
    font-size: 1rem;
    margin-bottom: 16px;
    color: #374151;
  }
  
  .btn-block {
    width: 100%;
    margin-bottom: 12px;
  }
  
  .loading-state {
    text-align: center;
    padding: 16px;
    color: #6B7280;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }
  
  .error-message {
    background: #FEF2F2;
    border: 1px solid #EF4444;
    color: #991B1B;
    padding: 12px;
    border-radius: 8px;
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

// Footer
.modal-footer {
  padding: 20px 24px;
  border-top: 1px solid #E5E7EB;
  display: flex;
  justify-content: space-between;
  
  .btn {
    min-width: 120px;
  }
}

// Animations
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.5);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

// Spinner
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
```

---

## Uso del Componente

### En otro componente

```typescript
// En dashboard.component.ts
showEmailSetup(): void {
  const dialogRef = this.dialog.open(QuickEmailSetupComponent, {
    width: '600px',
    disableClose: false,
    data: {
      autoDetectProvider: true,
      runTestConnection: true
    }
  });
  
  dialogRef.afterClosed().subscribe((result: EmailConfig) => {
    if (result) {
      this.loadEmailConfigs();
      this.checkSystemStatus();
    }
  });
}
```

### En el HTML

```html
<!-- dashboard.component.html -->
<div class="no-email-configs" *ngIf="!hasEmailConfigs">
  <div class="empty-state">
    <i class="bi bi-envelope-open icon-large"></i>
    <h3>No tienes cuentas de correo configuradas</h3>
    <p>Conecta tu correo para empezar a procesar facturas automáticamente</p>
    <button class="btn btn-primary btn-lg" (click)="showEmailSetup()">
      <i class="bi bi-plus-circle"></i>
      Conectar Mi Primer Correo
    </button>
  </div>
</div>
```

---

## Testing

```typescript
// quick-email-setup.component.spec.ts
describe('QuickEmailSetupComponent', () => {
  let component: QuickEmailSetupComponent;
  let fixture: ComponentFixture<QuickEmailSetupComponent>;
  let apiService: jasmine.SpyObj<ApiService>;
  
  beforeEach(async () => {
    const apiSpy = jasmine.createSpyObj('ApiService', [
      'testEmailConnection',
      'createEmailConfig',
      'processEmails'
    ]);
    
    await TestBed.configureTestingModule({
      declarations: [ QuickEmailSetupComponent ],
      providers: [
        { provide: ApiService, useValue: apiSpy }
      ]
    }).compileComponents();
    
    apiService = TestBed.inject(ApiService) as jasmine.SpyObj<ApiService>;
  });
  
  it('should detect Gmail from email address', () => {
    component.onEmailInput('test@gmail.com');
    expect(component.selectedProvider?.id).toBe('gmail');
  });
  
  it('should test connection successfully', async () => {
    const mockResult: EmailTestResult = {
      success: true,
      emails_found: 10
    };
    apiService.testEmailConnection.and.returnValue(of(mockResult));
    
    await component.testConnection();
    
    expect(component.connectionTestResult).toEqual(mockResult);
    expect(component.isTestingConnection).toBeFalse();
  });
  
  it('should save and process in one action', async () => {
    const mockConfig: EmailConfig = { /* ... */ };
    apiService.createEmailConfig.and.returnValue(of(mockConfig));
    apiService.processEmails.and.returnValue(of({ success: true }));
    
    await component.saveAndProcess();
    
    expect(apiService.createEmailConfig).toHaveBeenCalled();
    expect(apiService.processEmails).toHaveBeenCalled();
  });
});
```
