import { Component, Input, Output, EventEmitter } from '@angular/core';
import { finalize } from 'rxjs';
import { ApiService } from '../../../services/api.service';
import { NotificationService } from '../../../services/notification.service';
import { EmailConfig } from '../../../models/invoice.model';

/**
 * QuickEmailModalComponent
 * Quick Win #2: Modal rápido para configuración de correo en 3-4 clicks
 * Reduce el proceso de configuración de 9+ clicks a 3-4 clicks
 */
@Component({
  selector: 'app-quick-email-modal',
  templateUrl: './quick-email-modal.component.html',
  styleUrls: ['./quick-email-modal.component.scss']
})
export class QuickEmailModalComponent {
  @Input() isOpen = false;
  @Output() closed = new EventEmitter<void>();
  @Output() saved = new EventEmitter<{ id?: string; provider?: string; username?: string }>();

  private readonly emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  private readonly knownAutoHosts = new Set(['imap.gmail.com', 'imap-mail.outlook.com']);

  detectedProvider: 'gmail' | 'outlook' | 'custom' | null = null;
  config: Partial<EmailConfig> = this.getDefaultConfig();

  saving = false;

  constructor(
    private api: ApiService,
    private notification: NotificationService
  ) {}

  /**
   * Auto-detectar proveedor de correo basado en el dominio del email
   */
  detectProvider(email: string): void {
    const normalizedEmail = (email || '').trim().toLowerCase();
    this.config.username = normalizedEmail;

    if (!normalizedEmail.includes('@')) {
      this.detectedProvider = null;
      return;
    }

    const domain = normalizedEmail.split('@')[1] || '';

    if (domain.includes('gmail.com')) {
      this.setProviderConfig('gmail', 'imap.gmail.com');
      return;
    }

    if (
      domain.includes('outlook.com') ||
      domain.includes('hotmail.com') ||
      domain.includes('live.com') ||
      domain.includes('msn.com')
    ) {
      this.setProviderConfig('outlook', 'imap-mail.outlook.com');
      return;
    }

    this.detectedProvider = 'custom';
    const currentHost = (this.config.host || '').trim().toLowerCase();
    if (this.knownAutoHosts.has(currentHost)) {
      this.config.host = '';
    }
    this.config.port = this.config.port || 993;
    this.config.use_ssl = this.config.use_ssl ?? true;
  }

  private setProviderConfig(provider: 'gmail' | 'outlook', host: string): void {
    this.detectedProvider = provider;
    this.config.provider = provider;
    this.config.host = host;
    this.config.port = 993;
    this.config.use_ssl = true;
  }

  isProviderAutoDetected(): boolean {
    return this.detectedProvider === 'gmail' || this.detectedProvider === 'outlook';
  }

  isCustomProvider(): boolean {
    return this.detectedProvider === 'custom';
  }

  isValidEmail(): boolean {
    return this.emailRegex.test((this.config.username || '').trim());
  }

  isValidHost(): boolean {
    const host = (this.config.host || '').trim();
    return host.length > 0 && !host.includes(' ');
  }

  isValidPort(): boolean {
    const port = Number(this.config.port || 0);
    return Number.isInteger(port) && port > 0 && port <= 65535;
  }

  /**
   * Validar que los campos requeridos estén completos
   */
  isValid(): boolean {
    return (
      this.isValidEmail() &&
      !!(this.config.password || '').trim() &&
      this.isValidHost() &&
      this.isValidPort()
    );
  }

  /**
   * Guardar configuración y procesar correos inmediatamente
   * Acción combinada para máxima eficiencia
   */
  saveAndProcess(): void {
    if (this.saving) {
      return;
    }

    if (!this.isValid()) {
      this.notification.warning('Completa todos los campos requeridos', 'Validación');
      return;
    }

    this.saving = true;

    // Crear EmailConfig completo desde Partial
    const emailConfig: EmailConfig = {
      host: (this.config.host || '').trim(),
      port: this.config.port || 993,
      username: (this.config.username || '').trim(),
      password: this.config.password || '',
      use_ssl: this.config.use_ssl !== undefined ? this.config.use_ssl : true,
      search_terms: this.config.search_terms || ['factura', 'invoice', 'comprobante', 'electronico'],
      provider: this.detectedProvider === 'custom' ? 'other' : (this.detectedProvider || 'other')
    };

    this.api.createEmailConfig(emailConfig).subscribe({
      next: (savedConfig) => {
        this.notification.success('Cuenta de correo configurada exitosamente', 'Éxito');

        this.saved.emit({
          id: savedConfig.id,
          provider: emailConfig.provider,
          username: emailConfig.username
        });

        // Procesar correos inmediatamente
        this.api.processEmails(false).pipe(
          finalize(() => {
            this.saving = false;
            this.close();
          })
        ).subscribe({
          next: (result) => {
            if (!result.success) {
              this.notification.info(
                result.message || 'La cuenta se guardó. El procesamiento se ejecutará en segundo plano.',
                'Cuenta Configurada'
              );
              return;
            }

            const processedInvoices = result.invoice_count ?? result.invoices?.length ?? 0;
            if (processedInvoices > 0) {
              this.notification.success(
                `Se procesaron ${processedInvoices} factura(s)`,
                'Procesamiento Completado'
              );
              return;
            }

            this.notification.info('Cuenta lista. No se encontraron facturas nuevas.', 'Sin Novedades');
          },
          error: (err) => {
            console.error('Error processing emails:', err);
            this.notification.warning(
              'La cuenta se configuró, pero hubo un problema al iniciar el procesamiento',
              'Advertencia'
            );
          }
        });
      },
      error: (err) => {
        console.error('Error creating email config:', err);
        const errorMsg = err.error?.message || err.message || 'Error al configurar cuenta de correo';
        this.notification.error(errorMsg, 'Error');
        this.saving = false;
      }
    });
  }
  
  /**
   * Cerrar modal y limpiar formulario
   */
  close(): void {
    if (this.saving) {
      return;
    }

    this.isOpen = false;
    this.detectedProvider = null;
    this.config = this.getDefaultConfig();
    this.closed.emit();
  }

  /**
   * Obtener URL de ayuda para crear contraseña de aplicación
   */
  getHelpUrl(): string {
    if (this.detectedProvider === 'gmail') {
      return 'https://myaccount.google.com/apppasswords';
    }

    if (this.detectedProvider === 'outlook') {
      return 'https://support.microsoft.com/es-es/account-billing/uso-de-contrase%C3%B1as-de-aplicaci%C3%B3n-con-aplicaciones-que-no-admiten-la-verificaci%C3%B3n-en-dos-pasos-5896ed9b-4263-e681-128a-a6f2979a7944';
    }

    return '';
  }

  private getDefaultConfig(): Partial<EmailConfig> {
    return {
      host: '',
      port: 993,
      use_ssl: true,
      search_terms: ['factura', 'invoice', 'comprobante']
    };
  }
}
