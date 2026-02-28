# Integración Pagopar: Suscripciones y Pagos Recurrentes (Paso a Paso)

Este documento describe el **flujo de integración implementado en Cuenly** para el modelo de suscripciones: el usuario se suscribe en la plataforma, y Pagopar debita mes a mes mediante **Catastro de Tarjetas / Pagos Recurrentes**.

> **⚠️ Seguridad Crítica**
> *   **Nunca** expongas `PAGOPAR_PRIVATE_KEY` en el frontend.
> *   Usa el backend para generar tokens (`sha1`) y firmar solicitudes.

---

## 🏗️ 1) Modelo de Datos de Cuenly

Para gestionar la recurrencia, Cuenly utiliza la siguiente estructura en su Base de Datos:

1.  **`subscription_plans`**: Define los planes (`BASIC`, `PRO`, `PREMIUM`), su precio mensual en Guaraníes (PYG) y límites (ej. uso de IA).
2.  **`user_subscriptions`**: Almacena a qué plan está suscrito cada usuario, su estado (`ACTIVE`, `PAST_DUE`, `CANCELLED`) y la fecha de próximo cobro (`next_billing_date`).
3.  **`payment_methods`**: (Temporal) El `alias_token` de la tarjeta no se guarda permanentemente, ya que tiene validez de solo 15 minutos. Siempre se lista al momento de cobrar.

---

## 💳 2) Flujo de Alta de Suscripción (Catastro)

El objetivo de esta fase es vincular de manera segura una tarjeta de crédito/débito al usuario, sin que Cuenly retenga datos sensibles.

### Paso 1 — Crear Cliente en Pagopar (1 sola vez por usuario)
Cuenly registra al usuario en Pagopar generando un *hash* de autenticación.
*   **Token:** `sha1(PRIVATE_KEY + "PAGO-RECURRENTE")`
*   **Endpoint:** `POST /api/pago-recurrente/3.0/agregar-cliente/`
*   **Datos enviados:** RUC o documento, email, nombre, celular.

### Paso 2 — Solicitar Alta de Tarjeta (Form ID)
Pagopar debe preparar un formulario seguro (iframe) para la captura de tarjeta.
*   **Token:** `sha1(PRIVATE_KEY + "PAGO-RECURRENTE")`
*   **Endpoint:** `POST /api/pago-recurrente/3.0/agregar-tarjeta/`
*   **Datos enviados:** URL de retorno a Cuenly, `user_id`.
*   **Respuesta:** `form_id` (Identificador del iframe).

### Paso 3 — Mostrar Iframe de Bancard (Frontend)
Angular toma el `form_id` e inyecta el script de Bancard en un componente seguro.
```javascript
Bancard.Cards.createForm('iframe-container', 'FORM_ID', {});
```

### Paso 4 — Confirmación a la URL de Retorno
Una vez cargada la tarjeta, Bancard redirige al usuario a Cuenly.
En este momento, **es obligatorio** avisar a Pagopar que confirmamos el alta.
*   **Token:** `sha1(PRIVATE_KEY + "PAGO-RECURRENTE")`
*   **Endpoint:** `POST /api/pago-recurrente/3.0/confirmar-tarjeta/`

> **✅ Resultado Inicial:** Tarjeta catastrada exitosamente. Cuenly guarda la suscripción como `ACTIVE` y realiza el primer cobro de forma síncrona. Se establece el `next_billing_date` para dentro de 30 días.

---

## 🔄 3) Cobro Mensual (Job Automático en Backend)

A los 30 días, el cronjob de Cuenly (`subscription_billing_job`) ejecuta el siguiente paso a paso automático para recolectar el pago mensual.

### Paso A — Iniciar Transacción (El Pedido)
Cuenly avisa a Pagopar que pretende cobrar un monto específico acorde al plan.
*   **Token de Pedido:** `sha1(PRIVATE_KEY + ID_PEDIDO + MONTO_TOTAL)`
*   **Endpoint:** `POST /api/comercios/2.0/iniciar-transaccion`
*   **Datos:** Monto a cobrar, comprador, concepto (Ej: "Suscripción PRO").
*   **Respuesta Clave:** `hash_pedido`.

