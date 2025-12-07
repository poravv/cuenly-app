export interface Invoice {
  fecha?: string;
  ruc_emisor?: string;
  nombre_emisor?: string;
  numero_factura?: string;
  monto_total?: number;
  iva?: number;
  pdf_path?: string;
  email_origen?: string;
  procesado_en?: string;
}

export interface ProcessResult {
  success: boolean;
  message: string;
  invoice_count?: number;
  invoices?: Invoice[];
}

export interface SystemStatus {
  status: string;
  temp_dir?: string;
  email_configured: boolean;
  email_configs_count?: number;
  openai_configured: boolean;
  job?: {
    running: boolean;
    interval_minutes: number;
    next_run?: string;
    last_run?: string;
  };
}

export interface JobStatus {
  running: boolean;
  interval_minutes: number;
  next_run?: string;
  last_run?: string;
  last_result?: ProcessResult;
  next_run_ts?: number;
  last_run_ts?: number;
}

export interface TaskSubmitResponse {
  job_id: string;
}

export interface TaskStatusResponse {
  job_id: string;
  action: string;
  status: 'queued' | 'running' | 'done' | 'error';
  created_at?: number;
  started_at?: number | null;
  finished_at?: number | null;
  message?: string | null;
  result?: ProcessResult | null;
}

// Modelos de Excel eliminados

export interface EmailConfig {
  id?: string;
  name?: string;
  host: string;
  port: number;
  username: string;
  password: string;
  use_ssl: boolean;
  search_terms: string[];
  search_criteria?: string;
  provider?: string;
  enabled?: boolean;
}

export interface EmailConfigsResponse {
  success: boolean;
  configs: EmailConfig[];
  total: number;
  max_allowed?: number;
  can_add_more?: boolean;
}

export interface EmailTestResult {
  success: boolean;
  message: string;
  connection_test: boolean;
  login_test: boolean;
  search_test?: boolean;
  email_count?: number;
}

// Preferencias UI
export interface AutoRefreshPref {
  uid: string;
  enabled: boolean;
  interval_ms: number;
}
