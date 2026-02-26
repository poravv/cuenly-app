import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { ApiService } from '../../services/api.service';
import {
  ProcessResult,
  SystemStatus,
  JobStatus,
  TaskSubmitResponse,
  TaskStatusResponse,
  EmailConfig,
  EmailTestResult,
} from '../../models/invoice.model';
import { interval, Subscription, startWith, switchMap } from 'rxjs';
import { ObservabilityService } from '../../services/observability.service';

@Component({
  selector: 'app-invoice-processing',
  templateUrl: './invoice-processing.component.html',
  styleUrls: ['./invoice-processing.component.scss']
})
export class InvoiceProcessingComponent implements OnInit, OnDestroy {
  status: SystemStatus | null = null;
  jobStatus: JobStatus | null = null;
  loading = false;
  jobLoading = false;
  processingResult: ProcessResult | null = null;
  processingJobId: string | null = null;
  processingPolling: Subscription | null = null;
  error: string | null = null;
  jobError: string | null = null;

  // Para actualización automática
  autoRefresh: boolean = false;
  refreshSubscription: Subscription | null = null;
  autoRefreshIntervalMs: number = 30000;
  intervalOptions: number[] = [5, 10, 15, 20];
  jobIntervalInput: number | null = null;
  jobIntervalTouched = false;

  // Para procesamiento por rango de fechas
  dateRangeStart: string = '';
  dateRangeEnd: string = '';
  dateRangeLoading = false;
  dateRangeCancelLoading = false;
  dateRangeCancelRequested = false;
  dateRangeResult: any = null;
  dateRangeNotice: string | null = null;
  dateRangeError: string | null = null;
  dateRangeJobId: string | null = null;
  dateRangeTaskStatus: TaskStatusResponse | null = null;
  dateRangePolling: Subscription | null = null;

  // Setup rápido en la misma pantalla (Fase 5 UX)
  showQuickSetup = false;
  quickSetupDismissed = false;
  quickSaving = false;
  quickTesting = false;
  quickError: string | null = null;
  quickTestResult: EmailTestResult | null = null;
  quickAdvancedOpen = false;
  quickSynonymsText = '';
  quickConfig: EmailConfig = this.createQuickConfig();
  quickProviders = [
    { id: 'gmail', label: 'Gmail', host: 'imap.gmail.com', port: 993, use_ssl: true },
    { id: 'outlook', label: 'Outlook/Hotmail', host: 'imap-mail.outlook.com', port: 993, use_ssl: true },
    { id: 'custom', label: 'Personalizado', host: '', port: 993, use_ssl: true },
  ];

  private storageHandler: any;
  private savePrefTimer: any = null;

  constructor(
    private apiService: ApiService,
    private cdr: ChangeDetectorRef,
    private observability: ObservabilityService
  ) {
    const saved = localStorage.getItem('cuenlyapp:autoRefresh');
    this.autoRefresh = (saved === 'true' || saved === 'True' || saved === '1');
    const savedInt = localStorage.getItem('cuenlyapp:autoRefreshInterval');
    if (savedInt) {
      const val = parseInt(savedInt, 10);
      if (!isNaN(val) && val >= 5000) this.autoRefreshIntervalMs = val;
    }

    // Cargar rango de fechas y resultado guardado
    const savedStartDate = localStorage.getItem('cuenlyapp:dateRangeStart');
    const savedEndDate = localStorage.getItem('cuenlyapp:dateRangeEnd');
    if (savedStartDate) this.dateRangeStart = savedStartDate;
    if (savedEndDate) this.dateRangeEnd = savedEndDate;

    const savedResult = localStorage.getItem('cuenlyapp:dateRangeResult');
    if (savedResult) {
      try {
        this.dateRangeResult = JSON.parse(savedResult);
        if (this.dateRangeResult?.job_id) {
          this.dateRangeJobId = this.dateRangeResult.job_id;
        }
      } catch (e) {
        localStorage.removeItem('cuenlyapp:dateRangeResult');
      }
    }

    this.jobIntervalInput = this.intervalOptions[0];
  }

