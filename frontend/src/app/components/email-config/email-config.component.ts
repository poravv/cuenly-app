import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { EmailConfig, EmailTestResult } from '../../models/invoice.model';

@Component({
  selector: 'app-email-config',
  templateUrl: './email-config.component.html',
  styleUrls: ['./email-config.component.scss']
})
export class EmailConfigComponent implements OnInit {
  emailConfigs: EmailConfig[] = [];
  newConfig: EmailConfig = this.createEmptyConfig();
  showAddForm = false;
  testResults: { [key: string]: EmailTestResult; [key: number]: EmailTestResult } = {} as any;
  testing: { [key: string]: boolean; [key: number]: boolean } = {} as any;
  loading = false;
  error: string | null = null;
  
  // Configuraciones predefinidas para proveedores comunes
  providers = [
    {
      name: 'Gmail',
      host: 'imap.gmail.com',
      port: 993,
      use_ssl: true
    },
    {
      name: 'Outlook/Hotmail',
      host: 'imap-mail.outlook.com', 
      port: 993,
      use_ssl: true
    },
    {
      name: 'Yahoo',
      host: 'imap.mail.yahoo.com',
      port: 993,
      use_ssl: true
    },
    {
      name: 'Personalizado',
      host: '',
      port: 993,
      use_ssl: true
    }
  ];

  constructor(
    private apiService: ApiService,
    private notificationService: NotificationService
  ) { }

  ngOnInit(): void {
    // Cargar configuraciones desde el backend
    this.loadConfigs();
  }

  loadConfigs(): void {
    this.loading = true; this.error = null;
    this.apiService.getEmailConfigs().subscribe({
      next: (resp) => {
        this.emailConfigs = resp.configs || [];
        this.loading = false;
      },
      error: (err) => {
        console.error('Error cargando configs', err);
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
      search_terms: ['factura', 'invoice', 'comprobante'],
      search_criteria: 'UNSEEN',
      provider: 'other',
      enabled: true
    };
  }

  selectProvider(provider: any): void {
    this.newConfig.host = provider.host;
    this.newConfig.port = provider.port;
    this.newConfig.use_ssl = provider.use_ssl;
  }

  addSearchTerm(): void {
    this.newConfig.search_terms.push('');
  }

  removeSearchTerm(index: number): void {
    this.newConfig.search_terms.splice(index, 1);
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
      : this.apiService.testEmailConfig(config);

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
        console.error(err);
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
        alert('No se pudo actualizar el estado de la cuenta');
      }
    });
  }

  addEmailConfig(): void {
    // Validación básica
    if (!this.newConfig.host || !this.newConfig.username || !this.newConfig.password) {
      alert('Por favor completa todos los campos obligatorios');
      return;
    }

    // Filtrar términos de búsqueda vacíos
    this.newConfig.search_terms = this.newConfig.search_terms.filter(term => term.trim() !== '');

    // Guardar en backend
    this.apiService.createEmailConfig(this.newConfig).subscribe({
      next: () => {
        this.newConfig = this.createEmptyConfig();
        this.showAddForm = false;
        this.loadConfigs();
        alert('Configuración de correo agregada exitosamente');
      },
      error: () => {
        alert('No se pudo guardar la configuración');
      }
    });
  }

  removeConfig(index: number): void {
    if (!confirm('¿Estás seguro de que quieres eliminar esta configuración?')) return;
    const cfg = this.emailConfigs[index];
    if (!cfg || !cfg.id) {
      this.emailConfigs.splice(index, 1);
      return;
    }
    this.apiService.deleteEmailConfig(cfg.id).subscribe({
      next: () => {
        this.emailConfigs.splice(index, 1);
        delete this.testResults[index];
        delete this.testing[index];
      },
      error: () => {
        alert('No se pudo eliminar la configuración');
      }
    });
  }

  cancelAdd(): void {
    this.newConfig = this.createEmptyConfig();
    this.showAddForm = false;
  }

  getProvider(config: EmailConfig): string {
    const host = (config.host || '').toLowerCase();
    if (host.includes('gmail')) return 'Gmail';
    if (host.includes('outlook') || host.includes('hotmail') || host.includes('office365')) return 'Outlook';
    if (host.includes('yahoo')) return 'Yahoo';
    return 'Otro';
  }

  // ---------- Mejoras UI: filtro + edición inline ----------
  filterText: string = '';
  editing: { [id: string]: boolean } = {};
  editData: { [id: string]: EmailConfig } = {};
  saving: { [id: string]: boolean; [key: number]: boolean } = {} as any;

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

  startEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const key = this.keyFor(i, cfg);
    this.editing[key] = true;
    const copy = this.cloneConfig(cfg);
    copy.password = '';
    this.editData[key] = copy;
    delete this.testResults[key];
    delete this.testing[key];
  }

  cancelEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const key = this.keyFor(i, cfg);
    delete this.editing[key];
    delete this.editData[key];
    delete this.testing[key];
    delete this.testResults[key];
  }

  saveEdit(i: number): void {
    const cfg = this.emailConfigs[i];
    if (!cfg || !cfg.id) return;
    const id = cfg.id;
    const key = this.keyFor(i, cfg);
    const payload = this.cloneConfig(this.editData[key]);
    if (!payload.password) delete (payload as any).password;
    this.saving[key] = true;
    this.apiService.updateEmailConfig(id, payload).subscribe({
      next: () => {
        const updated = { ...cfg, ...payload } as EmailConfig;
        this.emailConfigs[i] = updated;
        this.saving[key] = false;
        this.cancelEdit(i);
      },
      error: (err) => {
        console.error('Error guardando configuración', err);
        this.saving[key] = false;
        this.testResults[key] = { success: false, message: 'No se pudo guardar', connection_test: false, login_test: false };
      }
    });
  }

  addEditSearchTerm(key: string): void {
    if (!this.editData[key].search_terms) this.editData[key].search_terms = [] as any;
    this.editData[key].search_terms.push('');
  }

  removeEditSearchTerm(key: string, idx: number): void {
    this.editData[key].search_terms.splice(idx, 1);
  }

  testEditedConfiguration(key: string): void {
    const cfg = this.editData[key];
    if (!cfg) return;
    this.testing[key] = true;
    cfg.search_terms = (cfg.search_terms || []).filter(t => (t || '').trim() !== '');
    this.apiService.testEmailConfig(cfg).subscribe({
      next: (res) => { this.testResults[key] = res; this.testing[key] = false; },
      error: (err) => {
        console.error('Test edición falló', err);
        this.testResults[key] = { success: false, message: 'Error al conectar', connection_test: false, login_test: false };
        this.testing[key] = false;
      }
    });
  }
}
