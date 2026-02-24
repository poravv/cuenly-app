# Plan Maestro de Optimizaciones Post-Mapeo

Fecha: 2026-02-24  
Estado: `APROBADO PARA EJECUCIÓN`  
Regla de trabajo: **no avanzar de fase hasta cerrar criterios de aceptación de la fase actual**.

## 1) Objetivo

Asegurar que el nuevo mapeo SIFEN quede correcto de punta a punta:

- Sin campos faltantes ni sobrantes en tablas frontend.
- Campos correctos y utilizables en templates de exportación.
- Flujos de procesamiento (manual, automático y por rango) optimizados para cola.
- Búsqueda robusta por nomenclaturas (incluyendo acentos y variantes).
- Seguridad estricta multi-tenant y resguardo de secretos.

Referencia de verdad de mapeo:

- `docs/cuenly-enterprise/Extructura xml_DE.xml`
- `docs/cuenly-enterprise/Estructura_DE xsd.xml`

## 2) Hallazgos críticos confirmados (P0)

1. `retry` de cola con firma inconsistente:
- `backend/app/api/endpoints/user_profile.py` encola kwargs que no coinciden con `process_single_email_from_uid_job` en `backend/app/worker/jobs.py`.

2. Riesgo de fuga multi-tenant en búsqueda avanzada:
- `POST /invoices/search` no recibe usuario autenticado ni filtra por `owner_email`.
- `search_invoices` en `backend/app/modules/mongo_query_service.py` no aplica `owner_email`.

3. Secretos sensibles almacenados en claro:
- `password`, `access_token`, `refresh_token` en `backend/app/modules/email_processor/config_store.py` se guardan y leen sin cifrado en reposo.

4. Exposición de secreto en perfil:
- En `backend/app/api/api.py` se retorna `webhook_secret` en respuesta de perfil.

5. Error técnico de limpieza Redis:
- `close_redis_client()` usa `_redis_client` inexistente en `backend/app/core/redis_client.py`.

6. Inconsistencia en job de sincronización:
- `handle_full_sync_job` invoca `ignore_date_filter=True` en `single.process_emails(...)` sin parámetro compatible en implementación actual.

7. Límite manual/fan-out inconsistente:
- `process-direct` recibe `limit`, pero en fan-out por cuenta puede encolar más de lo esperado.

8. Exposición innecesaria de tokens OAuth al frontend:
- `list_configs(..., include_password=False)` no debe retornar `access_token` ni `refresh_token`.

9. Riesgo de duplicidad de cuentas por tenant:
- Falta reforzar unicidad operativa por `owner_email + username` en `email_configs`.

## 3) Plan de ejecución obligatorio

## Fase 0 - Bloqueantes de seguridad y estabilidad (P0)

- [ ] Corregir firma de `retry` de cola para que use argumentos válidos de `process_single_email_from_uid_job`.
- [ ] Proteger `POST /invoices/search` con autenticación y `owner_email` obligatorio.
- [ ] Revisar endpoints similares sin auth/filtro (`/invoices/recent-activity` y relacionados) y asegurar aislamiento por usuario o mover a admin.
- [ ] Eliminar `webhook_secret` de respuestas API; devolver solo metadata segura.
- [ ] Cifrar en reposo credenciales de correo y tokens OAuth en `email_configs`.
- [ ] Evitar exponer tokens OAuth en respuestas de configuración al frontend.
- [ ] Corregir `close_redis_client()` para manejar clientes decoded/raw correctamente.
- [ ] Resolver llamada incompatible en `handle_full_sync_job`.

Criterios de aceptación Fase 0:

- [ ] Tests de autorización: usuario A no puede ver ni consultar datos de B.
- [ ] Tests de cola: retry manual encola job válido y ejecuta sin error de firma.
- [ ] Ningún endpoint público devuelve secretos.
- [ ] Credenciales/tokens no aparecen en texto plano en MongoDB.

## Fase 1 - Matriz de mapeo SIFEN end-to-end (P0)

