import { Component, OnInit, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { UserService } from '../../services/user.service';
import { AnalyticsService } from '../../services/analytics.service';
import { TaskSubmitResponse, TaskStatusResponse } from '../../models/invoice.model';
import { Subscription, interval, Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { NotificationService } from '../../services/notification.service';
import { ToastrService } from 'ngx-toastr';
import { createWorker } from 'tesseract.js';
import { FileTransferService } from '../../services/file-transfer.service';

interface UploadFileItem {
  file: File;
  status: 'pending' | 'validating' | 'uploading' | 'success' | 'error' | 'skipped' | 'invalid_content';
  progress: number;
  message?: string;
  invoiceId?: string;
  isImage?: boolean;
  jobId?: string; // Re-adding jobId for PDF tracking
  result?: any; // Re-adding result for PDF tracking
}

@Component({
  selector: 'app-upload',
  templateUrl: './upload.component.html',
  styleUrls: ['./upload.component.scss']
})
export class UploadComponent implements OnInit, OnDestroy {
  uploadForm: FormGroup;
  files: UploadFileItem[] = [];
  isProcessing = false; // Renamed from 'loading'

  // Polling
  private pollInterval: any;
  private activeJobs: string[] = []; // To track job_ids for PDFs

  constructor(
    private fb: FormBuilder,
    private api: ApiService, // Renamed from apiService
    private userService: UserService,
    private router: Router,
    private notificationService: NotificationService, // Kept for existing usage
    private analytics: AnalyticsService,
    private toastr: ToastrService, // Added
    private fileTransfer: FileTransferService // Added
  ) {
    this.uploadForm = this.fb.group({
      sender: ['', [Validators.maxLength(100)]],
      date: ['', []]
    });
  }

  ngOnInit(): void {
    // Check for files transferred from Navbar
    const transferredFiles = this.fileTransfer.getFiles();
    if (transferredFiles.length > 0) {
      this.processFiles(transferredFiles);
    }
  }

  ngOnDestroy(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
  }

  async onFileSelected(event: any): Promise<void> {
    const fileList: FileList = event.target.files;
    if (!fileList || fileList.length === 0) return;

    const filesArray = Array.from(fileList);
    await this.processFiles(filesArray);

    // Clear input
    event.target.value = '';
  }

  async processFiles(fileList: File[]): Promise<void> {
    for (const file of fileList) {
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp)$/i.test(file.name);

      if (!isPdf && !isImage) {
        this.toastr.warning(`El archivo ${file.name} no es un PDF ni una imagen soportada.`);
        continue;
      }

      if (file.size > 10 * 1024 * 1024) {
        this.toastr.warning(`El archivo ${file.name} excede el tamaño máximo de 10MB.`);
        continue;
      }

      // Evitar duplicados por nombre
      if (this.files.some(f => f.file.name === file.name)) {
        this.toastr.info(`El archivo ${file.name} ya ha sido seleccionado.`);
        continue;
      }

      const item: UploadFileItem = {
        file: file,
        status: 'pending',
        progress: 0,
        isImage: isImage
      };

      this.files.push(item);

      if (isImage) {
        // Start OCR validation for images
        await this.validateImage(item);
      }
    }
  }

  async validateImage(item: UploadFileItem): Promise<void> {
    item.status = 'validating';
    item.message = 'Analizando contenido...';

    try {
      const worker = await createWorker('spa'); // Spanish language
      const ret = await worker.recognize(item.file);
      const text = ret.data.text.toLowerCase();
      await worker.terminate();

      const keywords = ['factura', 'invoice', 'recibo', 'comprobante', 'ruc', 'timbrado', 'venta', 'compra', 'total', 'iva'];
      const hasKeyword = keywords.some(k => text.includes(k));

      if (hasKeyword) {
        item.status = 'pending';
        item.message = 'Contenido válido. Listo para subir.';
      } else {
        item.status = 'invalid_content';
        item.message = 'No parece ser una factura. ¿Deseas subirlo de todas formas?';
      }
    } catch (error) {
      console.error('OCR Error:', error);
      item.status = 'error';
      item.message = 'Error al analizar la imagen.';
    }
  }

  forceUpload(item: UploadFileItem): void {
    item.status = 'pending';
    item.message = 'Subida forzada por usuario.';
  }

  removeFile(index: number): void {
    // Allow removal unless it's actively uploading/processing a PDF
    if (this.files[index].status === 'uploading' && !this.files[index].isImage) {
      this.toastr.warning('No se puede eliminar un archivo PDF mientras se está procesando.');
      return;
    }
    const removedItem = this.files.splice(index, 1)[0];
    if (removedItem.jobId) {
      this.activeJobs = this.activeJobs.filter(jobId => jobId !== removedItem.jobId);
    }
    this.checkAllFinished();
  }

  onSubmit(): void {
    const pendingFiles = this.files.filter(f => f.status === 'pending' || f.status === 'error');

    if (pendingFiles.length === 0) {
      if (this.files.some(f => f.status === 'invalid_content')) {
        this.toastr.warning('Hay archivos con contenido inválido. Debes "Forzar subida" o eliminarlos.');
      } else {
        this.toastr.info('No hay archivos pendientes para subir.');
      }
      return;
    }

    this.isProcessing = true;
    const formData = this.uploadForm.value;

    pendingFiles.forEach(item => {
      item.status = 'uploading';
      item.progress = 10; // Started
      item.message = 'Iniciando subida...';

      if (item.isImage) {
        this.api.uploadImage(item.file).subscribe({
          next: (res: any) => { // Assuming res has success, invoice_id, error
            if (res.success) {
              item.status = 'success';
              item.progress = 100;
              item.message = 'Imagen subida correctamente';
              item.invoiceId = res.invoice_id;
              this.userService.updateProfileAfterProcessing();
            } else {
              item.status = 'error';
              item.message = res.error || 'Error al subir imagen';
            }
            this.checkAllFinished();
          },
          error: (err) => {
            item.status = 'error';
            item.message = err.error?.detail || 'Error de conexión';
            this.checkAllFinished();
          }
        });
      } else {
        // PDF Logic (Queue)
        this.api.enqueueUploadPdf(item.file, formData).subscribe({
          next: (res: TaskSubmitResponse) => {
            if (res.job_id) {
              item.jobId = res.job_id;
              this.activeJobs.push(res.job_id);
              item.message = 'Procesando en segundo plano...';
              this.startPolling();
            }
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
      }
    });
  }

  startPolling(): void {
    if (this.pollInterval) return;

    this.pollInterval = setInterval(() => {
      this.checkJobsStatus();
    }, 2000);
  }

  checkJobsStatus(): void {
    if (this.activeJobs.length === 0) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
      this.checkAllFinished();
      return;
    }

    // Create a copy of activeJobs to iterate, as it might be modified during processing
    const jobsToCheck = [...this.activeJobs];

    jobsToCheck.forEach(jobId => {
      const item = this.files.find(f => f.jobId === jobId);
      if (!item) {
        // Job ID not found in files, remove from activeJobs
        this.activeJobs = this.activeJobs.filter(id => id !== jobId);
        return;
      }

      this.api.getTaskStatus(jobId).subscribe({
        next: (st: TaskStatusResponse) => {
          if (st.status === 'done') {
            item.status = st.result?.success ? 'success' : 'error';
            item.message = st.result?.success ? 'Procesado exitosamente' : (st.result?.message || 'Error en procesamiento');
            item.result = st.result;
            item.progress = 100;

            if (st.result?.success) {
              this.userService.updateProfileAfterProcessing();
            }
            this.activeJobs = this.activeJobs.filter(id => id !== jobId); // Remove from active jobs
            this.checkAllFinished();
          } else if (st.status === 'error') {
            item.status = 'error';
            item.message = st.message || 'Error en la tarea';
            item.progress = 100;
            this.activeJobs = this.activeJobs.filter(id => id !== jobId); // Remove from active jobs
            this.checkAllFinished();
          } else {
            // Task is still pending/processing
            item.message = st.message || 'Procesando...';
            // Update progress if available from API, otherwise a generic increment
            const progress = (st as any).progress;
            if (progress !== undefined) {
              item.progress = progress;
            } else if (item.progress < 90) { // Generic progress for long-running tasks
              item.progress += 5;
            }
          }
        },
        error: (err) => {
          console.error('Error polling job', jobId, err);
          // If polling fails, mark as error and remove from active jobs
          item.status = 'error';
          item.message = 'Error de conexión al verificar estado.';
          item.progress = 100;
          this.activeJobs = this.activeJobs.filter(id => id !== jobId);
          this.checkAllFinished();
        }
      });
    });
  }

  checkAllFinished(): void {
    const uploadingOrValidating = this.files.some(f =>
      f.status === 'uploading' || f.status === 'validating'
    );
    const activePdfJobs = this.activeJobs.length > 0;

    if (!uploadingOrValidating && !activePdfJobs) {
      this.isProcessing = false;
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
    }
  }

  // Limpiar formulario y lista
  resetForm(): void {
    this.uploadForm.reset();
    this.files = [];
    this.checkAllFinished(); // Stop things if running
  }
}
