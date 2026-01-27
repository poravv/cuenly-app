# 💳 Tarjetas de Prueba - Pagopar Sandbox

Este documento recopila las tarjetas de crédito válidas para realizar pruebas en el entorno **Sandbox** de Pagopar, separadas por proveedor.

> **⚠️ Importante:** Estas tarjetas solo funcionan en el entorno de pruebas. Nunca las uses en producción.

## 🟢 Proveedor: uPay (Cybersource)
Recomendado para pruebas de tarjetas internacionales o flujo uPay.

| Marca | Número de Tarjeta | Vencimiento | CVV | Notas |
| :--- | :--- | :--- | :--- | :--- |
| **Visa** | `4111 1111 1111 1111` | Cualquier fecha futura (ej. 12/30) | 123 | Tarjeta estándar de prueba Cybersource |
| **Mastercard** | `5454 5454 5454 5454` | Cualquier fecha futura | 123 | Alternativa para MC |

---

## 🔵 Proveedor: Bancard (vPOS 2.0)
Recomendado si uPay falla en Sandbox, suele ser más estable para pruebas locales.

| Marca | Número de Tarjeta | Vencimiento | CVV | Notas |
| :--- | :--- | :--- | :--- | :--- |
| **Visa** | `4000 0000 0000 0001` | Cualquier fecha futura (ej. 12/30) | 123 | Tarjeta de éxito garantizado |
| **Mastercard** | `5100 0000 0000 0000` | Cualquier fecha futura | 123 | |
| **Amex** | `3782 8224 6310 005` | Cualquier fecha futura | 1234 | |

## 🛠️ Datos Comunes para el Formulario
Al llenar el formulario de catastro/pago:

*   **Nombre del Titular:** `Test User` o `Pagopar Test`
*   **Cédula/RUC:** `1234567` (o cualquier número válido)
*   **Dirección:** `Calle de Prueba 123`
*   **Teléfono:** `0981123456`
*   **Email:** Tu email de desarrollador (para recibir comprobantes de prueba)

## ❌ Solución de Errores Comunes
*   **"Complete todos los datos de la tarjeta" / Rechazo inmediato:** Indica que estás usando un número de tarjeta inválido o generado al azar. Usa estrictamente los números de esta lista.
*   **Error "No existe comprador":** El cliente no está registrado en Pagopar. El backend ahora tiene un sistema de auto-reparación, simplemente reintenta la operación.
*   **Iframe en blanco:** Verifica que la URL de retorno sea HTTPS (en local usa `ngrok`).