  ngOnInit(): void {
    this.getSystemStatus();
    this.getJobStatus();

    this.apiService.getAutoRefreshPref().subscribe({
      next: (pref) => {
        const backendEnabled = !!pref.enabled;
        const backendInterval = Math.max(5000, Number(pref.interval_ms) || this.autoRefreshIntervalMs);
        let changed = false;
        if (backendInterval !== this.autoRefreshIntervalMs) {
          this.autoRefreshIntervalMs = backendInterval;
          localStorage.setItem('cuenlyapp:autoRefreshInterval', String(this.autoRefreshIntervalMs));
          changed = true;
        }
        if (backendEnabled !== this.autoRefresh) {
          if (backendEnabled) { this.startAutoRefresh(); } else { this.stopAutoRefresh(); }
          changed = true;
        }
        if (changed) this.cdr.detectChanges();
      },
      error: () => { /* si falla, seguimos con localStorage */ }
    });

    if (this.autoRefresh) {
      this.startAutoRefresh();
    }

    if (this.dateRangeJobId) {
      this.startDateRangeTaskPolling(this.dateRangeJobId, true);
    }

    this.storageHandler = (e: StorageEvent) => {
      if (!e) { return; }
      if (e.key === 'cuenlyapp:autoRefresh' && e.newValue !== null) {
        const enabled = (e.newValue === 'true' || e.newValue === 'True' || e.newValue === '1');
        if (enabled && !this.autoRefresh) {
          this.startAutoRefresh();
          this.cdr.detectChanges();
        } else if (!enabled && this.autoRefresh) {
          this.stopAutoRefresh();
          this.cdr.detectChanges();
        }
      }
      if (e.key === 'cuenlyapp:autoRefreshInterval' && e.newValue !== null) {
        const val = parseInt(e.newValue, 10);
        if (!isNaN(val) && val >= 5000) {
          this.autoRefreshIntervalMs = val;
          if (this.autoRefresh) {
            this.startAutoRefresh();
          }
          this.cdr.detectChanges();
        }
      }
    };
    window.addEventListener('storage', this.storageHandler);
  }

  ngOnDestroy(): void {
    this.stopAutoRefresh();
    if (this.processingPolling) {
      this.processingPolling.unsubscribe();
      this.processingPolling = null;
    }
    this.clearDateRangePolling();
    if (this.storageHandler) {
      window.removeEventListener('storage', this.storageHandler);
      this.storageHandler = null;
    }
  }

  get hasConfiguredEmail(): boolean {
    return !!this.status?.email_configured;
  }

  get isDateRangeTaskActive(): boolean {
    const status = String(this.dateRangeTaskStatus?.status || '').toLowerCase();
    return status === 'queued' || status === 'running' || status === 'started';
  }

  get isProcessingBlocked(): boolean {
    return !!this.jobStatus?.is_processing || this.isDateRangeTaskActive;
  }

  getSystemStatus(): void {
    this.loading = true;
    this.apiService.getStatus().subscribe({
      next: (data) => {
        this.status = data;
        const hasAccounts = (data.email_configs_count || 0) > 0;
        if (!hasAccounts && !this.quickSetupDismissed) {
          this.showQuickSetup = true;
        }
        if (hasAccounts) {
          this.showQuickSetup = false;
        }
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.error = 'Error al obtener el estado del sistema';
        this.observability.error('Error loading system status', err, 'InvoiceProcessingComponent', {
          endpoint: '/status',
          action: 'loadSystemStatus'
        });
      }
    });
  }

  getJobStatus(): void {
    this.jobLoading = true;
    this.apiService.getJobStatus().subscribe({
      next: (data) => {
        this.jobStatus = {
          ...data,
          interval_minutes: this.getValidInterval(data?.interval_minutes)
        };
        this.jobLoading = false;
        if (!this.jobIntervalTouched) {
          this.jobIntervalInput = this.getValidInterval(this.jobStatus?.interval_minutes ?? this.jobIntervalInput);
        }
      },
      error: (err) => {
        this.jobLoading = false;
        this.jobError = 'Error al obtener el estado del trabajo';
        this.observability.error('Error loading job status', err, 'InvoiceProcessingComponent', {
          endpoint: '/job/status',
          action: 'loadJobStatus'
        });
      }
    });
  }

