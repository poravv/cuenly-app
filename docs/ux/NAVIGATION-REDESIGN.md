# 🧭 Sistema de Navegación Rediseñado

## Visión General

El nuevo sistema de navegación reduce la complejidad visual y agrupa funcionalidades relacionadas para mejorar la experiencia del usuario.

---

## Estructura Actual vs. Nueva

### ANTES (8 items principales)
```
Navbar
├── Dashboard
├── Gestión
├── Explorador
├── Facturas
├── Exportar
├── Subir Archivo
├── Ayuda
└── Perfil (Dropdown)
    ├── Mi Perfil
    ├── Cola de Procesamiento
    ├── Ayuda AI
    ├── Suscripción
    ├── Medios de Pago
    └── Admin (si aplica)
```

**Problemas:**
- Demasiados items compiten por atención
- Funciones relacionadas están separadas
- Poca claridad en la jerarquía
- Dificulta el escaneo visual

### DESPUÉS (4 secciones principales)

```
Navbar Simplificado
├── 🏠 Inicio (Dashboard unificado)
├── 📊 Facturas (Lista + Explorador + Stats)
├── ⚙️ Automatización (Correo + Procesamiento + Cola)
└── 👤 Cuenta (Perfil + Suscripción + Configuración)
```

**Beneficios:**
- Fácil de escanear
- Agrupación lógica
- Menos carga cognitiva
- Mejor para móvil

---

## Especificación Detallada

### 1. 🏠 Inicio (Dashboard)

**Ruta:** `/`

**Descripción:** Vista principal unificada con acceso a todas las acciones frecuentes.

**Contenido:**

```
┌─────────────────────────────────────────────────────┐
│  CUENLYAPP                    👤 Juan Pérez        │
│  ───────────────────────────────────────────────   │
│  🏠 Inicio  📊 Facturas  ⚙️ Automatización  👤     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Estado del Sistema                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✅ 2 correos conectados                     │   │
│  │ 📧 Última sync: hace 5 min                  │   │
│  │ 📊 125 facturas este mes                    │   │
│  │                                             │   │
│  │ [🔄 Procesar Ahora] [⚙️ Configurar]        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Resumen Rápido (Este mes)                         │
│  ┌──────────┬──────────┬──────────┐                │
│  │ 125      │ ₲ 45.5M  │ ₲ 364K   │                │
│  │ Facturas │ Total    │ Promedio │                │
│  └──────────┴──────────┴──────────┘                │
│  [Ver Todas] [Exportar]                            │
│                                                     │
│  [Gráfico de tendencia - últimos 6 meses]         │
│                                                     │
│  Últimas Facturas                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ • Factura 001-001-0123 - ₲ 150,000         │   │
│  │   Empresa XYZ - 22/02/2026                 │   │
│  │   [Ver] [Exportar]                         │   │
│  │─────────────────────────────────────────────│   │
│  │ • Factura 002-001-0456 - ₲ 250,000         │   │
│  │   Proveedor ABC - 21/02/2026               │   │
│  │   [Ver] [Exportar]                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Ver todas las facturas →]                        │
└─────────────────────────────────────────────────────┘
```

**Acciones Rápidas:**
- Procesar correos (botón prominente)
- Ver estado de sincronización
- Acceso directo a configuración
- Ver últimas facturas
- Exportar facturas del mes

**Características:**
- **Widget interactivo** de estado del sistema
- **Acciones contextuales** sin navegar
- **Actualizaciones en tiempo real**
- **Gráficos interactivos**

---

### 2. 📊 Facturas

**Ruta:** `/facturas`

**Descripción:** Vista consolidada de todas las facturas con explorador, lista y estadísticas.

**Tabs Internos:**

```
┌─────────────────────────────────────────────────────┐
│  📊 FACTURAS                                        │
│  ───────────────────────────────────────────────   │
│  [📋 Todas] [🔍 Explorador] [📈 Estadísticas]      │
└─────────────────────────────────────────────────────┘
```

#### Tab 1: Todas (Lista)