### Paso B — Obtener Token Temporal de Tarjeta (El Plástico)
Inmediatamente después, Cuenly solicita acceder a la tarjeta catastrada en el paso 2.
*   **Token Requerido:** `sha1(PRIVATE_KEY + "PAGO-RECURRENTE")`
*   **Endpoint:** `POST /api/pago-recurrente/3.0/listar-tarjeta/`
*   **Respuesta Clave:** `alias_token` (Válido solo por 15 minutos).

### Paso C — Ejecutar el Débito
Cuenly cruza el "Pedido" (Paso A) con la "Tarjeta" (Paso B).
*   **Token Requerido:** `sha1(PRIVATE_KEY + "PAGO-RECURRENTE")`
*   **Endpoint:** `POST /api/pago-recurrente/3.0/pagar/`
*   **Cuerpo (Payload):**
    ```json
    {
      "token": "TOKEN_SEGURO",
      "token_publico": "TU_PUBLIC_KEY",
      "hash_pedido": "HASH_PEDIDO_PASO_A",
      "tarjeta": "ALIAS_TOKEN_PASO_B",
      "identificador": "USER_ID"
    }
    ```

---

## 🚦 4) Manejo de Estados y Morosidad

Dependiendo de la respuesta del **Paso C (Ejecutar Débito)**, Cuenly actualiza su base de datos interna:

*   🟢 **Cobro Exitoso:** 
    *   La fecha de vencimiento (`next_billing_date`) se actualiza a `fecha_actual + 30 días`.
    *   Suscripción se mantiene `ACTIVE`.
    *   Límites de IA en la cuenta se reestablecen.

*   🔴 **Cobro Fallido (Falta de fondos, error de conexión, etc.):** 
    *   Estado de suscripción pasa a `PAST_DUE`.
    *   El usuario pierde temporalmente los beneficios automáticos del plan.
    *   El sistema programará reintentos según política interna (ej. Días 1, 3, 7).
    *   Si los reintentos se agotan, la suscripción pasa a `CANCELLED`.

---

> *Base documental extraída de `pagopar_suscripciones_paso_a_paso_recomendado` y adaptada al backend implementado en CuenlyApp.*

---

## 💳 5) Tarjetas de Prueba - Pagopar Sandbox

Este bloque recopila las tarjetas de crédito válidas para realizar pruebas en el entorno **Sandbox** de Pagopar, separadas por proveedor.

> **⚠️ Importante:** Estas tarjetas solo funcionan en el entorno de pruebas. Nunca las uses en producción.

### 🟢 Proveedor: uPay (Cybersource)
Recomendado para pruebas de tarjetas internacionales o flujo uPay.

| Marca | Número de Tarjeta | Vencimiento | CVV | Notas |
| :--- | :--- | :--- | :--- | :--- |
| **Visa** | `4111 1111 1111 1111` | Cualquier fecha futura (ej. 12/30) | 123 | Tarjeta estándar de prueba Cybersource |
| **Mastercard** | `5454 5454 5454 5454` | Cualquier fecha futura | 123 | Alternativa para MC |

### 🔵 Proveedor: Bancard (vPOS 2.0)
Recomendado si uPay falla en Sandbox, suele ser más estable para pruebas locales.

| Marca | Número de Tarjeta | Vencimiento | CVV | Notas |
| :--- | :--- | :--- | :--- | :--- |
| **Visa** | `4000 0000 0000 0001` | Cualquier fecha futura (ej. 12/30) | 123 | Tarjeta de éxito garantizado |
| **Mastercard** | `5100 0000 0000 0000` | Cualquier fecha futura | 123 | |
| **Amex** | `3782 8224 6310 005` | Cualquier fecha futura | 1234 | |

### 🛠️ Datos Comunes para el Formulario
Al llenar el formulario de catastro/pago:

*   **Nombre del Titular:** `Test User` o `Pagopar Test`
*   **Cédula/RUC:** `1234567` (o cualquier número válido)
*   **Dirección:** `Calle de Prueba 123`
*   **Teléfono:** `0981123456`
*   **Email:** Tu email de desarrollador (para recibir comprobantes de prueba)

### ❌ Solución de Errores Comunes
*   **"Complete todos los datos de la tarjeta" / Rechazo inmediato:** Indica que estás usando un número de tarjeta inválido o generado al azar. Usa estrictamente los números de esta lista.
*   **Error "No existe comprador":** El cliente no está registrado en Pagopar. El backend ahora tiene un sistema de auto-reparación, simplemente reintenta la operación.
*   **Iframe en blanco:** Verifica que la URL de retorno sea HTTPS (en local usa `ngrok`).
