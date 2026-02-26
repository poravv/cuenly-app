from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field
import logging

logger = logging.getLogger(__name__)

class FieldType(str, Enum):
    """Tipos de datos para los campos del template"""
    TEXT = "TEXT"
    NUMBER = "NUMBER" 
    DATE = "DATE"
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    ARRAY = "ARRAY"  # Para productos agrupados

class FieldAlignment(str, Enum):
    """Alineación de datos en Excel"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"

class GroupingType(str, Enum):
    """Tipos de agrupación para productos"""
    CONCATENATE = "CONCATENATE"  # Unir en una celda separado por comas
    SEPARATE_ROWS = "SEPARATE_ROWS"  # Cada producto en una fila
    SUMMARY = "SUMMARY"  # Solo totales

# SIN CAMPOS CALCULADOS - Solo campos reales de la BD
class CalculatedFieldType(str, Enum):
    """No hay campos calculados - eliminados todos"""
    pass

class ExportField(BaseModel):
    """Campo individual del template de exportación"""
    model_config = ConfigDict(populate_by_name=True)
    
    field_key: str = Field(..., description="Campo fuente de la factura")
    display_name: str = Field(..., description="Nombre a mostrar en el Excel")
    field_type: FieldType = Field(..., description="Tipo de dato del campo")
    alignment: FieldAlignment = Field(FieldAlignment.LEFT, description="Alineación del campo")
    grouping_type: Optional[GroupingType] = Field(None, description="Tipo de agrupación para arrays")
    separator: Optional[str] = Field(", ", description="Separador para arrays concatenados")
    order: int = Field(0, description="Orden del campo en el template")
    is_visible: bool = Field(True, description="Si el campo es visible en la exportación")
    width: Optional[int] = Field(None, description="Ancho personalizado de la columna")
    
    # Campos para calculados - ELIMINADOS
    is_calculated: bool = Field(False, description="Siempre False - sin campos calculados")
    calculated_type: Optional[CalculatedFieldType] = Field(None, description="Eliminado")
    calculation_params: Optional[Dict[str, Any]] = Field(None, description="Eliminado")

class CalculatedFieldDefinition(BaseModel):
    """Definición de campo calculado - ELIMINADA"""
    model_config = ConfigDict(populate_by_name=True)
    pass

class ExportTemplate(BaseModel):
    """Template de exportación personalizado"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[str] = Field(None, description="ID único del template")
    name: str = Field(..., description="Nombre del template")
    description: Optional[str] = Field(None, description="Descripción del template")
    sheet_name: Optional[str] = Field("Facturas", description="Nombre de la hoja Excel")
    include_header: bool = Field(True, description="Incluir fila de encabezados")
    include_totals: bool = Field(False, description="Incluir fila de totales")
    fields: List[ExportField] = Field(default_factory=list, description="Campos del template")
    
    # Metadatos
    owner_email: Optional[str] = Field(None, description="Email del propietario")
    is_default: bool = Field(False, description="Si es el template por defecto")
    created_at: Optional[datetime] = Field(default_factory=datetime.now, description="Fecha de creación")
    updated_at: Optional[datetime] = Field(default_factory=datetime.now, description="Fecha de modificación")

