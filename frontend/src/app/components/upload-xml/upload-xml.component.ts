import { Component, OnInit, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { UserService } from '../../services/user.service';
import { TaskSubmitResponse, TaskStatusResponse } from '../../models/invoice.model';
import { Subscription, interval, Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { NotificationService } from '../../services/notification.service';

interface UploadFileItem {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error' | 'ai_limit';
  message?: string;
  jobId?: string;
  progress?: number;
  result?: any;
  reasonCode?: string;
}

@Component({
  selector: 'app-upload-xml',
  templateUrl: './upload-xml.component.html',
  styleUrls: ['./upload-xml.component.scss']
})
export class UploadXmlComponent implements OnInit, OnDestroy {
  uploadForm: FormGroup;
  files: UploadFileItem[] = [];
  loading = false;
  destroy$ = new Subject<void>();
  pollingSub: Subscription | null = null;

  constructor(
    private fb: FormBuilder,
    private apiService: ApiService,
    private userService: UserService,
    private router: Router,
    private notificationService: NotificationService
  ) {
    this.uploadForm = this.fb.group({
      sender: ['', [Validators.maxLength(100)]],
      date: ['', []]
    });
  }

  ngOnInit(): void { }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    if (this.pollingSub) {
      this.pollingSub.unsubscribe();
    }
  }

  onFileSelected(event: Event): void {
    const element = event.target as HTMLInputElement;
    const fileList: FileList | null = element.files;

    if (fileList && fileList.length > 0) {
      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];

        const isXml = file.name.toLowerCase().endsWith('.xml') || file.type === 'text/xml' || file.type === 'application/xml';
        if (!isXml) {
          this.notificationService.warning(`El archivo ${file.name} no es un XML y fue ignorado.`);
          continue;
        }

        if (file.size > 10 * 1024 * 1024) {
          this.notificationService.warning(`El archivo ${file.name} excede el tamaño máximo de 10MB.`);
          continue;
        }

        // Evitar duplicados por nombre
        if (!this.files.some(f => f.file.name === file.name)) {
          this.files.push({
            file: file,
            status: 'pending'
          });
        }
      }
      element.value = '';
    }
  }

  removeFile(index: number): void {
    if (this.files[index].status === 'uploading') {
      return;
    }
    this.files.splice(index, 1);
  }

  onSubmit(): void {
    if (this.files.length === 0) {
      this.notificationService.warning('Debe seleccionar al menos un archivo XML');
      return;
    }

    const pendingFiles = this.files.filter(f => f.status === 'pending' || f.status === 'error');
    if (pendingFiles.length === 0) {
      this.notificationService.info('No hay archivos pendientes para procesar');
      return;
    }

    this.loading = true;
    const formData = this.uploadForm.value;

    pendingFiles.forEach(item => {
      item.status = 'uploading';
      item.message = 'Iniciando subida...';

      this.apiService.enqueueUploadXml(item.file, formData).subscribe({
        next: (res: TaskSubmitResponse) => {
          item.jobId = res.job_id;
          item.message = 'Procesando...';
          this.startPolling();
        },
        error: (err) => {
          item.status = 'error';
          if (err?.status === 403) {
            item.message = 'Cuenta suspendida';
          } else if (err?.status === 402) {
            item.message = 'Pago requerido o límite alcanzado';
          } else {
            item.message = err.error?.detail || err.message || 'Error al encolar';
          }
          this.checkAllFinished();
        }
      });
    });
  }

  startPolling(): void {
    if (this.pollingSub && !this.pollingSub.closed) return;

    this.pollingSub = interval(2000)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        const activeJobs = this.files.filter(f => f.status === 'uploading' && f.jobId);

        if (activeJobs.length === 0) {
          if (this.pollingSub) {
            this.pollingSub.unsubscribe();
            this.pollingSub = null;
          }
          this.checkAllFinished();
          return;
        }

        activeJobs.forEach(item => {
          if (item.jobId) {
            this.apiService.getTaskStatus(item.jobId).subscribe({
              next: (st: TaskStatusResponse) => {
                if (st.status === 'done') {
                  const reasonCode = st.result?.reason_code;
                  item.result = st.result;
                  item.reasonCode = reasonCode;

                  if (reasonCode === 'ai_limit_reached' || reasonCode === 'ai_unavailable') {
                    item.status = 'ai_limit';
                    item.message = reasonCode === 'ai_limit_reached'
                      ? 'Archivo guardado pero pendiente de extracción (límite de IA alcanzado).'
                      : 'Archivo guardado pero pendiente de extracción (IA no disponible temporalmente).';
                  } else if (st.result?.success) {
                    item.status = 'success';
                    item.message = 'Procesado exitosamente';
                    this.userService.updateProfileAfterProcessing();
                  } else {
                    item.status = 'error';
                    item.message = st.result?.message || 'Error en procesamiento';
                  }
                } else if (st.status === 'error') {
                  item.status = 'error';
                  item.message = st.message || 'Error en la tarea';
                }
              },
              error: (err) => {
                console.error('Error polling job', err);
              }
            });
          }
        });
      });
  }

  checkAllFinished(): void {
    const uploading = this.files.some(f => f.status === 'uploading');
    if (!uploading) {
      this.loading = false;
    }
  }

  goToDashboard(): void {
    this.router.navigate(['/']);
  }

  trackByFile(index: number, item: UploadFileItem): string {
    return item.file.name;
  }

  resetForm(): void {
    this.uploadForm.reset();
    this.files = [];
    this.loading = false;
    if (this.pollingSub) {
      this.pollingSub.unsubscribe();
      this.pollingSub = null;
    }
  }
}
