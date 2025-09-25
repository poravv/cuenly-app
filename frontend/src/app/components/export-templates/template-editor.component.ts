import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ExportTemplateService } from '../../services/export-template.service';
import { NotificationService } from '../../services/notification.service';
import { 
  ExportTemplate, 
  ExportField, 
  FieldType, 
  FieldAlignment, 
  GroupingType,
  CalculatedFieldType,
  AvailableField,
  AvailableFieldsResponse
} from '../../models/export-template.model';

@Component({
  selector: 'app-template-editor',
  templateUrl: './template-editor.component.html',
  styleUrls: ['./template-editor.component.scss']
})
export class TemplateEditorComponent implements OnInit {
  templateId: string | null = null;
  isEditMode = false;
  loading = true;
  saving = false;
  
  template: Partial<ExportTemplate> = {
    name: '',
    description: '',
    sheet_name: 'Facturas',
    include_header: true,
    include_totals: false,
    fields: [],
    is_default: false
  };

  // Solo campos disponibles reales de la base de datos
  availableFields: { [key: string]: AvailableField } = {};
  fieldCategories: any = {};
  
  // Enums para templates
  FieldType = FieldType;
  FieldAlignment = FieldAlignment;
  GroupingType = GroupingType;
  CalculatedFieldType = CalculatedFieldType;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private exportTemplateService: ExportTemplateService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.templateId = this.route.snapshot.paramMap.get('id');
    this.isEditMode = !!this.templateId;
    
    this.loadAvailableFields();
    
