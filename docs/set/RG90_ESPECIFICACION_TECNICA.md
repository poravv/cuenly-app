# Resolucion General 90 (RG-90) — Especificacion Tecnica y Funcional

> Sistema Marangatu — DNIT (ex SET) Paraguay
> Documento interno CuenlyApp

---

## 1. Objetivo

La RG-90 obliga a contribuyentes a presentar libros de Compras, Ventas, Ingresos y Egresos en formato digital ante la DNIT a traves del sistema Marangatu. CuenlyApp genera estas planillas automaticamente a partir de las facturas electronicas (SIFEN) ya procesadas.

---

## 2. Hojas de la Planilla

| Hoja | Descripcion |
|------|-------------|
| **COMPRAS** | Facturas recibidas de proveedores (principal para CuenlyApp) |
| **VENTAS** | Facturas emitidas a clientes |
| **INGRESOS** | Salarios, dividendos, intereses (IRP-RSP) |
| **EGRESOS** | Pagos de IPS, gastos no comerciales (IRP-RSP) |

---

## 3. Estructura de Columnas — Hoja COMPRAS (20 columnas)

| Col | Nombre | Tipo | Ejemplo / Regla |
|-----|--------|------|-----------------|
| A | Codigo Tipo de Registro | Num | Siempre `2` (Compras/Egresos) |
| B | Codigo Tipo de ID del Proveedor | Num | `1`=RUC, `2`=CI, `3`=Pasaporte |
| C | Nro Identificacion Proveedor | Texto | RUC **sin** digito verificador. Ej: `80012345-6` → `80012345` |
| D | Nombre/Razon Social Proveedor | Texto | Nombre completo |
| E | Codigo Tipo de Comprobante | Num | `1`=Factura, `2`=NC, `3`=ND... |
| F | Fecha Emision | Fecha | `DD/MM/YYYY` |
| G | Numero de Timbrado | Texto | 8 digitos |
| H | Numero del Comprobante | Texto | `001-001-0000001` (15 chars) |
| I | Monto Gravado 10% (IVA INCLUIDO) | Num | `gravado_10 + iva_10` |
| J | Monto Gravado 5% (IVA INCLUIDO) | Num | `gravado_5 + iva_5` |
| K | Monto No Gravado o Exento | Num | `monto_exento` |
| L | Monto Total del Comprobante | Num | `monto_total` |
| M | Condicion de Compra | Num | `1`=Contado, `2`=Credito |
| N | Operacion en Moneda Extranjera | Flag | `S` si moneda != PYG/GS |
| O | Imputa al IVA | Flag | `S` o `N` |
| P | Imputa al IRE | Flag | `S` o `N` |
| Q | Imputa al IRP-RSP | Flag | `S` o `N` |
| R | No Imputa | Flag | `S` o `N` |
| S | Nro Comprobante Venta Asociado | Texto | Vacio si no aplica |
| T | Timbrado Comprobante Asociado | Texto | Vacio si no aplica |

---

## 4. Estructura de Columnas — Hoja VENTAS (19 columnas)

| Col | Nombre | Tipo | Ejemplo / Regla |
|-----|--------|------|-----------------|
| A | Codigo Tipo de Registro | Num | Siempre `1` |
| B | Codigo Tipo de ID del Comprador | Num | `1`=RUC, `2`=CI, `3`=Pasaporte |
| C | Nro Identificacion Comprador | Texto | RUC sin DV |
| D | Nombre/Razon Social Comprador | Texto | Nombre completo |
| E | Codigo Tipo de Comprobante | Num | `1`=Factura, `2`=NC, `3`=ND... |
| F | Fecha Emision | Fecha | `DD/MM/YYYY` |
| G | Numero de Timbrado | Texto | 8 digitos |
| H | Numero del Comprobante | Texto | `001-001-0000001` |
| I | Monto Gravado 10% (IVA INCLUIDO) | Num | `gravado_10 + iva_10` |
| J | Monto Gravado 5% (IVA INCLUIDO) | Num | `gravado_5 + iva_5` |
| K | Monto No Gravado o Exento | Num | `monto_exento` |
| L | Monto Total del Comprobante | Num | `monto_total` |
| M | Codigo Condicion de Venta | Num | `1`=Contado, `2`=Credito |
| N | Operacion en Moneda Extranjera | Flag | `S`/`N` |
| O | Imputa al IVA | Flag | `S`/`N` |
| P | Imputa al IRE | Flag | `S`/`N` |
| Q | Imputa al IRP-RSP | Flag | `S`/`N` |
| R | Nro Comprobante Venta Asociado | Texto | Para NC/ND |
| S | Timbrado Comprobante Asociado | Texto | Para NC/ND |

