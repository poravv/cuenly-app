import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { SystemStatus, ProcessResult, JobStatus, EmailConfig, EmailTestResult, TaskSubmitResponse, TaskStatusResponse, AutoRefreshPref } from '../models/invoice.model';
import { AuthService } from './auth.service';


@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient, private authService: AuthService) { }

  /**
   * Obtiene headers con autenticación Firebase y API Key del frontend
   */
  private getSecureHeaders(): HttpHeaders {
    let headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'X-Frontend-Key': environment.frontendApiKey
    });

    // Agregar token Firebase si está disponible
    const token = this.authService.getIdToken();
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }

    return headers;
  }

  /**
   * Obtiene headers básicos (sin API Key para endpoints públicos)
   */
  private getBasicHeaders(): HttpHeaders {
    let headers = new HttpHeaders({
      'Content-Type': 'application/json'
    });

    const token = this.authService.getIdToken();
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }

    return headers;
  }

  // Obtener estado del sistema
  getStatus(): Observable<SystemStatus> {
    return this.http.get<SystemStatus>(`${this.apiUrl}/status`);
  }

  // Procesar correos
  processEmails(runAsync: boolean = false): Observable<ProcessResult> {
    return this.http.post<ProcessResult>(
      `${this.apiUrl}/process`,
      { run_async: runAsync },
      { headers: this.getSecureHeaders() }
    );
  }

  // Subir un archivo PDF
  uploadPdf(file: File, metadata: { sender?: string, date?: string }): Observable<ProcessResult> {
    const formData = new FormData();
    formData.append('file', file);

    if (metadata.sender) {
      formData.append('sender', metadata.sender);
    }

    if (metadata.date) {
      formData.append('date', metadata.date);
    }

    return this.http.post<ProcessResult>(`${this.apiUrl}/api/upload`, formData);
  }

  // Subir un archivo XML
  uploadXml(file: File, metadata: { sender?: string, date?: string }): Observable<ProcessResult> {
    const formData = new FormData();
    formData.append('file', file);

    if (metadata.sender) {
      formData.append('sender', metadata.sender);
    }

    if (metadata.date) {
      formData.append('date', metadata.date);
    }

    return this.http.post<ProcessResult>(`${this.apiUrl}/api/upload-xml`, formData);
  }

  // Subir imagen para procesamiento (Async)
  uploadImage(file: File): Observable<{ job_id: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ job_id: string }>(`${this.apiUrl}/api/upload-image`, formData);
  }

  // Encolar carga de PDF
  enqueueUploadPdf(file: File, metadata: { sender?: string, date?: string }): Observable<TaskSubmitResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata.sender) formData.append('sender', metadata.sender);
    if (metadata.date) formData.append('date', metadata.date);
    return this.http.post<TaskSubmitResponse>(`${this.apiUrl}/tasks/upload-pdf`, formData);
  }

  // Encolar carga de XML
  enqueueUploadXml(file: File, metadata: { sender?: string, date?: string }): Observable<TaskSubmitResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata.sender) formData.append('sender', metadata.sender);
    if (metadata.date) formData.append('date', metadata.date);
    return this.http.post<TaskSubmitResponse>(`${this.apiUrl}/tasks/upload-xml`, formData);
  }

  // Excel removido: no hay endpoints de Excel

  // Probar configuración de email
  testEmailConfig(config: EmailConfig): Observable<EmailTestResult> {
    return this.http.post<EmailTestResult>(`${this.apiUrl}/email-config/test`, config);
  }

  // Probar configuración por ID (guardada en DB)
  testEmailConfigById(id: string): Observable<EmailTestResult> {
    return this.http.post<EmailTestResult>(`${this.apiUrl}/email-configs/${id}/test`, {});
  }

  // Email Configs CRUD
  getEmailConfigs(): Observable<{ success: boolean, configs: EmailConfig[], total: number }> {
    return this.http.get<{ success: boolean, configs: EmailConfig[], total: number }>(`${this.apiUrl}/email-configs`);
  }

  createEmailConfig(config: EmailConfig): Observable<{ success: boolean, id: string }> {
    return this.http.post<{ success: boolean, id: string }>(`${this.apiUrl}/email-configs`, config);
  }

  updateEmailConfig(id: string, config: EmailConfig): Observable<{ success: boolean, id: string }> {
    return this.http.put<{ success: boolean, id: string }>(`${this.apiUrl}/email-configs/${id}`, config);
  }

  /**
   * Actualización parcial de configuración de email.
   * Útil para OAuth2 donde solo se pueden editar ciertos campos como search_terms.
   */
  patchEmailConfig(id: string, fields: Partial<EmailConfig>): Observable<{ success: boolean, id: string, updated_fields: string[] }> {
    return this.http.patch<{ success: boolean, id: string, updated_fields: string[] }>(`${this.apiUrl}/email-configs/${id}`, fields);
  }

  deleteEmailConfig(id: string): Observable<{ success: boolean }> {
    return this.http.delete<{ success: boolean }>(`${this.apiUrl}/email-configs/${id}`);
  }

  setEmailConfigEnabled(id: string, enabled: boolean): Observable<{ success: boolean, enabled: boolean }> {
    return this.http.patch<{ success: boolean, enabled: boolean }>(`${this.apiUrl}/email-configs/${id}/enabled`, { enabled });
  }

  toggleEmailConfig(id: string): Observable<{ success: boolean, enabled: boolean }> {
    return this.http.post<{ success: boolean, enabled: boolean }>(`${this.apiUrl}/email-configs/${id}/toggle`, {});
  }

  // -----------------------------
  // OAuth 2.0 for Gmail (XOAUTH2)
  // -----------------------------

  // Check if Google OAuth is configured
  getGoogleOAuthStatus(): Observable<{ configured: boolean, provider: string, message: string }> {
    return this.http.get<{ configured: boolean, provider: string, message: string }>(`${this.apiUrl}/email-configs/oauth/google/status`);
  }

  // Initiate Google OAuth flow - returns authorization URL
  initiateGoogleOAuth(loginHint?: string): Observable<{ auth_url: string, state: string, message: string }> {
    const options: { params?: { [key: string]: string } } = {};
    if (loginHint) {
      options.params = { login_hint: loginHint };
    }
    return this.http.get<{ auth_url: string, state: string, message: string }>(
      `${this.apiUrl}/email-configs/oauth/google/authorize`,
      options
    );
  }

  // Save OAuth email configuration after successful authorization
  saveOAuthEmailConfig(data: {
    gmail_address: string,
    access_token: string,
    refresh_token: string,
    token_expiry: string,
    name?: string,
    search_terms?: string[]
  }): Observable<{ success: boolean, id: string, message: string }> {
    return this.http.post<{ success: boolean, id: string, message: string }>(
      `${this.apiUrl}/email-configs/oauth/save`,
      data
    );
  }

  // Refresh OAuth token for a saved config
  refreshOAuthToken(configId: string): Observable<{ success: boolean, token_expiry: string, message: string }> {
    return this.http.post<{ success: boolean, token_expiry: string, message: string }>(
      `${this.apiUrl}/email-configs/${configId}/oauth/refresh`,
      {}
    );
  }

  // Iniciar job programado
  startJob(): Observable<JobStatus> {
    return this.http.post<JobStatus>(`${this.apiUrl}/job/start`, {});
  }

  // Detener job programado
  stopJob(): Observable<JobStatus> {
    return this.http.post<JobStatus>(`${this.apiUrl}/job/stop`, {});
  }

  // Obtener estado del job
  getJobStatus(): Observable<JobStatus> {
    return this.http.get<JobStatus>(`${this.apiUrl}/job/status`);
  }

  // Ajustar intervalo del job (minutos)
  setJobInterval(minutes: number): Observable<JobStatus> {
    return this.http.post<JobStatus>(`${this.apiUrl}/job/interval`, { minutes });
  }

  // Procesamiento directo sin cola de tareas (máximo 10 facturas)
  processEmailsDirect(limit: number = 10): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/process-direct`, {}, {
      params: { limit: limit.toString() },
      headers: this.getSecureHeaders()
    });
  }

  // Procesar correos en un rango de fechas específico
  processDateRange(startDate: string, endDate: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/jobs/process-range`, {
      start_date: startDate,
      end_date: endDate
    }, {
      headers: this.getSecureHeaders()
    });
  }

  // Enviar tarea de procesamiento
  submitTask(): Observable<TaskSubmitResponse> {
    return this.http.post<TaskSubmitResponse>(
      `${this.apiUrl}/tasks/process`,
      {},
      { headers: this.getSecureHeaders() }
    );
  }

  // Consultar estado de tarea
  getTaskStatus(jobId: string): Observable<TaskStatusResponse> {
    return this.http.get<TaskStatusResponse>(`${this.apiUrl}/tasks/${jobId}`);
  }

  // Limpiar tareas antiguas
  cleanupOldTasks(): Observable<{ message: string, cleaned_count: number }> {
    return this.http.delete<{ message: string, cleaned_count: number }>(`${this.apiUrl}/tasks/cleanup`);
  }

  // Debug de tareas (solo para desarrollo)
  debugTasks(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/tasks/debug`);
  }

  // Preferencias: Auto‑refresh
  getAutoRefreshPref(): Observable<AutoRefreshPref> {
    return this.http.get<AutoRefreshPref>(`${this.apiUrl}/prefs/auto-refresh`);
  }

  setAutoRefreshPref(enabled: boolean, interval_ms: number): Observable<AutoRefreshPref> {
    return this.http.post<AutoRefreshPref>(`${this.apiUrl}/prefs/auto-refresh`, { enabled, interval_ms });
  }

  // V2: Headers + Items
  getV2Headers(params: {
    page?: number; page_size?: number; ruc_emisor?: string; ruc_receptor?: string;
    year_month?: string; date_from?: string; date_to?: string; search?: string;
    emisor_nombre?: string; sort_by?: string;
  }): Observable<any> {
    // Limpiar params: omitir undefined, null y strings vacíos
    const qp: any = {};
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      if (typeof v === 'string') {
        const trimmed = v.trim();
        if (trimmed === '') return;
        qp[k] = trimmed;
      } else {
        qp[k] = v as any;
      }
    });
    return this.http.get<any>(`${this.apiUrl}/v2/invoices/headers`, { params: qp });
  }

  getV2InvoiceById(headerId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/v2/invoices/${headerId}`);
  }

  getV2Items(params: { page?: number; page_size?: number; header_id?: string; iva?: number; search?: string; year_month?: string; }): Observable<any> {
    // Limpiar params: omitir undefined, null y strings vacíos
    const qp: any = {};
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      if (typeof v === 'string') {
        const trimmed = v.trim();
        if (trimmed === '') return;
        qp[k] = trimmed;
      } else {
        qp[k] = v as any;
      }
    });
    return this.http.get<any>(`${this.apiUrl}/v2/invoices/items`, { params: qp });
  }

  // Eliminación de facturas V2
  deleteV2Invoice(headerId: string): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/v2/invoices/${headerId}`);
  }

  deleteV2InvoicesBulk(headerIds: string[]): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/v2/invoices/bulk-delete`, { header_ids: headerIds });
  }

  downloadInvoice(invoiceId: string): Observable<{ success: boolean, download_url: string, filename?: string, content_type?: string, message?: string }> {
    return this.http.get<{ success: boolean, download_url: string, filename?: string, content_type?: string, message?: string }>(`${this.apiUrl}/invoices/${invoiceId}/download`);
  }

  /**
   * Descarga el archivo directamente con autenticación (streaming)
   */
  downloadInvoiceFile(invoiceId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/invoices/${invoiceId}/file`, {
      responseType: 'blob'
    });
  }

  getV2DeleteInfo(headerId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/v2/invoices/${headerId}/delete-info`);
  }

  getV2BulkDeleteInfo(headerIds: string[]): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/v2/invoices/bulk-delete-info`, { header_ids: headerIds });
  }

  // Métodos de administración
  checkAdminStatus(): Observable<{ success: boolean, is_admin: boolean, email: string, message: string }> {
    return this.http.get<{ success: boolean, is_admin: boolean, email: string, message: string }>(`${this.apiUrl}/admin/check`);
  }

  getAdminUsers(page: number = 1, pageSize: number = 20): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/users`, {
      params: { page: page.toString(), page_size: pageSize.toString() }
    });
  }

  updateUserRole(email: string, role: string): Observable<{ success: boolean, message: string }> {
    return this.http.put<{ success: boolean, message: string }>(`${this.apiUrl}/admin/users/${email}/role`, { role });
  }

  updateUserStatus(email: string, status: string): Observable<{ success: boolean, message: string }> {
    return this.http.put<{ success: boolean, message: string }>(`${this.apiUrl}/admin/users/${email}/status`, { status });
  }

  getAdminStats(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/stats`);
  }

  // =====================================
  // PLANES Y SUSCRIPCIONES
  // =====================================

  // API Pública de planes (sin autenticación)
  getPublicPlans(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/plans`);
  }

  getPublicPlan(planCode: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/plans/${planCode}`);
  }

  // Métodos administrativos para planes
  getAdminPlans(includeInactive: boolean = false): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/plans`, {
      params: { include_inactive: includeInactive.toString() }
    });
  }

  createPlan(planData: any): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/admin/plans`, planData);
  }

  updatePlan(planCode: string, planData: any): Observable<any> {
    return this.http.put<any>(`${this.apiUrl}/admin/plans/${planCode}`, planData);
  }

  deletePlan(planCode: string): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/admin/plans/${planCode}`);
  }

  // Métodos de suscripciones
  getSubscriptionStats(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/subscriptions/stats`);
  }

  assignPlanToUser(subscriptionData: any): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/admin/subscriptions`, subscriptionData);
  }

  getUserSubscriptions(userEmail: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/subscriptions/user/${userEmail}`);
  }

  // Suscripción del usuario actual
  getUserSubscription(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/user/subscription`);
  }

  getUserSubscriptionHistory(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/user/subscription/history`);
  }

  // Verificar estado del trial del usuario
  getTrialStatus(): Observable<{ success: boolean, can_process: boolean, is_trial_user: boolean, trial_expired: boolean, message: string }> {
    return this.http.get<{ success: boolean, can_process: boolean, is_trial_user: boolean, trial_expired: boolean, message: string }>(`${this.apiUrl}/user/trial-status`);
  }

  requestPlanChange(planId: string, buyerData?: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/user/subscription/change-plan`, {
      plan_id: planId,
      buyer_data: buyerData
    });
  }

  // DEPRECATED: Usar cancelMySubscription() en su lugar
  cancelUserSubscription(): Observable<any> {
    return this.cancelMySubscription();
  }

  // Estadísticas filtradas
  getFilteredStats(filters: {
    start_date?: string,
    end_date?: string,
    user_email?: string
  }): Observable<any> {
    let params: any = {};
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
    if (filters.user_email) params.user_email = filters.user_email;

    return this.http.get<any>(`${this.apiUrl}/admin/stats/filtered`, { params });
  }

  // =====================================
  // RESETEO DE LÍMITES DE IA
  // =====================================

  // Reseteo mensual automático
  resetMonthlyAiLimits(): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/admin/ai-limits/reset-monthly`, {});
  }

  // Reseteo manual de un usuario específico
  resetUserAiLimits(userEmail: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/admin/ai-limits/reset-user/${userEmail}`, {});
  }

  // Estadísticas de reseteo
  getResetStats(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/ai-limits/reset-stats`);
  }

  // Estado del scheduler
  getSchedulerStatus(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/scheduler/status`);
  }

  // Ejecutar reseteo mensual manual
  executeMonthlyReset(): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/admin/ai-limits/reset-monthly`, {});
  }

  // =====================================
  // PAGOPAR / SUSCRIPCIONES
  // =====================================

  // PASO 2: Auto-crear/verificar cliente en Pagopar (se llama después del login)
  ensurePagoparCustomer(): Observable<{ success: boolean, pagopar_user_id: string, message: string }> {
    return this.http.post<{ success: boolean, pagopar_user_id: string, message: string }>(
      `/api/subscriptions/ensure-customer`,
      {}
    );
  }

  // PASO 3: Iniciar suscripción (obtener form_id para iframe o activar directamente si tiene tarjeta)
  subscribeToSelectedPlan(planCode: string): Observable<{
    success: boolean,
    form_id: string | null,
    pagopar_user_id: string,
    message?: string,
    subscription_active?: boolean
  }> {
    return this.http.post<{
      success: boolean,
      form_id: string | null,
      pagopar_user_id: string,
      message?: string,
      subscription_active?: boolean
    }>(
      `/api/subscriptions/subscribe`,
      { plan_code: planCode }
    );
  }

  // PASO 5: Confirmar tarjeta catastrada y crear suscripción
  confirmSubscriptionCard(): Observable<{ success: boolean, message: string, subscription: any }> {
    return this.http.post<{ success: boolean, message: string, subscription: any }>(
      `/api/subscriptions/confirm-card`,
      {}
    );
  }

  // Obtener mi suscripción activa
  getMySubscription(): Observable<{ success: boolean, subscription: any }> {
    return this.http.get<{ success: boolean, subscription: any }>(
      `/api/subscriptions/my-subscription`
    );
  }

  // Cancelar mi suscripción
  cancelMySubscription(): Observable<{ success: boolean, message: string }> {
    return this.http.post<{ success: boolean, message: string }>(
      `/api/subscriptions/cancel`,
      {}
    );
  }

  // Obtener métodos de pago
  getPaymentMethods(): Observable<any[]> {
    return this.http.get<any[]>(`/api/subscriptions/payment-methods`);
  }

  // Eliminar método de pago
  deletePaymentMethod(cardToken: string): Observable<{ success: boolean, message: string }> {
    return this.http.delete<{ success: boolean, message: string }>(
      `/api/subscriptions/payment-methods/${cardToken}`
    );
  }

  // Obtener planes de suscripción (nuevo endpoint)
  getSubscriptionPlans(): Observable<any> {
    return this.http.get<any>(`/api/subscriptions/plans`);
  }

  // =====================================
  // PAGOPAR / MÉTODOS DE PAGO (Legacy - para compatibilidad)
  // =====================================

  getCards(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/pagopar/cards`);
  }

  initAddCard(returnUrl: string, provider: 'Bancard' | 'uPay' = 'Bancard'): Observable<{ hash: string, pagopar_user_id: string }> {
    return this.http.post<{ hash: string, pagopar_user_id: string }>(`${this.apiUrl}/pagopar/cards/init`, {
      return_url: returnUrl,
      provider
    });
  }

  confirmCard(returnUrl: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/pagopar/cards/confirm`, {
      return_url: returnUrl
    });
  }

  deleteCard(cardToken: string): Observable<{ success: boolean }> {
    return this.http.delete<{ success: boolean }>(`${this.apiUrl}/pagopar/cards/${cardToken}`);
  }

  testPay(cardToken: string, orderHash: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/pagopar/pay`, {
      order_hash: orderHash,
      card_token: cardToken
    });
  }

  // Admin Subscriptions
  getAdminSubscriptions(page: number = 1, pageSize: number = 20, status: string = 'active'): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/subscriptions`, {
      params: { page: page.toString(), page_size: pageSize.toString(), status }
    });
  }

  retrySubscriptionCharge(subscriptionId: string): Observable<{ success: boolean, message: string }> {
    return this.http.post<{ success: boolean, message: string }>(`${this.apiUrl}/admin/subscriptions/${subscriptionId}/retry-charge`, {});
  }

  cancelSubscriptionAdmin(subscriptionId: string, reason: string = 'admin_action'): Observable<{ success: boolean, message: string }> {
    return this.http.post<{ success: boolean, message: string }>(
      `${this.apiUrl}/admin/subscriptions/${subscriptionId}/cancel`,
      { reason }
    );
  }

  getSubscriptionDetails(subscriptionId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/subscriptions/${subscriptionId}`);
  }

  updateSubscriptionStatus(subscriptionId: string, status: string): Observable<{ success: boolean, message: string }> {
    return this.http.post<{ success: boolean, message: string }>(
      `${this.apiUrl}/admin/subscriptions/${subscriptionId}/status`,
      { status }
    );
  }

  // Métodos genéricos HTTP para compatibilidad
  get(url: string, options?: any): Promise<any> {
    return this.http.get<any>(`${this.apiUrl}${url}`, options).toPromise();
  }

  post(url: string, data: any, options?: any): Promise<any> {
    return this.http.post<any>(`${this.apiUrl}${url}`, data, options).toPromise();
  }

  put(url: string, data: any, options?: any): Promise<any> {
    return this.http.put<any>(`${this.apiUrl}${url}`, data, options).toPromise();
  }

  delete(url: string, options?: any): Promise<any> {
    return this.http.delete<any>(`${this.apiUrl}${url}`, options).toPromise();
  }
}
