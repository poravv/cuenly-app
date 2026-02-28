# Matriz SIFEN Fase 2 (Tablas + Templates)

Fecha: 2026-02-24  
Estado: `IMPLEMENTADO`

## Objetivo ejecutado

Alinear de punta a punta los campos mapeados para:

- Visualización en tablas frontend (`invoice-list` y `invoice-explorer`).
- Uso real en creación/edición de templates de exportación.
- Validación para evitar campos fantasma o campos no soportados.

## Cambios implementados

### 1) Catálogo canónico de export

Archivo: `backend/app/models/export_template.py`

- Se amplió `AVAILABLE_FIELDS` con campos SIFEN v150 y campos operativos:
  - `tipo_documento_electronico`, `tipo_de_codigo`
  - `ind_presencia*`
  - `cond_credito*`, `plazo_credito_dias`
  - `ciclo_*`
  - `transporte_*`
  - `qr_url`, `info_adicional`
  - `isc_*`
  - `total_operacion`
  - `fuente`, `email_origen`
- Se removieron campos legacy no soportados por `InvoiceData`:
  - `owner_email`, `updated_at`
- Se centralizaron categorías en `AVAILABLE_FIELD_CATEGORIES`.
- Se agregaron utilidades:
  - `get_available_field_categories()`
  - `get_invalid_template_field_keys(...)`

### 2) Validación backend de templates

Archivo: `backend/app/api/api.py`

- `POST /export-templates` y `PUT /export-templates/{id}` ahora validan `field_key`.
- Si hay campos inválidos, retorna `400` con `invalid_fields`.
- `GET /export-templates/available-fields` usa categorías canónicas del modelo.

### 3) Pipeline de export con datos completos

Archivos:

- `backend/app/repositories/mongo_invoice_repository.py`
- `backend/app/api/api.py` (`_mongo_doc_to_invoice_data`)

Mejoras:

- Se incluyeron campos SIFEN extendidos en payload de export.
- Se prioriza `totales.*` canónico para montos (`monto_exento`, `total_iva`, `total_operacion`, `total_base_gravada`, `isc_*`).
- Se corrigió filtro de monto por usuario en export (`totales.total`).

### 4) Frontend tablas y editor de template

Archivos:

- `frontend/src/app/components/invoices-v2/invoices-v2.component.{ts,html}`
- `frontend/src/app/components/invoice-explorer/invoice-explorer.component.{ts,html}`
- `frontend/src/app/components/export-templates/template-editor.component.{ts,html}`
- `frontend/src/app/services/export-template.service.ts`
- `frontend/src/app/models/export-template.model.ts`

Mejoras:

- Tablas muestran campos mapeados en formato básico + detalle expandible (`Campos SIFEN mapeados`).
- `invoice-explorer` ahora carga tabla v2 aunque falle el endpoint de KPIs mensuales.
- Editor de templates usa categorías dinámicas del backend (sin hardcode legacy).
- Validación frontend evita guardar templates con campos no soportados.

## Pruebas de fase

Archivo nuevo:

- `backend/tests/test_export_template_phase2.py`

Cubre:

- Consistencia de `AVAILABLE_FIELDS` y categorías.
- Validación de `field_key` inválidos en templates.
- Payload de export construido desde repositorio con campos SIFEN extendidos y filtros de monto correctos.

Ejecución local realizada:

- `python3 -m py_compile ...` (backend modificado): OK
- `PYTHONPATH=backend python3` (ejecución manual de tests Fase 1 + Fase 2): OK
- `npm --prefix frontend run build`: OK

Nota de entorno:

- `pytest` no está instalado en este entorno local, por eso se ejecutaron pruebas por invocación manual de funciones de test.
