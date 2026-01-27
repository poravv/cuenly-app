import { Component } from '@angular/core';

@Component({
    selector: 'app-terms-conditions',
    template: `
    <div class="legal-container">
      <div class="legal-card">
        <h1>Términos y Condiciones de Uso</h1>
        <p class="last-updated">Última actualización: 24 de enero, 2026</p>
        
        <section>
          <h2>1. Aceptación de los Términos</h2>
          <p>Al acceder y utilizar Cuenly, usted acepta estar sujeto a estos Términos y Condiciones. Si no está de acuerdo con alguna parte de estos términos, no podrá utilizar nuestro servicio.</p>
        </section>

        <section>
          <h2>2. Descripción del Servicio</h2>
          <p>Cuenly es una plataforma de gestión de facturas que utiliza inteligencia artificial para extraer información de correos electrónicos y documentos adjuntos (PDF, XML, Imágenes).</p>
        </section>

        <section>
          <h2>3. Cuentas de Usuario</h2>
          <p>Usted es responsable de mantener la confidencialidad de su cuenta y contraseña. Cuenly utiliza autenticación de terceros (Firebase) para garantizar la seguridad de su acceso.</p>
        </section>

        <section>
          <h2>4. Uso de IA y OpenAI</h2>
          <p>Cuenly utiliza servicios de OpenAI para procesar sus documentos. Al utilizar el servicio, usted acepta que el contenido de sus facturas sea procesado por estos modelos de IA de forma segura y privada.</p>
        </section>

        <section>
          <h2>5. Suscripciones y Pagos</h2>
          <p>Los servicios premium están sujetos a suscripciones mensuales procesadas a través de Pagopar. La falta de pago resultará en la degradación de su cuenta al plan básico.</p>
        </section>

        <section>
          <h2>6. Limitación de Responsabilidad</h2>
          <p>Cuenly no se hace responsable de errores en la extracción de datos realizados por la IA. El usuario debe verificar la información antes de utilizarla para fines legales o contables.</p>
        </section>

        <div class="footer-actions">
          <button class="btn-primary" routerLink="/">Volver al Dashboard</button>
        </div>
      </div>
    </div>
  `,
    styles: [`
    .legal-container {
      padding: 40px 20px;
      max-width: 900px;
      margin: 0 auto;
      background: var(--bg-color, #f8f9fa);
      min-height: 100vh;
    }
    .legal-card {
      background: white;
      padding: 40px;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.05);
    }
    h1 { color: #2d3436; margin-bottom: 8px; font-size: 2.2rem; }
    .last-updated { color: #636e72; font-style: italic; margin-bottom: 30px; }
    h2 { color: #0984e3; margin-top: 25px; margin-bottom: 12px; font-size: 1.4rem; }
    p { line-height: 1.6; color: #4b4b4b; margin-bottom: 15px; }
    section { margin-bottom: 20px; }
    .footer-actions { margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; }
    .btn-primary {
      background: #0984e3; color: white; border: none; padding: 12px 30px;
      border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.3s;
    }
    .btn-primary:hover { background: #074494; transform: translateY(-2px); }
  `]
})
export class TermsConditionsComponent { }
