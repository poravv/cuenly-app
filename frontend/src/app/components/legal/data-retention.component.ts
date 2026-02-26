import { Component } from '@angular/core';

@Component({
    selector: 'app-data-retention',
    template: `
    <div class="legal-container">
      <div class="legal-card">
        <h1>Política de Retención de Datos</h1>
        <p class="last-updated">Última actualización: 24 de enero, 2026</p>
        
        <section>
          <h2>1. Principio de Retención</h2>
          <p>Cuenly mantiene sus datos procesados e información contable de forma indefinida mientras su cuenta esté activa. Sin embargo, aplicamos una política de limpieza para los archivos físicos originales (PDF, XML, Imágenes).</p>
        </section>

        <div class="retention-info-box">
          <h3>Resumen de Retención</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">Información Procesada:</span>
              <span class="value">Indefinido</span>
            </div>
            <div class="info-item">
              <span class="label">Archivos Originales:</span>
              <span class="value">5 Año</span>
            </div>
          </div>
        </div>

        <section>
          <h2>2. Purga de Archivos Físicos</h2>
          <p>Para optimizar el almacenamiento y cumplir con estándares de privacidad, Cuenly elimina automáticamente los archivos adjuntos originales que tengan más de **cinco años** de antigüedad.</p>
          <p><strong>Importante:</strong> La información ya extraída (montos, RUC, conceptos) permanecerá en su panel de control; solo el archivo original para descarga dejará de estar disponible.</p>
        </section>

        <section>
          <h2>3. Exportación y Respaldos</h2>
          <p>Recomendamos a los usuarios que requieran preservar los archivos físicos por más de un año realizar descargas periódicas o respaldos externos de sus documentos originales.</p>
        </section>

        <section>
          <h2>4. Eliminación de Cuenta</h2>
          <p>Si usted decide eliminar su cuenta en Cuenly, toda su información y archivos asociados serán eliminados permanentemente de nuestros servidores en un plazo no mayor a 30 días.</p>
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
    h2 { color: #6c5ce7; margin-top: 25px; margin-bottom: 12px; font-size: 1.4rem; }
    p { line-height: 1.6; color: #4b4b4b; margin-bottom: 15px; }
    
    .retention-info-box {
      background: #efedff;
      border-left: 5px solid #6c5ce7;
      padding: 20px;
      border-radius: 8px;
      margin: 25px 0;
    }
    .retention-info-box h3 { color: #6c5ce7; margin-top: 0; margin-bottom: 15px; }
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .info-item { display: flex; flex-direction: column; }
    .label { font-size: 0.9rem; color: #636e72; margin-bottom: 4px; }
    .value { font-weight: 700; color: #2d3436; font-size: 1.1rem; }

    .footer-actions { margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; }
    .btn-primary {
      background: #6c5ce7; color: white; border: none; padding: 12px 30px;
      border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.3s;
    }
    .btn-primary:hover { background: #5649c0; transform: translateY(-2px); }
  `]
})
export class DataRetentionComponent { }