---

## 5. Reglas de Formato de Datos

### 5.1 RUC
- Extraer solo el cuerpo, sin digito verificador
- Ejemplo: `80012345-6` → `80012345`
- Si es CI o Pasaporte, usar el numero completo

### 5.2 Timbrado
- String de exactamente 8 digitos
- Sin guiones ni separadores

### 5.3 Numero de Comprobante
- Formato: `EEE-PPP-NNNNNNN` (15 caracteres con guiones)
  - `EEE` = establecimiento (3 digitos)
  - `PPP` = punto de expedicion (3 digitos)
  - `NNNNNNN` = numero secuencial (7 digitos)

### 5.4 Fechas
- Formato estricto: `DD/MM/YYYY`
- Ejemplo: `15/03/2026`

### 5.5 Montos
- Numeros enteros (sin decimales para Guaranies)
- Sin separadores de miles
- Sin formato de moneda
- Tipo de dato: Texto (para evitar alteracion por Excel)

### 5.6 Flags (S/N)
- Solo admiten `S` (Si) o `N` (No)
- No admiten valores vacios

---

## 6. Logica de Calculo de Montos (IVA Incluido)

La RG-90 requiere montos **CON IVA incluido**, no bases imponibles.

| Columna | Formula |
|---------|---------|
| Gravado 10% (col I) | `base_gravada_10 + iva_10` |
| Gravado 5% (col J) | `base_gravada_5 + iva_5` |
| Exento (col K) | `monto_exento` (sin cambios) |
| Total (col L) | `col_I + col_J + col_K` |

### Formulas inversas (verificacion contable / Formulario 120)

```
IVA efectivo 10% = Monto_Gravado_10 / 11
IVA efectivo 5%  = Monto_Gravado_5  / 21
```

---

## 7. Logica de Imputacion (Flags)

| Flag | Cuando marcar "S" |
|------|-------------------|
| **IMPUTA IVA** | Si la factura genera credito/debito fiscal |
| **IMPUTA IRE** | Si el gasto es deducible para el IRE |
| **IMPUTA IRP-RSP** | Si aplica a Rentas de Servicios Personales |
| **NO IMPUTA** | Solo si el gasto no es deducible de ningun impuesto |

- Un mismo comprobante puede imputar a multiples impuestos (IVA + IRE + IRP).
- "No Imputa" es exclusivo: si es `S`, los demas deben ser `N`.

---

## 8. Catalogo de Codigos DNIT (Marangatu)

El sistema Marangatu **no acepta texto descriptivo** en las columnas de codigo. Solo acepta los valores numericos definidos por la DNIT.

### 8.1 Codigo Tipo de Registro

| Codigo | Descripcion | Uso |
|--------|-------------|-----|
| `1` | Registro de Venta / Ingreso | Hojas VENTAS e INGRESOS |
| `2` | Registro de Compra / Egreso | Hojas COMPRAS y EGRESOS |

### 8.2 Codigo Tipo de Identificacion

| Codigo | Descripcion |
|--------|-------------|
| `1` | RUC (Paraguay) |
| `2` | Cedula de Identidad (Paraguay) |
| `3` | Pasaporte |
| `4` | Identificacion Tributaria del pais de origen (extranjeros) |
| `5` | Sin identificacion (ventas menores / "Sin Nombre") |

### 8.3 Codigo Tipo de Comprobante

| Codigo | Descripcion |
|--------|-------------|
| `1` | Factura |
| `2` | Nota de Credito |
| `3` | Nota de Debito |
| `4` | Autofactura |
| `11` | Liquidacion de Salarios (comun en Egresos IRP) |

### 8.4 Codigo Condicion de Venta/Compra

| Codigo | Descripcion |
|--------|-------------|
| `1` | Contado |
| `2` | Credito |

### 8.5 Flags de Imputacion