```
┌─────────────────────────────────────────────────────┐
│  [🔍 Buscar...]  [📅 Este mes ▼]  [⬇ Exportar]     │
│                                                     │
│  Mostrando 125 facturas                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ N°        │ Emisor    │ Fecha      │ Total  │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 001-0123  │ Empresa X │ 22/02/2026 │ 150K   │   │
│  │ [Ver Detalles] [Descargar PDF] [Exportar]   │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 002-0456  │ Proveedor │ 21/02/2026 │ 250K   │   │
│  │ [Ver Detalles] [Descargar PDF] [Exportar]   │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [← Anterior]  Página 1 de 5  [Siguiente →]       │
└─────────────────────────────────────────────────────┘
```

**Características:**
- Tabla responsiva (se convierte en cards en móvil)
- Búsqueda en tiempo real
- Filtros rápidos
- Acciones inline por factura
- Selección múltiple para exportar

#### Tab 2: Explorador (Búsqueda Avanzada)

```
┌─────────────────────────────────────────────────────┐
│  Búsqueda Avanzada                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ Filtros                                     │   │
│  │ [RUC Emisor...     ]                        │   │
│  │ [Razón Social...   ]                        │   │
│  │ [Desde] [___] a [___] (Rango de fechas)    │   │
│  │ [Monto desde] [___] a [___]                │   │
│  │ [IVA 10%] [IVA 5%] [Exento] (checkboxes)   │   │
│  │                                             │   │
│  │ [Limpiar] [🔍 Buscar]                       │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Resultados: 23 facturas encontradas               │
│                                                     │
│  [Tabla de resultados con acciones]                │
│                                                     │
│  [⬇ Exportar resultados]                           │
└─────────────────────────────────────────────────────┘
```

**Características:**
- Filtros colapsables
- Búsqueda por múltiples criterios
- Preview de resultados en tiempo real
- Exportación directa de resultados filtrados

#### Tab 3: Estadísticas

```
┌─────────────────────────────────────────────────────┐
│  Estadísticas y Análisis                           │
│                                                     │
│  [Este año ▼]                                      │
│                                                     │
│  Resumen General                                   │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │ Total    │ Promedio │ IVA 10%  │ IVA 5%   │     │
│  │ ₲ 545M   │ ₲ 364K   │ ₲ 45M    │ ₲ 22M    │     │
│  └──────────┴──────────┴──────────┴──────────┘     │
│                                                     │
│  [Gráfico de tendencia mensual]                    │
│                                                     │
│  Top Proveedores                                   │
│  [Gráfico de donut/pie]                            │
│                                                     │
│  [⬇ Exportar Reporte Completo]                     │
└─────────────────────────────────────────────────────┘
```

---

### 3. ⚙️ Automatización

**Ruta:** `/automatizacion`

**Descripción:** Centro de control para procesamiento automático de facturas.

**Sections:**

```
┌─────────────────────────────────────────────────────┐
│  ⚙️ AUTOMATIZACIÓN                                  │
│  ───────────────────────────────────────────────   │
│  [📧 Correos] [⏱ Programación] [📋 Cola] [🧪 Test] │
└─────────────────────────────────────────────────────┘
```

#### Section 1: Correos

```
┌─────────────────────────────────────────────────────┐
│  Cuentas de Correo Configuradas (2/3)              │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✅ Gmail - andres@gmail.com                 │   │
│  │    Última sync: hace 5 min | 47 facturas    │   │
│  │    [⚙️ Editar] [❌ Deshabilitar] [🧪 Probar]│   │
│  ├─────────────────────────────────────────────┤   │
│  │ ✅ Outlook - contabilidad@empresa.com       │   │
│  │    Última sync: hace 1 hora | 23 facturas   │   │
│  │    [⚙️ Editar] [❌ Deshabilitar] [🧪 Probar]│   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [➕ Agregar Nueva Cuenta de Correo]               │
│                                                     │
│  Términos de Búsqueda Globales                     │
│  factura, invoice, comprobante                     │
│  [Editar términos]                                 │
└─────────────────────────────────────────────────────┘
```

