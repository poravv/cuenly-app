# Resolución del Error "No existe comprador" en PagoPar

## 📋 Resumen del Problema

El error **"No existe comprador"** (o "No existe comprador") que recibes al llamar al endpoint `/pagopar/cards/init` con `uPay` como proveedor ocurre porque:

1. **PagoPar requiere** que los clientes (compradores) sean registrados ANTES de poder agregar tarjetas
2. El código anterior intentaba registrar al cliente con `add_customer`, pero **continuaba incluso si fallaba**
3. Cuando se llamaba a `agregar-tarjeta`, PagoPar verificaba que el comprador existiera en su base de datos
4. Como el registro falló (silenciosamente), retornaba: **"No existe comprador"**

## 🔧 Cambios Implementados

### 1. **Endpoint `/pagopar/cards/init`** (`backend/app/api/endpoints/pagopar.py`)

**Cambios:**
- ✅ Ahora **FALLA EXPLÍCITAMENTE** si no se puede registrar el cliente en PagoPar
- ✅ Retorna mensajes de error claros y específicos:
  - `403 Forbidden` → "El comercio no tiene permisos habilitados para pagos recurrentes"
  - `500 Internal Error` → "No se pudo registrar el cliente en PagoPar: [razón]"
- ✅ Solo continúa con `agregar-tarjeta` si el cliente fue registrado exitosamente
- ✅ Logs mejorados con emojis para facilitar debugging

### 2. **Servicio PagoPar** (`backend/app/services/pagopar_service.py`)

**Cambios:**
- ✅ Nuevo parámetro `raise_on_error` en el método `_post` para control fino de errores
- ✅ Manejo diferenciado de errores:
  - **HTTP errors** → Excepción con código de estado
  - **Network errors** → Excepción clara
  - **Pagopar errors** → Propagación controlada
- ✅ Los endpoints críticos (`agregar-tarjeta`, `pagar`, etc.) usan `raise_on_error=True`
- ✅ `add_customer` retorna el resultado tal cual para que el endpoint decida cómo manejarlo

## 🔍 Verificación de la Configuración de PagoPar

Para verificar que tu cuenta de PagoPar esté configurada correctamente, necesitas confirmar lo siguiente:

### **A. Permisos del Comercio**

1. **Accede a tu panel de PagoPar**: https://www.pagopar.com/
2. Ve a **"Integrar con mi sitio web"** o **"Configuración"**
3. Verifica que tengas habilitado:
   - ✅ **Pagos Recurrentes v3.0**
   - ✅ **Catastro de Tarjetas**
   - ✅ **Proveedor uPay** (si planeas usarlo)
   - ✅ **Proveedor Bancard** (obligatorio para algunos casos)

4. **Contacta a PagoPar** si no ves estas opciones habilitadas:
   - Email: **administracion@pagopar.com** o **soporte@pagopar.com**
   - Teléfono: Consulta en su sitio web
   - **Solicita explícitamente**: "Habilitar pagos recurrentes con tarjetas (v3.0) con proveedores Bancard y uPay"

### **B. Credenciales Correctas**

Verifica que tus variables de entorno estén correctamente configuradas:

```bash
# .env
PAGOPAR_PUBLIC_KEY=tu_clave_publica_aqui
PAGOPAR_PRIVATE_KEY=tu_clave_privada_aqui
PAGOPAR_BASE_URL=https://api.pagopar.com/api/pago-recurrente/3.0/
```

**Importante:**
- Las claves deben ser las de **PRODUCCIÓN** (o **STAGING** si estás en ambiente de pruebas)
- **NO** deben tener espacios en blanco al inicio o final
- La `PAGOPAR_BASE_URL` debe terminar con `/`

### **C. Ambiente (Staging vs Producción)**

PagoPar tiene dos ambientes:

#### **Staging (Pruebas)**
```
PAGOPAR_BASE_URL=https://api.pagopar.com/api/pago-recurrente/3.0/  # Mismo endpoint
# Pero con credenciales de "Entorno de pruebas" de tu panel
```

