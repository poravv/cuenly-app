from __future__ import annotations
from typing import Tuple, List, Optional
from datetime import datetime

from app.models.models import InvoiceData
from app.models.invoice_v2 import InvoiceHeader, InvoiceDetail, InvoiceDocument, Party, Totales


def _split_numero(numero: Optional[str]) -> Tuple[str, str, str, str]:
    if not numero:
        return "", "", "", ""
    parts = str(numero).split("-")
    if len(parts) == 3:
        est, pto, num = parts
        return est, pto, num, f"{est}-{pto}-{num}"
    return "", "", numero, numero


def map_invoice(invoice: InvoiceData, fuente: str = "", minio_key: str = "") -> InvoiceDocument:
    est, pto, num, full = _split_numero(getattr(invoice, "numero_factura", ""))
    fecha: Optional[datetime] = getattr(invoice, "fecha", None)
    if fecha and isinstance(fecha, str):
        try:
            fecha = datetime.fromisoformat(fecha)
        except Exception:
            fecha = None

    header_id = (getattr(invoice, "cdc", None) or f"{getattr(invoice, 'ruc_emisor', 'SINRUC')}_{full}_{(fecha or datetime.utcnow()).date().isoformat()}")

    header = InvoiceHeader(
        id=str(header_id),
        cdc=getattr(invoice, "cdc", ""),
        tipo_documento=getattr(invoice, "tipo_documento", "CO") or "CO",
        establecimiento=est,
        punto=pto,
        numero=num,
        numero_documento=full,
        message_id=getattr(invoice, "message_id", "") or "",
        fecha_emision=fecha,
        condicion_venta=(getattr(invoice, "condicion_venta", "CONTADO") or "CONTADO").upper(),
        moneda=(getattr(invoice, "moneda", "GS") or "GS").upper(),
        tipo_cambio=float(getattr(invoice, "tipo_cambio", 0.0) or 0.0),
        timbrado=getattr(invoice, "timbrado", ""),
        emisor=Party(
            ruc=getattr(invoice, "ruc_emisor", ""),
            nombre=getattr(invoice, "nombre_emisor", ""),
            direccion=getattr(invoice, "direccion_emisor", ""),
            telefono=getattr(invoice, "telefono_emisor", ""),
            email=getattr(invoice, "email_emisor", ""),
            actividad_economica=getattr(invoice, "actividad_economica", "")
        ),
        receptor=Party(
            ruc=getattr(invoice, "ruc_cliente", ""),
            nombre=getattr(invoice, "nombre_cliente", ""),
            email=getattr(invoice, "email_cliente", ""),
            direccion=getattr(invoice, "direccion_cliente", ""),
            telefono=getattr(invoice, "telefono_cliente", "")
        ),
        totales=Totales(
            exentas=float(getattr(invoice, "exento", 0) or getattr(invoice, "subtotal_exentas", 0) or 0),
            gravado_5=float(getattr(invoice, "gravado_5", 0) or getattr(invoice, "subtotal_5", 0) or 0),
            iva_5=float(getattr(invoice, "iva_5", 0) or 0),
            gravado_10=float(getattr(invoice, "gravado_10", 0) or getattr(invoice, "subtotal_10", 0) or 0),
            iva_10=float(getattr(invoice, "iva_10", 0) or 0),
            total=float(getattr(invoice, "monto_total", 0) or getattr(invoice, "total_general", 0) or 0),
            # CRÍTICO: Mapear campos faltantes para template export
            total_operacion=float(getattr(invoice, "total_operacion", 0) or 0),
            monto_exento=float(getattr(invoice, "monto_exento", 0) or 0),
            exonerado=float(getattr(invoice, "exonerado", 0) or 0),
            total_iva=float(getattr(invoice, "total_iva", 0) or 0),
            total_descuento=float(getattr(invoice, "total_descuento", 0) or 0),
            anticipo=float(getattr(invoice, "anticipo", 0) or 0),
            total_base_gravada=float(
                getattr(invoice, "total_base_gravada", 0)
                or (
                    float(getattr(invoice, "gravado_5", 0) or getattr(invoice, "subtotal_5", 0) or 0)
                    + float(getattr(invoice, "gravado_10", 0) or getattr(invoice, "subtotal_10", 0) or 0)
                )
            ),
            # ISC
            isc_total=float(getattr(invoice, "isc_total", 0) or 0),
            isc_base_imponible=float(getattr(invoice, "isc_base_imponible", 0) or 0),
            isc_subtotal_gravado=float(getattr(invoice, "isc_subtotal_gravado", 0) or 0),
        ),
        # === Estado de procesamiento ===
        status=getattr(invoice, "status", "DONE") or "DONE",
        processing_error=getattr(invoice, "processing_error", None),
        # === Campos nuevos XSD SIFEN v150 ===
        qr_url=getattr(invoice, "qr_url", "") or "",
        info_adicional=getattr(invoice, "info_adicional", "") or "",
        tipo_documento_electronico=getattr(invoice, "tipo_documento_electronico", "") or "",
        tipo_de_codigo=getattr(invoice, "tipo_de_codigo", "") or "",
        ind_presencia=getattr(invoice, "ind_presencia", "") or "",
        ind_presencia_codigo=getattr(invoice, "ind_presencia_codigo", "") or "",
        cond_credito=getattr(invoice, "cond_credito", "") or "",
        cond_credito_codigo=getattr(invoice, "cond_credito_codigo", "") or "",
        plazo_credito_dias=int(getattr(invoice, "plazo_credito_dias", 0) or 0),
        ciclo_facturacion=getattr(invoice, "ciclo_facturacion", "") or "",
        ciclo_fecha_inicio=getattr(invoice, "ciclo_fecha_inicio", "") or "",
        ciclo_fecha_fin=getattr(invoice, "ciclo_fecha_fin", "") or "",
        transporte_modalidad=getattr(invoice, "transporte_modalidad", "") or "",
        transporte_modalidad_codigo=getattr(invoice, "transporte_modalidad_codigo", "") or "",
        transporte_resp_flete_codigo=getattr(invoice, "transporte_resp_flete_codigo", "") or "",
        transporte_nro_despacho=getattr(invoice, "transporte_nro_despacho", "") or "",
        email_origen=getattr(invoice, "email_origen", ""),
        mes_proceso=getattr(invoice, "mes_proceso", ""),
        fuente=fuente,
        minio_key=minio_key
    )

    items: List[InvoiceDetail] = []
    productos = getattr(invoice, "productos", []) or []
    for idx, p in enumerate(productos, start=1):
        if isinstance(p, dict):
            # Mapeo mejorado para productos desde dict
            desc = p.get("descripcion") or p.get("articulo") or p.get("nombre") or ""
            cant = float(p.get("cantidad", 0) or 0)
            pu = float(p.get("precio_unitario", 0) or 0)
            tot = float(p.get("total", 0) or 0)
            iva = int(p.get("iva", 0) or 0)
        else:
            # Mapeo desde objeto Pydantic
            desc = (getattr(p, "descripcion", "") or 
                   getattr(p, "articulo", "") or 
                   getattr(p, "nombre", "") or "")
            cant = float(getattr(p, "cantidad", 0) or 0)
            pu = float(getattr(p, "precio_unitario", 0) or 0)
            tot = float(getattr(p, "total", 0) or 0)
            iva = int(getattr(p, "iva", 0) or 0)
        items.append(InvoiceDetail(
            header_id=header.id,
            linea=idx,
            descripcion=desc,
            cantidad=cant,
            precio_unitario=pu,
            total=tot,
            iva=iva
        ))

    return InvoiceDocument(header=header, items=items)