  processEmails(async: boolean = true): void {
    if (!this.hasConfiguredEmail) {
      this.error = 'Configura al menos una cuenta de correo para procesar.';
      return;
    }

    this.loading = true;
    this.processingResult = null;
    this.error = null;
    this.processingJobId = null;
    this.clearProcessingPolling();

    // Log user action
    this.observability.logUserAction('process_emails_started', 'InvoiceProcessingComponent', {
      async_mode: async
    });

    // Asíncrono real: encolar job y poll de estado
    this.apiService.submitTask().subscribe({
      next: (task) => {
        if (!task?.job_id) {
          this.error = 'No se recibió un identificador de tarea válido.';
          this.loading = false;
          return;
        }
        this.processingJobId = task.job_id;
        this.startProcessingTaskPolling(task.job_id);
      },
      error: (err) => {
        this.error = err.error?.detail || err.error?.message || 'No se pudo encolar el procesamiento';
        this.loading = false;
        this.processingJobId = null;
        this.observability.error('Error processing emails', err, 'InvoiceProcessingComponent', {
          action: 'enqueueProcessEmails',
          endpoint: '/tasks/process'
        });
      }
    });
  }

  private startProcessingTaskPolling(jobId: string): void {
    this.clearProcessingPolling();

    this.processingPolling = interval(2000).pipe(
      startWith(0),
      switchMap(() => this.apiService.getTaskStatus(jobId))
    ).subscribe({
      next: (job: TaskStatusResponse | any) => {
        const status = String(job?.status || '').toLowerCase();
        const hasResult = job?.result !== undefined && job?.result !== null;
        const hasFinished = !!job?.finished_at;
        const looksFinished = hasResult || hasFinished;
        if ((status === 'queued' || status === 'running' || status === 'started') && !looksFinished) {
          return;
        }

        if (status === 'done' || status === 'finished' || looksFinished) {
          const normalizedResult = this.normalizeTaskProcessResult(job?.result, job?.message);
          if (!normalizedResult.success && normalizedResult.message?.includes('TRIAL_EXPIRED')) {
            this.showTrialExpiredError(normalizedResult.message.replace('TRIAL_EXPIRED: ', ''));
            this.processingResult = null;
          } else {
            this.processingResult = normalizedResult;
          }

          this.loading = false;
          this.processingJobId = null;
          this.clearProcessingPolling();

          setTimeout(() => {
            this.getSystemStatus();
            this.getJobStatus();
          }, 1000);
          return;
        }

        // failed / error / fallback
        this.error = job?.message || job?.error || 'Error al procesar correos';
        this.loading = false;
        this.processingJobId = null;
        this.clearProcessingPolling();
        this.getJobStatus();
      },
      error: (err) => {
        this.error = err?.error?.detail || err?.error?.message || 'No se pudo consultar el estado de la tarea';
        this.loading = false;
        this.processingJobId = null;
        this.clearProcessingPolling();
        this.observability.error('Error polling processing task', err, 'InvoiceProcessingComponent', {
          action: 'pollProcessTask',
          endpoint: `/tasks/${jobId}`
        });
      }
    });
  }

  private normalizeTaskProcessResult(rawResult: any, fallbackMessage?: string): ProcessResult {
    const resultObj = rawResult && typeof rawResult === 'object' ? rawResult : {};
    const success = !!resultObj.success;
    const message = resultObj.message || fallbackMessage || (success ? 'Proceso completado' : 'Proceso finalizado con error');
    const invoiceCount = Number(resultObj.invoice_count || 0);
    const invoices = Array.isArray(resultObj.invoices) ? resultObj.invoices : [];

    return {
      success,
      message,
      invoice_count: invoiceCount,
      invoices
    };
  }

  private clearProcessingPolling(): void {
    if (this.processingPolling) {
      this.processingPolling.unsubscribe();
      this.processingPolling = null;
    }
  }

  createQuickConfig(): EmailConfig {
    return {
      name: 'Cuenta principal',
      host: '',
      port: 993,
      username: '',
      password: '',
      use_ssl: true,
      search_terms: ['factura', 'invoice', 'comprobante', 'electronico'],
      search_criteria: 'UNSEEN',
      provider: 'other',
      enabled: true,
      auth_type: 'password',
      search_synonyms: {},
      fallback_sender_match: true,
      fallback_attachment_match: true,
    };
  }

  openQuickSetup(): void {
    this.showQuickSetup = true;
    this.quickSetupDismissed = false;
    this.quickError = null;
  }

  dismissQuickSetup(): void {
    this.showQuickSetup = false;
    this.quickSetupDismissed = true;
  }

