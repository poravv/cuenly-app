# Fase 4 - Nomenclaturas y Acentos

Fecha: 2026-02-24  
Estado: `IMPLEMENTADO`

## Objetivo

Robustecer la detección de correos por nomenclaturas para evitar falsos negativos por tildes, puntuación y variantes de redacción, manteniendo aislamiento por tenant.

## Cambios implementados

## 1) Matcher robusto reutilizable

Archivo: `backend/app/modules/email_processor/subject_matcher.py`

- Normalización de texto:
  - Unicode `NFKD`
  - remoción de acentos
  - `lowercase` (`casefold`)
  - limpieza de puntuación/no alfanuméricos
  - colapso de espacios
- Estrategia de match:
  - término completo por tokens
  - `contains` por frase normalizada
- Expansión de términos:
  - `search_terms` base
  - `search_synonyms` por tenant (dict o lista)
  - deduplicación por término normalizado

## 2) Soporte configurable por tenant

Archivos:

- `backend/app/models/models.py`
- `backend/app/modules/email_processor/config_store.py`

Nuevos campos de configuración por cuenta:

- `search_synonyms`: sinónimos configurables por tenant.
- `fallback_sender_match`: fallback opcional por remitente.
- `fallback_attachment_match`: fallback opcional por nombre de adjunto.

Persistencia/lectura agregada en `email_configs`:

- `create_config`, `update_config`, `list_configs`, `get_enabled_configs`, `get_by_id`, `get_by_username`.

## 3) Integración en flujo IMAP real

Archivo: `backend/app/modules/email_processor/imap_client.py`

- `IMAPClient.search(...)` ahora soporta:
  - `search_synonyms`
  - `fallback_sender_match`
  - `fallback_attachment_match`
- El matching principal sigue siendo asunto.
- Si se habilita fallback por adjunto, se usa `BODYSTRUCTURE` para extraer nombres de adjuntos sin descargar el cuerpo completo.
- Se agregan métricas de trazabilidad por fuente de match:
  - `subject`
  - `sender`
  - `attachment`

Archivo: `backend/app/modules/email_processor/single_processor.py`

- `search_emails()` pasa la configuración de sinónimos/fallback al cliente IMAP.
- Se propagan los nuevos campos al construir `EmailConfig` desde configuraciones guardadas.

Archivos:

- `backend/app/modules/email_processor/multi_processor.py`
- `backend/app/modules/scheduler/job_handlers.py`

- Se propagan los nuevos campos en flujos manual, automático, rango y full sync.

## 4) API y frontend

Archivo backend:

- `backend/app/api/api.py` (test de configuración IMAP usa nuevos campos).

Archivos frontend:

- `frontend/src/app/models/invoice.model.ts` agrega campos opcionales:
  - `search_synonyms`
  - `fallback_sender_match`
  - `fallback_attachment_match`
- `frontend/src/app/components/email-config/email-config.component.ts`
- `frontend/src/app/components/email-config/email-config.component.html`

UI agregada en configuración de correos:

- checkboxes para `fallback_sender_match` y `fallback_attachment_match`
- editor de grupos de sinónimos por término base
- persistencia en creación (`POST`), edición completa (`PUT`) y parcial OAuth (`PATCH`)

## Pruebas

Nuevo archivo:

- `backend/tests/test_phase4_nomenclature_matching.py`
- `backend/tests/test_phase4_imap_search_fallback.py`

Cobertura incluida:

- normalización con acentos/puntuación
- sinónimos por tenant y deduplicación
- casos reales:
  - `factura electrónica`
  - `facturación`
  - `comprobante`
  - variantes con/sin tilde
- fallback por remitente (opcional)
- fallback por adjunto (opcional)

Ejecución de referencia:

- `PYTHONPATH=backend python3 -m pytest backend/tests -q`

Evidencia funcional guiada:

- `docs/fase4-qa-funcional-guiado.md`
- `docs/qa-docker-produccion-fase4.md`

## Payload de ejemplo (PATCH configuración de cuenta)

```json
{
  "search_terms": ["factura electronica", "comprobante"],
  "search_synonyms": {
    "factura electronica": ["facturación", "documento electrónico"],
    "comprobante": ["comprobante de pago", "cpe"]
  },
  "fallback_sender_match": true,
  "fallback_attachment_match": true
}
```
