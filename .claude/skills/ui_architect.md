# UI Architect — Frontend Angular 15

Esta skill se activa al trabajar en el directorio `frontend/`.

## Mapa de Estructura

```
frontend/src/app/
├── app.module.ts               # Módulo raíz
├── app.component.ts            # Componente raíz
├── app-routing.module.ts       # Rutas principales
├── components/                 # Componentes de página y reutilizables
│   ├── dashboard/              # / — Dashboard principal
│   ├── invoices-v2/            # /facturas/todas — Lista de facturas
│   ├── invoices-stats/         # /facturas/estadisticas — Gráficos y stats
│   ├── invoice-explorer/       # /facturas/explorador — Búsqueda avanzada (parcial)
│   ├── invoices-shell/         # Shell/layout para rutas de facturas
│   ├── invoice-processing/     # /automatizacion/procesamiento — Procesar correos
│   ├── email-config/           # /automatizacion/correos — Config IMAP
│   ├── profile/
│   │   ├── profile.component.ts       # /cuenta/perfil
│   │   └── queue-events.component.ts  # /automatizacion/cola — Cola de jobs
│   ├── upload/                 # /facturas/subir — Upload PDF/imagen
│   ├── upload-xml/             # /facturas/subir-xml — Upload XML SIFEN
│   ├── export-templates/       # /facturas/exportar — Templates de exportación
│   │   ├── export-templates.component.ts      # Lista de templates
│   │   ├── template-editor.component.ts       # Editor de template
│   │   ├── template-export.component.ts       # Ejecutar exportación
│   │   └── template-preset-selector.component.ts
│   ├── subscription/           # /cuenta/suscripcion
│   ├── payment-methods/        # /cuenta/pagos — Tarjetas Pagopar
│   ├── bancard-iframe-modal/   # Modal iframe Bancard para agregar tarjeta
│   ├── pagopar-result/         # /pagopar/resultado/:hash
│   ├── help/                   # /cuenta/ayuda
│   ├── login/                  # Login con Google
│   ├── navbar/                 # Barra de navegación
│   ├── footer/
│   ├── trial-banner/           # Banner de trial activo
│   ├── suspended/              # Pantalla de cuenta suspendida
│   ├── legal/                  # Términos, privacidad, retención
│   │   ├── terms-conditions.component.ts
│   │   ├── privacy-policy.component.ts
│   │   └── data-retention.component.ts
│   ├── shared/
│   │   └── notification-container/  # Notificaciones toast
│   └── (admin components — cargados via lazy loading)
│       ├── admin-layout/       # Layout del panel admin
│       ├── admin-dashboard/    # Dashboard admin
│       ├── admin-users/        # Gestión de usuarios
│       ├── admin-plans/        # Gestión de planes
│       ├── admin-subscriptions/# Gestión de suscripciones
│       ├── admin-system/       # Info del sistema (IA, scheduler)
│       ├── admin-audit/        # Logs de auditoría
│       └── plans-management/   # CRUD de planes
├── services/                   # Capa de comunicación HTTP
│   ├── api.service.ts          # CENTRAL — todas las llamadas HTTP al backend
│   ├── auth.service.ts         # Firebase Auth (login/logout/token)
│   ├── user.service.ts         # Estado del usuario actual
│   ├── firebase.service.ts     # Firebase SDK init
│   ├── firebase-metrics.service.ts
│   ├── notification.service.ts # Toast notifications
│   ├── export-template.service.ts
│   ├── mongo-query.service.ts  # Queries MongoDB via API
│   ├── file-transfer.service.ts # Upload/download archivos
│   ├── analytics.service.ts
│   ├── analytics-debug.service.ts
│   ├── avatar-cache.service.ts
│   ├── extended-metrics.service.ts
│   └── observability.service.ts
├── guards/
│   ├── auth.guard.ts           # Requiere autenticación
│   ├── admin.guard.ts          # Requiere rol admin
│   ├── login.guard.ts          # Redirige si ya autenticado
│   └── profile.guard.ts        # Requiere perfil completo
├── interceptors/
│   ├── auth.interceptor.ts     # Agrega JWT a requests
│   ├── trial.interceptor.ts    # Verifica estado de trial
│   └── observability.interceptor.ts
├── models/
│   ├── invoice.model.ts        # Interfaces de factura
│   └── export-template.model.ts
├── state/                      # Akita (subutilizado)
│   └── session/
│       ├── session.store.ts
│       └── session.query.ts
├── modules/
│   └── admin/                  # Lazy-loaded admin module
│       ├── admin.module.ts
│       └── admin-routing.module.ts
└── styles/
    └── _variables.scss         # Design system (colores, espaciado, tipografía)
```