**Características:**
- Lista de cuentas con estado visual
- Acciones inline por cuenta
- Agregar nueva cuenta (abre modal rápido)
- Test de conexión individual

#### Section 2: Programación

```
┌─────────────────────────────────────────────────────┐
│  Sincronización Automática                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ ⏰ Frecuencia de sincronización             │   │
│  │                                             │   │
│  │ [○ Manual]  [● Cada 15 min]  [○ Cada hora] │   │
│  │ [○ Cada 6 horas]  [○ Diaria]               │   │
│  │                                             │   │
│  │ Próxima ejecución: 22/02/2026 15:15        │   │
│  │                                             │   │
│  │ [💾 Guardar Configuración]                  │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Procesar Ahora                                    │
│  [🚀 Ejecutar Procesamiento Inmediato]             │
│                                                     │
│  Procesamiento por Rango de Fechas                 │
│  [Desde] [___] a [___]                             │
│  [▶️ Procesar Rango]                                │
└─────────────────────────────────────────────────────┘
```

**Características:**
- Configuración visual simple
- Preview de próxima ejecución
- Acción de procesamiento manual
- Procesamiento por rango de fechas

#### Section 3: Cola de Procesamiento

```
┌─────────────────────────────────────────────────────┐
│  Cola de Procesamiento                             │
│                                                     │
│  Estado Actual: ✅ Inactivo                        │
│                                                     │
│  Próximos Jobs                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🕐 22/02/2026 15:15 - Sincronización Auto   │   │
│  │    Cuentas: Gmail, Outlook                  │   │
│  │    [Cancelar] [Ejecutar Ahora]              │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Historial Reciente                                │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✅ 22/02/2026 14:45 - Completado            │   │
│  │    15 facturas procesadas en 2m 34s         │   │
│  │    [Ver Detalles]                           │   │
│  ├─────────────────────────────────────────────┤   │
│  │ ✅ 22/02/2026 14:30 - Completado            │   │
│  │    8 facturas procesadas en 1m 12s          │   │
│  │    [Ver Detalles]                           │   │
│  ├─────────────────────────────────────────────┤   │
│  │ ⚠️  22/02/2026 14:15 - Con errores          │   │
│  │    3 facturas procesadas, 2 errores         │   │
│  │    [Ver Detalles] [Reintentar Errores]     │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Ver Historial Completo →]                        │
└─────────────────────────────────────────────────────┘
```

**Características:**
- Estado en tiempo real
- Lista de jobs programados
- Historial con detalles
- Acciones contextuales

#### Section 4: Test & Diagnóstico

```
┌─────────────────────────────────────────────────────┐
│  Herramientas de Diagnóstico                       │
│                                                     │
│  Probar Conexión de Correo                        │
│  [Seleccionar cuenta ▼]                            │
│  [🧪 Ejecutar Test]                                 │
│                                                     │
│  Resultado:                                        │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✅ Conexión exitosa                         │   │
│  │ 📬 Encontrados: 47 correos con facturas     │   │
│  │ ⏱ Tiempo de respuesta: 2.3s                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Probar Extracción de Factura                      │
│  [Subir XML/PDF para probar] [📁 Seleccionar]      │
│  [🔬 Analizar]                                      │
│                                                     │
│  Ver Logs del Sistema                              │
│  [📋 Ver Logs]                                      │
└─────────────────────────────────────────────────────┘
```

---

### 4. 👤 Cuenta

**Ruta:** `/cuenta`

**Descripción:** Gestión unificada de perfil, suscripción y configuración.

**Tabs:**

```
┌─────────────────────────────────────────────────────┐
│  👤 MI CUENTA                                       │
│  ───────────────────────────────────────────────   │
│  [👤 Perfil] [💳 Suscripción] [💰 Pagos] [⚙️ Config]│
└─────────────────────────────────────────────────────┘
```

#### Tab 1: Perfil

