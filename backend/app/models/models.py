# app/models/models.py

from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.utils.date_utils import try_parse_date

# -----------------------
# Utilidades
# -----------------------
def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, list):
            for item in value:
                try:
                    return float(str(item).replace(',', '').replace(' ', ''))
                except Exception:
                    continue
            return default
        s = str(value).strip()
        if not s:
            return default
        # normaliza: quita espacios y separadores de miles
        s = s.replace(' ', '')
        if s.count('.') > 1:
            # deja solo el último punto como decimal
            head, dot, tail = s.rpartition('.')
            head = head.replace('.', '')
            s = head + '.' + tail
        s = s.replace(',', '')
        return float(s)
    except Exception:
        return default

# -----------------------
# Submodelos
# -----------------------
class ProductoFactura(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    nombre: Optional[str] = ""
    cantidad: Optional[float] = 0.0
    precio_unitario: Optional[float] = 0.0
    total: Optional[float] = 0.0
    iva: Optional[int] = 0

class EmpresaData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    nombre: Optional[str] = ""
    ruc: Optional[str] = ""
    direccion: Optional[str] = ""
    telefono: Optional[str] = ""
    actividad_economica: Optional[str] = ""

class TimbradoData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    nro: Optional[str] = ""
    fecha_inicio_vigencia: Optional[str] = ""
    valido_hasta: Optional[str] = ""

class FacturaData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contado_nro: Optional[str] = ""
    fecha: Optional[str] = ""
    caja_nro: Optional[str] = ""
    cdc: Optional[str] = ""
    condicion_venta: Optional[str] = ""

class TotalesData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    cantidad_articulos: Optional[int] = 0
    subtotal: Optional[float] = 0.0
    total_a_pagar: Optional[float] = 0.0
    iva_0: Optional[float] = Field(0.0, alias="iva_0%")
    iva_5: Optional[float] = Field(0.0, alias="iva_5%")
    iva_10: Optional[float] = Field(0.0, alias="iva_10%")
    total_iva: Optional[float] = 0.0

class ClienteData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    nombre: Optional[str] = ""
    ruc: Optional[str] = ""
    email: Optional[str] = ""

# -----------------------
# Modelo principal de factura (mapeo directo del XML)
# -----------------------
class InvoiceData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fecha: Optional[datetime] = None
    tipo_documento: Optional[str] = "CO"  # CO contado, CR crédito
    numero_documento: Optional[str] = ""
    ruc_proveedor: Optional[str] = ""
    razon_social_proveedor: Optional[str] = ""
    condicion_compra: Optional[str] = "CONTADO"  # CONTADO | CREDITO

    gravado_10: Optional[float] = 0.0
    iva_10: Optional[float] = 0.0
    gravado_5: Optional[float] = 0.0
    iva_5: Optional[float] = 0.0
    exento: Optional[float] = 0.0
    total_factura: Optional[float] = 0.0

    timbrado: Optional[str] = ""
    cdc: Optional[str] = ""
    moneda: Optional[str] = "GS"   # "GS" si es PYG, "USD" u otra tal cual en factura
    tipo_cambio: Optional[float] = 0.0  # Por defecto 0, se actualiza si hay tipo de cambio específico
    direccion_emisor: Optional[str] = ""
    telefono_emisor: Optional[str] = ""
    email_emisor: Optional[str] = ""

    descripcion_factura: Optional[str] = ""
    detalle_articulos: Optional[str] = ""
    email_origen: Optional[str] = ""

    procesado_en: Optional[datetime] = Field(default_factory=datetime.now)
    mes_proceso: Optional[str] = ""

    # campos “legacy” que siguen llegando desde el parser OpenAI
    ruc_emisor: Optional[str] = ""
    nombre_emisor: Optional[str] = ""
    numero_factura: Optional[str] = ""
    monto_total: Optional[float] = 0.0
    iva: Optional[float] = 0.0
    pdf_path: Optional[str] = ""
    minio_key: Optional[str] = ""

    ruc_cliente: Optional[str] = ""
    nombre_cliente: Optional[str] = ""
    email_cliente: Optional[str] = ""
    direccion_cliente: Optional[str] = ""
    telefono_cliente: Optional[str] = ""
    condicion_venta: Optional[str] = ""  # CONTADO | CREDITO

    subtotal_exentas: Optional[float] = 0.0
    subtotal_5: Optional[float] = 0.0
    subtotal_10: Optional[float] = 0.0

    # === CAMPOS CON NOMBRES EXACTOS DEL XML ===
    base_gravada_5: Optional[float] = 0.0   # Nombre exacto del XML
    base_gravada_10: Optional[float] = 0.0  # Nombre exacto del XML
    monto_exento: Optional[float] = 0.0     # Nombre exacto del XML
    exonerado: Optional[float] = 0.0        # dSubExo del XML
    total_operacion: Optional[float] = 0.0  # dTotOpe del XML
    total_descuento: Optional[float] = 0.0  # dTotDesc del XML 
    total_iva: Optional[float] = 0.0        # dTotIVA del XML
    total_base_gravada: Optional[float] = 0.0  # Total bases gravadas
    anticipo: Optional[float] = 0.0         # dAnticipo del XML

    actividad_economica: Optional[str] = ""
    empresa: Optional[EmpresaData] = None
    timbrado_data: Optional[TimbradoData] = None
    factura_data: Optional[FacturaData] = None
    productos: List[ProductoFactura] = Field(default_factory=list)
    totales: Optional[TotalesData] = None
    cliente: Optional[ClienteData] = None
    observacion: Optional[str] = ""
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict, email_metadata: dict = None):

        fecha_parsed = try_parse_date(data.get("fecha"))

        condicion_venta = (data.get("condicion_venta") or "CONTADO").upper()
        condicion_compra = condicion_venta
        tipo_documento = "CR" if "CREDITO" in condicion_venta else "CO"

        moneda = (data.get("moneda") or "GS").upper()
        if moneda == "PYG":
            moneda = "GS"

        # Fallbacks seguros
        td = data.get("timbrado_data") or {}
        fd = data.get("factura_data") or {}

        timbrado = data.get("timbrado") or td.get("nro") or ""
        cdc = data.get("cdc") or fd.get("cdc") or ""

        numero_doc = data.get("numero_factura") or fd.get("contado_nro") or ""
        
        fecha_parsed = try_parse_date(data.get("fecha"))

        condicion_venta = (data.get("condicion_venta") or "CONTADO").upper()
        condicion_compra = condicion_venta  # mismo valor
        
        # Fix: mapear correctamente Crédito/Contado a CR/CO
        tipo_documento = "CR" if any(word in condicion_venta for word in ["CREDITO", "CRÉDITO", "CREDIT"]) else "CO"

        # Fix: mapear correctamente monedas USD/PYG a valores finales
        moneda = (data.get("moneda") or "GS").upper()
        if moneda in ["PYG", "GUARANI", "GUARANÍES"]:
            moneda = "GS"
        elif moneda in ["USD", "DOLLAR", "DOLAR"]:
            moneda = "USD"
        else:
            # Default para valores desconocidos
            moneda = "GS"

        return cls(
            fecha=fecha_parsed,
            tipo_documento=tipo_documento,
            numero_documento=numero_doc,
            ruc_proveedor=data.get("ruc_emisor"),
            razon_social_proveedor=data.get("nombre_emisor"),
            condicion_compra=condicion_compra,

            gravado_10=safe_float(data.get("subtotal_10")),
            iva_10=safe_float(data.get("iva_10")),
            gravado_5=safe_float(data.get("subtotal_5")),
            iva_5=safe_float(data.get("iva_5")),
            exento=safe_float(data.get("exento") or data.get("subtotal_exentas")),  # Preferir "exento" del XML
            total_factura=safe_float(data.get("monto_total")),

            timbrado=timbrado,
            cdc=cdc,
            moneda=moneda,
            tipo_cambio=safe_float(data.get("tipo_cambio", 0.0)),

            descripcion_factura=data.get("descripcion_factura", ""),
            direccion_emisor=data.get("direccion_emisor", ""),
            telefono_emisor=data.get("telefono_emisor", ""),
            email_emisor=data.get("email_emisor", ""),

            ruc_emisor=data.get("ruc_emisor"),
            nombre_emisor=data.get("nombre_emisor"),
            numero_factura=data.get("numero_factura"),
            monto_total=safe_float(data.get("monto_total")),
            iva=safe_float(data.get("iva")),

            ruc_cliente=data.get("ruc_cliente"),
            nombre_cliente=data.get("nombre_cliente"),
            email_cliente=data.get("email_cliente"),
            direccion_cliente=data.get("direccion_cliente", ""),
            telefono_cliente=data.get("telefono_cliente", ""),
            condicion_venta=condicion_venta,

            subtotal_exentas=safe_float(data.get("exento") or data.get("subtotal_exentas")),  # Usar "exento" del XML
            subtotal_5=safe_float(data.get("subtotal_5")),
            subtotal_10=safe_float(data.get("subtotal_10")),

            # === CAMPOS CRÍTICOS PARA TEMPLATE EXPORT ===
            base_gravada_5=safe_float(data.get("gravado_5")),  # Mapeo correcto XML
            base_gravada_10=safe_float(data.get("gravado_10")),  # Mapeo correcto XML
            monto_exento=safe_float(data.get("monto_exento") or data.get("exento")),  # Campo crítico
            exonerado=safe_float(data.get("exonerado")),  # Campo dSubExo del XML
            total_operacion=safe_float(data.get("total_operacion")),  # Campo crítico  
            total_descuento=safe_float(data.get("total_descuento")),  
            total_iva=safe_float(data.get("total_iva")),
            total_base_gravada=safe_float(data.get("total_base_gravada")),
            anticipo=safe_float(data.get("anticipo")),

            actividad_economica=data.get("actividad_economica"),
            empresa=EmpresaData(**data["empresa"]) if data.get("empresa") else None,
            timbrado_data=TimbradoData(**data["timbrado_data"]) if data.get("timbrado_data") else None,
            factura_data=FacturaData(**data["factura_data"]) if data.get("factura_data") else None,
            # Normalizar productos: asegurar que 'nombre' exista tomando 'descripcion'/'articulo' si es necesario
            productos=[
                (
                    ProductoFactura(**({**p, 'nombre': (p.get('nombre') or p.get('descripcion') or p.get('articulo') or p.get('codigo') or '')}))
                    if isinstance(p, dict)
                    else ProductoFactura(**p.__dict__)
                )
                for p in (data.get("productos", []) or [])
            ],
            totales=TotalesData(**data["totales"]) if data.get("totales") else None,
            cliente=ClienteData(**data["cliente"]) if data.get("cliente") else None,

            email_origen=(email_metadata or {}).get("sender"),
            mes_proceso=fecha_parsed.strftime("%Y-%m") if fecha_parsed else datetime.now().strftime("%Y-%m"),
            created_at=data.get("created_at") if isinstance(data.get("created_at"), datetime) else None,
        )

