# 🎨 Plan de Transformación UX/UI de CuenlyApp

**Fecha:** 24 de febrero de 2026  
**Versión:** 1.0  
**Estado:** Planificación

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Análisis de Problemas Actuales](#análisis-de-problemas-actuales)
3. [Principios de Diseño](#principios-de-diseño)
4. [Arquitectura de Información](#arquitectura-de-información)
5. [Flujos Rediseñados](#flujos-rediseñados)
6. [Sistema de Diseño](#sistema-de-diseño)
7. [Roadmap de Implementación](#roadmap-de-implementación)

---

## 🎯 Resumen Ejecutivo

### Objetivo Principal
Transformar CuenlyApp en una aplicación moderna, intuitiva y eficiente que reduzca significativamente los clics necesarios para completar tareas comunes, mejorando la experiencia del usuario sin sacrificar funcionalidad.

### Métricas de Éxito
- **Reducir de 8+ clics a 3 clics** para configurar un correo
- **Reducir de 5 clics a 1 clic** para procesar facturas
- **Aumentar tasa de completación** de onboarding de 40% a 85%
- **Reducir tiempo de primera factura** de 15 min a 3 min
- **Aumentar satisfacción del usuario** de 6/10 a 9/10

### Filosofía
> "Menos clics, más valor. Menos pantallas, más claridad."

---

## 🔍 Análisis de Problemas Actuales

### 1. Navegación Fragmentada

**Problema:** El usuario debe navegar entre múltiples pantallas para completar flujos relacionados.

**Ejemplos:**
- Configurar correo → Ir a "Gestión" → Procesar → Volver a Dashboard
- Ver facturas → Exportar → Configurar template → Volver
- Dashboard → No tiene acciones directas

**Impacto:** Alta fricción, abandono en onboarding

### 2. Configuración de Correo Compleja

**Problema:** El proceso actual requiere:
1. Click en navbar → "Configuración"
2. Click en "Agregar Correo"
3. Seleccionar proveedor
4. Llenar formulario extenso
5. Configurar términos de búsqueda manualmente
6. Configurar sinónimos (panel avanzado)
7. Guardar
8. Volver a otra pantalla
9. Hacer clic en "Procesar"

**Total: 9+ clics y navegación entre 3 pantallas**

### 3. Falta de Contexto Visual

**Problema:** 
- Sin wizards o steppers de progreso
- Sin feedback visual de estado
- Sin ayuda contextual inline
- Formularios extensos sin agrupación lógica

### 4. Información Dispersa

**Problema:**
- Estadísticas en Dashboard
- Gestión en otra pantalla
- Configuración en otra
- Exportación separada
- Sin vista unificada del estado

### 5. Experiencia Móvil Deficiente

**Problema:**
- Navbar ocupa mucho espacio
- Formularios no optimizados para móvil
- Tablas horizontales difíciles de leer
- Botones pequeños

---

## 🎨 Principios de Diseño

### 1. **Progressive Disclosure**
Mostrar solo lo esencial primero, revelar lo avanzado bajo demanda.

```
✅ Correcto:
- Configuración básica visible
- Botón "Opciones Avanzadas" colapsable

❌ Incorrecto:
- Todo el formulario extenso visible
```

### 2. **Contextual Actions**
Las acciones deben estar donde el usuario las necesita, no en menús distantes.

```
✅ Correcto:
- Botón "Procesar Ahora" en el dashboard junto a stats
- "Configurar Correo" inline cuando no hay cuentas

❌ Incorrecto:
- Usuario debe ir a navbar → Gestión → Procesar
```

### 3. **Unified Workflows**
Un flujo debe completarse en una sola pantalla siempre que sea posible.

```
✅ Correcto:
- Wizard inline: Configurar → Probar → Procesar (una pantalla)

❌ Incorrecto:
- Pantalla 1: Configurar
- Pantalla 2: Probar
- Pantalla 3: Procesar
```

### 4. **Smart Defaults**
Pre-llenar con valores inteligentes basados en el contexto.

```
✅ Correcto:
- Gmail detectado → pre-fill host, port, SSL
- Términos comunes: "factura", "invoice" ya incluidos

❌ Incorrecto:
- Campos vacíos, usuario llena todo manualmente
```

### 5. **Visual Hierarchy**
Guiar la atención con tamaño, color y posición.

```
Primario (Grande, Color): Acción principal
Secundario (Mediano, Outline): Acciones alternativas
Terciario (Pequeño, Link): Opciones avanzadas
```

---

## 🗂️ Arquitectura de Información

### Estructura Actual (Problemática)

```
Navbar (8 items)
├── Dashboard (solo lectura, sin acciones)
├── Gestión (procesamiento)
├── Explorador (búsqueda avanzada)
├── Facturas (lista completa)
├── Exportar (templates)
├── Subir Archivo (upload manual)
├── Perfil (dropdown)
└── [Configuración distribuida en múltiples lugares]
```

**Problemas:**
- Demasiados items en navbar
- Funciones relacionadas separadas
- Sin jerarquía clara
- Configuración oculta

### Nueva Arquitectura (Propuesta)

```
Navbar Compacto (4 sections)
├── 🏠 Inicio (Dashboard unificado CON acciones)
├── 📊 Facturas (Explorador + Lista + Stats)
├── ⚙️ Automatización (Correo + Procesamiento + Cola)
└── 👤 Cuenta (Perfil + Suscripción + Ayuda)

Secundario (Tabs contextuales dentro de cada sección)
```

### Dashboard Unificado (Nueva Estructura)

```
┌─────────────────────────────────────────────┐
│  CUENLYAPP - Dashboard                      │
├─────────────────────────────────────────────┤
│                                             │
│  [Estado del Sistema - Widget Interactivo] │
│   ✅ 2 correos configurados                 │
│   📧 Última sincronización: hace 5 min      │
│   [Procesar Ahora] [Configurar]             │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │  Resumen (Este Mes)                   │ │
│  │  📄 125 facturas  💰 ₲ 45.5M          │ │
│  │  [Ver Todas] [Exportar]               │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  [Gráfico de Tendencias - Interactivo]     │
│                                             │
│  [Últimas Facturas - Quick Actions]        │
│   • Factura 001-001-0123 - ₲ 150,000       │
│     [Ver Detalles] [Exportar]              │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 🔄 Flujos Rediseñados

### 1. Onboarding Simplificado (First-Time User)

#### Flujo Actual vs. Nuevo

**ANTES (9+ pasos):**
1. Login → Dashboard vacío
2. Click navbar → Buscar "Configuración"
3. Click "Agregar Correo"
4. Seleccionar proveedor
5. Llenar formulario largo
6. Configurar términos de búsqueda
7. Guardar
8. Navegar a "Gestión"
9. Click "Procesar"
10. Esperar resultado

**DESPUÉS (3 pasos):**
1. Login → **Dashboard con Wizard Inline**
2. **"Conecta tu primer correo"** (formulario inteligente en modal)
   - Detecta Gmail/Outlook automáticamente
   - Pre-fill automático de configuración
   - Validación en tiempo real
   - Botón: **"Guardar y Procesar Primera Sincronización"**
3. Ver resultados inmediatamente en dashboard

**Reducción: 70% menos pasos**

#### Diseño del Wizard de Onboarding

```
┌────────────────────────────────────────────────────┐
│  🎉 ¡Bienvenido a CuenlyApp!                       │
│                                                    │
│  Conecta tu correo en 3 simples pasos:            │
│                                                    │
│  [Paso 1/3: Selecciona tu proveedor]              │
│  ●━━━━━━━━━━━━━━━━━━━━━━○ ··············· ○       │
│                                                    │
│  ┌─────┐  ┌─────┐  ┌─────┐                       │
│  │ 📧  │  │ 📫  │  │ ⚙️ │                        │
│  │Gmail│  │Outlk│  │Otro │                       │
│  └─────┘  └─────┘  └─────┘                       │
│    ✓                                              │
│                                                    │
│  [Email]: andres@gmail.com                        │
│  [Contraseña de App]: ••••••••••                  │
│  💡 ¿Cómo crear contraseña de app? [Tutorial]    │
│                                                    │
│            [← Atrás]  [Continuar →]               │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│  [Paso 2/3: Prueba la conexión]                   │
│  ● ●━━━━━━━━━━━━━━━━━━━━━○ ··············· ○       │
│                                                    │
│  ✅ Conexión exitosa                              │
│  📬 Encontrados: 47 correos con facturas          │
│                                                    │
│  ⚙️ Configuración avanzada (opcional)             │
│  [▼ Términos de búsqueda personalizados]          │
│                                                    │
│            [← Atrás]  [Continuar →]               │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│  [Paso 3/3: ¡Todo listo!]                         │
│  ● ● ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━○       │
│                                                    │
│  🎊 Tu cuenta está configurada                    │
│                                                    │
│  ¿Qué deseas hacer ahora?                         │
│                                                    │
│  [ 🚀 Procesar Facturas Ahora ]  (Recomendado)    │
│  [ 📅 Programar Automatización ]                  │
│  [ 🏠 Ir al Dashboard ]                           │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 2. Configuración Rápida de Correo (Rediseñada)

#### Modal Inteligente (No Nueva Pantalla)

```typescript
// Características del nuevo componente
interface QuickEmailSetup {
  // Auto-detección
  detectProvider(): 'gmail' | 'outlook' | 'custom';
  
  // Pre-fill inteligente
  autoFillSettings(provider: Provider): EmailConfig;
  
  // Validación en tiempo real
  validateOnType(): ValidationResult;
  
  // Test de conexión inline
  testConnection(): Promise<TestResult>;
  
  // Acción combinada
  saveAndProcess(): void; // Una sola acción!
}
```

#### UX del Modal

```
┌────────────────────────────────────────────────┐
│  ⚡ Configuración Rápida de Correo             │
│                                                │
│  Tu correo:                                    │
│  ┌──────────────────────────────────────────┐ │
│  │ 📧 juan@gmail.com                        │ │
│  └──────────────────────────────────────────┘ │
│  ✅ Gmail detectado - configuración cargada   │
│                                                │
│  Contraseña de aplicación:                    │
│  ┌──────────────────────────────────────────┐ │
│  │ ••••••••••••                             │ │
│  └──────────────────────────────────────────┘ │
│  💡 Crea una en: myaccount.google.com/apppass │
│                                                │
│  [◀ Probar Conexión]  [✓ Guardar y Procesar →]│
│                                                │
│  [⚙️ Configuración Avanzada]                  │
└────────────────────────────────────────────────┘
```

### 3. Procesamiento One-Click

**ANTES:**
```
Dashboard → Navbar → Gestión → Scroll → Procesar → 
Esperar → Ir a Explorador → Ver resultados
```

**DESPUÉS:**
```
Dashboard → [Procesar Ahora] → 
Ver progreso inline → Ver resultados en la misma pantalla
```

#### Diseño de Procesamiento Inline

```
┌────────────────────────────────────────────────┐
│  Dashboard                    [🔄 Procesar Now]│
├────────────────────────────────────────────────┤
│                                                │
│  Estado de Sincronización:                    │
│  ┌──────────────────────────────────────────┐ │
│  │ 🔄 Procesando...                         │ │
│  │ ████████████░░░░░░░░  60%                │ │
│  │                                          │ │
│  │ ✓ Gmail: 15 facturas encontradas        │ │
│  │ ⏳ Outlook: procesando...                │ │
│  │                                          │ │
│  │ [Ver Detalles] [Detener]                │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  Últimas Agregadas: (actualización en tiempo real)
│  • Factura 001-001-0456 - ₲ 250,000 (hace 5s) │
│  • Factura 002-001-0789 - ₲ 180,000 (hace 8s) │
│                                                │
└────────────────────────────────────────────────┘
```

### 4. Exportación Simplificada

**ANTES:**
```
Dashboard → Facturas → Seleccionar → Navbar → 
Exportar → Crear Template → Configurar Columnas → 
Guardar → Exportar → Download
```

**DESPUÉS:**
```
Dashboard/Facturas → [Exportar] → 
Quick Options Modal → Download
```

#### Modal de Exportación Rápida

```
┌────────────────────────────────────────────────┐
│  📊 Exportar Facturas                          │
│                                                │
│  Período:                                      │
│  ● Este mes (125 facturas)                    │
│  ○ Últimos 3 meses                            │
│  ○ Personalizado [____] a [____]              │
│                                                │
│  Formato:                                      │
│  [📋 Usar plantilla existente ▼]              │
│  ┌──────────────────────────────────────────┐ │
│  │ ✓ Plantilla Contabilidad General         │ │
│  │   (RUC, Razón, Total, IVA 10%, IVA 5%)   │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  o [⚡ Exportación Rápida] (todas las columnas)│
│                                                │
│             [Cerrar]  [⬇ Descargar Excel]      │
└────────────────────────────────────────────────┘
```

### 5. Gestión de Suscripción Mejorada

**ANTES:**
- Banner de trial en navbar (molesto)
- Información dispersa
- Proceso de pago complejo

**DESPUÉS:**
- Widget informativo no intrusivo
- Proceso de upgrade streamlined
- Comparación clara de planes

```
┌────────────────────────────────────────────────┐
│  💎 Estado de Suscripción                      │
│                                                │
│  Plan Actual: FREE (Trial)                    │
│  ⏱ 12 días restantes                          │
│  📊 IA: 23/50 facturas procesadas             │
│                                                │
│  [✨ Actualizar a PRO]  [Ver Planes]          │
│                                                │
│  Beneficios de actualizar:                    │
│  ✓ 1,000 facturas/mes                         │
│  ✓ IA ilimitada                               │
│  ✓ Soporte prioritario                        │
└────────────────────────────────────────────────┘
```

---

## 🎨 Sistema de Diseño

### Paleta de Colores

```scss
// Colores Primarios
$primary: #4F46E5;        // Índigo moderno
$primary-light: #818CF8;
$primary-dark: #3730A3;

// Colores Secundarios
$success: #10B981;        // Verde éxito
$warning: #F59E0B;        // Naranja advertencia
$danger: #EF4444;         // Rojo error
$info: #3B82F6;           // Azul información

// Neutrales
$gray-50: #F9FAFB;
$gray-100: #F3F4F6;
$gray-200: #E5E7EB;
$gray-300: #D1D5DB;
$gray-500: #6B7280;
$gray-700: #374151;
$gray-900: #111827;

// Semánticos
$background: #FFFFFF;
$surface: $gray-50;
$text-primary: $gray-900;
$text-secondary: $gray-500;
$border: $gray-200;
```

### Tipografía

```scss
// Familia
$font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

// Tamaños
$text-xs: 0.75rem;    // 12px
$text-sm: 0.875rem;   // 14px
$text-base: 1rem;     // 16px
$text-lg: 1.125rem;   // 18px
$text-xl: 1.25rem;    // 20px
$text-2xl: 1.5rem;    // 24px
$text-3xl: 1.875rem;  // 30px
$text-4xl: 2.25rem;   // 36px

// Pesos
$font-normal: 400;
$font-medium: 500;
$font-semibold: 600;
$font-bold: 700;
```

### Espaciado

```scss
// Sistema 8pt
$space-1: 0.25rem;   // 4px
$space-2: 0.5rem;    // 8px
$space-3: 0.75rem;   // 12px
$space-4: 1rem;      // 16px
$space-5: 1.25rem;   // 20px
$space-6: 1.5rem;    // 24px
$space-8: 2rem;      // 32px
$space-10: 2.5rem;   // 40px
$space-12: 3rem;     // 48px
$space-16: 4rem;     // 64px
```

### Componentes Base

#### Botones

```scss
// Primario
.btn-primary {
  background: $primary;
  color: white;
  padding: $space-3 $space-6;
  border-radius: 8px;
  font-weight: $font-semibold;
  font-size: $text-base;
  transition: all 0.2s;
  
  &:hover {
    background: $primary-dark;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba($primary, 0.3);
  }
}

// Secundario
.btn-secondary {
  background: white;
  color: $primary;
  border: 2px solid $primary;
  // ... similar styles
}

// Ghost
.btn-ghost {
  background: transparent;
  color: $gray-700;
  &:hover {
    background: $gray-100;
  }
}
```

#### Cards

```scss
.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  padding: $space-6;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  
  &--elevated {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }
}
```

#### Inputs

```scss
.input {
  width: 100%;
  padding: $space-3 $space-4;
  border: 2px solid $border;
  border-radius: 8px;
  font-size: $text-base;
  transition: all 0.2s;
  
  &:focus {
    outline: none;
    border-color: $primary;
    box-shadow: 0 0 0 3px rgba($primary, 0.1);
  }
  
  &--error {
    border-color: $danger;
  }
  
  &--success {
    border-color: $success;
  }
}
```

### Animaciones

```scss
// Transiciones suaves
$transition-fast: 0.15s ease;
$transition-base: 0.2s ease;
$transition-slow: 0.3s ease;

// Animaciones
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Iconografía

```scss
// Sistema de íconos Bootstrap Icons
// Tamaños estandarizados
.icon {
  &--sm { font-size: 1rem; }      // 16px
  &--base { font-size: 1.25rem; } // 20px
  &--lg { font-size: 1.5rem; }    // 24px
  &--xl { font-size: 2rem; }      // 32px
}

// Íconos por contexto
$icon-email: 'bi-envelope';
$icon-invoice: 'bi-receipt';
$icon-export: 'bi-download';
$icon-settings: 'bi-gear';
$icon-success: 'bi-check-circle-fill';
$icon-error: 'bi-x-circle-fill';
$icon-warning: 'bi-exclamation-triangle-fill';
$icon-info: 'bi-info-circle-fill';
```

---

## 🚀 Roadmap de Implementación

### Fase 1: Fundamentos (Semana 1-2)

**Prioridad: CRÍTICA**

- [ ] **Sistema de Diseño Base**
  - Crear archivo de variables SCSS
  - Definir clases utility
  - Componentes base reutilizables
  
- [ ] **Navbar Simplificado**
  - Reducir de 8 a 4 items principales
  - Reorganizar jerarquía
  - Mejorar responsive
  
- [ ] **Dashboard Unificado**
  - Widget de estado del sistema
  - Acciones rápidas inline
  - Resumen interactivo

**Archivos a modificar:**
```
frontend/src/styles.scss
frontend/src/app/components/navbar/
frontend/src/app/components/dashboard/
frontend/src/app/shared/components/ (nuevo)
```

### Fase 2: Onboarding & Configuración (Semana 3-4)

**Prioridad: ALTA**

- [ ] **Wizard de Onboarding**
  - Componente de stepper
  - Modal de configuración rápida
  - Auto-detección de proveedores
  - Validación en tiempo real
  
- [ ] **Configuración de Correo Rediseñada**
  - Modal inline en lugar de página separada
  - Pre-fill inteligente
  - Test de conexión inline
  - Acción combinada "Guardar y Procesar"

**Archivos a crear/modificar:**
```
frontend/src/app/components/shared/onboarding-wizard/
frontend/src/app/components/shared/quick-email-setup/
frontend/src/app/components/email-config/ (refactorizar)
frontend/src/app/services/onboarding.service.ts (nuevo)
```

### Fase 3: Procesamiento & Flujos (Semana 5-6)

**Prioridad: ALTA**

- [ ] **Procesamiento One-Click**
  - Botón prominente en dashboard
  - Progress tracking inline
  - Resultados en tiempo real
  - Notificaciones mejoradas
  
- [ ] **Explorador de Facturas Mejorado**
  - Filtros más accesibles
  - Quick actions por factura
  - Vista de detalles en modal

**Archivos a modificar:**
```
frontend/src/app/components/invoice-processing/ (refactorizar)
frontend/src/app/components/invoice-explorer/ (mejorar)
frontend/src/app/services/processing.service.ts (optimizar)
```

### Fase 4: Exportación & Templates (Semana 7)

**Prioridad: MEDIA**

- [ ] **Exportación Rápida**
  - Modal de exportación one-click
  - Plantillas predefinidas
  - Preview antes de descargar
  
- [ ] **Gestión de Templates Simplificada**
  - Templates como presets
  - Editor visual mejorado
  - Duplicar/compartir templates

**Archivos a modificar:**
```
frontend/src/app/components/export-templates/ (refactorizar)
frontend/src/app/components/shared/quick-export/ (nuevo)
```

### Fase 5: Suscripciones & Cuenta (Semana 8)

**Prioridad: MEDIA**

- [ ] **Widget de Suscripción Mejorado**
  - Card informativo no intrusivo
  - Comparación de planes clara
  - Upgrade flow simplificado
  
- [ ] **Gestión de Cuenta Unificada**
  - Perfil + Suscripción + Medios de pago en una vista
  - Tabs para organizar

**Archivos a modificar:**
```
frontend/src/app/components/subscription/ (mejorar)
frontend/src/app/components/profile/ (unificar)
frontend/src/app/components/payment-methods/ (integrar)
```

### Fase 6: Mobile & Responsive (Semana 9)

**Prioridad: ALTA**

- [ ] **Optimización Mobile**
  - Bottom navigation en móvil
  - Formularios optimizados
  - Tablas responsive con cards
  - Touch-friendly buttons

**Archivos a crear:**
```
frontend/src/app/components/shared/mobile-nav/
frontend/src/app/components/shared/responsive-table/
frontend/src/styles/mobile.scss
```

### Fase 7: Performance & Polish (Semana 10)

**Prioridad: MEDIA**

- [ ] **Optimizaciones**
  - Lazy loading de componentes
  - Optimización de imágenes
  - Reducción de bundle size
  - Caché estratégico
  
- [ ] **Animaciones & Microinteracciones**
  - Loading states
  - Skeleton screens
  - Smooth transitions
  - Feedback visual

### Fase 8: Testing & Refinamiento (Semana 11-12)

**Prioridad: CRÍTICA**

- [ ] **Testing de Usabilidad**
  - Tests con usuarios reales
  - A/B testing de flujos clave
  - Métricas de conversión
  
- [ ] **Refinamiento**
  - Ajustes basados en feedback
  - Pulido de detalles
  - Documentación

---

## 📊 Métricas de Seguimiento

### KPIs Principales

```typescript
interface UXMetrics {
  // Onboarding
  onboardingCompletionRate: number;      // Target: 85%
  timeToFirstInvoice: number;            // Target: < 3 min
  onboardingDropoffByStep: number[];     // Identificar cuellos de botella
  
  // Eficiencia
  clicksToProcessEmails: number;         // Target: 1 click
  clicksToExport: number;                // Target: 2 clicks
  clicksToConfigureEmail: number;        // Target: 3 clicks
  
  // Engagement
  dailyActiveUsers: number;
  weeklyActiveUsers: number;
  averageSessionDuration: number;
  returnRate: number;                     // Target: > 70%
  
  // Satisfacción
  nps: number;                            // Target: > 50
  userSatisfactionScore: number;          // Target: 9/10
  supportTicketsPerUser: number;          // Target: < 0.5
}
```

### Herramientas de Medición

1. **Google Analytics** - Flujos de usuario
2. **Hotjar** - Heatmaps y grabaciones
3. **Mixpanel** - Event tracking
4. **Custom Dashboard** - Métricas específicas de la app

---

## 🎯 Entregables por Fase

### Documentación
- [ ] Guía de estilo visual (Figma/PDF)
- [ ] Biblioteca de componentes (Storybook)
- [ ] Guía de implementación técnica
- [ ] Documentación de API de componentes

### Código
- [ ] Sistema de diseño (SCSS + classes)
- [ ] Componentes compartidos reutilizables
- [ ] Services refactorizados
- [ ] Tests unitarios para componentes nuevos

### Diseño
- [ ] Mockups de alta fidelidad (Figma)
- [ ] Prototipos interactivos
- [ ] Especificaciones de diseño (Zeplin/Figma Inspect)

---

## 💡 Próximos Pasos Inmediatos

1. **Revisar y aprobar este plan**
2. **Crear mockups en Figma** (diseños visuales)
3. **Implementar Fase 1** (fundamentos)
4. **Iterar con feedback** de usuarios

---

## 📝 Notas de Implementación

### Compatibilidad
- Mantener compatibilidad con flujos existentes durante transición
- Feature flags para habilitar/deshabilitar nuevas funcionalidades
- Migración gradual, no big bang

### Testing
- Unit tests para componentes nuevos (mínimo 80% coverage)
- E2E tests para flujos críticos
- Visual regression tests con Percy/Chromatic

### Accesibilidad
- WCAG 2.1 Level AA compliance
- Keyboard navigation
- Screen reader friendly
- Color contrast ratios válidos

### Performance
- First Contentful Paint < 1.5s
- Time to Interactive < 3s
- Lighthouse score > 90

---

**Versión:** 1.0  
**Última actualización:** 24 de febrero de 2026  
**Próxima revisión:** Después de Fase 1
