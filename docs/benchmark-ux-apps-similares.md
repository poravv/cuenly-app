# Benchmark UX - Apps Similares

Fecha: 2026-02-24

## Referencias investigadas

## Dext (captura por email + inbox)

- Extract by email con direcciones dedicadas y modos `single` / `multiple`.
- Recomendación explícita de reglas de auto-forward para reducir pasos manuales.
- Los documentos terminan en un inbox de costos/ventas.

Referencia:

- https://help.dext.com/en/articles/416754-submit-documents-to-dext-with-extract-by-email

## Hubdoc (captura omnicanal)

- Mensaje UX central: “todos los documentos en un solo lugar”.
- Ingesta por móvil, desktop, email y scanner.
- Reglas de forwarding para documentos recurrentes.

Referencias:

- https://www.hubdoc.com/
- https://content.hubdoc.com/getstarted/upload-paper-and-digital-documents

## Nanonets (email import + workflows + approvals)

- Flujo en 3 pasos para email parsing (captura, extracción, salida).
- Historial de corridas de importación por email con estado `queued/processing/completed/error`.
- Stages de aprobación y enrutamiento configurable por reglas.

Referencias:

- https://nanonets.com/email-parser
- https://docs.nanonets.com/docs/email-import-run-history
- https://docs.nanonets.com/docs/approvals
- https://docs.nanonets.com/docs/setup-document-classification-and-routing

## Rossum (cola/queue y validación)

- UX enfocada en `queues` y pantalla de validación optimizada.
- Configuración por cola y extensiones para clasificación/ruteo.

Referencias:

- https://knowledge-base.rossum.ai/docs/document-validation-screen-in-rossum
- https://knowledge-base.rossum.ai/docs/document-sorting-extension

## Patrones UX adoptados para Cuenly (iteración actual)

- CTA único de onboarding desde pantalla de procesamiento.
- Wizard inline en 3 pasos (sin navegación obligatoria).
- Acción final combinada: `Guardar y procesar ahora`.
- Acceso directo a cola de procesos desde la misma vista operativa.
- Configuración avanzada colapsable para no sobrecargar el primer uso.

## Próximos patrones a implementar (iteración siguiente)

- Estado visual de onboarding (stepper con progreso persistente).
- Historial de corridas/errores de importación visible en la misma pantalla.
- Reglas sugeridas por proveedor (plantillas de nomenclaturas por defecto).
- Métricas de funnel de onboarding (abandono por paso, tiempo al primer procesamiento).