| Valor | Significado |
|-------|-------------|
| `S` | Si — el comprobante imputa a este impuesto |
| `N` | No — el comprobante no imputa a este impuesto |

**Reglas de imputacion:**
- **IMPUTA IVA** = `S` si el contribuyente es de IVA y la factura genera credito/debito fiscal
- **IMPUTA IRE** = `S` si el gasto es deducible para el Impuesto a las Rentas Empresariales (Simple o Resimple)
- **IMPUTA IRP-RSP** = `S` si el gasto es deducible para la Renta Personal
- **NO IMPUTA** = `S` solo si las tres anteriores son `N` (gasto real pero no deducible)
- Un mismo comprobante puede imputar a multiples impuestos simultaneamente (IVA + IRE + IRP)

### 8.6 Columnas Especiales (Ingresos y Egresos)

| Columna | Descripcion |
|---------|-------------|
| Nro Identificacion del Empleador (IPS) | RUC de la empresa o numero patronal (solo en Egresos, para aportes IPS) |
| Especificar Tipo de Documento | Descripcion breve si el tipo de comprobante no es estandar (ej: "Recibo de Alquiler") |
| Comprobante Asociado / Timbrado Asociado | Solo para Notas de Credito: numero y timbrado de la factura original anulada/modificada |

---

## 9. Reglas de Exportacion Final

### 9.1 Formato de archivo
- CSV delimitado por comas (`,`) o punto y coma (`;`)
- Encoding: **UTF-8 sin BOM**
- **SIN fila de encabezados** (datos desde fila 1)

### 9.2 Compresion
- El CSV debe empaquetarse en un archivo `.zip`
- **Regla critica**: nombre del ZIP = nombre del CSV
  - Ejemplo: `compras_03_2026.zip` contiene `compras_03_2026.csv`

### 9.3 Ejemplo de fila CSV (Compras)

```
1,1,80001234,NOMBRE PROVEEDOR S.A.,1,15/03/2026,12345678,001-002-0000456,110000,0,0,110000,1,N,S,N,S,N,,
```

> Proveedor con RUC 80001234, factura por 110.000 Gs gravado 10%, contado, imputa al IVA y es deducible para IRP.

---

## 10. Mapeo CuenlyApp → RG-90 (COMPRAS)

| Columna RG-90 | Campo CuenlyApp | Transform |
|----------------|-----------------|-----------|
| Tipo Registro | — | Constante `2` (Compras/Egresos) |
| Tipo ID Proveedor | — | Constante `1` (RUC) |
| RUC Proveedor | `ruc_emisor` | `ruc_body` (sin DV) |
| Nombre Proveedor | `nombre_emisor` | Directo |
| Tipo Comprobante | `tipo_de_codigo` | Directo (ya es codigo) |
| Fecha Emision | `fecha` | `date_format` DD/MM/YYYY |
| Timbrado | `timbrado` | Directo |
| Nro Comprobante | `numero_factura` | Directo |
| Gravado 10% (IVA incl) | `gravado_10` + `iva_10` | `sum_fields` |
| Gravado 5% (IVA incl) | `gravado_5` + `iva_5` | `sum_fields` |
| Exento | `monto_exento` | Directo |
| Monto Total | `monto_total` | Directo |
| Condicion Compra | `condicion_venta` | `map_values` (CONTADO→1, CREDITO→2) |
| Moneda Extranjera | `moneda` | `boolean_flag` (!=PYG/GS) |
| Imputa IVA | — | Constante `S` |
| Imputa IRE | — | Constante `S` |
| Imputa IRP-RSP | — | Constante `N` |
| No Imputa | — | Constante `N` |
| Comprobante Asociado | — | Constante ` ` (vacio) |
| Timbrado Asociado | — | Constante ` ` (vacio) |

---

## 11. Implementacion en CuenlyApp

- Template de sistema: `system_code = "rg90_compras"`
- Usa `FieldTransform` en cada `ExportField` para las conversiones
- Asignable a planes via `features.included_system_templates`
- Visible en `/facturas/exportar` con badge "Incluido en tu plan"
- Solo lectura para usuarios (pueden duplicar para personalizar)
- Exporta como Excel (futuro: CSV + ZIP para carga directa a Marangatu)

---

> Documento generado para referencia interna del equipo de desarrollo.
> Basado en la Resolucion General 90 de la DNIT (ex SET) Paraguay.