# Modelo principal - mapea directamente desde XML

# -----------------------
# Configs y resultados
# -----------------------
class MultiEmailConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str] = None
    name: Optional[str] = ""
    host: str
    port: int
    username: str
    password: Optional[str] = None
    use_ssl: bool = True
    search_criteria: str = "UNSEEN"
    search_terms: Optional[List[str]] = None
    provider: str = "other"  # "gmail", "outlook", "yahoo", "other"
    enabled: bool = True
    owner_email: Optional[str] = None  # Campo agregado para multiusuario
    
    # OAuth 2.0 fields for Gmail XOAUTH2
    auth_type: str = "password"  # "password" | "oauth2"
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[str] = None  # ISO format string
    oauth_email: Optional[str] = None  # Email asociado a OAuth (puede diferir del username)
    ai_remaining: Optional[int] = None # Campo temporal para lógica de scheduler

# Modelo para actualizaciones parciales de configuración de email
class EmailConfigUpdate(BaseModel):
    """Modelo para actualizar parcialmente una configuración de email.
    Todos los campos son opcionales para permitir actualizaciones parciales.
    Útil especialmente para OAuth2 donde solo se pueden editar search_terms.
    """
    model_config = ConfigDict(populate_by_name=True)
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: Optional[bool] = None
    search_criteria: Optional[str] = None
    search_terms: Optional[List[str]] = None
    provider: Optional[str] = None
    enabled: Optional[bool] = None

class EmailConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    host: str
    port: int
    username: str
    password: str
    search_criteria: str = "UNSEEN"
    search_terms: List[str] = Field(default_factory=lambda: [
        "factura", "facturacion", "factura electronica", "comprobante",
        "Documento Electronico", "Documento electronico",
        "documento electrónico", "documento electronico",
        "DOCUMENTO ELECTRONICO", "DOCUMENTO ELECTRÓNICO"
    ])
    # OAuth 2.0 fields
    auth_type: str = "password"  # 'password' or 'oauth2'
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[str] = None

class ProcessResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    success: bool
    message: str
    invoice_count: int = 0
    invoices: List[InvoiceData] = Field(default_factory=list)  # <- evita lista mutable global
    # Campo de Excel removido

class JobStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    running: bool
    next_run: Optional[str] = None
    interval_minutes: int
    last_run: Optional[str] = None
    last_result: Optional[ProcessResult] = None
    # Timestamps en epoch (segundos) para facilitar cálculos en el frontend
    next_run_ts: Optional[int] = None
    last_run_ts: Optional[int] = None

# Modelos de Excel removidos
