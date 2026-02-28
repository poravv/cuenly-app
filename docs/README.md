# Documentación — CuenlyApp

> Índice maestro de toda la documentación del proyecto.
> Para contexto técnico completo de Claude ver: [`../CLAUDE.md`](../CLAUDE.md)

---

## Documentos Activos (Referencia Diaria)

| Archivo | Descripción |
|---------|-------------|
| [`PLAN-OPTIMIZACION.md`](./PLAN-OPTIMIZACION.md) | **Plan principal de mejoras** — 23 items en 5 fases, priorizado por impacto |
| [`documentacion-tecnica.md`](./documentacion-tecnica.md) | Arquitectura del sistema, base de datos, API, infraestructura |
| [`documentacion-funcional.md`](./documentacion-funcional.md) | Descripción de funcionalidades y flujos de usuario |
| [`OPTIMIZACIONES_POST_MAPEO.md`](./OPTIMIZACIONES_POST_MAPEO.md) | Mejoras pendientes post-implementación del mapeo SIFEN |

---

## Integraciones

### Pagopar (Pagos Recurrentes)
| Archivo | Descripción |
|---------|-------------|
| [`pagopar/pagopar-integration.md`](./pagopar/pagopar-integration.md) | Resumen del flujo de integración (inicio rápido) |
| [`pagopar/pagopar_suscripciones_paso_a_paso_recomendado.md`](./pagopar/pagopar_suscripciones_paso_a_paso_recomendado.md) | Flujo recomendado paso a paso con 3 planes |
| [`pagopar/TARJETAS_DE_PRUEBA.md`](./pagopar/TARJETAS_DE_PRUEBA.md) | Tarjetas sandbox para testing |
| [`pagopar/SOLUCION_NO_EXISTE_COMPRADOR.md`](./pagopar/SOLUCION_NO_EXISTE_COMPRADOR.md) | Troubleshooting del error "No existe comprador" |
| [`pagopar/pagopar_integracion_completa.md`](./pagopar/pagopar_integracion_completa.md) | Referencia completa (220KB, del proveedor) |

### SIFEN (Facturación Electrónica Paraguay)
| Archivo | Descripción |
|---------|-------------|
| [`sifen/Extructura xml_DE.xml`](./sifen/Extructura%20xml_DE.xml) | Ejemplo de XML DE (Documento Electrónico) |
| [`sifen/Estructura_DE xsd.xml`](./sifen/Estructura_DE%20xsd.xml) | Schema XSD del Documento Electrónico SIFEN |

---

## UX / Diseño

| Archivo | Descripción |
|---------|-------------|
| [`ux/UX-TRANSFORMATION-PLAN.md`](./ux/UX-TRANSFORMATION-PLAN.md) | Plan completo de transformación UX con fases |
| [`ux/NAVIGATION-REDESIGN.md`](./ux/NAVIGATION-REDESIGN.md) | Rediseño del sistema de navegación |
| [`ux/IMPLEMENTATION-GUIDE.md`](./ux/IMPLEMENTATION-GUIDE.md) | Guía de implementación fase a fase |
| [`ux/QUICK-WINS.md`](./ux/QUICK-WINS.md) | Mejoras de alto impacto y baja complejidad |
| [`ux/COMPONENT-SPECS-QUICK-EMAIL-SETUP.md`](./ux/COMPONENT-SPECS-QUICK-EMAIL-SETUP.md) | Especificaciones técnicas de componentes UX |

---

## Historial (Solo Referencia — Implementado)

Documentos de fases ya completadas. No requieren acción.

| Archivo | Estado |
|---------|--------|
| [`historial/fase3-flujos-cola.md`](./historial/fase3-flujos-cola.md) | ✅ Implementado |
| [`historial/fase4-nomenclaturas-acentos.md`](./historial/fase4-nomenclaturas-acentos.md) | ✅ Implementado |
| [`historial/fase4-qa-funcional-guiado.md`](./historial/fase4-qa-funcional-guiado.md) | ✅ QA ejecutado |
| [`historial/fase5-ux-simplificacion.md`](./historial/fase5-ux-simplificacion.md) | ✅ Implementado |
| [`historial/matriz-mapeo-sifen-fase1.md`](./historial/matriz-mapeo-sifen-fase1.md) | ✅ Implementado |
| [`historial/matriz-mapeo-sifen-fase2.md`](./historial/matriz-mapeo-sifen-fase2.md) | ✅ Implementado |
| [`historial/qa-docker-produccion-fase4.md`](./historial/qa-docker-produccion-fase4.md) | ✅ Verificado |
| [`historial/RESUMEN-EJECUTIVO.md`](./historial/RESUMEN-EJECUTIVO.md) | Referencia estratégica inicial |
| [`historial/benchmark-ux-apps-similares.md`](./historial/benchmark-ux-apps-similares.md) | Análisis competitivo inicial |
| [`historial/enterprise-legacy/`](./historial/enterprise-legacy/) | Arquitectura legacy (Spring Boot + RabbitMQ) |