```
┌─────────────────────────────────────────────────────┐
│  Información Personal                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ [📷 Avatar]                                 │   │
│  │                                             │   │
│  │ Nombre: [Juan Pérez____________]           │   │
│  │ Email: juan@empresa.com (verificado)       │   │
│  │ Teléfono: [+595 981 123456_____]           │   │
│  │ RUC: [1234567-8_______________]            │   │
│  │ Dirección: [Asunción, Paraguay__]          │   │
│  │                                             │   │
│  │ [💾 Guardar Cambios]                        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Seguridad                                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ Autenticación: Google OAuth ✅              │   │
│  │ Última sesión: 22/02/2026 14:30            │   │
│  │                                             │   │
│  │ [🔐 Cambiar Contraseña]                     │   │
│  │ [🚪 Cerrar Sesión]                          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

#### Tab 2: Suscripción

```
┌─────────────────────────────────────────────────────┐
│  Plan Actual                                        │
│  ┌─────────────────────────────────────────────┐   │
│  │ 💎 PLAN PRO                                 │   │
│  │                                             │   │
│  │ ₲ 150,000 / mes                            │   │
│  │ Próximo cobro: 15/03/2026                  │   │
│  │                                             │   │
│  │ Beneficios:                                 │   │
│  │ ✅ 1,000 facturas/mes                       │   │
│  │ ✅ IA ilimitada                             │   │
│  │ ✅ Soporte prioritario                      │   │
│  │ ✅ 3 cuentas de correo                      │   │
│  │                                             │   │
│  │ [✨ Actualizar a PREMIUM]  [❌ Cancelar]    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Uso Este Mes                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ 📊 Facturas procesadas: 125 / 1,000        │   │
│  │ ████████░░░░░░░░░░░░  12.5%                │   │
│  │                                             │   │
│  │ 🤖 Uso de IA: Ilimitado ✓                  │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Comparar Planes                                   │
│  [📋 Ver Todos los Planes]                         │
└─────────────────────────────────────────────────────┘
```

#### Tab 3: Medios de Pago

```
┌─────────────────────────────────────────────────────┐
│  Métodos de Pago                                    │
│  ┌─────────────────────────────────────────────┐   │
│  │ 💳 •••• 4242  Visa                          │   │
│  │    Vence: 12/2027                           │   │
│  │    [🌟 Predeterminada] [✏️ Editar] [🗑️]     │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [➕ Agregar Nuevo Método de Pago]                 │
│                                                     │
│  Historial de Facturas                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ 📄 Feb 2026 - ₲ 150,000                     │   │
│  │    Pagado ✓ - [⬇ Descargar]                │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 📄 Ene 2026 - ₲ 150,000                     │   │
│  │    Pagado ✓ - [⬇ Descargar]                │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Ver Todo el Historial →]                         │
└─────────────────────────────────────────────────────┘
```

#### Tab 4: Configuración

```
┌─────────────────────────────────────────────────────┐
│  Preferencias de Notificaciones                    │
│  ┌─────────────────────────────────────────────┐   │
│  │ [✓] Email al completar procesamiento        │   │
│  │ [✓] Email si hay errores                    │   │
│  │ [ ] Email semanal con resumen               │   │
│  │ [✓] Notificaciones en la app               │   │
│  │                                             │   │
│  │ [💾 Guardar]                                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Exportación                                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ Formato preferido: [Excel ▼]               │   │
│  │ Template por defecto: [Contabilidad ▼]     │   │
│  │                                             │   │
│  │ [💾 Guardar]                                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Zona de Peligro                                   │
│  ┌─────────────────────────────────────────────┐   │
│  │ ⚠️  Acciones irreversibles                  │   │
│  │                                             │   │
│  │ [🗑️ Eliminar Todas las Facturas]           │   │
│  │ [❌ Cerrar Cuenta Permanentemente]          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Implementación Técnica

### Estructura de Componentes

