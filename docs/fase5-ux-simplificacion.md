# Fase 5 - Simplificación de UX (Procesamiento y Correo)

Fecha: 2026-02-24  
Estado: `IMPLEMENTADO (iteración 1)`

## Objetivo

Reducir pasos y clics para que un usuario configure su correo y procese su primer lote sin salir de la vista de procesamiento.

## Cambios implementados (iteración 1)

Archivos:

- `frontend/src/app/components/invoice-processing/invoice-processing.component.ts`
- `frontend/src/app/components/invoice-processing/invoice-processing.component.html`

Cambios:

- CTA directo en cabecera: `Conectar Correo Ahora`.
- Acceso visible a cola: botón `Cola de Procesos`.
- Wizard inline de configuración rápida (sin navegar a otra vista):
  - Paso 1: proveedor + host/port/credencial.
  - Paso 2: nomenclaturas + prueba de conexión.
  - Paso 3: `Guardar configuración` o `Guardar y procesar ahora`.
- Panel avanzado opcional:
  - sinónimos por tenant
  - fallback por remitente
  - fallback por adjunto

## Resultado UX esperado

- Menos fricción para onboarding inicial.
- Menos navegación entre módulos.
- Time-to-first-process más corto.

## Evidencia operativa

- QA en despliegue docker producción:
  - `docs/qa-docker-produccion-fase4.md`
- Verificación de bundle frontend desplegado con nuevos textos del flujo rápido.

## Benchmark externo (apps similares y patrones relevantes)

Referencias evaluadas:

- Dext: ingesta por reenvío de correo y captura automática.
- Hubdoc (Xero): envío de documentos por email y centralización de fuentes.
- Rossum: separación clara entre ingesta, cola/inbox y validación de documentos.
- Nanonets: automatización por correo con enrutamiento y flujo de trabajo.

Patrones aplicados desde benchmark:

- Entrada principal con CTA único para onboarding.
- Cola/procesos accesible desde la misma pantalla operativa.
- Configuración por capas: básico primero, avanzado colapsable.
- Acción final combinada: guardar + ejecutar.

## Siguiente iteración recomendada (fase 5.2)

- Wizard tipo stepper visual con progreso persistente.
- Validación en vivo de credenciales y proveedor.
- Sugerencias automáticas de nomenclaturas según proveedor/historial.
- KPIs de onboarding (`time_to_first_invoice`, abandono por paso).
