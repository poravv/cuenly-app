import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  template: `
    <footer class="app-footer mt-5">
      <div class="container py-4">
        <div class="row align-items-center text-center text-md-start">
          <div class="col-md-6 mb-3 mb-md-0">
            <div class="brand d-flex align-items-center justify-content-center justify-content-md-start mb-1">
              <div class="footer-logo me-2">
                <img src="assets/logo.png" alt="CuenlyApp Logo" class="logo-image">
              </div>
              <strong>CuenlyApp</strong>
            </div>
            <div class="text-muted small">
              Automatización inteligente para la extracción de datos de facturas desde correos electrónicos.
            </div>
          </div>
          <div class="col-md-6">
            <nav class="footer-nav d-flex gap-3 flex-wrap justify-content-center justify-content-md-end">
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
    .footer-logo { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; }
    .footer-logo .logo-image { width: 100%; height: 100%; object-fit: contain; }
  `]
})
export class FooterComponent {
  currentYear = new Date().getFullYear();
}
