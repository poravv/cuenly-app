from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SifenFieldMapRow:
    xml_tag: str
    normalized_key: str
    invoice_data_field: str
    v2_field_path: str
    export_field_key: Optional[str] = None
    required_in_enterprise_sample: bool = False
    notes: str = ""


# Matriz canónica de mapeo SIFEN -> dominio -> v2 -> export templates.
# Se usa para validación automática en tests de Fase 1.
SIFEN_FIELD_MATRIX: List[SifenFieldMapRow] = [
    SifenFieldMapRow("dFeEmiDE", "fecha", "fecha", "fecha_emision", "fecha", True),
    SifenFieldMapRow("dEst+dPunExp+dNumDoc", "numero_factura", "numero_factura", "numero_documento", "numero_factura", True),
    SifenFieldMapRow("dNumTim", "timbrado", "timbrado", "timbrado", "timbrado", True),
    SifenFieldMapRow("DE@Id", "cdc", "cdc", "cdc", "cdc", True),
    SifenFieldMapRow("dRucEm+dDVEmi", "ruc_emisor", "ruc_emisor", "emisor.ruc", "ruc_emisor", True),
    SifenFieldMapRow("dNomEmi", "nombre_emisor", "nombre_emisor", "emisor.nombre", "nombre_emisor", True),
    SifenFieldMapRow("dDirEmi", "direccion_emisor", "direccion_emisor", "emisor.direccion", "direccion_emisor", True),
    SifenFieldMapRow("dTelEmi", "telefono_emisor", "telefono_emisor", "emisor.telefono", "telefono_emisor", True),
    SifenFieldMapRow("dEmailE", "email_emisor", "email_emisor", "emisor.email", "email_emisor", True),
    SifenFieldMapRow("dDesActEco", "actividad_economica", "actividad_economica", "emisor.actividad_economica", "actividad_economica", True),
    SifenFieldMapRow("dRucRec+dDVRec", "ruc_cliente", "ruc_cliente", "receptor.ruc", "ruc_cliente", True),
    SifenFieldMapRow("dNomRec", "nombre_cliente", "nombre_cliente", "receptor.nombre", "nombre_cliente", True),
    SifenFieldMapRow("dDirRec", "direccion_cliente", "direccion_cliente", "receptor.direccion", "direccion_cliente", True),
    SifenFieldMapRow("dTelRec", "telefono_cliente", "telefono_cliente", "receptor.telefono", "telefono_cliente", True),
    SifenFieldMapRow("dEmailRec", "email_cliente", "email_cliente", "receptor.email", "email_cliente", False),
    SifenFieldMapRow("cMoneOpe", "moneda", "moneda", "moneda", "moneda", True, "XML suele traer PYG; dominio lo normaliza a GS."),
    SifenFieldMapRow("dTiCam", "tipo_cambio", "tipo_cambio", "tipo_cambio", "tipo_cambio", False),
    SifenFieldMapRow("dDCondOpe", "condicion_venta", "condicion_venta", "condicion_venta", "condicion_venta", True),
    SifenFieldMapRow("iIndPres", "ind_presencia_codigo", "ind_presencia_codigo", "ind_presencia_codigo", "ind_presencia_codigo", True),
    SifenFieldMapRow("dDesIndPres", "ind_presencia", "ind_presencia", "ind_presencia", "ind_presencia", True),
    SifenFieldMapRow("iTiDE", "tipo_de_codigo", "tipo_de_codigo", "tipo_de_codigo", "tipo_de_codigo", True),
    SifenFieldMapRow("dDesTiDE", "tipo_documento_electronico", "tipo_documento_electronico", "tipo_documento_electronico", "tipo_documento_electronico", True),
    SifenFieldMapRow("iCondCred", "cond_credito_codigo", "cond_credito_codigo", "cond_credito_codigo", "cond_credito_codigo", True),
    SifenFieldMapRow("dDCondCred", "cond_credito", "cond_credito", "cond_credito", "cond_credito", True),
    SifenFieldMapRow("dPlazoCre", "plazo_credito_dias", "plazo_credito_dias", "plazo_credito_dias", "plazo_credito_dias", True),
    SifenFieldMapRow("dCiclo", "ciclo_facturacion", "ciclo_facturacion", "ciclo_facturacion", "ciclo_facturacion", True),
    SifenFieldMapRow("dFecIniC", "ciclo_fecha_inicio", "ciclo_fecha_inicio", "ciclo_fecha_inicio", "ciclo_fecha_inicio", True),
    SifenFieldMapRow("dFecFinC", "ciclo_fecha_fin", "ciclo_fecha_fin", "ciclo_fecha_fin", "ciclo_fecha_fin", True),
    SifenFieldMapRow("iModTrans", "transporte_modalidad_codigo", "transporte_modalidad_codigo", "transporte_modalidad_codigo", "transporte_modalidad_codigo", True),
    SifenFieldMapRow("dDesModTrans", "transporte_modalidad", "transporte_modalidad", "transporte_modalidad", "transporte_modalidad", True),
    SifenFieldMapRow("iRespFlete", "transporte_resp_flete_codigo", "transporte_resp_flete_codigo", "transporte_resp_flete_codigo", "transporte_resp_flete_codigo", True),
    SifenFieldMapRow("dNuDespImp", "transporte_nro_despacho", "transporte_nro_despacho", "transporte_nro_despacho", "transporte_nro_despacho", True),
    SifenFieldMapRow("dCarQR", "qr_url", "qr_url", "qr_url", "qr_url", True),
    SifenFieldMapRow("dInfAdic", "info_adicional", "info_adicional", "info_adicional", "info_adicional", False),
    SifenFieldMapRow("dSubExe", "monto_exento", "monto_exento", "totales.monto_exento", "monto_exento", True),
    SifenFieldMapRow("dSubExo", "exonerado", "exonerado", "totales.exonerado", "exonerado", True),
    SifenFieldMapRow("dBaseGrav5", "gravado_5", "gravado_5", "totales.gravado_5", "gravado_5", True),
    SifenFieldMapRow("dBaseGrav10", "gravado_10", "gravado_10", "totales.gravado_10", "gravado_10", True),
    SifenFieldMapRow("dIVA5", "iva_5", "iva_5", "totales.iva_5", "iva_5", True),
    SifenFieldMapRow("dIVA10", "iva_10", "iva_10", "totales.iva_10", "iva_10", True),
    SifenFieldMapRow("dTotIVA", "total_iva", "total_iva", "totales.total_iva", "total_iva", True),
    SifenFieldMapRow("dTotOpe", "total_operacion", "total_operacion", "totales.total_operacion", "total_operacion", True),
    SifenFieldMapRow("dTotDesc", "total_descuento", "total_descuento", "totales.total_descuento", "total_descuento", True),
    SifenFieldMapRow("dAnticipo", "anticipo", "anticipo", "totales.anticipo", "anticipo", True),
    SifenFieldMapRow("dTBasGraIVA", "total_base_gravada", "total_base_gravada", "totales.total_base_gravada", "total_base_gravada", True),
    SifenFieldMapRow("dTotGralOpe", "monto_total", "monto_total", "totales.total", "monto_total", True),
    SifenFieldMapRow("dLtotIsc", "isc_total", "isc_total", "totales.isc_total", "isc_total", False),
    SifenFieldMapRow("dBaseImpISC", "isc_base_imponible", "isc_base_imponible", "totales.isc_base_imponible", "isc_base_imponible", False),
    SifenFieldMapRow("dSubVISC", "isc_subtotal_gravado", "isc_subtotal_gravado", "totales.isc_subtotal_gravado", "isc_subtotal_gravado", False),
]