  selectQuickProvider(providerId: string): void {
    const selected = this.quickProviders.find((p) => p.id === providerId);
    if (!selected) return;

    if (providerId === 'custom') {
      this.quickConfig.provider = 'other';
      this.quickConfig.host = '';
      this.quickConfig.port = 993;
      this.quickConfig.use_ssl = true;
      return;
    }

    this.quickConfig.provider = providerId;
    this.quickConfig.host = selected.host;
    this.quickConfig.port = selected.port;
    this.quickConfig.use_ssl = selected.use_ssl;
  }

  private parseQuickSearchTerms(rawTerms: string[]): string[] {
    return (rawTerms || [])
      .map((term) => (term || '').trim())
      .filter((term) => !!term);
  }

  private parseQuickSynonyms(text: string): { [key: string]: string[] } {
    const result: { [key: string]: string[] } = {};
    const lines = (text || '').split('\n').map((line) => line.trim()).filter((line) => !!line);

    lines.forEach((line) => {
      const parts = line.split(':');
      if (parts.length < 2) return;
      const base = (parts[0] || '').trim();
      const synonymsRaw = parts.slice(1).join(':');
      const synonyms = synonymsRaw
        .split(',')
        .map((v) => (v || '').trim())
        .filter((v) => !!v);
      if (!base || !synonyms.length) return;
      result[base] = Array.from(new Set(synonyms));
    });

    return result;
  }

  private buildQuickPayload(): EmailConfig {
    const payload: EmailConfig = {
      ...this.quickConfig,
      search_terms: this.parseQuickSearchTerms(this.quickConfig.search_terms || []),
      search_synonyms: this.parseQuickSynonyms(this.quickSynonymsText),
      fallback_sender_match: !!this.quickConfig.fallback_sender_match,
      fallback_attachment_match: !!this.quickConfig.fallback_attachment_match,
      search_criteria: 'UNSEEN',
      enabled: true,
      auth_type: 'password',
      provider: this.quickConfig.provider || 'other',
    };
    return payload;
  }

  testQuickSetup(): void {
    this.quickError = null;
    this.quickTestResult = null;

    const payload = this.buildQuickPayload();
    if (!payload.host || !payload.username || !payload.password) {
      this.quickError = 'Completa host, usuario y contraseña para probar la conexión.';
      return;
    }

    this.quickTesting = true;
    this.apiService.testEmailConfig(payload).subscribe({
      next: (result) => {
        this.quickTestResult = result;
        this.quickTesting = false;
      },
      error: (err) => {
        this.quickTesting = false;
        this.quickTestResult = {
          success: false,
          message: err?.error?.detail || 'No se pudo probar la conexión',
          connection_test: false,
          login_test: false,
        };
      }
    });
  }

  saveQuickSetup(processNow: boolean): void {
    this.quickError = null;
    this.quickTestResult = null;

    const payload = this.buildQuickPayload();
    if (!payload.host || !payload.username || !payload.password) {
      this.quickError = 'Completa host, usuario y contraseña para guardar.';
      return;
    }

    if (!payload.search_terms || !payload.search_terms.length) {
      this.quickError = 'Agrega al menos un término de búsqueda.';
      return;
    }

    this.quickSaving = true;
    this.apiService.createEmailConfig(payload).subscribe({
      next: () => {
        this.quickSaving = false;
        this.quickConfig = this.createQuickConfig();
        this.quickSynonymsText = '';
        this.quickAdvancedOpen = false;
        this.showQuickSetup = false;
        this.quickSetupDismissed = false;
        this.getSystemStatus();
        this.getJobStatus();

        if (processNow) {
          setTimeout(() => this.processEmails(true), 250);
        }
      },
      error: (err) => {
        this.quickSaving = false;
        this.quickError = err?.error?.detail || 'No se pudo guardar la configuración rápida';
      }
    });
  }

  addQuickSearchTerm(): void {
    if (!this.quickConfig.search_terms) this.quickConfig.search_terms = [];
    this.quickConfig.search_terms.push('');
  }

  removeQuickSearchTerm(index: number): void {
    if (!this.quickConfig.search_terms || this.quickConfig.search_terms.length <= 1) return;
    this.quickConfig.search_terms.splice(index, 1);
  }

