import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { UserService } from '../../services/user.service';
import { ProcessResult, TaskSubmitResponse, TaskStatusResponse } from '../../models/invoice.model';
import { Subscription, interval } from 'rxjs';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-upload',
  templateUrl: './upload.component.html',
  styleUrls: ['./upload.component.scss']
})
export class UploadComponent implements OnInit {
  uploadForm: FormGroup;
  selectedFile: File | null = null;
  fileName: string = '';
  loading = false;
  result: ProcessResult | null = null;
  error: string | null = null;
  jobId: string | null = null;
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

  ngOnInit(): void {
    // Inicialización del componente
  }

  onFileSelected(event: Event): void {
    const element = event.target as HTMLInputElement;
    const fileList: FileList | null = element.files;
    
    if (fileList && fileList.length > 0) {
      const file = fileList[0];
      
      // Verificar si es un PDF
      if (file.type !== 'application/pdf') {
        this.error = 'Solo se permiten archivos PDF';
        this.selectedFile = null;
        this.fileName = '';
        return;
      }
      
      this.selectedFile = file;
      this.fileName = file.name;
      this.error = null;
    }
  }

  onSubmit(): void {
    if (!this.selectedFile) {
      this.error = 'Debe seleccionar un archivo PDF';
      return;
    }

    this.loading = true;
    this.error = null;
    this.result = null;

    const formData = this.uploadForm.value;

    this.apiService.enqueueUploadPdf(this.selectedFile, formData).subscribe({
      next: (res: TaskSubmitResponse) => {
        this.jobId = res.job_id;
        this.pollingSub = interval(2000).subscribe(() => this.pollJob());
      },
      error: (err) => {
        if (err?.status === 403) {
          this.error = 'No se pudo encolar el archivo: tu cuenta está suspendida. Contacta al administrador.';
          this.notificationService.error('Tu cuenta está suspendida. Contacta al administrador.', 'Cuenta suspendida');
        } else if (err?.status === 402) {
          const detail = err.error?.detail || err.error?.message || err.message || 'Pago requerido o límite alcanzado';
          this.error = 'No se pudo encolar el archivo: ' + detail;
          this.notificationService.warning(detail, 'Límite alcanzado');
        } else {
          const detail = err.error?.detail || err.error?.message || err.message || 'Error desconocido';
          this.error = 'Error al encolar el archivo: ' + detail;
          this.notificationService.error('No se pudo encolar el archivo', 'Error');
        }
        this.loading = false;
        console.error(err);
      }
    });
  }

  private pollJob(): void {
    if (!this.jobId) return;
    this.apiService.getTaskStatus(this.jobId).subscribe({
      next: (st: TaskStatusResponse) => {
        if (st.status === 'done' || st.status === 'error') {
          if (this.pollingSub) { this.pollingSub.unsubscribe(); this.pollingSub = null; }
          this.result = st.result || null;
          this.loading = false;
          
          // Si el procesamiento fue exitoso, actualizar el perfil del usuario
          if (st.status === 'done' && st.result?.success) {
            this.userService.updateProfileAfterProcessing();
          }
        }
      },
      error: (err) => console.error(err)
    });
  }

  goToDashboard(): void {
    this.router.navigate(['/']);
  }

  resetForm(): void {
    this.uploadForm.reset();
    this.selectedFile = null;
    this.fileName = '';
    this.error = null;
    this.result = null;
    this.jobId = null;
    if (this.pollingSub) { this.pollingSub.unsubscribe(); this.pollingSub = null; }
  }
}