```
app/
├── components/
│   ├── layout/
│   │   ├── navbar/
│   │   │   ├── navbar.component.ts
│   │   │   ├── navbar.component.html
│   │   │   └── navbar.component.scss
│   │   ├── mobile-nav/          (nuevo)
│   │   │   └── ...
│   │   └── sidebar/             (futuro)
│   │       └── ...
│   │
│   ├── pages/
│   │   ├── home/                (Dashboard)
│   │   │   └── ...
│   │   ├── invoices/            (Facturas con tabs)
│   │   │   ├── all-invoices/
│   │   │   ├── explorer/
│   │   │   └── stats/
│   │   ├── automation/          (Automatización con sections)
│   │   │   ├── email-accounts/
│   │   │   ├── scheduling/
│   │   │   ├── queue/
│   │   │   └── diagnostics/
│   │   └── account/             (Cuenta con tabs)
│   │       ├── profile/
│   │       ├── subscription/
│   │       ├── billing/
│   │       └── settings/
│   │
│   └── shared/
│       ├── quick-email-setup/
│       ├── quick-export/
│       └── ...
```

### Rutas

```typescript
// app-routing.module.ts
const routes: Routes = [
  {
    path: '',
    component: HomeComponent,
    canActivate: [AuthGuard]
  },
  {
    path: 'facturas',
    component: InvoicesComponent,
    canActivate: [AuthGuard],
    children: [
      { path: '', redirectTo: 'todas', pathMatch: 'full' },
      { path: 'todas', component: AllInvoicesComponent },
      { path: 'explorador', component: ExplorerComponent },
      { path: 'estadisticas', component: StatsComponent }
    ]
  },
  {
    path: 'automatizacion',
    component: AutomationComponent,
    canActivate: [AuthGuard],
    children: [
      { path: '', redirectTo: 'correos', pathMatch: 'full' },
      { path: 'correos', component: EmailAccountsComponent },
      { path: 'programacion', component: SchedulingComponent },
      { path: 'cola', component: QueueComponent },
      { path: 'diagnostico', component: DiagnosticsComponent }
    ]
  },
  {
    path: 'cuenta',
    component: AccountComponent,
    canActivate: [AuthGuard],
    children: [
      { path: '', redirectTo: 'perfil', pathMatch: 'full' },
      { path: 'perfil', component: ProfileComponent },
      { path: 'suscripcion', component: SubscriptionComponent },
      { path: 'pagos', component: BillingComponent },
      { path: 'configuracion', component: SettingsComponent }
    ]
  },
  // Admin
  {
    path: 'admin',
    loadChildren: () => import('./modules/admin/admin.module').then(m => m.AdminModule),
    canActivate: [AuthGuard, AdminGuard]
  },
  // Redirects para compatibilidad
  { path: 'manage-invoices', redirectTo: 'automatizacion', pathMatch: 'full' },
  { path: 'invoice-explorer', redirectTo: 'facturas/explorador', pathMatch: 'full' },
  { path: 'invoice-list', redirectTo: 'facturas/todas', pathMatch: 'full' },
  { path: 'email-settings', redirectTo: 'automatizacion/correos', pathMatch: 'full' },
  { path: 'subscription', redirectTo: 'cuenta/suscripcion', pathMatch: 'full' },
  { path: 'profile', redirectTo: 'cuenta/perfil', pathMatch: 'full' }
];
```

### Componente Navbar

