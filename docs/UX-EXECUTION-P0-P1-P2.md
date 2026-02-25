# UX Execution Matrix (P0/P1/P2)

**Fecha:** 25 de febrero de 2026  
**Objetivo:** priorizar mejoras de GUI con foco en facilidad de uso, luego estética visual.

## Criterios de priorización

- `P0`: reduce fricción directa en flujos críticos (procesar, configurar correo, entender estado).
- `P1`: ordena arquitectura y navegación para disminuir carga cognitiva.
- `P2`: optimiza polish visual, performance y refinamientos avanzados.

## Decisiones de base (source of truth)

- Arquitectura final de navegación: tomar como base [NAVIGATION-REDESIGN.md](./NAVIGATION-REDESIGN.md).
- Quick wins inmediatos: tomar como base [QUICK-WINS.md](./QUICK-WINS.md).
- Sistema visual: aplicar tokens/variables ya definidos en `frontend/src/styles/`.

## Plan por prioridad

### P0 (inmediato)

- [x] Quick Win #1: botón `Procesar Ahora` en dashboard (1 clic).
- [x] Quick Win #2: setup rápido de correo sin salir del contexto.
- [x] Quick Win #3: widget de estado visual del sistema.
- [x] Quick Win #5: loading states/skeletons donde hay espera relevante.

**KPI P0**
- Clics para procesar: `3 -> 1`.
- Tiempo a primera acción de valor (procesar): reducción esperada `>50%`.
- Menos dudas operativas por estado del sistema.

### P1 (siguiente bloque)

- [x] Reorganización de navegación principal (4 secciones) con migración gradual.
- [x] Unificación de vistas de facturas (lista/explorador/estadísticas por tabs).
- [x] Ajuste de rutas y redirects para compatibilidad.

**KPI P1**
- Menor tiempo para encontrar funciones clave.
- Menor tasa de navegación errática entre secciones.

### P2 (polish)

- [ ] Microinteracciones y feedback visual adicional.
- [ ] Optimización mobile avanzada.
- [ ] Optimización de bundle/lazy loading y mejoras de performance.

**KPI P2**
- Lighthouse y Web Vitals.
- Mejoras en satisfacción percibida de UI.

## Ejecución del primer punto (Quick Win #1)

### Entregado en código

- Acción primaria `Procesar Ahora` visible en dashboard.
- Estado de procesamiento (`Procesando...`) y bloqueo de doble acción.
- Mensajería contextual para:
  - éxito con facturas procesadas,
  - procesamiento sin novedades,
  - error.
- Recarga automática de datos del dashboard tras procesamiento.
- Acceso rápido a setup de correo cuando no hay cuentas configuradas.
- Setup rápido robusto para correo:
  - auto-detección Gmail/Outlook,
  - fallback para proveedor personalizado (host/puerto/SSL),
  - guardado + procesamiento inmediato con feedback claro.
- Widget de estado visual reforzado:
  - estado de correo,
  - estado de IA,
  - estado de procesamiento,
  - última actualización del dashboard.
- Loading states mejorados:
  - skeletons en carga inicial para métricas, gráficas y actividad,
  - recarga no bloqueante con indicador compacto,
  - eliminación de overlay full-screen durante actualizaciones.

### Criterios de aceptación

- Usuario con correo configurado puede iniciar procesamiento en 1 clic.
- Usuario sin correo configurado entiende qué falta y puede abrir setup rápido.
- Durante procesamiento no se permiten clics repetidos.
- Al finalizar, el dashboard refleja el estado actualizado.

### Verificación mínima

- `npm run build` en `frontend` sin errores de compilación.
