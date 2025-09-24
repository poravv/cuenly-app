# CuenlyApp - Frontend

Este proyecto contiene el frontend para la aplicación CuenlyApp, desarrollado con Angular.

## Descripción

CuenlyApp Frontend es una interfaz de usuario para gestionar y visualizar la extracción de facturas desde correos electrónicos. Permite iniciar el procesamiento de correos, visualizar los resultados, gestionar la automatización del proceso y subir facturas manualmente.

## Requisitos

- Node.js (v14 o superior)
- Angular CLI (v13 o superior)
- Navegador web moderno (Chrome, Firefox, Edge, etc.)

## Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/tu-usuario/cuenlyapp.git
cd cuenlyapp/frontend
```

2. Instala las dependencias:
```bash
npm install
```

3. Configura el entorno:
   - Ajusta la URL de la API en `src/environments/environment.ts` 
   - Para producción, configura `src/environments/environment.prod.ts`

## Ejecución

Para iniciar el servidor de desarrollo:

```bash
ng serve
```

Navega a `http://localhost:4200/` para ver la aplicación.

## Estructura del proyecto

- `src/app/components/` - Componentes de la aplicación
  - `dashboard/` - Panel principal con estado del sistema y acciones
  - `upload/` - Componente para subir facturas manualmente
- `src/app/services/` - Servicios para comunicación con la API
- `src/app/models/` - Interfaces y modelos de datos
- `src/environments/` - Configuraciones de entorno

## Características principales

1. **Panel de control** - Muestra el estado del sistema y permite realizar acciones
2. **Carga manual** - Permite subir archivos PDF de facturas para procesamiento
3. **Automatización** - Gestión de procesos automáticos de extracción
4. **Visualización de resultados** - Muestra las facturas procesadas y permite descargar el Excel

## Componentes

### Dashboard

El componente principal que muestra:
- Estado del sistema (configuración, último Excel generado)
- Acciones (procesar correos, descargar Excel)
- Control de automatización (iniciar/detener proceso automático)
- Últimas facturas procesadas

### Upload

Componente para subir facturas manualmente:
- Selección de archivo PDF
- Información adicional (remitente, fecha)
- Visualización de resultados del procesamiento

## Servicios

### ApiService

Gestiona la comunicación con el backend:
- `getStatus()` - Obtiene el estado del sistema
- `processEmails()` - Inicia el procesamiento de correos
- `uploadPdf()` - Sube un archivo PDF para procesamiento
- `getExcelUrl()` - Obtiene la URL para descargar el Excel
- `startJob()` / `stopJob()` - Controla la automatización
- `getJobStatus()` - Obtiene el estado del proceso automático

## Modelos de datos

- `Invoice` - Estructura de una factura procesada
- `ProcessResult` - Resultado del procesamiento de correos/archivos
- `SystemStatus` - Estado del sistema backend
- `JobStatus` - Estado del proceso automático

## Desarrollo

Para generar nuevos componentes:

```bash
ng generate component components/nombre-componente
```

Para generar nuevos servicios:

```bash
ng generate service services/nombre-servicio
```

## Build para producción

```bash
ng build --prod
```

Los archivos de build se guardarán en el directorio `dist/`.
# Trigger workflow sábado, 20 de septiembre de 2025, 19:19:04 -03
# Trigger workflow domingo, 21 de septiembre de 2025, 02:27
# Trigger workflow domingo, 21 de septiembre de 2025, 02:45
# Trigger workflow domingo, 21 de septiembre de 2025, 03:06
# Trigger workflow domingo, 21 de septiembre de 2025, 03:13
# Trigger workflow domingo, 21 de septiembre de 2025, 03:24
# Trigger workflow domingo, 21 de septiembre de 2025, 11:01
# Trigger workflow domingo, 21 de septiembre de 2025, 15:40
# Trigger workflow domingo, 21 de septiembre de 2025, 15:40
# Trigger workflow domingo, 24 de septiembre de 2025, 09:01
# Trigger workflow domingo, 24 de septiembre de 2025, 10:48