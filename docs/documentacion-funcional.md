# Documentación Funcional CuenlyApp

## Producto

CuenlyApp automatiza la captura y consulta de facturas para usuarios que reciben comprobantes por correo o los cargan manualmente.

## Funciones Activas

- Login con Google/Firebase.
- Perfil de usuario con datos requeridos para suscripción.
- Configuración de cuentas de correo IMAP u OAuth Gmail.
- Procesamiento manual, automático y por rango histórico.
- Cola visible al usuario con eventos pendientes, fallidos y reintentables.
- Procesamiento XML SIFEN nativo y procesamiento IA para PDF/imagen cuando hay cupo.
- Consulta de facturas por cabecera e ítems.
- Export templates y exportación de datos.
- Suscripciones Pagopar/Bancard con cobro inicial y cobros recurrentes.
- Administración de usuarios, planes, suscripciones, auditoría, colas y límites IA.

## Flujos Principales

### Configuración de Correo

1. Usuario inicia sesión.
2. Completa perfil si el flujo lo requiere.
3. Configura una o más cuentas de correo.
4. Define términos de búsqueda y fecha inicial de procesamiento.
5. Inicia procesamiento manual o deja la automatización operativa.

### Procesamiento

1. Backend descubre correos candidatos.
2. XML se procesa de forma nativa.
3. PDF/imagen usa IA si el usuario tiene cupo.
4. Si no hay cupo IA, el evento queda visible en cola como pendiente/no reintentable o reintentable según origen.
5. Facturas válidas se guardan en `invoice_headers` e `invoice_items`.

### Cola del Usuario

La pantalla de cola muestra eventos persistidos en `processed_emails` y jobs activos en RQ. Permite cancelar jobs activos y reintentar eventos compatibles con UID IMAP.

### Suscripción

1. Usuario elige plan.
2. Backend verifica/crea cliente Pagopar.
3. Si hay tarjeta existente, cobra el primer mes y activa la suscripción.
4. Si no hay tarjeta, retorna `form_id` para iframe Bancard.
5. Al completar el iframe, backend confirma tarjeta, cobra el primer mes y activa plan.
6. El billing diario cobra renovaciones según `next_billing_date`.

### Cancelación

El usuario o un admin puede cancelar una suscripción. Al cancelar, el backend revierte límites del usuario a plan gratuito y registra estado `cancelled`.

## Estados Relevantes

- Suscripción: `active`, `past_due`, `cancelled`, `expired`.
- Transacción: `success`, `failed`, `pending`.
- Tarea UI: `queued`, `running`, `done`, `error`.
- Eventos de cola: `pending`, `processing`, `failed`, `error`, `missing_metadata`, `pending_ai_unread`, `skipped_ai_limit`.

## Reglas de Negocio

- La fuente de verdad para admins es Firestore `admins`.
- Un usuario solo ve sus facturas, eventos y transacciones por `owner_email`/`user_email`.
- Los límites IA se resetean después de cobros exitosos, no solo por fecha calendario.
- No se puede eliminar la única tarjeta si existe suscripción activa.
- El procesamiento histórico por rango cancela jobs previos del mismo usuario para evitar duplicados.
