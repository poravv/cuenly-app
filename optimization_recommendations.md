# Recomendaciones de Integración y Optimización - Cuenly

Este documento describe prácticas recomendadas para mejorar la arquitectura, seguridad, rendimiento y mantenibilidad del proyecto Cuenly, considerando su stack actual (Angular, FastAPI, MongoDB, Docker).

## 1. Arquitectura y Backend (FastAPI + MongoDB)

### Optimización de Procesamiento en Segundo Plano
Actualmente, el procesamiento de PDFs e imágenes con OCR y OpenAI puede ser intensivo.
- [x] **Recomendación**: Desacoplar completamente el procesamiento pesado del ciclo de vida de la solicitud HTTP.
- [x] **Implementación**:
  - [x] Utilizar **RQ** (en lugar de Celery) con **Redis** como broker. (Código implementado en `worker.py` y `async_jobs.py`)
  - [x] Los endpoints de `/upload` y `/process` deben solo encolar la tarea y devolver un `job_id`. (Implementado `/tasks/process` y validaciones)
  - [ ] **Falta**: Habilitar Redis en `docker-compose.yml` (actualmente comentado). El worker existe pero no puede conectar.

### Almacenamiento de Archivos (Object Storage)
- **Problemática**: Guardar archivos en disco local dentro de contenedores dificulta la escalabilidad horizontal.
- [x] **Recomendación**: Migrar el almacenamiento de archivos a un servicio de Object Storage compatible con S3 (AWS S3, MinIO, Google Cloud Storage).
- [x] **Beneficio**: 
  - Persistencia segura independiente del ciclo de vida del contenedor.
  - Capacidad de servir archivos estáticos directamente desde CDN si es necesario.
- [ ] **Falta**: Habilitar servicio MinIO en `docker-compose.yml` y configurar credenciales. El código en `storage.py` ya soporta subida a MinIO si las credenciales existen.

### Optimización de Base de Datos (MongoDB)
- [x] **Índices**: Asegurar índices en campos de búsqueda frecuente:
  - [x] `invoices.fecha_emision` (para rangos de fecha y reportes). (Verificado en `mongo-init.js`)
  - [x] `invoices.emisor.ruc` (para filtrar por proveedor). (Verificado en `mongo-init.js`)
  - [x] `headers.year_month` (para agregaciones mensuales rápidas). (Verificado en `mongo-init.js`)
- [x] **Proyecciones**: En endpoints de listado (`/invoice-explorer`), usar proyecciones para retornar solo los campos necesarios. (Implementado en mappings y repositorios)

## 2. Frontend (Angular)

### Rendimiento y Carga (Lazy Loading)
- [ ] **Recomendación**: Implementar Lazy Loading para módulos grandes.
- [ ] **Detalle**: El módulo de administración (`AdminModule`) y reportes (`ReportsModule`) no deberían cargarse para usuarios normales.
- [ ] **Acción**: Separar rutas en `loadChildren`. (Actualmente `app-routing.module.ts` carga todo eager)

### Gestión de Estado
- Si la aplicación crece, el manejo de estado disperso en servicios (`AuthService`, `UserService`, `ApiService`) puede volverse difícil de mantener.
- [ ] Considerar adoptar un patrón Redux simplificado (como **Akita** o **NgRx**) para estados compartidos complejos (filtros globales, caché de datos maestros).

### Optimización de Assets
- [x] Usar formatos de imagen de nueva generación (WebP) para assets estáticos. (Lógica en `storage.py` para convertir)
- [x] Habilitar compresión Gzip/Brotli en la configuración de Nginx (`frontend/nginx.conf`). (Verificado `gzip on` en nginx)

## 3. Seguridad

### Rate Limiting (Limitación de Tasa)
- [x] **Estado Actual**: Nginx tiene una configuración básica. (Verificado `limit_req_zone`)
- [ ] **Mejora**: Implementar Rate Limiting a nivel de aplicación (FastAPI) usando `fastapi-limiter` con Redis. (Pendiente)
- [ ] **Granularidad**: Limites específicos por usuario (`user_id`) en endpoints costosos (ej. OCR, OpenAI) para prevenir abuso de cuotas.

### Validación de Entradas
- [x] Reforzar la validación de tipos MIME en el backend para subidas de archivos (no confiar solo en la extensión). (Parcialmente en `storage.py` y `api.py`)
- [ ] Usar `python-magic` para verificar headers de archivos reales.

### CORS y Headers de Seguridad
- [x] Restringir `allow_origins` en producción a dominios específicos. (Verificado en `api.py`)
- [ ] Implementar **Content Security Policy (CSP)** en Nginx para prevenir XSS. (Falta en `nginx.conf`)

## 4. DevOps e Infraestructura

### CI/CD Pipeline
- [x] Automatizar pruebas y despliegue usando GitHub Actions o GitLab CI.
  - [x] **Fase 1**: Linting (Frontend/Backend) y Tests Unitarios. (Verificado `.github/workflows`)
  - [x] **Fase 2**: Construcción y push de imágenes Docker a registro privado.
  - [x] **Fase 3**: Despliegue automático a entorno de Staging.

### Monitoreo Centralizado
- [ ] Implementar un stack ligero de monitoreo como **Prometheus + Grafana** o **ELK**. (`prometheus-client` instalado pero sin infra)
- [ ] Centralizar logs de contenedores para debugging post- mortem, ya que `docker logs` es efímero.

### Gestión de Secretos
- [ ] Evitar variables de entorno en claro en `docker-compose.yml`.
- [ ] Usar Docker Secrets o un gestor de secretos externo (AWS Secrets Manager, HashiCorp Vault) para credenciales de BD y API Keys.

---
*Generado por Antigravity Agent - 2025*
