import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { EmailConfig, EmailTestResult, EmailConfigsResponse } from '../../models/invoice.model';

interface SearchTermPreset {
  id: string;
  label: string;
  terms: string[];
}

@Component({
  selector: 'app-email-config',
  templateUrl: './email-config.component.html',
  styleUrls: ['./email-config.component.scss']
})
export class EmailConfigComponent implements OnInit, OnDestroy {
  emailConfigs: EmailConfig[] = [];
  newConfig: EmailConfig = this.createEmptyConfig();
  newSynonymsText = '';
  newAdvancedOpen = false;
  savingNew = false;
  showAddForm = false;
  testResults: { [key: string]: EmailTestResult;[key: number]: EmailTestResult } = {} as any;
  testing: { [key: string]: boolean;[key: number]: boolean } = {} as any;
  loading = false;
  error: string | null = null;

  // Límites de cuentas de correo por plan
  maxEmailAccounts: number = 1;
  canAddMore: boolean = true;
  hasActivePlan: boolean = false;

  // OAuth state
  googleOAuthConfigured: boolean = false;
  oauthLoading: boolean = false;
  pendingOAuthData: any = null;

  // Provider selection for new config
  selectedProvider: string = '';

  // Configuraciones predefinidas para proveedores comunes
  providers = [
    {
      name: 'Personalizado (IMAP)',
      id: 'other',
      host: '',
      port: 993,
      use_ssl: true,
      supportsOAuth: false
    },
    {
      name: 'Gmail',
      id: 'gmail',
      host: 'imap.gmail.com',
      port: 993,
      use_ssl: true,
      supportsOAuth: false, // Ahora se usa Custom IMAP primordialmente
      comingSoon: true
    },
    {
      name: 'Outlook/Hotmail',
      id: 'outlook',
      host: 'imap-mail.outlook.com',
      port: 993,
      use_ssl: true,
      supportsOAuth: false,
      comingSoon: true
    }
  ];