  // Mostrar notificación elegante para trial expirado
  private showTrialExpiredError(message: string): void {
    this.error = `🚫 ${message}`;

    // Auto-limpiar el error después de 10 segundos
    setTimeout(() => {
      if (this.error?.includes('🚫')) {
        this.error = null;
      }
    }, 10000);
  }

  startJob(): void {
    if (this.loading) {
      this.jobError = 'Espera a que termine el procesamiento manual actual antes de activar la automatización.';
      return;
    }

    if (!this.hasConfiguredEmail) {
      this.jobError = 'Configura al menos una cuenta de correo para activar la automatización.';
      return;
    }

    this.jobLoading = true;

    // Verificar trial antes de iniciar automatización
    this.apiService.getTrialStatus().subscribe({
      next: (trialStatus) => {
        if (!trialStatus.can_process) {
          this.jobError = trialStatus.message;
          this.jobLoading = false;
          return;
        }

        // Trial válido, proceder con el inicio del job
        const targetInterval = (this.jobIntervalInput && this.jobIntervalInput >= 1)
          ? this.getValidInterval(this.jobIntervalInput!)
          : this.getValidInterval(this.jobStatus?.interval_minutes || this.intervalOptions[0]);

        this.apiService.setJobInterval(targetInterval).subscribe({
          next: () => {
            this.apiService.startJob().subscribe({
              next: (result) => {
                this.jobStatus = result;
                this.jobLoading = false;
                this.jobIntervalTouched = false;
                this.jobIntervalInput = this.getValidInterval(this.jobStatus?.interval_minutes ?? targetInterval);

                // Log job started
                this.observability.logUserAction('scheduled_job_started', 'InvoiceProcessingComponent', {
                  interval_minutes: targetInterval
                });

                this.startAutoRefresh();
                setTimeout(() => this.getJobStatus(), 300);
              },
              error: (err) => {
                this.jobError = 'Error al iniciar el job programado';
                this.jobLoading = false;
                this.observability.error('Error starting scheduled job', err, 'InvoiceProcessingComponent', {
                  action: 'startJob'
                });
              }
            });
          },
          error: (err) => {
            this.jobError = 'No se pudo actualizar el intervalo';
            this.jobLoading = false;
            this.observability.error('Error updating job interval in start process', err, 'InvoiceProcessingComponent', {
              action: 'startJobUpdateInterval'
            });
          }
        });
      },
      error: (err) => {
        this.jobError = 'Error al verificar estado del trial';
        this.jobLoading = false;
        this.observability.error('Error checking trial status', err, 'InvoiceProcessingComponent', {
          action: 'startJobTrialCheck'
        });
      }
    });
  }

  stopJob(): void {
    if (this.loading) {
      this.jobError = 'Espera a que termine el procesamiento manual actual antes de cambiar el estado de automatización.';
      return;
    }

    this.jobLoading = true;

    this.apiService.stopJob().subscribe({
      next: (result) => {
        this.jobStatus = result;
        this.jobLoading = false;

        // Log job stopped
        this.observability.logUserAction('scheduled_job_stopped', 'InvoiceProcessingComponent');

        this.stopAutoRefresh();
      },
      error: (err) => {
        this.jobError = 'Error al detener el job programado';
        this.jobLoading = false;
        this.observability.error('Error stopping scheduled job', err, 'InvoiceProcessingComponent', {
          action: 'stopJob'
        });
      }
    });
  }

  private unsubscribeRefresh(): void {
    if (this.refreshSubscription) {
      this.refreshSubscription.unsubscribe();
      this.refreshSubscription = null;
    }
  }

  startAutoRefresh(): void {
    this.autoRefresh = true;
    this.unsubscribeRefresh();
    this.refreshSubscription = interval(this.autoRefreshIntervalMs).subscribe(() => {
      this.getSystemStatus();
      this.getJobStatus();
    });
    localStorage.setItem('cuenlyapp:autoRefresh', 'true');
    localStorage.setItem('cuenlyapp:autoRefreshInterval', String(this.autoRefreshIntervalMs));
  }

  stopAutoRefresh(): void {
    this.autoRefresh = false;
    this.unsubscribeRefresh();
    localStorage.setItem('cuenlyapp:autoRefresh', 'false');
  }