    if (this.isEditMode) {
      this.loadTemplate();
    } else {
      this.loading = false;
    }
  }

  loadAvailableFields(): void {
    this.exportTemplateService.getAvailableFields().subscribe({
      next: (response: AvailableFieldsResponse) => {
        this.availableFields = response.fields || {};
        // Ya no hay campos calculados
        this.fieldCategories = response.categories;
      },
      error: (error: any) => {
        console.error('Error cargando campos disponibles:', error);
      }
    });
  }

  loadTemplate(): void {
    if (!this.templateId) return;
    
    this.exportTemplateService.getTemplate(this.templateId).subscribe({
      next: (template: ExportTemplate) => {
        this.template = { ...template };
        this.loading = false;
      },
      error: (error) => {
        console.error('Error cargando template:', error);
        this.notificationService.error(
          'No se pudo cargar el template solicitado. Verifique que el ID sea correcto.',
          'Error al cargar template'
        );
        this.router.navigate(['/templates-export']);
      }
    });
  }

  addField(fieldKey: string): void {
    if (!fieldKey || this.isFieldAlreadyAdded(fieldKey)) return;
    
    // Verificar conflictos con campos de productos
    if (this.hasConflictingProductFields(fieldKey)) {
      const message = this.getConflictMessage(fieldKey);
      this.notificationService.warning(
        `${message}\n\n¿Deseas continuar agregando este campo de todas formas?`,
        '⚠️ Conflicto detectado',
        {
          persistent: true,
          action: {
            label: 'Continuar',
            handler: () => {
              this.doAddField(fieldKey);
            }
          }
        }
      );
      return;
    }
    
    this.doAddField(fieldKey);
  }
  
  private doAddField(fieldKey: string): void {
    
    // Obtener campo disponible
    const availableField = this.availableFields[fieldKey];
    
    if (!availableField) return;

    const newField: ExportField = {
      field_key: fieldKey,
      display_name: this.getFieldDisplayName(fieldKey),
      field_type: availableField.field_type,
      alignment: this.getDefaultAlignment(availableField.field_type),
      grouping_type: availableField.is_array ? GroupingType.SEPARATE_ROWS : undefined,
      separator: availableField.is_array ? ', ' : undefined,
      order: (this.template.fields?.length || 0) + 1,
      is_visible: true,
      width: undefined,
      
      // Sin campos calculados
      is_calculated: false,
      calculated_type: undefined
    };

    this.template.fields = [...(this.template.fields || []), newField];
  }

  removeField(index: number): void {
    if (!this.template.fields) return;
    this.template.fields.splice(index, 1);
    // Reordenar campos
    this.template.fields.forEach((field, i) => {
      field.order = i + 1;
    });
  }

  moveFieldUp(index: number): void {
    if (!this.template.fields || index <= 0) return;
    const fields = [...this.template.fields];
    [fields[index - 1], fields[index]] = [fields[index], fields[index - 1]];
    this.template.fields = fields;
    // Actualizar orden
    this.template.fields.forEach((field, i) => {
      field.order = i + 1;
    });
  }

  moveFieldDown(index: number): void {
    if (!this.template.fields || index >= this.template.fields.length - 1) return;
    const fields = [...this.template.fields];
    [fields[index], fields[index + 1]] = [fields[index + 1], fields[index]];
    this.template.fields = fields;
    // Actualizar orden
    this.template.fields.forEach((field, i) => {
      field.order = i + 1;
    });
  }

  isFieldAlreadyAdded(fieldKey: string): boolean {
    return !!(this.template.fields?.some(f => f.field_key === fieldKey));
  }

  hasConflictingProductFields(fieldKey: string): boolean {
    if (!this.template.fields) return false;
    
    // Si se intenta agregar 'productos' (general), verificar si hay campos específicos
    if (fieldKey === 'productos') {
      return this.template.fields.some(f => f.field_key.startsWith('productos.'));
    }
    
    // Si se intenta agregar un campo específico, verificar si existe 'productos' general
    if (fieldKey.startsWith('productos.')) {
      return this.template.fields.some(f => f.field_key === 'productos');
    }
    
    return false;
  }

  getConflictMessage(fieldKey: string): string {
    if (fieldKey === 'productos') {
      return 'Ya tienes campos específicos de productos. El campo "productos" concatenará todo en una celda.';
    }
    if (fieldKey.startsWith('productos.')) {
      return 'Ya tienes el campo "productos" general. Esto podría duplicar información.';
    }
    return '';
  }

  // Función auxiliar para obtener el nombre de display de cualquier campo
  getFieldDisplayName(fieldKey: string): string {
    const field = this.availableFields[fieldKey];
    
    // Usar descripción del campo si está disponible
    if (field && field.description) {
      return field.description;
    }
    
    // Mapeo específico para campos conocidos
    const fieldNames: { [key: string]: string } = {
      // Información básica
      'numero_factura': 'Número de Factura',
      'fecha': 'Fecha',
      'cdc': 'CDC',
      'timbrado': 'Timbrado',
      'establecimiento': 'Establecimiento',
      'punto_expedicion': 'Punto de Expedición',
      'tipo_documento': 'Tipo de Documento',
      'condicion_venta': 'Condición de Venta',
      'moneda': 'Moneda',
      'tipo_cambio': 'Tipo de Cambio',
      
      // Emisor
      'ruc_emisor': 'RUC Emisor',
      'nombre_emisor': 'Nombre Emisor',
      'direccion_emisor': 'Dirección Emisor',
      'telefono_emisor': 'Teléfono Emisor',
      'email_emisor': 'Email Emisor',
      'actividad_economica': 'Actividad Económica',
      
      // Cliente
      'ruc_cliente': 'RUC Cliente',
      'nombre_cliente': 'Nombre Cliente',
      'direccion_cliente': 'Dirección Cliente',
      'email_cliente': 'Email Cliente',
      
      // Montos - Nomenclatura XML SIFEN
      'subtotal_exentas': 'Subtotal Exentas',
      // 'exento' eliminado por redundancia con 'monto_exento'
      'monto_exento': 'Monto Exento',
      'exonerado': 'Exonerado',
      'subtotal_5': 'Base Gravada 5%',
      'gravado_5': 'Base Gravada 5%',
      'iva_5': 'IVA 5%',
      'subtotal_10': 'Base Gravada 10%',
      'gravado_10': 'Base Gravada 10%',
      'iva_10': 'IVA 10%',
      'total_iva': 'Total IVA',
      // 'total_operacion' eliminado por redundancia con 'monto_total'
      'monto_total': 'Monto Total',
      'total_general': 'Total General',
      'total_descuento': 'Total Descuento',
      'anticipo': 'Anticipo',
      // 'total_base_gravada': 'Total Base Gravada', // Campo comentado - no usar
      
      // Productos
      'productos': 'Productos',
      'productos.codigo': 'Código Producto',
      'productos.nombre': 'Nombre Producto',
      'productos.descripcion': 'Descripción Producto',
      'productos.articulo': 'Artículo',
      'productos.cantidad': 'Cantidad',
      'productos.unidad': 'Unidad',
      'productos.precio_unitario': 'Precio Unitario',
      'productos.total': 'Total Producto',
      'productos.iva': 'IVA Producto',
      'productos.afecta_iva': 'Afectación IVA',
      'productos.base_gravada': 'Base Gravada',
      'productos.monto_iva': 'Monto IVA',
      
      // Metadata
      'fuente': 'Fuente',
      'processing_quality': 'Calidad Procesamiento',
      'email_origen': 'Email Origen',
      'mes_proceso': 'Mes Proceso',
      'created_at': 'Fecha Procesamiento',
      'descripcion_factura': 'Descripción Factura'
    };
    
    return fieldNames[fieldKey] || fieldKey;
  }

  getDefaultAlignment(fieldType: FieldType): FieldAlignment {
    switch (fieldType) {
      case FieldType.NUMBER:
      case FieldType.CURRENCY:
      case FieldType.PERCENTAGE:
        return FieldAlignment.RIGHT;
      case FieldType.DATE:
        return FieldAlignment.CENTER;
      default:
        return FieldAlignment.LEFT;
    }
  }

  getCategoryFields(category: string): string[] {
    return this.fieldCategories[category] || [];
  }

  // Método simplificado sin campos calculados
  getAvailableCategoryFields(category: string): string[] {
    let fields = this.getCategoryFields(category);
    return fields.filter(field => !this.isFieldAlreadyAdded(field));
  }
  
  saveTemplate(): void {
    const errors = this.exportTemplateService.validateTemplate(this.template);
    if (errors.length > 0) {
      this.notificationService.error(
        'Por favor, corrija los siguientes errores:\n• ' + errors.join('\n• '),
        'Errores de validación'
      );
      return;
    }

    this.saving = true;
    
    const operation = this.isEditMode 
      ? this.exportTemplateService.updateTemplate(this.templateId!, this.template)
      : this.exportTemplateService.createTemplate(this.template);

    operation.subscribe({
      next: (response) => {
        this.notificationService.success(
          response.message || 'Template guardado correctamente',
          this.isEditMode ? 'Template actualizado' : 'Template creado'
        );
        this.router.navigate(['/templates-export']);
      },
      error: (error) => {
        console.error('Error guardando template:', error);
        this.notificationService.error(
          'No se pudo guardar el template. Por favor, intente nuevamente.',
          'Error al guardar'
        );
        this.saving = false;
      }
    });
  }

  cancel(): void {
    this.router.navigate(['/templates-export']);
  }

  isFieldTypeArray(fieldType: FieldType): boolean {
    return fieldType === FieldType.ARRAY;
  }

  // Método simple para nombres de categorías (solo las que existen)
  getCategoryName(category: string): string {
    const categoryNames: { [key: string]: string } = {
      'basic': 'Información Básica',
      'emisor': 'Datos del Emisor',
      'cliente': 'Datos del Cliente',
      'montos': 'Montos e Impuestos',
      'productos': 'Productos',
      'metadata': 'Información Adicional'
    };
    return categoryNames[category] || category;
  }
}