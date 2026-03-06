import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ExportTemplateService } from '../../services/export-template.service';
import { NotificationService } from '../../services/notification.service';
import { ExportTemplate } from '../../models/export-template.model';

@Component({
  selector: 'app-export-templates',
  templateUrl: './export-templates.component.html',
  styleUrls: ['./export-templates.component.scss']
})
export class ExportTemplatesComponent implements OnInit {
  templates: ExportTemplate[] = [];
  loading = true;
  error = '';

  constructor(
    private exportTemplateService: ExportTemplateService,
    private router: Router,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.loading = true;
    this.error = '';

    this.exportTemplateService.getTemplates().subscribe({
      next: (response) => {
        // Sort: system templates first, then user templates
        this.templates = (response.templates || []).sort((a, b) => {
          if (a.is_system && !b.is_system) return -1;
          if (!a.is_system && b.is_system) return 1;
          return 0;
        });
        this.loading = false;
      },
      error: () => {
        this.error = 'Error al cargar los templates';
        this.loading = false;
      }
    });
  }

  isSystemTemplate(template: ExportTemplate): boolean {
    return !!template.is_system;
  }

  createTemplate(): void {
    this.router.navigate(['/templates-export/new']);
  }

  editTemplate(template: ExportTemplate): void {
    this.router.navigate(['/templates-export/edit', template.id]);
  }

  duplicateTemplate(template: ExportTemplate): void {
    const suggested = `${template.name} - Copia`;
    this.notificationService.warning(
      `Duplicar el template "${template.name}" como "${suggested}"?`,
      'Confirmar duplicación',
      {
        persistent: true,
        action: {
          label: 'Duplicar',
          handler: () => {
            this.exportTemplateService.duplicateTemplate(template.id!, suggested).subscribe({
              next: (response) => {
                this.notificationService.success(
                  response.message || 'Template duplicado correctamente',
                  'Template duplicado'
                );
                this.loadTemplates();
              },
              error: () => {
                this.notificationService.error(
                  'No se pudo duplicar el template. Por favor, intente nuevamente.',
                  'Error al duplicar'
                );
              }
            });
          }
        }
      }
    );
  }

  setDefaultTemplate(template: ExportTemplate): void {
    this.notificationService.warning(
      `¿Establecer "${template.name}" como template por defecto?`,
      'Confirmar acción',
      {
        persistent: true,
        action: {
          label: 'Establecer',
          handler: () => {
            this.exportTemplateService.setDefaultTemplate(template.id!).subscribe({
              next: (response) => {
                this.notificationService.success(
                  response.message || 'Template establecido como predeterminado',
                  'Template actualizado'
                );
                this.loadTemplates();
              },
              error: () => {
                this.notificationService.error(
                  'No se pudo establecer el template como predeterminado.',
                  'Error al actualizar'
                );
              }
            });
          }
        }
      }
    );
  }

  deleteTemplate(template: ExportTemplate): void {
    this.notificationService.warning(
      `¿Está seguro de eliminar el template "${template.name}"?\n\nEsta acción no se puede deshacer.`,
      '⚠️ Confirmar eliminación',
      {
        persistent: true,
        action: {
          label: 'Eliminar',
          handler: () => {
            this.exportTemplateService.deleteTemplate(template.id!).subscribe({
              next: (response) => {
                this.notificationService.success(
                  response.message || 'Template eliminado correctamente',
                  'Template eliminado'
                );
                this.loadTemplates();
              },
              error: () => {
                this.notificationService.error(
                  'No se pudo eliminar el template. Por favor, intente nuevamente.',
                  'Error al eliminar'
                );
              }
            });
          }
        }
      }
    );
  }

  exportWithTemplate(template: ExportTemplate): void {
    this.router.navigate(['/templates-export/export', template.id]);
  }

  getFieldCount(template: ExportTemplate): number {
    return template.fields ? template.fields.length : 0;
  }

  formatDate(date: Date | string | undefined): string {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString('es-PY', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }
}
