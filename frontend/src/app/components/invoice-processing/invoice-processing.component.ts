import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ProcessResult, SystemStatus, JobStatus, TaskSubmitResponse, TaskStatusResponse } from '../../models/invoice.model';
import { interval, Subscription } from 'rxjs';
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
  jobIntervalInput: number | null = null;
  jobIntervalTouched = false;
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
    if (this.storageHandler) {
      window.removeEventListener('storage', this.storageHandler);
      this.storageHandler = null;
    }
  }

  getSystemStatus(): void {
    this.loading = true;
    this.apiService.getStatus().subscribe({
      next: (data) => {
        this.status = data;
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
        this.jobStatus = data;
        this.jobLoading = false;
        if (!this.jobIntervalTouched && this.jobStatus?.interval_minutes) {
          this.jobIntervalInput = this.jobStatus.interval_minutes;
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
    this.loading = true;
    this.processingResult = null;
    this.error = null;
    
    // Log user action
    this.observability.logUserAction('process_emails_started', 'InvoiceProcessingComponent', {
      async_mode: async
    });

    this.apiService.processEmailsDirect().subscribe({
      next: (result) => {
        // Verificar si es un error de trial expirado
        if (!result.success && result.message?.includes('TRIAL_EXPIRED')) {
          this.showTrialExpiredError(result.message.replace('TRIAL_EXPIRED: ', ''));
          this.loading = false;
          return;
        }
        
        this.processingResult = result;
        this.loading = false;
        
        setTimeout(() => {
          this.getSystemStatus();
          this.getJobStatus();
        }, 1000);
      },
      error: (err) => {
        // Verificar si el error del backend es trial expirado
        if (err.error?.message?.includes('TRIAL_EXPIRED')) {
          this.showTrialExpiredError(err.error.message.replace('TRIAL_EXPIRED: ', ''));
        } else {
          this.error = err.error?.detail || err.error?.message || 'Error al procesar correos';
        }
        this.loading = false;
        this.observability.error('Error processing emails', err, 'InvoiceProcessingComponent', {
          action: 'processEmails',
          endpoint: '/process-emails'
        });
      }
    });
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
          ? this.jobIntervalInput!
          : (this.jobStatus?.interval_minutes || 3);

        this.apiService.setJobInterval(targetInterval).subscribe({
          next: () => {
            this.apiService.startJob().subscribe({
              next: (result) => {
                this.jobStatus = result;
                this.jobLoading = false;
                this.jobIntervalTouched = false;
                this.jobIntervalInput = this.jobStatus?.interval_minutes ?? targetInterval;
                
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
    if (!this.jobIntervalInput || this.jobIntervalInput < 1) return;
    this.jobLoading = true;
    this.apiService.setJobInterval(this.jobIntervalInput).subscribe({
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

  onJobIntervalChange(val: any): void {
    this.jobIntervalTouched = true;
    const n = Number(val);
    this.jobIntervalInput = isNaN(n) ? null : n;
  }

  isJobIntervalInvalid(): boolean {
    return !this.jobIntervalInput || this.jobIntervalInput < 1;
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
        .subscribe({ next: () => {}, error: () => {} });
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
}
