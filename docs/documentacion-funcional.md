# Documentación Funcional de CuenlyApp

CuenlyApp es una herramienta automatizada diseñada para facilitar la extracción, verificación y consolidación de información de facturas a partir de correos electrónicos, exportándola finalmente a archivos Excel personalizables.

## 🎯 Objetivo del Producto

El objetivo principal de Cuenly es ahorrar tiempo en la contabilidad automatizando la lectura de correos, la descarga de adjuntos (PDFs y XMLs), la extracción de los datos de las facturas (usando Inteligencia Artificial cuando es necesario) y la generación de reportes ordenados.

## 🚀 Funcionalidades Principales

### 1. Procesamiento Inteligente de Facturas
El sistema es capaz de conectarse automáticamente a las cuentas de correo electrónico configuradas por el usuario (vía IMAP) y recuperar facturas. 

**Estrategia de priorización:**
1. **Adjuntos XML (Facturación Electrónica):** Máxima prioridad. Se usa un parser nativo gratuito y rápido. Solo si falla, se utiliza IA como respaldo.
2. **Adjuntos PDF:** Se procesan mediante conversión a imagen + OCR y luego se envían a OpenAI Vision (GPT-4o) para extraer los datos estructurados.
3. **Enlaces Externos:** Como último recurso, el sistema visita enlaces en los correos y descarga los comprobantes que encuentre (XML o PDF).

### 2. Exportación y Templates
Los usuarios pueden generar reportes de todas sus facturas procesadas.
- **Plantillas (Templates) dinámicos:** El usuario puede crear *export templates* seleccionando exactamente qué columnas desea en su Excel (ej. RUC, Razón Social, IVA 5%, IVA 10%, Total, etc.).
- **Precisión Financiera:** Los montos de IVA y totales incluyen un sistema de redondeo correcto que previene pérdida de decimales en contabilidad.

### 3. Sistema de Planes y Suscripciones
CuenlyApp cuenta con un esquema de suscripción (Freemium/Premium) administrado mediante **Pagopar**.

**Planes Típicos:**
- **FREE / Trial:** Gratis, límite de 50 facturas/mes.
- **BASIC:** 50,000 PYG/mes, límite de 200 facturas/mes.
- **PRO:** 150,000 PYG/mes, límite de 1,000 facturas/mes.
- **PREMIUM:** 300,000 PYG/mes, facturas ilimitadas.

**Control de Trial Expirado:**
Si un usuario está en su periodo de prueba y éste expira, la automatización se bloquea. El usuario ve alertas visuales y amigables (estado `TRIAL_EXPIRED`) instándolo a actualizar su plan para continuar procesando.

### 4. Panel de Administración (Admin Dashboard)
Los administradores tienen control total sobre la plataforma:
- **Gestión de Usuarios:** Cambiar roles (admin/user) y estados (activar/suspender cuentas).
- **Gestión de Planes:** Creación, edición y eliminación de planes que luego se asocian a los clientes.
- **Auditoría y Estadísticas:** Verificación de métricas de uso y cantidad de facturas parseadas por IA.
- **Control de Límites:** Funciones para reiniciar o modificar los topes de consumo de IA por usuario de forma manual.

### 5. Sistema de Notificaciones Moderno
La aplicación cuenta con feedback visual no intrusivo para todas las acciones del usuario (ejitos, errores, advertencias).
- Notificaciones Toast en la esquina superior que desaparecen automáticamente.
- Confirmaciones de acciones destructivas (ej. "Eliminar plantilla") presentadas de forma elegante, sin bloquear la pantalla con popups nativos del navegador.

## 🔄 Flujos de Usuario Comunes

### Flujo de Onboarding y Configuración de Correo
1. El usuario se registra / hace login vía Firebase (Google OAuth).
2. Se dirige a "Configuración de Email" y añade las credenciales IMAP (ej. correo de Gmail y "App Password").
3. El sistema valida las credenciales y las guarda cifradas.

### Flujo de Sincronización
1. El usuario hace clic en "Procesar Correos" o activa la automatización.
2. (Si su trial está expirado, el sistema bloquea aquí de inmediato y muestra una pantalla para ir a facturación).
3. El backend lee los últimos emails buscando adjuntos válidos (XML/PDF).
4. El sistema sube copias originales a un bucket remoto (MinIO) como respaldo legal.
5. El motor extrae los datos (cabecera de la factura + ítems del producto) y los guarda en la base de datos.
6. El usuario visualiza la grilla de facturas extraídas en el "Explorador de Facturas".

### Flujo de Suscripción y Cobro (Vía Pagopar)
1. El usuario ingresa a la pestaña "Suscripción" y selecciona el plan deseado (ej. PRO).
2. El sistema muestra un formulario seguro de Bancard (PagoPar) para que introduzca los datos de su tarjeta de crédito.
3. Se realiza un "catastro" (guardado seguro del token de la tarjeta).
4. Se realiza el débito inicial de forma síncrona en el momento de crear la suscripción.
5. Mensualmente, un cronjob interno en Cuenly debita automáticamente la siguiente cuota de su tarjeta guardada.
5. Si falla el débito, se reintenta varias veces antes de cancelar el servicio y notificar al usuario.