```typescript
// navbar.component.ts
export class NavbarComponent implements OnInit {
  
  // Navegación principal
  mainNav = [
    {
      label: 'Inicio',
      icon: 'bi-house-fill',
      route: '/',
      exact: true
    },
    {
      label: 'Facturas',
      icon: 'bi-receipt',
      route: '/facturas',
      badge: null,     // Se puede agregar contador
      submenu: [
        { label: 'Todas', route: '/facturas/todas' },
        { label: 'Explorador', route: '/facturas/explorador' },
        { label: 'Estadísticas', route: '/facturas/estadisticas' }
      ]
    },
    {
      label: 'Automatización',
      icon: 'bi-gear-wide-connected',
      route: '/automatizacion',
      submenu: [
        { label: 'Cuentas de Correo', route: '/automatizacion/correos' },
        { label: 'Programación', route: '/automatizacion/programacion' },
        { label: 'Cola', route: '/automatizacion/cola' },
        { label: 'Diagnóstico', route: '/automatizacion/diagnostico' }
      ]
    }
  ];
  
  // Menú de usuario (dropdown)
  userMenu = [
    {
      label: 'Mi Perfil',
      icon: 'bi-person-circle',
      route: '/cuenta/perfil'
    },
    {
      label: 'Suscripción',
      icon: 'bi-credit-card',
      route: '/cuenta/suscripcion'
    },
    {
      label: 'Configuración',
      icon: 'bi-gear',
      route: '/cuenta/configuracion'
    },
    { divider: true },
    {
      label: 'Ayuda',
      icon: 'bi-question-circle',
      action: () => this.openHelp()
    },
    {
      label: 'Cerrar Sesión',
      icon: 'bi-box-arrow-right',
      action: () => this.logout()
    }
  ];
  
  // Estado
  currentUser$ = this.userService.currentUser$;
  isMenuOpen = false;
  
  constructor(
    private router: Router,
    private userService: UserService,
    private authService: AuthService
  ) {}
  
  isActive(route: string, exact = false): boolean {
    if (exact) {
      return this.router.url === route;
    }
    return this.router.url.startsWith(route);
  }
  
  toggleMenu(): void {
    this.isMenuOpen = !this.isMenuOpen;
  }
  
  closeMenu(): void {
    this.isMenuOpen = false;
  }
  
  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
```

---

## Responsive Behavior

### Desktop (> 992px)
- Navbar horizontal completo
- Todos los items visibles
- Submenús en hover/click

### Tablet (768px - 992px)
- Navbar colapsable con hamburger
- Items en menú vertical
- Submenús expandibles

### Mobile (< 768px)
- Bottom navigation bar (opcional)
- Hamburger menu
- Iconos simplificados

```scss
// Responsive Navbar
.navbar {
  @media (max-width: 768px) {
    .nav-item {
      .nav-label {
        display: none; // Solo iconos en móvil
      }
    }
  }
}

// Bottom navigation para móvil
.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  display: none;
  z-index: 1000;
  
  @media (max-width: 768px) {
    display: flex;
    justify-content: space-around;
    padding: 8px 0;
  }
  
  .nav-item {
    flex: 1;
    text-align: center;
    padding: 8px;
    
    i {
      font-size: 1.5rem;
      display: block;
      margin-bottom: 4px;
    }
    
    span {
      font-size: 0.75rem;
    }
    
    &.active {
      color: #4F46E5;
    }
  }
}
```

---

## Migración Gradual

### Fase 1: Dual Navigation
- Mantener navbar antiguo como fallback
- Agregar nuevo navbar con feature flag
- Permitir a usuarios probar y dar feedback

### Fase 2: Soft Launch
- Activar para usuarios nuevos por defecto
- Usuarios existentes pueden optar-in
- Recopilar métricas

### Fase 3: Full Rollout
- Activar para todos
- Deprecar navbar antiguo
- Limpiar código legacy

---

## Testing

### E2E Tests

```typescript
describe('Navigation', () => {
  it('should navigate between main sections', () => {
    cy.visit('/');
    cy.get('[data-test="nav-facturas"]').click();
    cy.url().should('include', '/facturas');
  });
  
  it('should show active state correctly', () => {
    cy.visit('/facturas');
    cy.get('[data-test="nav-facturas"]').should('have.class', 'active');
  });
  
  it('should open submenu on hover', () => {
    cy.get('[data-test="nav-facturas"]').trigger('mouseover');
    cy.get('[data-test="submenu-facturas"]').should('be.visible');
  });
});
```

---

## Métricas de Éxito

```typescript
interface NavigationMetrics {
  avgClicksToDestination: number;        // Target: < 2
  primaryNavUsage: Record<string, number>; // Identificar items más usados
  submenuEngagement: number;             // Tasa de uso de submenús
  mobileVsDesktop: {
    mobile: number;
    desktop: number;
  };
  userFeedback: {
    satisfaction: number;                // Target: > 4/5
    easiestToFind: string;
    hardestToFind: string;
  };
}
```

---

**Próximos Pasos:**
1. Crear prototipos interactivos en Figma
2. Implementar navbar base
3. Test con usuarios
4. Iterar basado en feedback