# === CAMPOS DISPONIBLES - SOLO REALES DE LA BD ===
AVAILABLE_FIELDS: Dict[str, Dict[str, Any]] = {
    # === INFORMACIÓN BÁSICA ===
    "fecha": {"description": "Fecha de emisión", "field_type": FieldType.DATE},
    "numero_factura": {"description": "Número de factura", "field_type": FieldType.TEXT},
    "cdc": {"description": "Código CDC", "field_type": FieldType.TEXT},
    "timbrado": {"description": "Número de timbrado", "field_type": FieldType.TEXT},
    "tipo_documento": {"description": "Tipo de documento", "field_type": FieldType.TEXT},
    "tipo_documento_electronico": {"description": "Tipo de documento electrónico", "field_type": FieldType.TEXT},
    "tipo_de_codigo": {"description": "Código del tipo de documento electrónico", "field_type": FieldType.TEXT},
    "condicion_venta": {"description": "Condición de venta", "field_type": FieldType.TEXT},
    "cond_credito": {"description": "Condición de crédito", "field_type": FieldType.TEXT},
    "cond_credito_codigo": {"description": "Código de condición de crédito", "field_type": FieldType.TEXT},
    "plazo_credito_dias": {"description": "Plazo de crédito (días)", "field_type": FieldType.NUMBER},
    "moneda": {"description": "Tipo de moneda", "field_type": FieldType.TEXT},
    "tipo_cambio": {"description": "Tipo de cambio", "field_type": FieldType.NUMBER},
    "ind_presencia": {"description": "Indicador de presencia", "field_type": FieldType.TEXT},
    "ind_presencia_codigo": {"description": "Código de indicador de presencia", "field_type": FieldType.TEXT},
    "qr_url": {"description": "URL de consulta QR SET", "field_type": FieldType.TEXT},
    "info_adicional": {"description": "Información adicional SIFEN", "field_type": FieldType.TEXT},

    # === EMISOR ===
    "ruc_emisor": {"description": "RUC del emisor", "field_type": FieldType.TEXT},
    "nombre_emisor": {"description": "Nombre del emisor", "field_type": FieldType.TEXT},
    "direccion_emisor": {"description": "Dirección del emisor", "field_type": FieldType.TEXT},
    "telefono_emisor": {"description": "Teléfono del emisor", "field_type": FieldType.TEXT},
    "email_emisor": {"description": "Email del emisor", "field_type": FieldType.TEXT},
    
    # === CLIENTE ===
    "ruc_cliente": {"description": "RUC del cliente", "field_type": FieldType.TEXT},
    "nombre_cliente": {"description": "Nombre del cliente", "field_type": FieldType.TEXT},
    "direccion_cliente": {"description": "Dirección del cliente", "field_type": FieldType.TEXT},
    "telefono_cliente": {"description": "Teléfono del cliente", "field_type": FieldType.TEXT},
    "email_cliente": {"description": "Email del cliente", "field_type": FieldType.TEXT},
    "actividad_economica": {"description": "Actividad económica", "field_type": FieldType.TEXT},
    
    # === MONTOS - SOLO CAMPOS REALES ===
    "gravado_5": {"description": "Base gravada 5%", "field_type": FieldType.CURRENCY},
    "iva_5": {"description": "IVA 5%", "field_type": FieldType.CURRENCY},
    "gravado_10": {"description": "Base gravada 10%", "field_type": FieldType.CURRENCY},
    "iva_10": {"description": "IVA 10%", "field_type": FieldType.CURRENCY},
    "monto_exento": {"description": "Monto exento", "field_type": FieldType.CURRENCY},
    "exonerado": {"description": "Exonerado", "field_type": FieldType.CURRENCY},
    "total_iva": {"description": "Total IVA", "field_type": FieldType.CURRENCY},
    "total_operacion": {"description": "Total operación", "field_type": FieldType.CURRENCY},
    "monto_total": {"description": "Monto total final", "field_type": FieldType.CURRENCY},

    # === TOTALES DEL XML ===
    "total_descuento": {"description": "Total descuento", "field_type": FieldType.CURRENCY},
    "total_base_gravada": {"description": "Total base gravada", "field_type": FieldType.CURRENCY},
    "anticipo": {"description": "Anticipo recibido", "field_type": FieldType.CURRENCY},
    "isc_total": {"description": "Total ISC", "field_type": FieldType.CURRENCY},
    "isc_base_imponible": {"description": "Base imponible ISC", "field_type": FieldType.CURRENCY},
    "isc_subtotal_gravado": {"description": "Subtotal gravado ISC", "field_type": FieldType.CURRENCY},

    # === OPERACIÓN Y LOGÍSTICA (SIFEN v150) ===
    "ciclo_facturacion": {"description": "Ciclo de facturación", "field_type": FieldType.TEXT},
    "ciclo_fecha_inicio": {"description": "Fecha inicio ciclo", "field_type": FieldType.DATE},
    "ciclo_fecha_fin": {"description": "Fecha fin ciclo", "field_type": FieldType.DATE},
    "transporte_modalidad": {"description": "Modalidad de transporte", "field_type": FieldType.TEXT},
    "transporte_modalidad_codigo": {"description": "Código modalidad transporte", "field_type": FieldType.TEXT},
    "transporte_resp_flete_codigo": {"description": "Código responsable de flete", "field_type": FieldType.TEXT},
    "transporte_nro_despacho": {"description": "Número de despacho/importación", "field_type": FieldType.TEXT},

    # === PRODUCTOS (agrupados) ===
    "productos": {"description": "Productos (todos juntos)", "field_type": FieldType.ARRAY},
    
    # === PRODUCTOS INDIVIDUALES ===
    "productos.codigo": {"description": "Código productos", "field_type": FieldType.ARRAY},
    "productos.nombre": {"description": "Nombre productos", "field_type": FieldType.ARRAY},
    "productos.descripcion": {"description": "Descripción productos", "field_type": FieldType.ARRAY},
    "productos.cantidad": {"description": "Cantidad productos", "field_type": FieldType.ARRAY},
    "productos.unidad": {"description": "Unidad productos", "field_type": FieldType.ARRAY},
    "productos.precio_unitario": {"description": "Precio unitario productos", "field_type": FieldType.ARRAY},
    "productos.total": {"description": "Total productos", "field_type": FieldType.ARRAY},
    "productos.iva": {"description": "IVA productos", "field_type": FieldType.ARRAY},
    "productos.base_gravada": {"description": "Base gravada productos", "field_type": FieldType.ARRAY},
    "productos.monto_iva": {"description": "Monto IVA productos", "field_type": FieldType.ARRAY},
    
    # === METADATOS ===
    "fuente": {"description": "Fuente de procesamiento", "field_type": FieldType.TEXT},
    "email_origen": {"description": "Email origen", "field_type": FieldType.TEXT},
    "mes_proceso": {"description": "Mes de proceso", "field_type": FieldType.TEXT},
    "created_at": {"description": "Fecha de creación", "field_type": FieldType.DATE},
}

