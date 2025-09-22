from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

class FieldType(str, Enum):
    """Tipos de datos para los campos del template"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"
    ARRAY = "array"  # Para productos agrupados

class FieldAlignment(str, Enum):
    """Alineación de los campos"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"

class GroupingType(str, Enum):
    """Tipos de agrupación para productos"""
    NONE = "none"
    CONCATENATE = "concatenate"  # Unir en una celda separado por comas
    SEPARATE_ROWS = "separate_rows"  # Cada producto en una fila
    SUMMARY = "summary"  # Solo totales

class ExportField(BaseModel):
    """Configuración de un campo en el template"""
    id: str = Field(..., description="ID único del campo")
    name: str = Field(..., description="Nombre a mostrar en el header")
    source_field: str = Field(..., description="Campo fuente de la factura (ej: 'numero_factura', 'productos.articulo')")
    field_type: FieldType = Field(default=FieldType.TEXT, description="Tipo de dato")
    order: int = Field(..., description="Orden de la columna (0-based)")
    width: Optional[int] = Field(default=None, description="Ancho de la columna")
    alignment: FieldAlignment = Field(default=FieldAlignment.LEFT, description="Alineación")
    format_string: Optional[str] = Field(default=None, description="Formato personalizado (ej: '#,##0.00' para moneda)")
    is_visible: bool = Field(default=True, description="Si la columna es visible")
    grouping: GroupingType = Field(default=GroupingType.NONE, description="Tipo de agrupación para arrays")
    separator: Optional[str] = Field(default=", ", description="Separador para agrupación concatenate")

class ExportTemplate(BaseModel):
    """Template de exportación personalizable"""
    id: Optional[str] = Field(default=None, description="ID del template")
    name: str = Field(..., description="Nombre del template")
    description: Optional[str] = Field(default=None, description="Descripción del template")
    owner_email: str = Field(..., description="Email del propietario")
    fields: List[ExportField] = Field(..., description="Campos configurados")
    
    # Configuración global
    include_header: bool = Field(default=True, description="Incluir fila de encabezados")
    include_totals: bool = Field(default=False, description="Incluir fila de totales al final")
    sheet_name: str = Field(default="Facturas", description="Nombre de la hoja")
    
    # Filtros por defecto
    date_range_days: Optional[int] = Field(default=None, description="Rango de días por defecto (ej: 30 para último mes)")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_default: bool = Field(default=False, description="Si es el template por defecto del usuario")

class ExportRequest(BaseModel):
    """Request para exportar usando un template"""
    template_id: str = Field(..., description="ID del template a usar")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Filtros adicionales")
    filename: Optional[str] = Field(default=None, description="Nombre del archivo")

# Campos disponibles para templates
AVAILABLE_FIELDS = {
    # Información básica de la factura
    "numero_factura": {"name": "Número de Factura", "type": FieldType.TEXT, "description": "Número de la factura"},
    "fecha": {"name": "Fecha", "type": FieldType.DATE, "description": "Fecha de emisión"},
    "cdc": {"name": "CDC", "type": FieldType.TEXT, "description": "Código de Control"},
    "timbrado": {"name": "Timbrado", "type": FieldType.TEXT, "description": "Número de timbrado"},
    
    # Emisor
    "ruc_emisor": {"name": "RUC Emisor", "type": FieldType.TEXT, "description": "RUC del emisor"},
    "nombre_emisor": {"name": "Nombre Emisor", "type": FieldType.TEXT, "description": "Nombre del emisor"},
    
    # Cliente
    "ruc_cliente": {"name": "RUC Cliente", "type": FieldType.TEXT, "description": "RUC del cliente"},
    "nombre_cliente": {"name": "Nombre Cliente", "type": FieldType.TEXT, "description": "Nombre del cliente"},
    
    # Montos
    "subtotal_5": {"name": "Subtotal 5%", "type": FieldType.CURRENCY, "description": "Base gravada 5%"},
    "iva_5": {"name": "IVA 5%", "type": FieldType.CURRENCY, "description": "IVA 5%"},
    "subtotal_10": {"name": "Subtotal 10%", "type": FieldType.CURRENCY, "description": "Base gravada 10%"},
    "iva_10": {"name": "IVA 10%", "type": FieldType.CURRENCY, "description": "IVA 10%"},
    "subtotal_exentas": {"name": "Exentas", "type": FieldType.CURRENCY, "description": "Monto exento"},
    "monto_total": {"name": "Total", "type": FieldType.CURRENCY, "description": "Monto total"},
    
    # Productos (arrays)
    "productos": {"name": "Productos", "type": FieldType.ARRAY, "description": "Lista de productos"},
    "productos.articulo": {"name": "Artículos", "type": FieldType.ARRAY, "description": "Nombres de productos"},
    "productos.cantidad": {"name": "Cantidades", "type": FieldType.ARRAY, "description": "Cantidades de productos"},
    "productos.precio_unitario": {"name": "Precios Unit.", "type": FieldType.ARRAY, "description": "Precios unitarios"},
    "productos.total": {"name": "Totales Productos", "type": FieldType.ARRAY, "description": "Totales por producto"},
    "productos.iva": {"name": "IVA Productos", "type": FieldType.ARRAY, "description": "Tipo de IVA por producto"},
    
    # Metadata
    "condicion_venta": {"name": "Condición Venta", "type": FieldType.TEXT, "description": "Condición de venta"},
    "moneda": {"name": "Moneda", "type": FieldType.TEXT, "description": "Moneda de la factura"},
    "descripcion_factura": {"name": "Descripción", "type": FieldType.TEXT, "description": "Descripción de la factura"},
    
    # Procesamiento
    "processing_quality": {"name": "Calidad", "type": FieldType.TEXT, "description": "Calidad del procesamiento"},
    "created_at": {"name": "Fecha Procesada", "type": FieldType.DATE, "description": "Fecha de procesamiento"},
}