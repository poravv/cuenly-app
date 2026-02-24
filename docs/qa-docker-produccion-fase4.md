# QA en Docker Compose Producción - Fase 4

Fecha: 2026-02-24  
Entorno: `docker compose --profile production`

## 1) Estado de contenedores

Comando:

`docker compose ps`

Resultado:

```text
NAME                 IMAGE             SERVICE    STATUS
cuenlyapp-backend    cuenly-backend    backend    Up (healthy)
cuenlyapp-frontend   cuenly-frontend   frontend   Up (healthy)
cuenlyapp-mongodb    mongo:7-jammy     mongodb    Up (healthy)
cuenlyapp-redis      redis:7-alpine    redis      Up (healthy)
cuenlyapp-worker     cuenly-worker     worker     Up (healthy)
```

## 2) Healthcheck backend desplegado

Comando:

`docker compose exec -T backend python -c "import requests; print(requests.get('http://localhost:8000/health').status_code)"`

Resultado:

```text
200
```

## 3) Evidencia funcional de matcher en contenedor desplegado

Comando:

`docker compose exec -T backend ... match_email_candidate(...)`

Resultado:

```text
Factura electrónica SET - marzo => True subject factura electronica
FACTURACIÓN mensual => True subject facturación
Resumen semanal => True sender facturación
Resumen semanal => True attachment comprobante
```

Interpretación:

- Coincide con/sin acentos.
- Sinónimos funcionan en producción.
- Fallback por remitente y adjunto funciona en producción.

## 4) Firma de `IMAPClient.search` en producción

Comando:

`docker compose exec -T backend ... print('search_synonyms' in client.search.__code__.co_varnames)`

Resultado:

```text
has_search_synonyms_arg True
has_fallback_sender_arg True
has_fallback_attachment_arg True
```

## 5) Modelo de configuración con campos de Fase 4

Comando:

`docker compose exec -T backend ... EmailConfig(... search_synonyms, fallback_*)`

Resultado:

```text
email_config_fields_ok True
```

## 6) Validación de build y regresión local (código actual)

Comandos:

- `npm --prefix frontend run build`
- `PYTHONPATH=backend python3 -m pytest backend/tests -q`

Resultados:

- Frontend build: `OK`
- Tests backend: `24 passed`

## 7) Despliegue actualizado y verificación de frontend

Comando:

- `docker compose --profile production up -d --build frontend`

Resultado:

- `frontend` y `backend` reconstruidos y levantados correctamente.
- `docker compose ps` quedó con todos los servicios en estado `healthy`.

Comprobación de contenido desplegado:

- Búsqueda de texto UI en bundle del contenedor frontend:
  - `Conectar Correo Ahora`
  - `Configuración Rápida en 3 pasos`
  - `Guardar y procesar ahora`

Evidencia:

- `grep` en `/usr/share/nginx/html/main.bf8b74c52527a434.js` retorna coincidencias.
- Validación post-redeploy del matcher:
  - `match_email_candidate("FACTURACIÓN marzo", ...) -> (True, 'subject', 'facturación')`
