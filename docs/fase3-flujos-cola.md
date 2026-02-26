# Fase 3 - Flujos de Procesamiento y Cola

Fecha: 2026-02-24  
Estado: `IMPLEMENTADO`

## Objetivo

Unificar manual, automático y rango para priorizar fan-out a cola, con límites exactos y parametrización por entorno.

## Cambios realizados

## 1) Parametrización de batch/límites

Archivo: `backend/app/config/settings.py`

- `EMAIL_BATCH_SIZE` (fallback local): default `50`
- `FANOUT_DISCOVERY_BATCH_SIZE`: default `250`
- `FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN`: default `200`
- `PROCESS_DIRECT_DEFAULT_LIMIT`: default `50`
- `PROCESS_DIRECT_MAX_LIMIT`: default `200`

## 2) Manual (`/process-direct`) con límites reales configurables

Archivo: `backend/app/api/api.py`

- El endpoint usa defaults/máximos desde settings.
- Si `limit` es nulo o inválido, usa `PROCESS_DIRECT_DEFAULT_LIMIT`.
- Si excede máximo, aplica `PROCESS_DIRECT_MAX_LIMIT`.

## 3) Fan-out con cap global + cap por cuenta

Archivo: `backend/app/modules/email_processor/multi_processor.py`

- `process_limited_emails(...)` ahora:
  - respeta cap global exacto (`limit`)
  - aplica cap por cuenta (`FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN`)
  - encola en múltiples cuentas solo hasta completar límite global

## 4) Automático y rango priorizan fan-out

Archivo: `backend/app/modules/email_processor/multi_processor.py`

- `process_all_emails(...)` ejecuta `single.process_emails(..., fan_out=True, max_discovery_emails=cap_por_cuenta)` tanto en modo paralelo como secuencial.

Archivo: `backend/app/modules/scheduler/job_handlers.py`

- `handle_full_sync_job` también usa fan-out con cap por cuenta.

## 5) Política de búsqueda e idempotencia de cola

Archivo: `backend/app/modules/email_processor/single_processor.py`

- Política de búsqueda:
  - flujo normal/manual: usa `UNSEEN` por defecto
  - flujo por rango: fuerza `ALL` para recorrer históricos del período solicitado
- Trazabilidad de fan-out:
  - encolados
  - omitidos por estado existente
  - reencolados solo desde estados explícitamente reintentables
- Evita duplicidad de cola/procesamiento:
  - reserva atómica previa por correo (`status=processing`)
  - no reencola ni reprocesa correos ya reservados/procesados desde cualquier botón/método
  - reintentos permitidos solo para `skipped_ai_limit`, `skipped_ai_limit_unread` y `retry_requested`

## 6) Frontend default alineado

Archivo: `frontend/src/app/services/api.service.ts`

- `processEmailsDirect()` ahora usa default `50`.

## Pruebas

Nuevo archivo:

- `backend/tests/test_phase3_fanout_limits.py`

Casos cubiertos:

- límite global exacto en fan-out manual
- cap por cuenta + cap global
- aplicación de default/max configurable para manual

Ejecución:

- `PYTHONPATH=backend python3 -m pytest backend/tests/test_sifen_mapping_phase1.py backend/tests/test_export_template_phase2.py backend/tests/test_phase3_fanout_limits.py -q`
- Resultado: `9 passed`

Validación frontend:

- `npm --prefix frontend run build`
- Resultado: `OK`
