# Recomendaciones de Integración y Optimización - Cuenly

Este documento describe prácticas recomendadas para mejorar la arquitectura, seguridad, rendimiento y mantenibilidad del proyecto Cuenly, considerando su stack actual (Angular, FastAPI, MongoDB, Docker).

## 1. Arquitectura y Backend (FastAPI + MongoDB)

### Optimización de Procesamiento en Segundo Plano
Actualmente, el procesamiento de PDFs e imágenes con OCR y OpenAI puede ser intensivo.
- **Recomendación**: Desacoplar completamente el procesamiento pesado del ciclo de vida de la solicitud HTTP.
- **Implementación**:
  - Utilizar **Celery** con **Redis** como broker.
  - Los endpoints de `/upload` y `/process` deben solo encolar la tarea y devolver un `job_id`.
  - Workers dedicados procesan la cola, liberando el hilo principal de FastAPI.
  - Esto evitará timeouts en Nginx para archivos grandes o respuestas lentas de OpenAI.

### Almacenamiento de Archivos (Object Storage)
- **Problemática**: Guardar archivos en disco local dentro de contenedores dificulta la escalabilidad horizontal.
- **Recomendación**: Migrar el almacenamiento de archivos a un servicio de Object Storage compatible con S3 (AWS S3, MinIO, Google Cloud Storage).
- **Beneficio**: 
  - Persistencia segura independiente del ciclo de vida del contenedor.
  - Capacidad de servir archivos estáticos directamente desde CDN si es necesario.

### Optimización de Base de Datos (MongoDB)
- **Índices**: Asegurar índices en campos de búsqueda frecuente:
  - `invoices.fecha_emision` (para rangos de fecha y reportes).
  - `invoices.emisor.ruc` (para filtrar por proveedor).
  - `headers.year_month` (para agregaciones mensuales rápidas).
- **Proyecciones**: En endpoints de listado (`/invoice-explorer`), usar proyecciones para retornar solo los campos necesarios, excluyendo objetos grandes anidados si no se muestran en la tabla.

## 2. Frontend (Angular)

### Rendimiento y Carga (Lazy Loading)
- **Recomendación**: Implementar Lazy Loading para módulos grandes.
- **Detalle**: El módulo de administración (`AdminModule`) y reportes (`ReportsModule`) no deberían cargarse para usuarios normales.
- **Acción**: Separar rutas en `loadChildren`.

### Gestión de Estado
- Si la aplicación crece, el manejo de estado disperso en servicios (`AuthService`, `UserService`, `ApiService`) puede volverse difícil de mantener.
- Considerar adoptar un patrón Redux simplificado (como **Akita** o **NgRx**) para estados compartidos complejos (filtros globales, caché de datos maestros).

### Optimización de Assets
- Usar formatos de imagen de nueva generación (WebP) para assets estáticos.
- Habilitar compresión Gzip/Brotli en la configuración de Nginx (`frontend/nginx.conf`).

## 3. Seguridad

### Rate Limiting (Limitación de Tasa)
- **Estado Actual**: Nginx tiene una configuración básica.
- **Mejora**: Implementar Rate Limiting a nivel de aplicación (FastAPI) usando `fastapi-limiter` con Redis.
- **Granularidad**: Limites específicos por usuario (`user_id`) en endpoints costosos (ej. OCR, OpenAI) para prevenir abuso de cuotas.

### Validación de Entradas
- Reforzar la validación de tipos MIME en el backend para subidas de archivos (no confiar solo en la extensión).
- Usar `python-magic` para verificar headers de archivos reales.

### CORS y Headers de Seguridad
- Restringir `allow_origins` en producción a dominios específicos.
- Implementar **Content Security Policy (CSP)** en Nginx para prevenir XSS.

## 4. DevOps e Infraestructura

### CI/CD Pipeline
- Automatizar pruebas y despliegue usando GitHub Actions o GitLab CI.
  - **Fase 1**: Linting (Frontend/Backend) y Tests Unitarios.
  - **Fase 2**: Construcción y push de imágenes Docker a registro privado.
  - **Fase 3**: Despliegue automático a entorno de Staging.

### Monitoreo Centralizado
- Implementar un stack ligero de monitoreo como **Prometheus + Grafana** o **ELK**.
- Centralizar logs de contenedores para debugging post- mortem, ya que `docker logs` es efímero.

### Gestión de Secretos
- Evitar variables de entorno en claro en `docker-compose.yml`.
- Usar Docker Secrets o un gestor de secretos externo (AWS Secrets Manager, HashiCorp Vault) para credenciales de BD y API Keys.

---
*Generado por Antigravity Agent - 2025*
