# CuenlyApp

Bienvenido a **CuenlyApp**, el producto estrella automatizado para extraer información de facturas a partir de correos electrónicos y consolidarla en archivos Excel. Cuenly simplifica la contabilidad ahorrando tiempo valioso, con procesamiento Inteligente mediante IA y control exhaustivo de transacciones.

🎯 **Estado actual**: Sistema robusto, con subscripciones activas mediante Pagopar, notificaciones UI modernas y seguridad en Kubernetes.

---

## 📚 Documentación Centralizada

Para no tener demasiados archivos `.md` sueltos, la documentación de Cuenly está estructurada en únicamente **tres archivos base**. 

Asegúrate de consultar estos archivos según tu rol o la tarea a realizar:

1. 🚀 **[Este Archivo] README.md**: Información general de configuración e introducción al proyecto.
2. 📖 **[documentacion-funcional.md](docs/documentacion-funcional.md)**: Aquí encontrarás **TODOS** los aspectos de negocio y funcionales de Cuenly.
   - Qué hace el producto.
   - Detalle de cómo se extrae y prioriza el cobro mensual, exportación de Excel, etc.
   - Sistema de notificaciones moderno (Toast UI).
   - Control de trial (Freemium, Pro, Suscripciones).
3. ⚙️ **[documentacion-tecnica.md](docs/documentacion-tecnica.md)**: Aquí encontrarás toda la arquitectura de sistemas:
   - Diagramas Mermaid de Backend y Frontend.
   - Estructura de Base de Datos.
   - **Información completa de integración de pagos con Pagopar (Paso a Paso de Bancard y suscripciones).**
   - Cómo lidiar con métricas de Prometheus, Loki, y Security in Kubernetes.

---

## 📋 Requisitos Previos

### Para Desarrollo
- **Python 3.11+** - Backend.
- **Node.js 18+** - Frontend Angular 17.
- **Docker & Docker Compose** - Para orquestar bases de datos.
- **Tesseract OCR** - IA vision (fallback).

### Para Producción
- **Kubernetes cluster**
- **Firebase project** (Auth / Analytics)
- **OpenAI API Key**
- **SMTP server** (Envío de correos de Alerta)
- **Claves Privadas/Públicas Pagopar** (Cobros locales)

---

## 🛠️ Instalación Rápida (Local)

1. Clona el repositorio:
   ```bash
   git clone https://github.com/poravv/cuenly-app.git
   cd cuenly-app
   ```

2. Configura las variables de entorno en un archivo `.env` en la raíz (Backend) y tu `environment.ts` (Frontend). Es fundamental incluir `OPENAI_API_KEY` y claves de Firebase/Pagopar.
   
3. Inicia los contenedores (stack local estándar):
   ```bash
   docker compose up -d --build
   ```

   Stack dev aislado (opcional, sin pisar puertos del stack estándar):
   ```bash
   docker compose --profile dev up -d --build mongodb-dev redis-dev backend-dev frontend-dev
   ```

4. Accede:
   - Frontend en `http://localhost:4200`
   - Backend API Docs (vía proxy) en `http://localhost:4200/docs`
   - Stack dev aislado: Frontend `http://localhost:4300`, Backend `http://localhost:8001/docs`

---

## 🚀 Despliegue en Producción

Los deployments se gestionan de forma limpia **vía GitHub Actions (CI/CD)**.
Al hacer un push a `main`, se trigerean workflows automáticos que actualizan la imagen de Kubernetes.
Existen configuraciones robustas de **Rate Limiting, Ingress seguro y aislamiento de pods**. Consulta `documentacion-tecnica.md` para ver los detalles.

---

## 📞 Soporte y Roadmap

- Para consultas sobre pagos paraguayos y validación de tokens, dirígete a `documentacion-tecnica.md` en la sección "PAGOPAR".
- Si requieres comprender cómo interactúa el backend con el frontend, revisa los flujos de "Trial" y "Suscripción" en `documentacion-funcional.md`.
