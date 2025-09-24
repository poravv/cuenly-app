# Sistema de Notificaciones - CuenlyApp

Este documento describe el nuevo sistema de notificaciones moderno y reutilizable implementado en CuenlyApp.

## 🎯 Características

- **Moderno y Elegante**: Diseño atractivo con animaciones suaves
- **Tipos de Notificación**: Success, Error, Warning, Info
- **Auto-dismiss**: Se cierran automáticamente después de un tiempo configurable
- **Acciones Personalizadas**: Botones de acción opcional
- **Persistentes**: Opción para notificaciones que no se cierran automáticamente
- **Responsive**: Adaptado para móviles y tablets
- **Accesible**: Soporte para screen readers
- **Theme Support**: Compatible con modo oscuro

## 🚀 Uso Básico

### 1. Inyectar el servicio

```typescript
import { NotificationService } from '../../services/notification.service';

constructor(private notificationService: NotificationService) {}
```

### 2. Mostrar notificaciones

```typescript
// Notificación de éxito
this.notificationService.success('Operación completada exitosamente');

// Notificación de error
this.notificationService.error('Error al procesar la solicitud');

// Notificación de advertencia
this.notificationService.warning('Su sesión expirará pronto');

// Notificación de información
this.notificationService.info('Nueva actualización disponible');
```

### 3. Con títulos personalizados

```typescript
this.notificationService.success(
  'El archivo se descargó correctamente',
  'Descarga completada'
);
```

### 4. Con opciones avanzadas

```typescript
this.notificationService.info(
  'Se encontraron cambios no guardados',
  'Cambios pendientes',
  {
    duration: 10000,        // 10 segundos
    persistent: true,       // No se cierra automáticamente
    action: {
      label: 'Guardar',
      handler: () => {
        // Lógica para guardar
        this.notificationService.success('Guardado exitosamente');
      }
    }
  }
);
```

## 🔧 Configuración

### Duraciones por defecto:
- **Success**: 4 segundos
- **Info**: 5 segundos
- **Warning**: 6 segundos
- **Error**: 8 segundos

### Posición:
- Desktop: Esquina superior derecha
- Mobile: Ancho completo en la parte superior

## 🎨 Estilos

Las notificaciones incluyen:
- Iconos diferenciados por tipo
- Colores semánticamente apropiados
- Animaciones de entrada y salida
- Barra de progreso para auto-dismiss
- Sombras y efectos modernos

## 📱 Responsive

- **Desktop**: Máximo 400px de ancho, posición fija
- **Tablet**: Se adapta al ancho disponible
- **Mobile**: Ancho completo con márgenes reducidos

## ♿ Accesibilidad

- Botón de cierre con `aria-label`
- Soporte para navegación con teclado
- Colores con suficiente contraste
- Texto legible en todos los tamaños

## 🔄 Migración desde Alerts

### Antes:
```typescript
alert('Error al guardar');
```

### Después:
```typescript
this.notificationService.error('Error al guardar los datos');
```

### Confirmaciones:
```typescript
// Antes
if (confirm('¿Está seguro?')) {
  // hacer algo
}

// Después
this.notificationService.warning(
  '¿Está seguro de continuar con esta acción?',
  'Confirmar acción',
  {
    persistent: true,
    action: {
      label: 'Continuar',
      handler: () => {
        // hacer algo
      }
    }
  }
);
```

## 📦 Archivos del Sistema

```
src/app/
├── services/
│   └── notification.service.ts
├── components/shared/notification-container/
│   ├── notification-container.component.ts
│   ├── notification-container.component.html
│   ├── notification-container.component.scss
│   └── notification-usage-example.ts
└── app.component.html (incluye <app-notification-container>)
```

## 🎯 Ejemplos Prácticos

### Exportación de archivos:
```typescript
this.notificationService.success(
  `El archivo "${filename}" se ha descargado correctamente.`,
  'Exportación completada'
);
```

### Errores de validación:
```typescript
this.notificationService.warning('Debe completar todos los campos obligatorios');
```

### Errores de conexión:
```typescript
this.notificationService.error(
  'No se pudo conectar al servidor. Verifique su conexión e intente nuevamente.',
  'Error de conexión'
);
```

### Información del sistema:
```typescript
this.notificationService.info(
  'Se han aplicado nuevas configuraciones. La página se recargará automáticamente.',
  'Configuración actualizada'
);
```

---

**Nota**: El sistema reemplaza completamente los `alert()` básicos por notificaciones modernas y mejoradas que proporcionan una mejor experiencia de usuario.