AVAILABLE_FIELD_CATEGORIES: Dict[str, List[str]] = {
    "basic": [
        "numero_factura",
        "fecha",
        "cdc",
        "timbrado",
        "tipo_documento",
        "tipo_documento_electronico",
        "tipo_de_codigo",
        "condicion_venta",
        "cond_credito",
        "cond_credito_codigo",
        "plazo_credito_dias",
        "moneda",
        "tipo_cambio",
        "ind_presencia",
        "ind_presencia_codigo",
        "qr_url",
        "info_adicional",
    ],
    "emisor": [
        "ruc_emisor",
        "nombre_emisor",
        "direccion_emisor",
        "telefono_emisor",
        "email_emisor",
        "actividad_economica",
    ],
    "cliente": [
        "ruc_cliente",
        "nombre_cliente",
        "direccion_cliente",
        "telefono_cliente",
        "email_cliente",
    ],
    "montos": [
        "gravado_5",
        "iva_5",
        "gravado_10",
        "iva_10",
        "monto_exento",
        "exonerado",
        "total_base_gravada",
        "total_iva",
        "total_descuento",
        "anticipo",
        "total_operacion",
        "monto_total",
        "isc_total",
        "isc_base_imponible",
        "isc_subtotal_gravado",
    ],
    "operacion": [
        "ciclo_facturacion",
        "ciclo_fecha_inicio",
        "ciclo_fecha_fin",
        "transporte_modalidad",
        "transporte_modalidad_codigo",
        "transporte_resp_flete_codigo",
        "transporte_nro_despacho",
    ],
    "productos": [
        "productos",
        "productos.codigo",
        "productos.nombre",
        "productos.descripcion",
        "productos.cantidad",
        "productos.unidad",
        "productos.precio_unitario",
        "productos.total",
        "productos.iva",
        "productos.base_gravada",
        "productos.monto_iva",
    ],
    "metadata": [
        "fuente",
        "email_origen",
        "mes_proceso",
        "created_at",
    ],
}


def get_available_field_keys() -> Set[str]:
    return set(AVAILABLE_FIELDS.keys())


def get_available_field_categories() -> Dict[str, List[str]]:
    return {category: list(keys) for category, keys in AVAILABLE_FIELD_CATEGORIES.items()}


def get_invalid_template_field_keys(fields: List[ExportField]) -> List[str]:
    allowed = get_available_field_keys()
    invalid = {
        field.field_key
        for field in fields
        if field.field_key not in allowed
    }
    return sorted(invalid)

# === SIN CAMPOS CALCULADOS ===
CALCULATION_FUNCTIONS: Dict[CalculatedFieldType, Callable[[Dict[str, Any]], Any]] = {}
CALCULATED_FIELDS_DEFINITIONS: Dict[CalculatedFieldType, CalculatedFieldDefinition] = {}

def calculate_field(field_type: CalculatedFieldType, invoice_data: Dict[str, Any]) -> Any:
    """
    Calcula un campo - ELIMINADO - No hay campos calculados
    """
    return None

def get_calculated_fields_by_category() -> Dict[str, List[CalculatedFieldDefinition]]:
    """
    Agrupa campos calculados por categoría - ELIMINADO
    """
    return {}

def get_available_normal_fields() -> Dict[str, Dict[str, Any]]:
    """
    Retorna solo los campos normales disponibles
    """
    return AVAILABLE_FIELDS.copy()

def get_all_available_fields() -> Dict[str, Dict[str, Any]]:
    """
    Retorna todos los campos disponibles (solo normales)
    """
    return AVAILABLE_FIELDS.copy()
