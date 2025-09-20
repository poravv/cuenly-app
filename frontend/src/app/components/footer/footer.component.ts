import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  template: `
    <footer class="app-footer mt-5">
      <div class="container py-4">
        <div class="row align-items-center">
          <div class="col-md-6 mb-3 mb-md-0">
            <div class="brand d-flex align-items-center mb-1">
              <i class="bi bi-receipt me-2 text-primary"></i>
              <strong>CuenlyApp</strong>
            </div>
            <div class="text-muted small">
              Automatización inteligente para la extracción de datos de facturas desde correos electrónicos.
            </div>
          </div>
          <div class="col-md-6">
            <nav class="footer-nav d-flex gap-3 justify-content-md-end">
              <a class="link" routerLink="/">Dashboard</a>
              
              <a class="link" routerLink="/upload">Subir PDF</a>
              <a class="link" routerLink="/upload-xml">Subir XML</a>
            </nav>
          </div>
        </div>
      </div>
      <div class="bottom text-center py-3">
        © {{currentYear}} CuenlyApp
      </div>
    </footer>
  `,
  styles: [`
    .app-footer { background: var(--color-surface); border-top: 1px solid var(--color-border); color: var(--color-text); }
    .app-footer .brand strong { font-weight: 800; letter-spacing: .2px; }
    .app-footer .footer-nav .link { color: var(--color-muted); text-decoration: none; font-weight: 600; }
    .app-footer .footer-nav .link:hover { color: var(--primary); }
    .app-footer .bottom { background: #F3F5FA; color: var(--color-muted); }
  `]
})
export class FooterComponent {
  currentYear = new Date().getFullYear();
}
