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

// === CAMPOS CALCULADOS ELIMINADOS ===
// Solo campos reales de la base de datos
export enum CalculatedFieldType {
  // Sin campos calculados
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
  
    // Sin campos calculados
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
  // Sin campos calculados
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
  categories: { [category: string]: string[] };
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
