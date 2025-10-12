import { Injectable } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { FirebaseService } from './firebase.service';

@Injectable({
  providedIn: 'root'
})
export class AnalyticsService {
  
  constructor(
    private router: Router,
    private firebase: FirebaseService
  ) {
    this.initializeRouteTracking();
  }

  /**
   * Inicializa el tracking automático de rutas
   */
  private initializeRouteTracking(): void {
    this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe((event: NavigationEnd) => {
        // Obtener nombre de la página desde la ruta
        const pageName = this.getPageNameFromUrl(event.urlAfterRedirects);
        
        // Enviar evento de page_view
        this.firebase.trackPageView(pageName);
      });
  }

  /**
   * Convierte URL en nombre de página legible
   */
  private getPageNameFromUrl(url: string): string {
    if (url === '/' || url === '') return 'dashboard';
    
    const segments = url.split('/').filter(s => s);
    const mainPath = segments[0];
    
    const pageNames: { [key: string]: string } = {
      'dashboard': 'dashboard',
      'upload': 'upload',
      'upload-xml': 'upload_xml',
      'email-config': 'email_config',
      'help': 'help',
      'invoice-explorer': 'invoice_explorer',
      'invoices': 'invoices',
      'login': 'login',
      'subscription': 'subscription',
      'export-templates': 'export_templates',
      'admin': 'admin_panel',
      'plans': 'plans_management',
      'suspended': 'suspended',
      'invoice-processing': 'invoice_processing'
    };

    return pageNames[mainPath] || mainPath || 'unknown_page';
  }

  // Métodos de conveniencia
  trackUpload(fileType: string, fileSize: number): void {
    this.firebase.logEvent('file_upload', {
      file_type: fileType,
      file_size_kb: Math.round(fileSize / 1024)
    });
  }

  trackSearch(query: string, resultsCount: number): void {
    this.firebase.logEvent('search_performed', {
      query_length: query.length,
      results_count: resultsCount
    });
  }

  trackExport(templateId?: string): void {
    this.firebase.logEvent('export_action', { template_id: templateId });
  }
}