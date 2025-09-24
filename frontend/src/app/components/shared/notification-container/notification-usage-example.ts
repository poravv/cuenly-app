// Ejemplo de uso del NotificationService en cualquier componente

import { Component } from '@angular/core';
import { NotificationService } from 'src/app/services/notification.service';


@Component({
  selector: 'app-example',
  template: `
    <div class="d-flex gap-2 p-3">
      <button class="btn btn-success" (click)="showSuccess()">Éxito</button>
      <button class="btn btn-danger" (click)="showError()">Error</button>
      <button class="btn btn-warning" (click)="showWarning()">Advertencia</button>
      <button class="btn btn-info" (click)="showInfo()">Información</button>
      <button class="btn btn-secondary" (click)="showWithAction()">Con Acción</button>
    </div>
  `
})
export class ExampleComponent {
  constructor(private notificationService: NotificationService) {}

  showSuccess(): void {
    this.notificationService.success(
      'La operación se completó correctamente',
      'Operación exitosa'
    );
  }

  showError(): void {
    this.notificationService.error(
      'Ocurrió un error al procesar la solicitud. Por favor, intente nuevamente.',
      'Error en la operación'
    );
  }

  showWarning(): void {
    this.notificationService.warning(
      'Su sesión expirará en 5 minutos. Guarde su trabajo.',
      'Sesión por expirar'
    );
  }

  showInfo(): void {
    this.notificationService.info(
      'Nueva actualización disponible. Reinicie la aplicación para aplicar los cambios.',
      'Actualización disponible'
    );
  }

  showWithAction(): void {
    this.notificationService.info(
      'Se encontraron cambios no guardados en el formulario.',
      'Cambios no guardados',
      {
        persistent: true,
        action: {
          label: 'Guardar',
          handler: () => {
            // Lógica para guardar
            this.notificationService.success('Cambios guardados correctamente');
          }
        }
      }
    );
  }
}

/* 
INSTRUCCIONES DE USO:

1. Inyectar el servicio en el constructor:
   constructor(private notificationService: NotificationService) {}

2. Usar los métodos del servicio:
   
   // Notificación de éxito
   this.notificationService.success('Mensaje de éxito');
   
   // Notificación de error
   this.notificationService.error('Mensaje de error');
   
   // Notificación de advertencia
   this.notificationService.warning('Mensaje de advertencia');
   
   // Notificación de información
   this.notificationService.info('Mensaje de información');
   
   // Con título personalizado
   this.notificationService.success('Mensaje', 'Título personalizado');
   
   // Con opciones avanzadas
   this.notificationService.info('Mensaje', 'Título', {
     duration: 10000,        // 10 segundos
     persistent: true,       // No se cierra automáticamente
     action: {
       label: 'Acción',
       handler: () => { /* hacer algo */ }
     }
   });

3. REEMPLAZAR ALERTS EXISTENTES:

   // Antes:
   alert('Error al guardar');
   
   // Después:
   this.notificationService.error('Error al guardar los datos');
   
   // Antes:
   if (confirm('¿Está seguro?')) { /* acción */ }
   
   // Después:
   this.notificationService.warning('¿Está seguro de continuar?', 'Confirmar acción', {
     persistent: true,
     action: {
       label: 'Continuar',
       handler: () => { /* acción */ }
     }
   });
*/