- [ ] Construir matriz única de campos: `XML/XSD -> parser -> InvoiceData -> InvoiceHeader/Totales -> API -> frontend -> export`.
- [ ] Agregar test de cobertura de mapeo usando ejemplos reales de `docs/cuenly-enterprise`.
- [ ] Validar campos nuevos SIFEN v150:
  - `qr_url`, `info_adicional`, `tipo_documento_electronico`, `ind_presencia*`
  - `cond_credito*`, `ciclo_*`, `transporte_*`
  - `isc_*`
- [ ] Marcar explícitamente campos permitidos para UI (tabla) y para export templates.

Criterios de aceptación Fase 1:

- [ ] Cobertura 100% de campos definidos como “soportados”.
- [ ] Cero “campos fantasma” en frontend/export (sin fuente real).
- [ ] Cero campos de XML soportado ausentes en mapeo backend.

## Fase 2 - Frontend: tablas + templates sin faltantes/sobrantes (P0)

- [x] Ajustar tablas (`invoice-list`, `invoice-explorer`) para exponer campos mapeados relevantes con configuración clara (básicos + expandibles).
- [x] Alinear `available-fields` backend con modelo real persistido y lo que exporta `template_exporter`.
- [x] Eliminar categorías/campos legacy desalineados en editor de templates.
- [x] Añadir validación de consistencia: campo visible en template debe existir realmente en payload de export.

Criterios de aceptación Fase 2:

- [x] QA funcional: mismo campo visible en tabla puede exportarse correctamente.
- [x] QA de exportación: no aparecen columnas vacías por mapeos inexistentes.

## Fase 3 - Flujos de procesamiento y cola (P0)

- [x] Unificar comportamiento de manual, automático y rango para que prioricen fan-out a cola.
- [x] Hacer que `limit` manual se respete realmente en fan-out (cap por cuenta + cap global).
- [x] Mantener compatibilidad de payloads legacy en jobs encolados (retry manual).
- [x] Parametrizar lotes con variables:
  - `EMAIL_BATCH_SIZE` (fallback local)
  - `FANOUT_DISCOVERY_BATCH_SIZE`
  - `FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN`
  - `PROCESS_DIRECT_DEFAULT_LIMIT`
- [x] Ajuste inicial recomendado:
  - manual default: `50`
  - manual max: `200` (`PROCESS_DIRECT_MAX_LIMIT`)
  - fan-out discovery batch: `200` a `500` (según benchmark) (`250` por defecto)
- [x] Mantener política de no leídos (`UNSEEN`) y trazar cuántos se encolan/omiten por corrida.

Criterios de aceptación Fase 3:

- [x] Manual, automático y rango encolan rápido (respuesta API no bloqueante).
- [x] Cola mantiene throughput estable sin saturar IMAP.
- [x] Límite manual se cumple exactamente.

## Fase 4 - Nomenclaturas y acentos (P0)

- [x] Fortalecer matcher de asuntos/remitentes:
  - normalización Unicode (`NFKD`), remover acentos, lowercase, limpieza de puntuación.
  - tokenización y comparación por término completo + contains.
  - soporte de sinónimos configurables por tenant.
- [x] Añadir fallback opcional por remitente/adjunto cuando asunto no coincide.
- [x] Crear suite de pruebas con casos reales:
  - “factura electrónica”, “facturación”, “comprobante”, variantes con/ sin tilde.

Criterios de aceptación Fase 4:

- [x] Los correos esperados por nomenclatura se detectan con alta precisión.
- [x] No hay regresión en falsos positivos críticos.

## Fase 5 - UX y simplificación de flujo (P1)

- [x] Reducir fricción de “configurar correo -> ir a procesamiento” a flujo guiado único.
- [x] Implementar CTA directo desde procesamiento: “Conectar correo ahora” (modal/wizard inline).
- [x] Flujo propuesto en 3 pasos:
  - Paso 1: proveedor + credencial
  - Paso 2: términos + prueba conexión
  - Paso 3: guardar + activar + procesar ahora