#### **Producción**
```
PAGOPAR_BASE_URL=https://api.pagopar.com/api/pago-recurrente/3.0/
# Con credenciales de "Producción" de tu panel
```

**Nota:** En el panel de PagoPar, puedes tener credenciales diferentes para cada ambiente.

## 🧪 Prueba de Diagnóstico

Hemos creado un script de diagnóstico en:
```
backend/test_pagopar_customer.py
```

Para ejecutarlo (detectará automáticamente el problema):

```bash
# Opción 1: Desde Docker
docker-compose exec backend python test_pagopar_customer.py

# Opción 2: Localmente (con venv activo)
cd backend
source venv/bin/activate  # o tu entorno virtual
python test_pagopar_customer.py
```

Este script te dirá exactamente qué está fallando.

## 📊 Posibles Errores y Soluciones

### Error 1: "No existe comprador"
**Causa:** El cliente no fue registrado en PagoPar antes de agregar tarjeta.
**Solución:** ✅ Ya implementada. El código ahora falla explícitamente si no se puede registrar.

### Error 2: "El comercio no tiene permisos"
**Causa:** Tu cuenta de PagoPar no tiene habilitada la funcionalidad de pagos recurrentes.
**Solución:** 
1. Contacta a `administracion@pagopar.com`
2. Solicita: "Habilitar API de Pagos Recurrentes v3.0 con Bancard y uPay"
3. Firma el contrato necesario (si aplica)

### Error 3: "Token no corresponde"
**Causa:** Tu `PAGOPAR_PRIVATE_KEY` o `PAGOPAR_PUBLIC_KEY` son incorrectas.
**Solución:**
1. Ve al panel de PagoPar → "Integrar con mi sitio web"
2. Copia las claves EXACTAMENTE como aparecen
3. Actualiza tu `.env`
4. Reinicia el backend

### Error 4: "Ya existe comprador con ese identificador"
**Causa:** El usuario ya fue registrado previamente en PagoPar (esto es normal).
**Solución:** ✅ El código ahora maneja esto correctamente y continúa con agregar tarjeta.

### Error 5: Network/Connection errors
**Causa:** Problemas de conectividad con la API de PagoPar.
**Solución:**
- Verifica tu conexión a internet
- Verifica que no haya firewall bloqueando `api.pagopar.com`
- Intenta nuevamente después de unos minutos

## 🚀 Próximos Pasos

1. **Reinicia el backend** para aplicar los cambios:
   ```bash
   docker-compose restart backend
   ```

2. **Verifica tus credenciales** de PagoPar siguiendo la sección "Verificación de la Configuración"

3. **Contacta a PagoPar** si no tienes los permisos habilitados

4. **Prueba nuevamente** el endpoint desde el frontend:
   ```bash
   curl 'http://localhost:4200/pagopar/cards/init' \
     -H 'Authorization: Bearer [TU_TOKEN]' \
     -H 'Content-Type: application/json' \
     --data-raw '{"return_url":"http://localhost:4200/payment-methods","provider":"uPay"}'
   ```

5. **Revisa los logs** del backend para ver exactamente qué error retorna PagoPar:
   ```bash
   docker-compose logs -f backend
   ```

## 📞 Soporte de PagoPar

- **Email**: administracion@pagopar.com, soporte@pagopar.com
- **Documentación**: https://soporte.pagopar.com/
- **Teléfono**: Consulta en su sitio web oficial

---

## 📝 Logs Mejorados

Ahora verás logs más claros como:

```
✅ Cliente registrado exitosamente en PagoPar: user@example.com
```

O en caso de error:

```
❌ No se pudo registrar cliente en PagoPar: El comercio no tiene permisos. CF
```

Esto te permitirá identificar rápidamente la causa del problema.

---

**Fecha de implementación:** 2026-01-27  
**Versión de la API de PagoPar:** v3.0  
**Compatibilidad:** Bancard y uPay