  setAutoRefreshInterval(ms: number): void {
    this.autoRefreshIntervalMs = Math.max(5000, Number(ms) || 30000);
    localStorage.setItem('cuenlyapp:autoRefreshInterval', String(this.autoRefreshIntervalMs));
    if (this.autoRefresh) {
      this.startAutoRefresh();
    }
    this.scheduleSavePref();
  }

  applyJobInterval(): void {
    if (this.loading) {
      this.jobError = 'No puedes cambiar el intervalo mientras hay un procesamiento manual en curso.';
      return;
    }

    const target = this.getValidInterval(this.jobIntervalInput);
    this.jobIntervalInput = target;
    this.jobLoading = true;
    this.apiService.setJobInterval(target).subscribe({
      next: (st) => { this.jobStatus = st; this.jobLoading = false; },
      error: (err) => {
        this.jobError = 'No se pudo actualizar el intervalo';
        this.jobLoading = false;
        this.observability.error('Error updating job interval', err, 'InvoiceProcessingComponent', {
          action: 'updateJobInterval'
        });
      }
    });
  }

  // Procesar correos en un rango de fechas específico
  processDateRange(): void {
    if (!this.hasConfiguredEmail) {
      this.dateRangeError = 'Configura al menos una cuenta de correo para procesar por rango.';
      return;
    }

    if (!this.dateRangeStart || !this.dateRangeEnd) {
      this.dateRangeError = 'Por favor selecciona ambas fechas';
      return;
    }

    if (this.dateRangeStart > this.dateRangeEnd) {
      this.dateRangeError = 'La fecha de inicio debe ser anterior a la fecha fin';
      return;
    }

    this.dateRangeLoading = true;
    this.dateRangeCancelLoading = false;
    this.dateRangeCancelRequested = false;
    this.dateRangeResult = null;
    this.dateRangeNotice = null;
    this.dateRangeError = null;
    this.dateRangeTaskStatus = null;
    this.clearDateRangePolling();

    this.observability.logUserAction('process_date_range_started', 'InvoiceProcessingComponent', {
      start_date: this.dateRangeStart,
      end_date: this.dateRangeEnd
    });

    this.apiService.processDateRange(this.dateRangeStart, this.dateRangeEnd).subscribe({
      next: (result) => {
        this.dateRangeResult = result;
        this.dateRangeLoading = false;
        this.dateRangeCancelLoading = false;
        this.dateRangeCancelRequested = false;
        this.dateRangeNotice = null;

        // Persistir resultado
        if (result && result.job_id) {
          this.dateRangeJobId = result.job_id;
          localStorage.setItem('cuenlyapp:dateRangeResult', JSON.stringify(result));
          this.startDateRangeTaskPolling(result.job_id);
        }
      },
      error: (err) => {
        this.dateRangeError = err.error?.detail || err.error?.message || 'Error al procesar rango de fechas';
        this.dateRangeNotice = null;
        this.dateRangeLoading = false;
        this.dateRangeCancelLoading = false;
        this.dateRangeCancelRequested = false;
        this.observability.error('Error processing date range', err, 'InvoiceProcessingComponent', {
          action: 'processDateRange',
          start_date: this.dateRangeStart,
          end_date: this.dateRangeEnd
        });
      }
    });
  }

