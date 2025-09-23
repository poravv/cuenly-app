import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ExportTemplateService } from '../../services/export-template.service';
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
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.loading = true;
    this.error = '';
    
    this.exportTemplateService.getTemplates().subscribe({
      next: (response) => {
        this.templates = response.templates;
        this.loading = false;
      },
      error: (error) => {
        console.error('Error cargando templates:', error);
        this.error = 'Error al cargar los templates';
        this.loading = false;
      }
    });
  }

  createTemplate(): void {
    this.router.navigate(['/templates-export/create']);
  }

  createSmartTemplate(): void {
    this.router.navigate(['/templates-export/new']);
  }

  editTemplate(template: ExportTemplate): void {
    this.router.navigate(['/templates-export/edit', template.id]);
  }

  duplicateTemplate(template: ExportTemplate): void {
    const newName = prompt('Nombre para el template duplicado:', `${template.name} - Copia`);
    if (newName && newName.trim()) {
      this.exportTemplateService.duplicateTemplate(template.id!, newName.trim()).subscribe({
        next: (response) => {
          alert(response.message);
          this.loadTemplates();
        },
        error: (error) => {
          console.error('Error duplicando template:', error);
          alert('Error al duplicar el template');
        }
      });
    }
  }

  setDefaultTemplate(template: ExportTemplate): void {
    if (confirm(`¿Establecer "${template.name}" como template por defecto?`)) {
      this.exportTemplateService.setDefaultTemplate(template.id!).subscribe({
        next: (response) => {
          alert(response.message);
          this.loadTemplates();
        },
        error: (error) => {
          console.error('Error estableciendo template por defecto:', error);
          alert('Error al establecer template por defecto');
        }
      });
    }
  }

  deleteTemplate(template: ExportTemplate): void {
    if (confirm(`¿Está seguro de eliminar el template "${template.name}"?`)) {
      this.exportTemplateService.deleteTemplate(template.id!).subscribe({
        next: (response) => {
          alert(response.message);
          this.loadTemplates();
        },
        error: (error) => {
          console.error('Error eliminando template:', error);
          alert('Error al eliminar el template');
        }
      });
    }
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