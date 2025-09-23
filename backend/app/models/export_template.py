from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
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
    "tipo_documento": {"description": "Tipo de documento", "field_type": FieldType.TEXT},
    "condicion_venta": {"description": "Condición de venta", "field_type": FieldType.TEXT},
    "moneda": {"description": "Tipo de moneda", "field_type": FieldType.TEXT},
    "tipo_cambio": {"description": "Tipo de cambio", "field_type": FieldType.NUMBER},
    
    # === EMISOR ===
    "ruc_emisor": {"description": "RUC del emisor", "field_type": FieldType.TEXT},
    "nombre_emisor": {"description": "Nombre del emisor", "field_type": FieldType.TEXT},
    "direccion_emisor": {"description": "Dirección del emisor", "field_type": FieldType.TEXT},
    "telefono_emisor": {"description": "Teléfono del emisor", "field_type": FieldType.TEXT},
    
    # === CLIENTE ===
    "ruc_cliente": {"description": "RUC del cliente", "field_type": FieldType.TEXT},
    "nombre_cliente": {"description": "Nombre del cliente", "field_type": FieldType.TEXT},
    "direccion_cliente": {"description": "Dirección del cliente", "field_type": FieldType.TEXT},
    "telefono_cliente": {"description": "Teléfono del cliente", "field_type": FieldType.TEXT},
    "email_cliente": {"description": "Email del cliente", "field_type": FieldType.TEXT},
    "actividad_economica": {"description": "Actividad económica", "field_type": FieldType.TEXT},
    
    # === MONTOS - SOLO CAMPOS REALES ===
    "base_gravada_5": {"description": "Base gravada 5% (del XML)", "field_type": FieldType.CURRENCY},
    "iva_5": {"description": "IVA 5% (del XML)", "field_type": FieldType.CURRENCY},
    "base_gravada_10": {"description": "Base gravada 10% (del XML)", "field_type": FieldType.CURRENCY},
    "iva_10": {"description": "IVA 10% (del XML)", "field_type": FieldType.CURRENCY},
    "monto_exento": {"description": "Monto exento", "field_type": FieldType.CURRENCY},
    "monto_exonerado": {"description": "Monto exonerado", "field_type": FieldType.CURRENCY},
    "total_iva": {"description": "Total IVA", "field_type": FieldType.CURRENCY},
    "monto_total": {"description": "Monto total final", "field_type": FieldType.CURRENCY},
    
    # === TOTALES DEL XML ===
    "total_operacion": {"description": "Total operación (del XML)", "field_type": FieldType.CURRENCY},
    "total_descuento": {"description": "Total descuento (del XML)", "field_type": FieldType.CURRENCY},
    "total_base_gravada": {"description": "Total base gravada", "field_type": FieldType.CURRENCY},
    "anticipo": {"description": "Anticipo recibido", "field_type": FieldType.CURRENCY},
    
    # === IDENTIFICADORES ===
    "timbrado": {"description": "Número de timbrado", "field_type": FieldType.TEXT},
    "cdc": {"description": "Código CDC", "field_type": FieldType.TEXT},
    
    # === PRODUCTOS (agrupados) ===
    "productos": {"description": "Productos (todos juntos)", "field_type": FieldType.ARRAY},
    
    # === PRODUCTOS INDIVIDUALES ===
    "productos.descripcion": {"description": "Descripción productos", "field_type": FieldType.ARRAY},
    "productos.cantidad": {"description": "Cantidad productos", "field_type": FieldType.ARRAY},
    "productos.precio_unitario": {"description": "Precio unitario productos", "field_type": FieldType.ARRAY},
    "productos.total": {"description": "Total productos", "field_type": FieldType.ARRAY},
    "productos.iva": {"description": "IVA productos", "field_type": FieldType.ARRAY},
    
    # === METADATOS ===
    "created_at": {"description": "Fecha de creación", "field_type": FieldType.DATE},
    "updated_at": {"description": "Fecha de actualización", "field_type": FieldType.DATE},
    "owner_email": {"description": "Email propietario", "field_type": FieldType.TEXT},
}

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