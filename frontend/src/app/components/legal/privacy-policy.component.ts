import { Component } from '@angular/core';

@Component({
    selector: 'app-privacy-policy',
    template: `
    <div class="legal-container">
      <div class="legal-card">
        <h1>Política de Privacidad</h1>
        <p class="last-updated">Última actualización: 24 de enero, 2026</p>
        
        <section>
          <h2>1. Recolección de Datos</h2>
          <p>Cuenly recolecta información necesaria para la gestión de sus facturas:</p>
          <ul>
            <li>Información de contacto (Nombre, Email).</li>
            <li>Configuración de cuentas de correo (cifrado).</li>
            <li>Contenido de facturas procesadas.</li>
          </ul>
        </section>

        <section>
          <h2>2. Uso de la Información</h2>
          <p>Utilizamos sus datos exclusivamente para proveer el servicio de extracción y organización de facturas. No compartimos su información con terceros para fines publicitarios.</p>
        </section>

        <section>
          <h2>3. Seguridad de los Datos</h2>
          <p>Implementamos medidas de seguridad robustas:</p>
          <ul>
            <li>Cifrado de credenciales sensibles.</li>
            <li>Almacenamiento seguro de archivos.</li>
            <li>Uso de tokens seguros para comunicación Frontend-Backend.</li>
          </ul>
        </section>

        <section>
          <h2>4. Servicios de Terceros</h2>
          <p>Utilizamos <strong>OpenAI</strong> para el procesamiento de IA y <strong>Pagopar</strong> para la gestión de pagos. Ambos proveedores cumplen con altos estándares de seguridad y privacidad.</p>
        </section>

        <section>
          <h2>5. Sus Derechos</h2>
          <p>Usted tiene derecho a acceder, rectificar o eliminar sus datos personales de nuestro sistema en cualquier momento a través de la configuración de su cuenta.</p>
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
    h2 { color: #00b894; margin-top: 25px; margin-bottom: 12px; font-size: 1.4rem; }
    p { line-height: 1.6; color: #4b4b4b; margin-bottom: 15px; }
    ul { margin-bottom: 20px; padding-left: 20px; }
    li { margin-bottom: 8px; color: #4b4b4b; }
    .footer-actions { margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; }
    .btn-primary {
      background: #00b894; color: white; border: none; padding: 12px 30px;
      border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.3s;
    }
    .btn-primary:hover { background: #009475; transform: translateY(-2px); }
  `]
})
export class PrivacyPolicyComponent { }