  searchTermPresets: SearchTermPreset[] = [
    { id: 'facturas', label: 'Facturas', terms: ['factura', 'comprobante', 'factura electronica'] },
    { id: 'pagos', label: 'Pagos', terms: ['pago', 'recibo', 'cobro'] },
    { id: 'compras', label: 'Compras', terms: ['orden de compra', 'pedido', 'adquisicion'] },
    { id: 'servicios', label: 'Servicios', terms: ['servicio', 'suscripcion', 'plan'] }
  ];

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) { }

  ngOnInit(): void {
    // Cargar configuraciones desde el backend
    this.loadConfigs();
    // Check Google OAuth availability
    this.checkGoogleOAuthStatus();
    // Listen for OAuth callback messages
    window.addEventListener('message', this.handleOAuthMessage.bind(this));
    // Check for OAuth result in localStorage (fallback mechanism)
    this.checkLocalStorageOAuth();
  }

  ngOnDestroy(): void {
    window.removeEventListener('message', this.handleOAuthMessage.bind(this));
  }

  @HostListener('window:message', ['$event'])
  handleOAuthMessage(event: MessageEvent): void {
    // Handle new simplified OAuth complete message
    if (event.data?.type === 'GOOGLE_OAUTH_COMPLETE') {
      this.oauthLoading = false;
      if (event.data.success) {
        this.loadConfigs();
        this.showAddForm = false;
        this.selectedProvider = '';
        this.notificationService.success('Cuenta Gmail conectada exitosamente', 'OAuth Completado');
      }
      return;
    }
    // Legacy handler for full OAuth callback data
    if (event.data?.type === 'GOOGLE_OAUTH_CALLBACK') {
      this.handleGoogleOAuthCallback(event.data);
    }
  }

  checkLocalStorageOAuth(): void {
    try {
      const stored = localStorage.getItem('cuenly_oauth_result');
      if (stored) {
        localStorage.removeItem('cuenly_oauth_result');
        const result = JSON.parse(stored);
        if (result?.success && result?.data) {
          this.handleGoogleOAuthCallback(result);
        }
      }
    } catch (e) {
      // Error handled silently
    }
  }

  checkGoogleOAuthStatus(): void {
    this.apiService.getGoogleOAuthStatus().subscribe({
      next: (status) => {
        this.googleOAuthConfigured = status.configured;
      },
      error: () => {
        this.googleOAuthConfigured = false;
      }
    });
  }

  loadConfigs(): void {
    this.loading = true; this.error = null;
    this.apiService.getEmailConfigs().subscribe({
      next: (resp: EmailConfigsResponse) => {
        this.emailConfigs = (resp.configs || []).map((cfg: EmailConfig) => ({
          ...cfg,
          search_synonyms: cfg.search_synonyms || {},
          fallback_sender_match: cfg.fallback_sender_match !== undefined ? !!cfg.fallback_sender_match : true,
          fallback_attachment_match: cfg.fallback_attachment_match !== undefined ? !!cfg.fallback_attachment_match : true
        }));
        this.maxEmailAccounts = resp.max_allowed || 1;
        this.canAddMore = resp.can_add_more !== undefined ? resp.can_add_more : true;
        this.hasActivePlan = resp.has_active_plan !== undefined ? resp.has_active_plan : false;
        this.loading = false;

        // Mostrar información de límite si está cerca
        if (!this.canAddMore) {
          const limit = this.maxEmailAccounts === -1 ? 'ilimitadas' : this.maxEmailAccounts;
          const planName = this.hasActivePlan ? 'tu plan' : 'tu Plan Gratuito';
          this.notificationService.info(
            `Has alcanzado el límite de ${limit} cuentas de correo de ${planName}`,
            'Límite alcanzado'
          );
        }
      },
      error: (err) => {
        this.emailConfigs = [];
        this.loading = false;
        this.error = 'No se pudieron cargar las configuraciones';
      }
    });
  }

  createEmptyConfig(): EmailConfig {
    return {
      id: undefined,
      name: '',
      host: '',
      port: 993,
      username: '',
      password: '',
      use_ssl: true,
      search_terms: ['factura', 'invoice', 'comprobante', 'electronico'],
      search_synonyms: {},
      fallback_sender_match: true,
      fallback_attachment_match: true,
      search_criteria: 'UNSEEN',
      provider: 'other',
      enabled: true,
      auth_type: 'password'
    };
  }

  selectProvider(provider: any): void {
    this.selectedProvider = provider.id;
    this.newConfig.host = provider.host;
    this.newConfig.port = provider.port;
    this.newConfig.use_ssl = provider.use_ssl;
    this.newConfig.provider = provider.id;
  }

  selectProviderById(providerId: string): void {
    const provider = this.providers.find((p) => p.id === providerId) || this.providers.find((p) => p.id === 'other');
    if (provider) {
      this.selectProvider(provider);
    }
  }

  startQuickAdd(providerId: 'other' | 'gmail' | 'outlook'): void {
    if (!this.canAddMore) {
      const planName = this.hasActivePlan ? 'tu plan actual' : 'el Plan Gratuito';
      this.notificationService.warning(
        `Ya alcanzaste el límite de cuentas para ${planName}.`,
        'Límite de cuentas'
      );
      return;
    }

    this.newConfig = this.createEmptyConfig();
    this.newSynonymsText = '';
    this.newAdvancedOpen = false;
    this.savingNew = false;
    this.pendingOAuthData = null;
    this.showAddForm = true;
    const provider = this.providers.find((p) => p.id === providerId) || this.providers.find((p) => p.id === 'other');
    if (provider) {
      this.selectProvider(provider);
    }
  }

  // -----------------------------
  // Google OAuth Flow
  // -----------------------------

  initiateGoogleOAuth(): void {
    if (!this.canAddMore) {
      this.notificationService.error(
        `Has alcanzado el límite de ${this.maxEmailAccounts} cuentas de correo. Actualiza tu plan para agregar más.`,
        'Límite alcanzado'
      );
      return;
    }

    this.oauthLoading = true;

    this.apiService.initiateGoogleOAuth().subscribe({
      next: (response) => {
        // Open Google OAuth in a popup window
        const width = 600;
        const height = 700;
        const left = (window.innerWidth - width) / 2;
        const top = (window.innerHeight - height) / 2;

        const popup = window.open(
          response.auth_url,
          'Google OAuth',
          `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
        );

        if (!popup) {
          this.notificationService.error(
            'No se pudo abrir la ventana de autorización. Por favor habilita los popups para este sitio.',
            'Popup bloqueado'
          );
          this.oauthLoading = false;
        }
        // OAuth callback will be handled by handleOAuthMessage
      },
      error: (err) => {
        this.oauthLoading = false;
        const errorMsg = err?.error?.detail || 'No se pudo iniciar la autorización de Google';
        this.notificationService.error(errorMsg, 'Error OAuth');
      }
    });
  }

  handleGoogleOAuthCallback(data: any): void {
    this.oauthLoading = false;

    if (!data.success) {
      this.notificationService.error(data.message || 'Error en la autorización de Google', 'OAuth Error');
      return;
    }

    // Store OAuth data and show confirmation
    this.pendingOAuthData = data.data;

    // Auto-save the OAuth configuration
    this.saveOAuthConfig();
  }

  saveOAuthConfig(): void {
    if (!this.pendingOAuthData) {
      this.notificationService.error('No hay datos de OAuth pendientes', 'Error');
      return;
    }

    const oauthData = this.pendingOAuthData;

    this.apiService.saveOAuthEmailConfig({
      gmail_address: oauthData.gmail_address,
      access_token: oauthData.access_token,
      refresh_token: oauthData.refresh_token,
      token_expiry: oauthData.token_expiry,
      name: `Gmail - ${oauthData.gmail_address}`,
      search_terms: ['factura', 'invoice', 'comprobante', 'electronico']
    }).subscribe({
      next: (response) => {
        this.pendingOAuthData = null;
        this.showAddForm = false;
        this.selectedProvider = '';
        this.loadConfigs();
        this.notificationService.success(
          `Cuenta ${oauthData.gmail_address} conectada exitosamente con OAuth`,
          'Gmail Conectado'
        );
      },
      error: (err) => {
        const errorMsg = err?.error?.detail || 'No se pudo guardar la configuración OAuth';
        this.notificationService.error(errorMsg, 'Error al guardar');
      }
    });
  }

  refreshOAuthToken(config: EmailConfig): void {
    if (!config.id) return;

    this.apiService.refreshOAuthToken(config.id).subscribe({
      next: (response) => {
        this.notificationService.success('Token OAuth actualizado', 'Token Renovado');
        this.loadConfigs();
      },
      error: (err) => {
        this.notificationService.error('No se pudo renovar el token OAuth', 'Error');
      }
    });
  }

  isOAuthConfig(config: EmailConfig): boolean {
    return config.auth_type === 'oauth2';
  }

  isTokenExpired(config: EmailConfig): boolean {
    if (!config.token_expiry) return true;
    return new Date(config.token_expiry) <= new Date();
  }

  addSearchTerm(): void {
    this.newConfig.search_terms.push('');
  }

  removeSearchTerm(index: number): void {
    this.newConfig.search_terms.splice(index, 1);
  }

  applySearchPresetToNew(presetId: string): void {
    const preset = this.searchTermPresets.find((p) => p.id === presetId);
    if (!preset) return;
    this.newConfig.search_terms = this.mergeSearchTerms(this.newConfig.search_terms || [], preset.terms);
  }

  trackByIndex(index: number): number {
    return index;
  }

  testConfiguration(config: EmailConfig, index?: number): void {
    const testIndex = index !== undefined ? index : -1;
    this.testing[testIndex] = true;

    const isExisting = testIndex >= 0 && !!config?.id;
    const obs = isExisting
      ? this.apiService.testEmailConfigById(config.id!)
      : (() => {
        const temp = this.cloneConfig(config);
        temp.search_terms = (temp.search_terms || []).filter((t: string) => (t || '').trim() !== '');
        temp.search_synonyms = this.parseSynonymsByLine(this.newSynonymsText);
        temp.fallback_sender_match = !!temp.fallback_sender_match;
        temp.fallback_attachment_match = !!temp.fallback_attachment_match;
        return this.apiService.testEmailConfig(temp);
      })();

    obs.subscribe({
      next: (result: EmailTestResult) => {
        this.testResults[testIndex] = result;
        this.testing[testIndex] = false;
      },
      error: (err) => {
        this.testResults[testIndex] = {
          success: false,
          message: 'Error al conectar con el servidor',
          connection_test: false,
          login_test: false
        };
        this.testing[testIndex] = false;
      }
    });
  }

  onToggleEnabled(index: number, event: any): void {
    const cfg = this.emailConfigs[index];
    if (!cfg || !cfg.id) { return; }
    const enabled = !!event?.target?.checked;
    this.apiService.setEmailConfigEnabled(cfg.id, enabled).subscribe({
      next: (resp) => {
        this.emailConfigs[index].enabled = resp.enabled;
      },
      error: () => {
        // revert UI toggle on error
        this.emailConfigs[index].enabled = !enabled;
        this.notificationService.error('No se pudo actualizar el estado de la cuenta', 'Error');
      }
    });
  }

  addEmailConfig(processAfterSave: boolean = false): void {
    if (this.savingNew) {
      return;
    }

    // Validar límite de cuentas ANTES de intentar crear
    if (!this.canAddMore) {
      const limit = this.maxEmailAccounts === -1 ? 'ilimitadas' : this.maxEmailAccounts;
      this.notificationService.error(
        `Has alcanzado el límite de ${limit} cuentas de correo. Actualiza tu plan para agregar más.`,
        'Límite alcanzado'
      );
      return;
    }

    // Validación básica
    if (!this.newConfig.host || !this.newConfig.username || !this.newConfig.password) {
      this.notificationService.warning('Por favor completa todos los campos obligatorios', 'Validación');
      return;
    }

    const payload = this.cloneConfig(this.newConfig);
    payload.search_terms = (payload.search_terms || []).filter(term => (term || '').trim() !== '');
    payload.search_synonyms = this.parseSynonymsByLine(this.newSynonymsText);
    payload.fallback_sender_match = !!payload.fallback_sender_match;
    payload.fallback_attachment_match = !!payload.fallback_attachment_match;
    this.savingNew = true;

    // Guardar en backend
    this.apiService.createEmailConfig(payload).subscribe({
      next: () => {
        this.newConfig = this.createEmptyConfig();
        this.newSynonymsText = '';
        this.newAdvancedOpen = false;
        this.showAddForm = false;
        this.selectedProvider = '';
        this.loadConfigs();
        this.notificationService.success('Configuración de correo agregada exitosamente', 'Cuenta agregada');

        if (!processAfterSave) {
          this.savingNew = false;
          return;
        }

        this.notificationService.info('Procesando correos en este momento...', 'Procesamiento');
        this.apiService.processEmails(false).subscribe({
          next: (result: any) => {
            if (!result?.success) {
              this.notificationService.warning(
                result?.message || 'La cuenta se guardó, pero no se pudo iniciar el procesamiento',
                'Procesamiento'
              );
              this.savingNew = false;
              return;
            }

            const processedInvoices = result.invoice_count ?? result.invoices?.length ?? 0;
            if (processedInvoices > 0) {
              this.notificationService.success(
                `Se procesaron ${processedInvoices} factura(s)`,
                'Procesamiento Completado'
              );
            } else {
              this.notificationService.info(
                'Cuenta guardada. No se encontraron facturas nuevas.',
                'Sin Novedades'
              );
            }
            this.savingNew = false;
          },
          error: () => {
            this.notificationService.warning(
              'La cuenta se guardó, pero hubo un problema al iniciar el procesamiento',
              'Advertencia'
            );
            this.savingNew = false;
          }
        });
      },
      error: (err) => {
        const errorMsg = err?.error?.detail || 'No se pudo guardar la configuración';
        this.notificationService.error(errorMsg, 'Error al guardar');
        this.savingNew = false;
      }
    });
  }

  removeConfig(index: number): void {
    const cfg = this.emailConfigs[index];
    const cfgName = cfg?.username || cfg?.host || 'esta configuración';
    this.notificationService.warning(
      `¿Estás seguro de eliminar ${cfgName}?`,
      'Confirmar eliminación',
      {
        persistent: true,
        action: {
          label: 'Eliminar',
          handler: () => {
            // Si no hay id, es una fila nueva sin guardar
            if (!cfg || !cfg.id) {
              this.emailConfigs.splice(index, 1);
              return;
            }
            this.apiService.deleteEmailConfig(cfg.id).subscribe({
              next: () => {
                this.emailConfigs.splice(index, 1);
                delete this.testResults[index];
                delete this.testing[index];
                this.notificationService.success('Configuración eliminada correctamente', 'Eliminada');
              },
              error: () => {
                this.notificationService.error('No se pudo eliminar la configuración', 'Error al eliminar');
              }
            });
          }
        }
      }
    );
  }

  cancelAdd(): void {
    if (this.savingNew) {
      return;
    }
    this.newConfig = this.createEmptyConfig();
    this.newSynonymsText = '';
    this.newAdvancedOpen = false;
    this.savingNew = false;
    this.showAddForm = false;
    this.selectedProvider = '';
    this.pendingOAuthData = null;
  }

  getProvider(config: EmailConfig): string {
    const host = (config.host || '').toLowerCase();
    if (host.includes('gmail')) return 'Gmail';
    if (host.includes('outlook') || host.includes('hotmail') || host.includes('office365')) return 'Outlook';
    return 'Otro';
  }

  // ---------- Mejoras UI: filtro + edición inline ----------
  filterText: string = '';
  editing: { [id: string]: boolean } = {};
  editData: { [id: string]: EmailConfig } = {};
  saving: { [id: string]: boolean;[key: number]: boolean } = {} as any;

  keyFor(i: number, cfg: EmailConfig): string {
    return (cfg.id || `idx_${i}`);
  }

  matchesFilter(cfg: EmailConfig): boolean {
    const q = (this.filterText || '').trim().toLowerCase();
    if (!q) return true;
    return (
      (cfg.username || '').toLowerCase().includes(q) ||
      (cfg.host || '').toLowerCase().includes(q) ||
      (this.getProvider(cfg) || '').toLowerCase().includes(q)
    );
  }

  private cloneConfig(cfg: EmailConfig): EmailConfig {
    return JSON.parse(JSON.stringify(cfg));
  }

  private parseSynonymsText(raw: string): string[] {
    return (raw || '')
      .split(/[\n,;]+/)
      .map((v: string) => (v || '').trim())
      .filter((v: string) => !!v);
  }

  private parseSynonymsByLine(raw: string): { [key: string]: string[] } {
    const result: { [key: string]: string[] } = {};
    const lines = (raw || '')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => !!line);

    lines.forEach((line) => {
      const parts = line.split(':');
      if (parts.length < 2) return;

      const base = (parts.shift() || '').trim();
      const variants = this.parseSynonymsText(parts.join(':'));
      if (!base || !variants.length) return;

      const uniqueVariants: string[] = [];
      const seen = new Set<string>();
      variants.forEach((variant) => {
        const key = variant.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        uniqueVariants.push(variant);
      });

      if (uniqueVariants.length) {
        result[base] = uniqueVariants;
      }
    });

    return result;
  }

  private synonymsToText(value: EmailConfig['search_synonyms']): string {
    if (!value || Array.isArray(value)) return '';

    const lines = Object.keys(value)
      .map((base) => {
        const cleanBase = (base || '').trim();
        const variants = ((value as { [key: string]: string[] })[base] || [])
          .map((variant) => (variant || '').trim())
          .filter((variant) => !!variant);
        if (!cleanBase || !variants.length) return '';
        return `${cleanBase}: ${variants.join(', ')}`;
      })
      .filter((line) => !!line);

    return lines.join('\n');
  }

  getSynonymSummary(config: EmailConfig): string {
    if (!config.search_synonyms || Array.isArray(config.search_synonyms)) {
      return 'Sin grupos configurados';
    }
    const groups = Object.keys(config.search_synonyms)
      .filter((base) => !!(base || '').trim());
    if (!groups.length) return 'Sin grupos configurados';
    return `${groups.length} grupo(s)`;
  }

  editSynonymsText: { [key: string]: string } = {};
  editAdvancedOpen: { [key: string]: boolean } = {};

  startEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const key = this.keyFor(i, cfg);
    this.editing[key] = true;
    const copy = this.cloneConfig(cfg);
    copy.password = '';
    copy.search_synonyms = copy.search_synonyms || {};
    copy.fallback_sender_match = !!copy.fallback_sender_match;
    copy.fallback_attachment_match = !!copy.fallback_attachment_match;
    this.editData[key] = copy;
    this.editSynonymsText[key] = this.synonymsToText(copy.search_synonyms);
    this.editAdvancedOpen[key] = !!this.editSynonymsText[key];
    delete this.testResults[key];
    delete this.testing[key];
  }

  cancelEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const key = this.keyFor(i, cfg);
    delete this.editing[key];
    delete this.editData[key];
    delete this.editSynonymsText[key];
    delete this.editAdvancedOpen[key];
    delete this.testing[key];
    delete this.testResults[key];
  }

  saveEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const id = cfg.id;
    const key = this.keyFor(i, cfg);
    const editedData = this.editData[key];
    const normalizedSynonyms = this.parseSynonymsByLine(this.editSynonymsText[key] || '');

    this.saving[key] = true;

    if (this.isOAuthConfig(cfg)) {
      // OAuth2: usar PATCH para actualización parcial sin tocar credenciales
      const partialPayload = {
        search_terms: (editedData.search_terms || []).filter((t: string) => (t || '').trim() !== ''),
        search_synonyms: normalizedSynonyms,
        fallback_sender_match: !!editedData.fallback_sender_match,
        fallback_attachment_match: !!editedData.fallback_attachment_match
      };

      this.apiService.patchEmailConfig(id, partialPayload).subscribe({
        next: () => {
          this.emailConfigs[i] = { ...cfg, ...partialPayload };
          this.saving[key] = false;
          this.cancelEdit(i);
        },
        error: (err) => {
          this.saving[key] = false;
          this.testResults[key] = { success: false, message: 'No se pudo guardar', connection_test: false, login_test: false };
        }
      });
    } else {
      // Password auth: usar PUT con payload completo
      const payload = this.cloneConfig(editedData);
      payload.search_terms = (payload.search_terms || []).filter((t: string) => (t || '').trim() !== '');
      payload.search_synonyms = normalizedSynonyms;
      payload.fallback_sender_match = !!payload.fallback_sender_match;
      payload.fallback_attachment_match = !!payload.fallback_attachment_match;
      if (!payload.password) delete (payload as any).password;

      this.apiService.updateEmailConfig(id, payload as EmailConfig).subscribe({
        next: () => {
          this.emailConfigs[i] = { ...cfg, ...payload };
          this.saving[key] = false;
          this.cancelEdit(i);
        },
        error: (err) => {
          this.saving[key] = false;
          this.testResults[key] = { success: false, message: 'No se pudo guardar', connection_test: false, login_test: false };
        }
      });
    }
  }

  addEditSearchTerm(key: string): void {
    if (!this.editData[key].search_terms) this.editData[key].search_terms = [] as any;
    this.editData[key].search_terms.push('');
  }

  removeEditSearchTerm(key: string, idx: number): void {
    this.editData[key].search_terms.splice(idx, 1);
  }

  applySearchPresetToEdit(key: string, presetId: string): void {
    if (!this.editData[key]) return;
    const preset = this.searchTermPresets.find((p) => p.id === presetId);
    if (!preset) return;
    this.editData[key].search_terms = this.mergeSearchTerms(this.editData[key].search_terms || [], preset.terms);
  }

  testEditedConfiguration(key: string): void {
    const cfg = this.editData[key];
    if (!cfg) return;
    this.testing[key] = true;
    cfg.search_terms = (cfg.search_terms || []).filter(t => (t || '').trim() !== '');
    cfg.search_synonyms = this.parseSynonymsByLine(this.editSynonymsText[key] || '');
    cfg.fallback_sender_match = !!cfg.fallback_sender_match;
    cfg.fallback_attachment_match = !!cfg.fallback_attachment_match;
    this.apiService.testEmailConfig(cfg).subscribe({
      next: (res) => { this.testResults[key] = res; this.testing[key] = false; },
      error: (err) => {
        this.testResults[key] = { success: false, message: 'Error al conectar', connection_test: false, login_test: false };
        this.testing[key] = false;
      }
    });
  }

  private mergeSearchTerms(existing: string[], additions: string[]): string[] {
    const normalized = (existing || [])
      .map((t) => (t || '').trim())
      .filter((t) => !!t);

    const seen = new Set(normalized.map((t) => t.toLowerCase()));
    (additions || []).forEach((term) => {
      const clean = (term || '').trim();
      if (!clean) return;
      const key = clean.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      normalized.push(clean);
    });

    return normalized;
  }
}
