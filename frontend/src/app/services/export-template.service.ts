import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  ExportTemplate,
  TemplateResponse,
  TemplatesListResponse,
  AvailableFieldsResponse,
  ExportRequest,
  ExportFilters
} from '../models/export-template.model';

@Injectable({
  providedIn: 'root'
})
export class ExportTemplateService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ================================
  // GESTIÓN DE TEMPLATES
  // ================================

  /**
   * Obtener todos los templates del usuario
   */
  getTemplates(): Observable<TemplatesListResponse> {
    return this.http.get<TemplatesListResponse>(`${this.baseUrl}/export-templates`);
  }

  /**
   * Obtener un template específico
   */
  getTemplate(templateId: string): Observable<ExportTemplate> {
    return this.http.get<ExportTemplate>(`${this.baseUrl}/export-templates/${templateId}`);
  }

  /**
   * Crear un nuevo template
   */
  createTemplate(template: Partial<ExportTemplate>): Observable<TemplateResponse> {
    return this.http.post<TemplateResponse>(`${this.baseUrl}/export-templates`, template);
  }

  /**
   * Actualizar un template existente
   */
  updateTemplate(templateId: string, template: Partial<ExportTemplate>): Observable<TemplateResponse> {
    return this.http.put<TemplateResponse>(`${this.baseUrl}/export-templates/${templateId}`, template);
  }

  /**
   * Eliminar un template
   */
  deleteTemplate(templateId: string): Observable<TemplateResponse> {
    return this.http.delete<TemplateResponse>(`${this.baseUrl}/export-templates/${templateId}`);
  }

  /**
   * Duplicar un template
   */
  duplicateTemplate(templateId: string, newName: string): Observable<TemplateResponse> {
    return this.http.post<TemplateResponse>(
      `${this.baseUrl}/export-templates/${templateId}/duplicate`,
      { name: newName }
    );
  }

  /**
   * Establecer template como por defecto
   */
  setDefaultTemplate(templateId: string): Observable<TemplateResponse> {
    return this.http.post<TemplateResponse>(
      `${this.baseUrl}/export-templates/${templateId}/set-default`,
      {}
    );
  }

  // ================================
  // CAMPOS DISPONIBLES
  // ================================

  /**
   * Obtener campos disponibles para templates
   */
  getAvailableFields(): Observable<AvailableFieldsResponse> {
    return this.http.get<AvailableFieldsResponse>(`${this.baseUrl}/export-templates/available-fields`);
  }

  /**
   * Obtener preview de campos calculados con ejemplos
   */
  getCalculatedFieldsPreview(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/export-templates/calculated-fields/preview`);
  }

  /**
   * Obtener templates predefinidos inteligentes
   */
  getTemplatePresets(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/export-templates/presets`);
  }

  /**
   * Crear template a partir de preset inteligente
   */
  createFromPreset(request: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/export-templates/create-from-preset`, request);
  }

  // ================================
  // EXPORTACIÓN
  // ================================

  /**
   * Exportar facturas con template personalizado
   */
  exportWithTemplate(exportRequest: ExportRequest): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export/custom`, exportRequest, {
      responseType: 'blob'
    });
  }

  /**
   * Generar y descargar archivo Excel
   */
  downloadExcelFile(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'facturas_export.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }

  // ================================
  // UTILIDADES
  // ================================

  /**
   * Validar template antes de guardar
   */
  validateTemplate(template: Partial<ExportTemplate>): string[] {
    const errors: string[] = [];

    if (!template.name || template.name.trim() === '') {
      errors.push('El nombre del template es requerido');
    }

    if (!template.fields || template.fields.length === 0) {
      errors.push('Debe seleccionar al menos un campo');
    }

    if (template.fields) {
      const fieldKeys = template.fields.map(f => f.field_key);
      const duplicates = fieldKeys.filter((key, index) => fieldKeys.indexOf(key) !== index);
      if (duplicates.length > 0) {
        errors.push('No se pueden tener campos duplicados');
      }
    }

    return errors;
  }

  /**
   * Generar nombre de archivo por defecto
   */
  generateDefaultFilename(templateName: string): string {
    const now = new Date();
    const timestamp = now.toISOString().slice(0, 19).replace(/[:-]/g, '');
    const safeName = templateName.replace(/[^a-zA-Z0-9]/g, '_');
    return `${safeName}_${timestamp}.xlsx`;
  }
}