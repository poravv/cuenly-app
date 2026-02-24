from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class Party(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ruc: Optional[str] = ""
    nombre: Optional[str] = ""
    direccion: Optional[str] = ""
    telefono: Optional[str] = ""
    email: Optional[str] = ""
    actividad_economica: Optional[str] = ""


class Totales(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    exentas: float = 0.0
    gravado_5: float = 0.0
    iva_5: float = 0.0
    gravado_10: float = 0.0
    iva_10: float = 0.0
    total: float = 0.0
    # CRÍTICO: Campos faltantes para template export
    total_operacion: float = 0.0
    monto_exento: float = 0.0
    exonerado: float = 0.0
    total_iva: float = 0.0
    total_descuento: float = 0.0
    anticipo: float = 0.0
    total_base_gravada: float = 0.0
    # ISC — Impuesto Selectivo al Consumo
    isc_total: float = 0.0
    isc_base_imponible: float = 0.0
    isc_subtotal_gravado: float = 0.0


class InvoiceHeader(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    cdc: Optional[str] = ""

    # Documento
    tipo_documento: Optional[str] = "CO"  # CO/CR
    establecimiento: Optional[str] = ""
    punto: Optional[str] = ""
    numero: Optional[str] = ""
    numero_documento: Optional[str] = ""
    message_id: Optional[str] = ""
    fecha_emision: Optional[datetime] = None
    condicion_venta: Optional[str] = "CONTADO"

    # Moneda
    moneda: Optional[str] = "GS"
    tipo_cambio: float = 0.0

    # Identificadores
    timbrado: Optional[str] = ""

    # Partes
    emisor: Optional[Party] = None
    receptor: Optional[Party] = None

    # Totales
    totales: Totales = Field(default_factory=Totales)

    # === Estado de procesamiento ===
    # PROCESSING → DONE | PENDING_AI | FAILED
    status: Optional[str] = "DONE"
    processing_error: Optional[str] = None

    # === Campos nuevos XSD SIFEN v150 ===
    # Verificación SET (gCamFuFD)
    qr_url: Optional[str] = ""
    info_adicional: Optional[str] = ""

    # Tipo de Documento Electrónico (gTimb)
    tipo_documento_electronico: Optional[str] = ""   # ej: "Factura electrónica"
    tipo_de_codigo: Optional[str] = ""               # 1=Factura, 4=Autofactura, 5=NC, 6=ND

    # Indicador de presencia (gCamFE)
    ind_presencia: Optional[str] = ""                # ej: "Operación presencial"
    ind_presencia_codigo: Optional[str] = ""

    # Crédito (gCamCond.gPagCred)
    cond_credito: Optional[str] = ""
    cond_credito_codigo: Optional[str] = ""
    plazo_credito_dias: Optional[int] = 0

    # Ciclo de facturación — servicios (gCamEsp.gGrupAdi)
    ciclo_facturacion: Optional[str] = ""
    ciclo_fecha_inicio: Optional[str] = ""
    ciclo_fecha_fin: Optional[str] = ""

    # Transporte (gTransp)
    transporte_modalidad: Optional[str] = ""
    transporte_modalidad_codigo: Optional[str] = ""
    transporte_resp_flete_codigo: Optional[str] = ""
    transporte_nro_despacho: Optional[str] = ""

    # Metadata / Índices
    email_origen: Optional[str] = ""
    mes_proceso: Optional[str] = ""
    fuente: Optional[str] = ""  # XML_NATIVO / OPENAI_VISION
    minio_key: Optional[str] = ""
    owner_email: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InvoiceDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    header_id: str
    linea: int
    descripcion: str
    cantidad: float
    unidad: Optional[str] = ""
    precio_unitario: float
    total: float
    iva: int = 0  # 0, 5, 10
    owner_email: Optional[str] = ""


class InvoiceDocument(BaseModel):
    header: InvoiceHeader
    items: List[InvoiceDetail]
