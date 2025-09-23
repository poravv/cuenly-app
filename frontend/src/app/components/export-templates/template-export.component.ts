import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ExportTemplateService } from '../../services/export-template.service';
import { 
  ExportTemplate, 
  ExportRequest, 
  ExportFilters,
  TemplatesListResponse 
} from '../../models/export-template.model';

@Component({
  selector: 'app-template-export',
  templateUrl: './template-export.component.html',
  styleUrls: ['./template-export.component.scss']
})
export class TemplateExportComponent implements OnInit {
  templateId: string | null = null;
  selectedTemplate: ExportTemplate | null = null;
  templates: ExportTemplate[] = [];
  
  loading = true;
  exporting = false;
  
  exportRequest: ExportRequest = {
    template_id: '',
    filters: {},
    filename: ''
  };

  filters: ExportFilters = {};

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private exportTemplateService: ExportTemplateService
  ) {}

  ngOnInit(): void {
    this.templateId = this.route.snapshot.paramMap.get('id');
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.exportTemplateService.getTemplates().subscribe({
      next: (response: TemplatesListResponse) => {
        this.templates = response.templates;
        
        if (this.templateId) {
          this.selectedTemplate = this.templates.find(t => t.id === this.templateId) || null;
          if (this.selectedTemplate) {
            this.exportRequest.template_id = this.selectedTemplate.id!;
            this.generateDefaultFilename();
          }
        } else {
          // Buscar template por defecto
          const defaultTemplate = this.templates.find(t => t.is_default);
          if (defaultTemplate) {
            this.selectTemplate(defaultTemplate);
          }
        }
        
        this.loading = false;
      },
      error: (error) => {
        console.error('Error cargando templates:', error);
        alert('Error al cargar los templates');
        this.router.navigate(['/templates-export']);
      }
    });
  }

  selectTemplate(template: ExportTemplate): void {
    this.selectedTemplate = template;
    this.exportRequest.template_id = template.id!;
    this.generateDefaultFilename();
  }

  generateDefaultFilename(): void {
    if (this.selectedTemplate) {
      this.exportRequest.filename = this.exportTemplateService.generateDefaultFilename(this.selectedTemplate.name);
    }
  }

  exportFacturas(): void {
    if (!this.selectedTemplate) {
      alert('Debe seleccionar un template');
      return;
    }

    if (!this.exportRequest.filename?.trim()) {
      alert('Debe especificar un nombre de archivo');
      return;
    }

    this.exporting = true;

    // Preparar filtros
    this.exportRequest.filters = { ...this.filters };

    // Limpiar filtros vacíos
    Object.keys(this.exportRequest.filters).forEach(key => {
      const value = (this.exportRequest.filters as any)[key];
      if (!value || value === '') {
        delete (this.exportRequest.filters as any)[key];
      }
    });

    this.exportTemplateService.exportWithTemplate(this.exportRequest).subscribe({
      next: (blob: Blob) => {
        this.exportTemplateService.downloadExcelFile(blob, this.exportRequest.filename!);
        this.exporting = false;
        alert('Exportación completada exitosamente');
      },
      error: (error) => {
        console.error('Error exportando:', error);
        alert('Error al exportar las facturas');
        this.exporting = false;
      }
    });
  }

  goBack(): void {
    this.router.navigate(['/templates-export']);
  }

  editTemplate(): void {
    if (this.selectedTemplate) {
      this.router.navigate(['/templates-export/edit', this.selectedTemplate.id]);
    }
  }

  getFieldCount(): number {
    return this.selectedTemplate?.fields?.length || 0;
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

  clearFilters(): void {
    this.filters = {};
  }

  hasActiveFilters(): boolean {
    return Object.values(this.filters).some(value => value && value !== '');
  }
}