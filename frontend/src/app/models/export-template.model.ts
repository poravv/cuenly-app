export enum FieldType {
  TEXT = 'TEXT',
  NUMBER = 'NUMBER',
  CURRENCY = 'CURRENCY',
  DATE = 'DATE',
  PERCENTAGE = 'PERCENTAGE',
  ARRAY = 'ARRAY'
}

export enum FieldAlignment {
  LEFT = 'left',
  CENTER = 'center',
  RIGHT = 'right'
}

export enum GroupingType {
  CONCATENATE = 'CONCATENATE',
  SEPARATE_ROWS = 'SEPARATE_ROWS',
  SUMMARY = 'SUMMARY'
}

// Tipos de campos calculados disponibles
export enum CalculatedFieldType {
  MONTO_CON_IVA_5 = 'MONTO_CON_IVA_5',
  MONTO_CON_IVA_10 = 'MONTO_CON_IVA_10',
  MONTO_SIN_IVA_5 = 'MONTO_SIN_IVA_5',
  MONTO_SIN_IVA_10 = 'MONTO_SIN_IVA_10',
  TOTAL_IVA_5_ONLY = 'TOTAL_IVA_5_ONLY',
  TOTAL_IVA_10_ONLY = 'TOTAL_IVA_10_ONLY',
  TOTAL_IVA_GENERAL = 'TOTAL_IVA_GENERAL',
  PORCENTAJE_IVA_5 = 'PORCENTAJE_IVA_5',
  PORCENTAJE_IVA_10 = 'PORCENTAJE_IVA_10',
  PORCENTAJE_EXENTO = 'PORCENTAJE_EXENTO',
  SUBTOTAL_GRAVADO = 'SUBTOTAL_GRAVADO',
  SUBTOTAL_NO_GRAVADO = 'SUBTOTAL_NO_GRAVADO',
  TOTAL_ANTES_IVA = 'TOTAL_ANTES_IVA',
  CANTIDAD_PRODUCTOS = 'CANTIDAD_PRODUCTOS',
  VALOR_PROMEDIO_PRODUCTO = 'VALOR_PROMEDIO_PRODUCTO'
}

export interface ExportField {
  field_key: string;
  display_name: string;
  field_type: FieldType;
  alignment?: FieldAlignment;
  grouping_type?: GroupingType;
  separator?: string;
  order?: number;
  is_visible?: boolean;
  width?: number;
  
  // Campos para calculados
  is_calculated?: boolean;
  calculated_type?: CalculatedFieldType;
  calculation_params?: any;
}

export interface ExportTemplate {
  id?: string;
  name: string;
  description?: string;
  sheet_name?: string;
  include_header?: boolean;
  include_totals?: boolean;
  fields: ExportField[];
  owner_email?: string;
  is_default?: boolean;
  created_at?: Date;
  updated_at?: Date;
}

export interface AvailableField {
  description: string;
  field_type: FieldType;
  is_array?: boolean;
  // Para campos calculados
  display_name?: string;
  is_calculated?: boolean;
  calculated_type?: string;
  example_value?: string;
  category?: string;
}

export interface ExportFilters {
  fecha_inicio?: string;
  fecha_fin?: string;
  ruc_emisor?: string;
  ruc_cliente?: string;
  monto_minimo?: number;
  monto_maximo?: number;
}

export interface ExportRequest {
  template_id: string;
  filters?: ExportFilters;
  filename?: string;
}

export interface TemplateResponse {
  success: boolean;
  template_id?: string;
  message: string;
}

export interface TemplatesListResponse {
  templates: ExportTemplate[];
  count: number;
}

export interface AvailableFieldsResponse {
  fields: { [key: string]: AvailableField };
  calculated_fields?: { [key: string]: AvailableField };
  categories: {
    basic: string[];
    emisor: string[];
    cliente: string[];
    montos: string[];
    productos: string[];
    metadata: string[];
    // Categorías de campos calculados
    calculated_iva_montos?: string[];
    calculated_analisis?: string[];
    calculated_totales?: string[];
    calculated_productos?: string[];
  };
}

// Interfaces para Templates Inteligentes
export interface TemplatePreset {
  name: string;
  description: string;
  field_count: number;
  calculated_fields: number;
  group_type: string;
  features: string[];
}

export interface PresetsResponse {
  presets: { [key: string]: TemplatePreset };
  recommendations: {
    new_user: string;
    accountant: string;
    business_owner: string;
    auditor: string;
  };
}

export interface CreateFromPresetRequest {
  preset: string;
  name?: string;
}

export interface CreateFromPresetResponse {
  success: boolean;
  template_id: string;
  message: string;
  preset_used: string;
}