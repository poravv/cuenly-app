# Matriz SIFEN Fase 1 (End-to-End)

Fecha: 2026-02-24  
Estado: `IMPLEMENTADO`

Fuente real validada:
- `docs/cuenly-enterprise/Extructura xml_DE.xml`
- `docs/cuenly-enterprise/Estructura_DE xsd.xml`

Matriz canónica en código:
- `backend/app/modules/mapping/sifen_field_matrix.py`

Pruebas automáticas Fase 1:
- `backend/tests/test_sifen_mapping_phase1.py`

## Cobertura principal (extracto)

| XML SIFEN | Normalizado | InvoiceData | V2 Header/Totales | Export |
|---|---|---|---|---|
| `dFeEmiDE` | `fecha` | `fecha` | `fecha_emision` | `fecha` |
| `dEst+dPunExp+dNumDoc` | `numero_factura` | `numero_factura` | `numero_documento` | `numero_factura` |
| `DE@Id` | `cdc` | `cdc` | `cdc` | `cdc` |
| `dNumTim` | `timbrado` | `timbrado` | `timbrado` | `timbrado` |
| `dRucEm+dDVEmi` | `ruc_emisor` | `ruc_emisor` | `emisor.ruc` | `ruc_emisor` |
| `dNomEmi` | `nombre_emisor` | `nombre_emisor` | `emisor.nombre` | `nombre_emisor` |
| `dRucRec+dDVRec` | `ruc_cliente` | `ruc_cliente` | `receptor.ruc` | `ruc_cliente` |
| `dNomRec` | `nombre_cliente` | `nombre_cliente` | `receptor.nombre` | `nombre_cliente` |
| `iIndPres` | `ind_presencia_codigo` | `ind_presencia_codigo` | `ind_presencia_codigo` | - |
| `dDesIndPres` | `ind_presencia` | `ind_presencia` | `ind_presencia` | - |
| `iTiDE` | `tipo_de_codigo` | `tipo_de_codigo` | `tipo_de_codigo` | - |
| `dDesTiDE` | `tipo_documento_electronico` | `tipo_documento_electronico` | `tipo_documento_electronico` | - |
| `iCondCred` | `cond_credito_codigo` | `cond_credito_codigo` | `cond_credito_codigo` | - |
| `dDCondCred` | `cond_credito` | `cond_credito` | `cond_credito` | - |
| `dPlazoCre` | `plazo_credito_dias` | `plazo_credito_dias` | `plazo_credito_dias` | - |
| `dCiclo` | `ciclo_facturacion` | `ciclo_facturacion` | `ciclo_facturacion` | - |
| `iModTrans` | `transporte_modalidad_codigo` | `transporte_modalidad_codigo` | `transporte_modalidad_codigo` | - |
| `dNuDespImp` | `transporte_nro_despacho` | `transporte_nro_despacho` | `transporte_nro_despacho` | - |
| `dCarQR` | `qr_url` | `qr_url` | `qr_url` | - |
| `dSubExe` | `monto_exento` | `monto_exento` | `totales.monto_exento` | `monto_exento` |
| `dSubExo` | `exonerado` | `exonerado` | `totales.exonerado` | `exonerado` |
| `dBaseGrav5` | `gravado_5` | `gravado_5` | `totales.gravado_5` | `gravado_5` |
| `dBaseGrav10` | `gravado_10` | `gravado_10` | `totales.gravado_10` | `gravado_10` |
| `dIVA5` | `iva_5` | `iva_5` | `totales.iva_5` | `iva_5` |
| `dIVA10` | `iva_10` | `iva_10` | `totales.iva_10` | `iva_10` |
| `dTotIVA` | `total_iva` | `total_iva` | `totales.total_iva` | `total_iva` |
| `dTotOpe` | `total_operacion` | `total_operacion` | `totales.total_operacion` | - |
| `dTotDesc` | `total_descuento` | `total_descuento` | `totales.total_descuento` | `total_descuento` |
| `dAnticipo` | `anticipo` | `anticipo` | `totales.anticipo` | `anticipo` |
| `dTBasGraIVA` | `total_base_gravada` | `total_base_gravada` | `totales.total_base_gravada` | `total_base_gravada` |
| `dTotGralOpe` | `monto_total` | `monto_total` | `totales.total` | `monto_total` |
| `dLtotIsc` | `isc_total` | `isc_total` | `totales.isc_total` | - |
| `dBaseImpISC` | `isc_base_imponible` | `isc_base_imponible` | `totales.isc_base_imponible` | - |
| `dSubVISC` | `isc_subtotal_gravado` | `isc_subtotal_gravado` | `totales.isc_subtotal_gravado` | - |

## Nota de alcance

- Esta fase valida la continuidad de mapeo backend y disponibilidad para export donde ya existe campo.
- La exposición completa en tablas frontend y editor de templates se ejecuta en Fase 2 (UI/UX).

