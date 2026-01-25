# Recomendaciones de Integración y Optimización - Cuenly

Este documento describe prácticas recomendadas para mejorar la arquitectura, seguridad, rendimiento y mantenibilidad del proyecto Cuenly, considerando su stack actual (Angular, FastAPI, MongoDB, Docker).

## 1. Arquitectura y Backend (FastAPI + MongoDB)

### Optimización de Procesamiento en Segundo Plano
Actualmente, el procesamiento de PDFs e imágenes con OCR y OpenAI puede ser intensivo.
- [x] **Recomendación**: Desacoplar completamente el procesamiento pesado del ciclo de vida de la solicitud HTTP.
- [x] **Implementación**:
  - [x] Utilizar **RQ** (en lugar de Celery) con **Redis** como broker. (Código implementado en `worker.py` y `async_jobs.py`)
  - [x] Los endpoints de `/upload` y `/process` deben solo encolar la tarea y devolver un `job_id`. (Implementado `/tasks/process` y validaciones)
  - [x] **Redis**: Gestionado externamente (no en docker-compose local).

### Almacenamiento de Archivos (Object Storage)
- **Problemática**: Guardar archivos en disco local dentro de contenedores dificulta la escalabilidad horizontal.
- [x] **Recomendación**: Migrar el almacenamiento de archivos a un servicio de Object Storage compatible con S3 (AWS S3, MinIO, Google Cloud Storage).
- [x] **Beneficio**: 
  - Persistencia segura independiente del ciclo de vida del contenedor.
  - Capacidad de servir archivos estáticos directamente desde CDN si es necesario.
- [x] **MinIO**: Gestionado externamente (no en docker-compose local). Código soporta integración.

### Optimización de Base de Datos (MongoDB)
- [x] **Índices**: Asegurar índices en campos de búsqueda frecuente:
  - [x] `invoices.fecha_emision` (para rangos de fecha y reportes). (Verificado en `mongo-init.js`)
  - [x] `invoices.emisor.ruc` (para filtrar por proveedor). (Verificado en `mongo-init.js`)
  - [x] `headers.year_month` (para agregaciones mensuales rápidas). (Verificado en `mongo-init.js`)
- [x] **Proyecciones**: En endpoints de listado (`/invoice-explorer`), usar proyecciones para retornar solo los campos necesarios. (Implementado en mappings y repositorios)

## 2. Frontend (Angular)

### Rendimiento y Carga (Lazy Loading)
- [x] **Recomendación**: Implementar Lazy Loading para módulos grandes.
- [x] **Detalle**: El módulo de administración (`AdminModule`) y reportes (`ReportsModule`) no deberían cargarse para usuarios normales.
- [x] **Acción**: Separar rutas en `loadChildren`. (Implementado: AdminModule carga perezosa)

### Gestión de Estado
- Si la aplicación crece, el manejo de estado disperso en servicios (`AuthService`, `UserService`, `ApiService`) puede volverse difícil de mantener.
- [ ] **Recomendación**: Considerar adoptar un patrón Redux simplificado (como **Akita** o **NgRx**).
- **¿Por qué?**: Estas librerías crean una "base de datos única" en el navegador para toda la app. Ayuda a evitar bugs donde una pantalla muestra un dato viejo y otra el nuevo, y facilita mucho el debugging.

### Optimización de Assets
- [x] Usar formatos de imagen de nueva generación (WebP) para assets estáticos. (Lógica en `storage.py` para convertir)
- [x] Habilitar compresión Gzip/Brotli en la configuración de Nginx (`frontend/nginx.conf`). (Verificado `gzip on` en nginx)

## 3. Seguridad

### Rate Limiting (Limitación de Tasa)
- [x] **Estado Actual**: Nginx tiene una configuración básica. (Verificado `limit_req_zone`)
- [x] **Mejora**: Implementada a nivel de Infraestructura (K8s Ingress / ConfigMap). No requerido en Backend.

### Validación de Entradas
- [x] Reforzar la validación de tipos MIME en el backend para subidas de archivos (no confiar solo en la extensión). (Parcialmente en `storage.py` y `api.py`)
- [ ] **Recomendación**: Usar `python-magic` para verificar headers de archivos reales.
- **¿Por qué?**: Actualmente confiamos en la extensión (ej. `.pdf`). `python-magic` lee los primeros bytes (binarios) del archivo para asegurar que *realmente* es un PDF y no un ejecutable o script malicioso renombrado.

### CORS y Headers de Seguridad
- [x] Restringir `allow_origins` en producción a dominios específicos. (Verificado en `api.py`)
- [x] Implementar **Content Security Policy (CSP)**. (Implementado en K8s Ingress Headers).

## 4. DevOps e Infraestructura

### CI/CD Pipeline
- [x] Automatizar pruebas y despliegue usando GitHub Actions o GitLab CI.
  - [x] **Fase 1**: Linting (Frontend/Backend) y Tests Unitarios. (Verificado `.github/workflows`)
  - [x] **Fase 2**: Construcción y push de imágenes Docker a registro privado.
  - [x] **Fase 3**: Despliegue automático a entorno de Staging.



---
*Generado por Antigravity Agent - 2025*