  cancelDateRangeTask(): void {
    if (!this.dateRangeJobId || this.dateRangeCancelLoading || this.dateRangeCancelRequested) {
      return;
    }

    this.dateRangeLoading = false;
    this.dateRangeCancelLoading = true;
    const jobId = this.dateRangeJobId;
    this.apiService.cancelTask(jobId).subscribe({
      next: (resp) => {
        const responseStatus = String(resp?.status || '').toLowerCase();
        const isStopping = responseStatus === 'stopping';
        const message = resp?.message || (isStopping
          ? 'Cancelación solicitada. El proceso se está deteniendo.'
          : 'Proceso cancelado por el usuario');

        this.dateRangeLoading = false;
        this.dateRangeCancelLoading = false;
        this.dateRangeError = null;
        this.dateRangeNotice = message;
        this.dateRangeCancelRequested = isStopping;

        if (isStopping) {
          this.dateRangeTaskStatus = {
            ...(this.dateRangeTaskStatus || {}),
            job_id: jobId,
            action: 'process_emails_range',
            status: 'running',
            message
          };
          this.dateRangeResult = {
            ...(this.dateRangeResult || {}),
            job_id: jobId,
            success: true,
            message
          };
          localStorage.setItem('cuenlyapp:dateRangeResult', JSON.stringify(this.dateRangeResult));
          if (!this.dateRangePolling) {
            this.startDateRangeTaskPolling(jobId, true);
          }
          return;
        }

        this.dateRangeTaskStatus = {
          ...(this.dateRangeTaskStatus || {}),
          job_id: jobId,
          action: 'process_emails_range',
          status: 'error',
          finished_at: Date.now() / 1000,
          message
        };
        this.dateRangeResult = {
          ...(this.dateRangeResult || {}),
          job_id: jobId,
          success: true,
          message
        };
        localStorage.setItem('cuenlyapp:dateRangeResult', JSON.stringify(this.dateRangeResult));
        this.clearDateRangePolling();
      },
      error: (err) => {
        this.dateRangeLoading = false;
        this.dateRangeCancelLoading = false;
        this.dateRangeCancelRequested = false;
        this.dateRangeNotice = null;
        this.dateRangeError = err?.error?.detail || err?.error?.message || 'No se pudo cancelar el procesamiento por rango';
        this.observability.error('Error cancelling date range task', err, 'InvoiceProcessingComponent', {
          action: 'cancelDateRangeTask',
          endpoint: `/tasks/${jobId}/cancel`
        });
      }
    });
  }

  clearDateRangeResult(): void {
    this.clearDateRangePolling();
    this.dateRangeLoading = false;
    this.dateRangeCancelLoading = false;
    this.dateRangeCancelRequested = false;
    this.dateRangeResult = null;
    this.dateRangeNotice = null;
    this.dateRangeError = null;
    this.dateRangeJobId = null;
    this.dateRangeTaskStatus = null;
    localStorage.removeItem('cuenlyapp:dateRangeResult');
  }

  private startDateRangeTaskPolling(jobId: string, isResume: boolean = false): void {
    this.clearDateRangePolling();
    this.dateRangeJobId = jobId;

    if (!isResume) {
      this.dateRangeTaskStatus = {
        job_id: jobId,
        action: 'process_emails_range',
        status: 'queued'
      };
    }

    this.dateRangePolling = interval(2500).pipe(
      startWith(0),
      switchMap(() => this.apiService.getTaskStatus(jobId))
    ).subscribe({
      next: (job: TaskStatusResponse | any) => {
        const status = String(job?.status || '').toLowerCase();
        const message = (job?.message || job?.error || '').toString();
        this.dateRangeTaskStatus = {
          ...job,
          status: (status as any) || 'queued'
        };

        if (status === 'running' && message) {
          this.dateRangeNotice = message;
          this.dateRangeError = null;
        }

        if (status === 'queued' || status === 'running' || status === 'started') {
          return;
        }

        if (status === 'done' || status === 'finished') {
          this.dateRangeCancelRequested = false;
          const normalized = this.normalizeTaskProcessResult(job?.result, job?.message);
          this.dateRangeResult = {
            ...(this.dateRangeResult || {}),
            success: normalized.success,
            message: normalized.message,
            invoice_count: normalized.invoice_count || 0,
            invoices: normalized.invoices || [],
            job_id: jobId
          };
          this.dateRangeError = null;
          localStorage.setItem('cuenlyapp:dateRangeResult', JSON.stringify(this.dateRangeResult));
          this.clearDateRangePolling();
          return;
        }

        this.dateRangeCancelRequested = false;
        const terminalMessage = job?.message || job?.error || 'Error al procesar rango de fechas';
        if (String(terminalMessage).toLowerCase().includes('cancel')) {
          this.dateRangeNotice = terminalMessage;
          this.dateRangeError = null;
        } else {
          this.dateRangeNotice = null;
          this.dateRangeError = terminalMessage;
        }
        this.clearDateRangePolling();
      },
      error: (err) => {
        const statusCode = err?.status;
        if (isResume && statusCode === 404) {
          this.clearDateRangeResult();
          return;
        }
        this.dateRangeCancelRequested = false;
        this.dateRangeNotice = null;
        this.dateRangeError = err?.error?.detail || err?.error?.message || 'No se pudo consultar el estado del procesamiento por rango';
        this.clearDateRangePolling();
        this.observability.error('Error polling date range task', err, 'InvoiceProcessingComponent', {
          action: 'pollDateRangeTask',
          endpoint: `/tasks/${jobId}`
        });
      }
    });
  }