## Reglas Obligatorias

### 1. HTTP centralizado
- **TODA** llamada HTTP pasa por `api.service.ts`. Los componentes NUNCA importan `HttpClient` directamente.
- Servicios especializados (`export-template.service.ts`, `file-transfer.service.ts`) pueden existir pero deben usar `HttpClient` inyectado, no duplicar lógica de `api.service.ts`.

### 2. Change Detection
- Usar `ChangeDetectionStrategy.OnPush` en todos los componentes, especialmente los que renderizan listas o datos frecuentes.
- Inyectar `ChangeDetectorRef` y llamar `markForCheck()` después de actualizaciones async que no vengan de `| async` pipe.

### 3. Listas y *ngFor
- **SIEMPRE** usar `trackBy` en `*ngFor`. La función trackBy debe retornar un ID único del item.
- Esto previene re-renders innecesarios y flickering.

### 4. Cleanup de suscripciones
- Crear `private destroy$ = new Subject<void>()` en el componente.
- Aplicar `.pipe(takeUntil(this.destroy$))` a toda suscripción RxJS.
- En `ngOnDestroy()`: `this.destroy$.next(); this.destroy$.complete();`
- Esto previene memory leaks en intervalos, timers, y observables.

### 5. Estado con Akita
- El store Akita (`state/session/`) maneja el estado de sesión del usuario.
- Para features nuevas, considerar crear Store + Query + Service de Akita en vez de manejar estado local.
- Los componentes consumen datos via `Query` (observables), los `Service` actualizan el `Store`.
- Actualmente subutilizado — al agregar features nuevas, migrar hacia este patrón.

### 6. Diseño con Bootstrap 5
- Usar clases utilitarias de Bootstrap (`d-flex`, `gap-2`, `mb-3`, `text-muted`, etc.) antes de escribir CSS custom.
- Seguir el design system en `_variables.scss` para colores, tipografía y espaciado.
- Componentes responsive: usar grid de Bootstrap (`col-md-6`, `col-lg-4`) y clases `d-none d-md-block` para hide en mobile.

### 7. Notificaciones
- Usar `notification.service.ts` para mostrar toasts al usuario (success, error, warning).
- No usar `alert()` ni `console.log()` para feedback al usuario.

### 8. Guards y navegación
- `auth.guard.ts` protege rutas que requieren login.
- `admin.guard.ts` protege rutas `/admin/**`.
- `profile.guard.ts` requiere que el usuario tenga perfil completo.
- `login.guard.ts` redirige usuarios ya autenticados fuera del login.
- Al agregar rutas nuevas, aplicar los guards correspondientes en `app-routing.module.ts`.

### 9. Admin module (lazy loading)
- Todo lo admin se carga via lazy loading en `modules/admin/`.
- Componentes admin: `admin-dashboard`, `admin-users`, `admin-plans`, `admin-subscriptions`, `admin-system`, `admin-audit`.
- Al agregar funcionalidad admin, registrar en `admin-routing.module.ts` y `admin.module.ts`.

### 10. No console.log
- Prohibido `console.log()` en código de producción.
- Excepciones: `observability.service.ts`, `analytics-debug.service.ts`, `firebase-metrics.service.ts` (donde es intencional).
- Para debug temporal, eliminar antes de commit.