- [x] Mantener estética actual (sin romper diseño), pero con menos clics y sin navegación innecesaria.
- [x] Añadir acceso visible a “Cola de Procesamiento” desde el panel de procesamiento.

Criterios de aceptación Fase 5:

- [ ] Usuario nuevo puede conectar cuenta y procesar primer lote en un solo flujo.
- [ ] Menor cantidad de pasos/clics para configurar correo.

## Fase 6 - Docker y operación segura (P1)

- [ ] Endurecer `docker-compose`:
  - no exponer Mongo/Redis en perfiles no-dev.
  - habilitar auth de Redis en entornos reales.
  - revisar variables sensibles en `.env`.
- [ ] Definir perfiles claros `dev` vs `production` sin puertos inseguros por defecto.
- [ ] Añadir checklists operativos de despliegue.

Criterios de aceptación Fase 6:

- [ ] En perfil productivo, DB/Redis no quedan expuestos públicamente.
- [ ] Worker y backend conectan con credenciales seguras.

## 4) Seguridad obligatoria (no negociable)

- Aislamiento estricto por tenant en consultas, colas, retry, export y métricas.
- Contraseñas nunca en claro:
  - Usuarios: hash (cuando aplique autenticación local).
  - Credenciales de correo/tokens: cifrado reversible en reposo (no hash).
- Nunca devolver secretos en respuestas API o logs.
- No exponer `access_token`/`refresh_token` a clientes frontend.

## 7) Optimizaciones adicionales detectadas durante implementación

- [ ] Configurar `EMAIL_CONFIG_ENCRYPTION_KEY` dedicada por entorno (no usar fallback en producción).
- [ ] Ejecutar migración gradual para recifrar credenciales legacy en claro al nuevo formato `enc:v1`.
- [ ] Monitorear y limpiar duplicados históricos para habilitar índice único `owner_email + username` sin warnings.
- [ ] Definir límite configurable de fan-out por corrida y por cuenta en `settings` para tuning sin despliegue de código.
- [ ] Estandarizar ejecución de tests en CI (agregar `pytest` al entorno de desarrollo/CI y pipeline de `backend/tests`).
- [ ] Mantener `totales.total_base_gravada` persistido en v2 como campo canónico (evitar depender solo de cálculos derivados).
- [x] Corregir filtro de monto en exportación por usuario para usar `totales.total` (antes consultaba un campo inexistente `total_monto`).
- [x] Garantizar en `invoice-explorer` la carga de tabla v2 incluso si falla el endpoint de estadísticas del mes (UX resiliente).
- [x] Evitar re-encolado automático de correos ya `pending/success/skipped_ai_limit` para reducir ruido y duplicidad en cola.
- [x] Exponer límites manuales por `settings` (`PROCESS_DIRECT_DEFAULT_LIMIT` / `PROCESS_DIRECT_MAX_LIMIT`) para tuning sin despliegue funcional.
- [x] Implementar matcher robusto de nomenclaturas (`NFKD`, acentos, puntuación, tokens + contains) con sinónimos por tenant.
- [x] Agregar fallback opcional por remitente y nombre de adjunto en discovery IMAP sin descargar el cuerpo completo.
- [x] Exponer en frontend (pantalla de configuración de correo) los campos de Fase 4: sinónimos por tenant y toggles de fallback.
- [x] Ejecutar QA funcional guiado de Fase 4 (casos asunto/remitente/adjunto + evidencia documentada).

## 5) Entregables mínimos por fase

- Código + pruebas automáticas.
- Evidencia de prueba manual (casos clave).
- Actualización de documentación técnica/funcional.
- Checklist de regresión firmado antes de pasar a la siguiente fase.

## 6) Orden de ejecución recomendado

1. Fase 0  
2. Fase 1  
3. Fase 2  
4. Fase 3  
5. Fase 4  
6. Fase 5  
7. Fase 6

---

Este documento es la guía oficial de implementación post-mapeo para este repositorio.