  private clearDateRangePolling(): void {
    if (this.dateRangePolling) {
      this.dateRangePolling.unsubscribe();
      this.dateRangePolling = null;
    }
  }

  // Guardar fechas cuando cambien
  onDateRangeStartChange(value: string): void {
    this.dateRangeStart = value;
    localStorage.setItem('cuenlyapp:dateRangeStart', value);
  }

  onDateRangeEndChange(value: string): void {
    this.dateRangeEnd = value;
    localStorage.setItem('cuenlyapp:dateRangeEnd', value);
  }

  onJobIntervalChange(val: any): void {
    this.jobIntervalTouched = true;
    this.jobIntervalInput = this.getValidInterval(Number(val));
  }

  onAutoRefreshToggle(enabled: boolean): void {
    localStorage.setItem('cuenlyapp:autoRefresh', enabled ? 'true' : 'false');
    if (enabled) this.startAutoRefresh(); else this.stopAutoRefresh();
    this.scheduleSavePref();
  }

  private scheduleSavePref(): void {
    if (this.savePrefTimer) {
      clearTimeout(this.savePrefTimer);
      this.savePrefTimer = null;
    }
    this.savePrefTimer = setTimeout(() => {
      this.apiService.setAutoRefreshPref(this.autoRefresh, this.autoRefreshIntervalMs)
        .subscribe({ next: () => { }, error: () => { } });
    }, 300);
  }

  formatYearMonth(yearMonth: string): string {
    if (yearMonth.length !== 6) return yearMonth;

    const year = yearMonth.substring(0, 4);
    const month = yearMonth.substring(4, 6);
    const monthNames = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    const monthIndex = parseInt(month, 10) - 1;
    return `${monthNames[monthIndex]} ${year}`;
  }

  formatParaguayTime(dateTime: any): string {
    try {
      const date = (typeof dateTime === 'number')
        ? new Date(dateTime * 1000)
        : new Date(dateTime);
      return new Intl.DateTimeFormat('es-PY', {
        timeZone: 'America/Asuncion',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).format(date);
    } catch (error) {
      this.observability.error('Error formatting Paraguay time', error as Error, 'InvoiceProcessingComponent', {
        action: 'formatParaguayTime'
      });
      return '--:--';
    }
  }

  nextRunDisplay(): string {
    if (!this.jobStatus || !this.jobStatus.running || !this.jobStatus.next_run) {
      return '--:--';
    }
    return this.formatParaguayTime(this.jobStatus.next_run);
  }

  getDisplayIntervalMinutes(): number {
    return this.getValidInterval(this.jobStatus?.interval_minutes ?? this.jobIntervalInput);
  }

  formatParaguayDateTime(dateTime: any): string {
    try {
      const date = (typeof dateTime === 'number')
        ? new Date(dateTime * 1000)
        : new Date(dateTime);
      return new Intl.DateTimeFormat('es-PY', {
        timeZone: 'America/Asuncion',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).format(date).replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$1/$2/$3');
    } catch (error) {
      this.observability.error('Error formatting Paraguay datetime', error as Error, 'InvoiceProcessingComponent', {
        action: 'formatParaguayDateTime'
      });
      return 'N/A';
    }
  }

  formatParaguayDate(dateTime: string): string {
    try {
      const date = new Date(dateTime);
      return new Intl.DateTimeFormat('es-PY', {
        timeZone: 'America/Asuncion',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
      }).format(date);
    } catch (error) {
      this.observability.error('Error formatting Paraguay date', error as Error, 'InvoiceProcessingComponent', {
        action: 'formatParaguayDate'
      });
      return 'N/A';
    }
  }

  private getValidInterval(value: number | null | undefined): number {
    const fallback = this.intervalOptions[0];
    const parsed = Number(value);
    if (!isNaN(parsed) && this.intervalOptions.includes(parsed)) {
      return parsed;
    }
    if (isNaN(parsed)) {
      return fallback;
    }
    // Elegir el intervalo permitido más cercano para evitar saturación
    return this.intervalOptions.reduce((prev, curr) => {
      return Math.abs(curr - parsed) < Math.abs(prev - parsed) ? curr : prev;
    }, fallback);
  }
}
