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

class CalculatedFieldType(str, Enum):
    """Tipos de campos calculados - ELIMINADOS - Solo campos reales de BD"""
    pass  # No hay campos calculados

class ExportField(BaseModel):
    """Campo individual del template de exportación"""
    model_config = ConfigDict(populate_by_name=True)
    
    field_key: str = Field(..., description="Campo fuente de la factura (ej: 'numero_factura', 'productos.nombre')")
    display_name: str = Field(..., description="Nombre a mostrar en el Excel")
    field_type: FieldType = Field(..., description="Tipo de dato del campo")
    alignment: FieldAlignment = Field(FieldAlignment.LEFT, description="Alineación del campo")
    grouping_type: Optional[GroupingType] = Field(None, description="Tipo de agrupación para arrays")
    separator: Optional[str] = Field(", ", description="Separador para arrays concatenados")
    order: int = Field(0, description="Orden del campo en el template")
    is_visible: bool = Field(True, description="Si el campo es visible en la exportación")
    width: Optional[int] = Field(None, description="Ancho personalizado de la columna")
    
    # Campos para calculados
    is_calculated: bool = Field(False, description="Si es un campo calculado")
    calculated_type: Optional[CalculatedFieldType] = Field(None, description="Tipo de cálculo a realizar")
    calculation_params: Optional[Dict[str, Any]] = Field(None, description="Parámetros adicionales para el cálculo")

class CalculatedFieldDefinition(BaseModel):
    """Definición de un campo calculado"""
    model_config = ConfigDict(populate_by_name=True)
    
    field_type: CalculatedFieldType = Field(..., description="Tipo de campo calculado")
    display_name: str = Field(..., description="Nombre a mostrar")
    description: str = Field(..., description="Descripción del campo calculado")
    data_type: FieldType = Field(..., description="Tipo de dato resultante")
    calculation_function: str = Field(..., description="Nombre de la función de cálculo")
    required_fields: List[str] = Field(default_factory=list, description="Campos requeridos para el cálculo")
    example_value: Optional[str] = Field(None, description="Ejemplo del valor calculado")
    category: str = Field(..., description="Categoría del campo (IVA, Totales, Análisis, etc.)")

class ExportTemplate(BaseModel):
    """Template para exportación personalizada de facturas"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[str] = Field(None, description="ID único del template")
    name: str = Field(..., description="Nombre del template")
    description: Optional[str] = Field("", description="Descripción del template")
    sheet_name: Optional[str] = Field("Facturas", description="Nombre de la hoja de Excel")
    include_header: bool = Field(True, description="Incluir fila de encabezados")
    include_totals: bool = Field(False, description="Incluir fila de totales")
    fields: List[ExportField] = Field(default_factory=list, description="Campos a exportar")
    owner_email: Optional[str] = Field(None, description="Email del propietario")
    is_default: bool = Field(False, description="Template por defecto")
    created_at: Optional[datetime] = Field(None, description="Fecha de creación")
    updated_at: Optional[datetime] = Field(None, description="Fecha de última actualización")

# Campos disponibles para templates - NOMENCLATURA UNIFICADA Y SIN DUPLICADOS
AVAILABLE_FIELDS = {
    # ================================
    # INFORMACIÓN BÁSICA DE LA FACTURA
    # ================================
    "numero_factura": {"description": "Número de la factura", "field_type": FieldType.TEXT},
    "fecha": {"description": "Fecha de emisión", "field_type": FieldType.DATE},
    "cdc": {"description": "Código de Control (CDC)", "field_type": FieldType.TEXT},
    "timbrado": {"description": "Número de timbrado", "field_type": FieldType.TEXT},
    "establecimiento": {"description": "Establecimiento", "field_type": FieldType.TEXT},
    "punto_expedicion": {"description": "Punto de expedición", "field_type": FieldType.TEXT},
    "tipo_documento": {"description": "Tipo de documento (CO/CR)", "field_type": FieldType.TEXT},
    "condicion_venta": {"description": "Condición de venta (CONTADO/CREDITO)", "field_type": FieldType.TEXT},
    "moneda": {"description": "Moneda de la factura", "field_type": FieldType.TEXT},
    "tipo_cambio": {"description": "Tipo de cambio", "field_type": FieldType.NUMBER},
    
    # ================================
    # DATOS DEL EMISOR
    # ================================
    "ruc_emisor": {"description": "RUC del emisor", "field_type": FieldType.TEXT},
    "nombre_emisor": {"description": "Nombre/Razón social del emisor", "field_type": FieldType.TEXT},
    "direccion_emisor": {"description": "Dirección del emisor", "field_type": FieldType.TEXT},
    "telefono_emisor": {"description": "Teléfono del emisor", "field_type": FieldType.TEXT},
    "email_emisor": {"description": "Email del emisor", "field_type": FieldType.TEXT},
    "actividad_economica": {"description": "Actividad económica del emisor", "field_type": FieldType.TEXT},
    
    # ================================
    # DATOS DEL CLIENTE/RECEPTOR
    # ================================
    "ruc_cliente": {"description": "RUC del cliente", "field_type": FieldType.TEXT},
    "nombre_cliente": {"description": "Nombre del cliente", "field_type": FieldType.TEXT},
    "direccion_cliente": {"description": "Dirección del cliente", "field_type": FieldType.TEXT},
    "email_cliente": {"description": "Email del cliente", "field_type": FieldType.TEXT},
    
    # ================================
    # MONTOS E IMPUESTOS (XML SIFEN)
    # ================================
    
    # === BASES GRAVADAS (Sin IVA incluido) ===
    "base_gravada_5": {"description": "Base gravada IVA 5% (sin impuesto)", "field_type": FieldType.CURRENCY},
    "base_gravada_10": {"description": "Base gravada IVA 10% (sin impuesto)", "field_type": FieldType.CURRENCY},
    
    # === IMPUESTOS CALCULADOS ===
    "iva_5": {"description": "Monto IVA 5%", "field_type": FieldType.CURRENCY},
    "iva_10": {"description": "Monto IVA 10%", "field_type": FieldType.CURRENCY},
    "total_iva": {"description": "Total IVA (5% + 10%)", "field_type": FieldType.CURRENCY},
    
    # === MONTOS SIN IMPUESTOS ===
    "monto_exento": {"description": "Monto exento de IVA", "field_type": FieldType.CURRENCY},
    "monto_exonerado": {"description": "Monto exonerado de IVA", "field_type": FieldType.CURRENCY},
    
    # === TOTALES FINALES ===
    "total_operacion": {"description": "Total operación (antes impuestos)", "field_type": FieldType.CURRENCY},
    "monto_total": {"description": "Monto total final (con IVA)", "field_type": FieldType.CURRENCY},
    "total_base_gravada": {"description": "Total base gravada (5% + 10%)", "field_type": FieldType.CURRENCY},
    
    # === OTROS CONCEPTOS ===
    "total_descuento": {"description": "Total descuentos aplicados", "field_type": FieldType.CURRENCY},
    "anticipo": {"description": "Anticipo recibido", "field_type": FieldType.CURRENCY},
    
    # ================================
    # PRODUCTOS/ITEMS (ARRAYS)
    # ================================
    "productos": {"description": "Todos los productos en una celda", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.codigo": {"description": "Código/SKU del producto", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.nombre": {"description": "Nombre/descripción del producto", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.cantidad": {"description": "Cantidad de cada producto", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.unidad": {"description": "Unidad de medida", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.precio_unitario": {"description": "Precio unitario (sin IVA)", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.total": {"description": "Total por producto (con IVA)", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.iva": {"description": "Tipo de IVA (0, 5, 10)", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.base_gravada": {"description": "Base gravada por producto", "field_type": FieldType.ARRAY, "is_array": True},
    "productos.monto_iva": {"description": "Monto IVA por producto", "field_type": FieldType.ARRAY, "is_array": True},
    
    # ================================
    # METADATOS Y CONTROL
    # ================================
    "fuente": {"description": "Origen del procesamiento (XML_NATIVO/OPENAI_VISION)", "field_type": FieldType.TEXT},
    "processing_quality": {"description": "Calidad del procesamiento", "field_type": FieldType.TEXT},
    "email_origen": {"description": "Email de origen del documento", "field_type": FieldType.TEXT},
    "mes_proceso": {"description": "Mes de procesamiento (YYYY-MM)", "field_type": FieldType.TEXT},
    "created_at": {"description": "Fecha y hora de procesamiento", "field_type": FieldType.DATE},
    "descripcion_factura": {"description": "Descripción adicional", "field_type": FieldType.TEXT},
}

# ================================================================
# CAMPOS CALCULADOS DISPONIBLES - SISTEMA ESTRUCTURADO
# ================================================================

def _calculate_monto_con_iva_5(invoice_data: Dict[str, Any]) -> float:
    """
    Calcula monto con IVA 5% incluido - prioriza productos ya que precios incluyen IVA
    """
    try:
        # Método 1: Calcular desde productos (más confiable para precios con IVA incluido)
        productos_total = 0.0
        productos = invoice_data.get('productos', [])
        for producto in productos:
            if isinstance(producto, dict):
                iva_tipo = producto.get('iva', 0)
                if iva_tipo == 5:
                    total_producto = float(producto.get('total', 0) or 0)
                    productos_total += total_producto
            else:
                # Si es un objeto Pydantic
                iva_tipo = getattr(producto, 'iva', 0)
                if iva_tipo == 5:
                    total_producto = float(getattr(producto, 'total', 0) or 0)
                    productos_total += total_producto
        
        # Método 2: Usar totales del XML como fallback
        base = float(invoice_data.get('base_gravada_5', 0) or invoice_data.get('gravado_5', 0) or 0)
        iva = float(invoice_data.get('iva_5', 0) or 0)
        xml_total = base + iva
        
        # Priorizar productos si tienen datos, sino usar XML
        if productos_total > 0:
            return productos_total
        elif xml_total > 0:
            return xml_total
        else:
            return 0.0
            
    except (ValueError, TypeError):
        return 0.0

def _calculate_monto_con_iva_10(invoice_data: Dict[str, Any]) -> float:
    """
    Calcula monto con IVA 10% incluido - prioriza productos ya que precios incluyen IVA
    """
    try:
        # Método 1: Calcular desde productos (más confiable para precios con IVA incluido)
        productos_total = 0.0
        productos = invoice_data.get('productos', [])
        for producto in productos:
            if isinstance(producto, dict):
                iva_tipo = producto.get('iva', 0)
                if iva_tipo == 10:
                    total_producto = float(producto.get('total', 0) or 0)
                    productos_total += total_producto
            else:
                # Si es un objeto Pydantic
                iva_tipo = getattr(producto, 'iva', 0)
                if iva_tipo == 10:
                    total_producto = float(getattr(producto, 'total', 0) or 0)
                    productos_total += total_producto
        
        # Método 2: Usar totales del XML como fallback
        base = float(invoice_data.get('base_gravada_10', 0) or invoice_data.get('gravado_10', 0) or 0)
        iva = float(invoice_data.get('iva_10', 0) or 0)
        xml_total = base + iva
        
        # Priorizar productos si tienen datos, sino usar XML
        if productos_total > 0:
            return productos_total
        elif xml_total > 0:
            return xml_total
        else:
            return 0.0
            
    except (ValueError, TypeError):
        return 0.0





def _calculate_total_iva_general(invoice_data: Dict[str, Any]) -> float:
    """
    Calcula IVA total (5% + 10%) usando directamente los campos del XML SIFEN
    """
    try:
        iva_5 = float(invoice_data.get('iva_5', 0) or 0)
        iva_10 = float(invoice_data.get('iva_10', 0) or 0)
        return iva_5 + iva_10
    except (ValueError, TypeError):
        return 0.0

def _calculate_porcentaje_iva_5(invoice_data: Dict[str, Any]) -> float:
    """Calcula % que representa IVA 5% del total"""
    try:
        iva_5 = float(invoice_data.get('iva_5', 0) or 0)
        total = float(invoice_data.get('monto_total', 0) or invoice_data.get('total_general', 0) or 0)
        return (iva_5 / total * 100) if total > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

def _calculate_porcentaje_iva_10(invoice_data: Dict[str, Any]) -> float:
    """Calcula % que representa IVA 10% del total"""
    try:
        iva_10 = float(invoice_data.get('iva_10', 0) or 0)
        total = float(invoice_data.get('monto_total', 0) or invoice_data.get('total_general', 0) or 0)
        return (iva_10 / total * 100) if total > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

def _calculate_porcentaje_exento(invoice_data: Dict[str, Any]) -> float:
    """Calcula % exento del total"""
    try:
        exento = float(invoice_data.get('monto_exento', 0) or invoice_data.get('exento', 0) or 0)
        total = float(invoice_data.get('monto_total', 0) or invoice_data.get('total_general', 0) or 0)
        return (exento / total * 100) if total > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

def _calculate_subtotal_gravado(invoice_data: Dict[str, Any]) -> float:
    """Calcula subtotal gravado total (5% + 10%) sin IVA"""
    try:
        gravado_5 = float(invoice_data.get('base_gravada_5', 0) or invoice_data.get('gravado_5', 0) or 0)
        gravado_10 = float(invoice_data.get('base_gravada_10', 0) or invoice_data.get('gravado_10', 0) or 0)
        return gravado_5 + gravado_10
    except (ValueError, TypeError):
        return 0.0

def _calculate_subtotal_no_gravado(invoice_data: Dict[str, Any]) -> float:
    """Calcula subtotal no gravado (Exento + Exonerado)"""
    try:
        exento = float(invoice_data.get('monto_exento', 0) or invoice_data.get('exento', 0) or 0)
        exonerado = float(invoice_data.get('monto_exonerado', 0) or invoice_data.get('exonerado', 0) or 0)
        return exento + exonerado
    except (ValueError, TypeError):
        return 0.0

def _calculate_total_antes_iva(invoice_data: Dict[str, Any]) -> float:
    """Calcula total antes de IVA (total operación)"""
    try:
        return float(invoice_data.get('total_operacion', 0) or 0)
    except (ValueError, TypeError):
        return 0.0

def _calculate_cantidad_productos(invoice_data: Dict[str, Any]) -> int:
    """Cuenta el número de productos en la factura"""
    try:
        productos = invoice_data.get('productos', [])
        return len(productos) if isinstance(productos, list) else 0
    except (ValueError, TypeError):
        return 0

def _calculate_valor_promedio_producto(invoice_data: Dict[str, Any]) -> float:
    """Calcula el valor promedio por producto"""
    try:
        productos = invoice_data.get('productos', [])
        if not isinstance(productos, list) or len(productos) == 0:
            return 0.0
        
        total_productos = 0.0
        for producto in productos:
            if isinstance(producto, dict):
                precio = float(producto.get('precio_unitario', 0) or producto.get('total', 0) or 0)
                total_productos += precio
            else:
                # Si es un objeto Pydantic
                precio = float(getattr(producto, 'precio_unitario', 0) or getattr(producto, 'total', 0) or 0)
                total_productos += precio
        
        return total_productos / len(productos)
    except (ValueError, TypeError):
        return 0.0

# Registro de funciones de cálculo
CALCULATION_FUNCTIONS: Dict[CalculatedFieldType, Callable[[Dict[str, Any]], Any]] = {
    CalculatedFieldType.MONTO_CON_IVA_5: _calculate_monto_con_iva_5,
    CalculatedFieldType.MONTO_CON_IVA_10: _calculate_monto_con_iva_10,
    CalculatedFieldType.TOTAL_IVA_GENERAL: _calculate_total_iva_general,
    CalculatedFieldType.PORCENTAJE_IVA_5: _calculate_porcentaje_iva_5,
    CalculatedFieldType.PORCENTAJE_IVA_10: _calculate_porcentaje_iva_10,
    CalculatedFieldType.PORCENTAJE_EXENTO: _calculate_porcentaje_exento,
    CalculatedFieldType.SUBTOTAL_GRAVADO: _calculate_subtotal_gravado,
    CalculatedFieldType.SUBTOTAL_NO_GRAVADO: _calculate_subtotal_no_gravado,
    CalculatedFieldType.TOTAL_ANTES_IVA: _calculate_total_antes_iva,
    CalculatedFieldType.CANTIDAD_PRODUCTOS: _calculate_cantidad_productos,
    CalculatedFieldType.VALOR_PROMEDIO_PRODUCTO: _calculate_valor_promedio_producto,
}

# Definiciones de campos calculados disponibles
CALCULATED_FIELDS_DEFINITIONS: Dict[CalculatedFieldType, CalculatedFieldDefinition] = {
    # === MONTOS CON IVA INCLUIDO ===
    CalculatedFieldType.MONTO_CON_IVA_5: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.MONTO_CON_IVA_5,
        display_name="Monto IVA 5% (Con impuesto)",
        description="Base gravada 5% + IVA 5% = Monto total con impuesto incluido",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_monto_con_iva_5",
        required_fields=["base_gravada_5", "iva_5"],
        example_value="₲ 1,050,000",
        category="IVA y Montos"
    ),
    
    CalculatedFieldType.MONTO_CON_IVA_10: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.MONTO_CON_IVA_10,
        display_name="Monto IVA 10% (Con impuesto)",
        description="Base gravada 10% + IVA 10% = Monto total con impuesto incluido",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_monto_con_iva_10",
        required_fields=["base_gravada_10", "iva_10"],
        example_value="₲ 2,200,000",
        category="IVA y Montos"
    ),
    
    # === TOTAL DE IVA GENERAL ===
    CalculatedFieldType.TOTAL_IVA_GENERAL: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.TOTAL_IVA_GENERAL,
        display_name="Total IVA General (5% + 10%)",
        description="Suma total de todos los IVAs aplicados",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_total_iva_general",
        required_fields=["iva_5", "iva_10"],
        example_value="₲ 250,000",
        category="IVA y Montos"
    ),
    
    # === PORCENTAJES Y PROPORCIONES ===
    CalculatedFieldType.PORCENTAJE_IVA_5: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.PORCENTAJE_IVA_5,
        display_name="% IVA 5% del total",
        description="Porcentaje que representa el IVA 5% del monto total",
        data_type=FieldType.PERCENTAGE,
        calculation_function="_calculate_porcentaje_iva_5",
        required_fields=["iva_5", "monto_total"],
        example_value="15.4%",
        category="Análisis y Proporciones"
    ),
    
    CalculatedFieldType.PORCENTAJE_IVA_10: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.PORCENTAJE_IVA_10,
        display_name="% IVA 10% del total",
        description="Porcentaje que representa el IVA 10% del monto total",
        data_type=FieldType.PERCENTAGE,
        calculation_function="_calculate_porcentaje_iva_10",
        required_fields=["iva_10", "monto_total"],
        example_value="61.5%",
        category="Análisis y Proporciones"
    ),
    
    CalculatedFieldType.PORCENTAJE_EXENTO: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.PORCENTAJE_EXENTO,
        display_name="% Exento del total",
        description="Porcentaje que representa el monto exento del total",
        data_type=FieldType.PERCENTAGE,
        calculation_function="_calculate_porcentaje_exento",
        required_fields=["monto_exento", "monto_total"],
        example_value="23.1%",
        category="Análisis y Proporciones"
    ),
    
    # === SUBTOTALES ÚTILES ===
    CalculatedFieldType.SUBTOTAL_GRAVADO: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.SUBTOTAL_GRAVADO,
        display_name="Subtotal Gravado (5% + 10%)",
        description="Total de bases gravadas sin IVA incluido",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_subtotal_gravado",
        required_fields=["base_gravada_5", "base_gravada_10"],
        example_value="₲ 3,000,000",
        category="Totales y Subtotales"
    ),
    
    CalculatedFieldType.SUBTOTAL_NO_GRAVADO: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.SUBTOTAL_NO_GRAVADO,
        display_name="Subtotal No Gravado",
        description="Total de montos exentos y exonerados",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_subtotal_no_gravado",
        required_fields=["monto_exento", "monto_exonerado"],
        example_value="₲ 750,000",
        category="Totales y Subtotales"
    ),
    
    CalculatedFieldType.TOTAL_ANTES_IVA: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.TOTAL_ANTES_IVA,
        display_name="Total Antes de IVA",
        description="Total de la operación antes de aplicar impuestos",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_total_antes_iva",
        required_fields=["total_operacion"],
        example_value="₲ 3,750,000",
        category="Totales y Subtotales"
    ),
    
    # === ANÁLISIS DE PRODUCTOS ===
    CalculatedFieldType.CANTIDAD_PRODUCTOS: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.CANTIDAD_PRODUCTOS,
        display_name="Cantidad de Productos",
        description="Número total de líneas de productos en la factura",
        data_type=FieldType.NUMBER,
        calculation_function="_calculate_cantidad_productos",
        required_fields=["productos"],
        example_value="15",
        category="Análisis de Productos"
    ),
    
    CalculatedFieldType.VALOR_PROMEDIO_PRODUCTO: CalculatedFieldDefinition(
        field_type=CalculatedFieldType.VALOR_PROMEDIO_PRODUCTO,
        display_name="Valor Promedio por Producto",
        description="Precio promedio por línea de producto",
        data_type=FieldType.CURRENCY,
        calculation_function="_calculate_valor_promedio_producto",
        required_fields=["productos"],
        example_value="₲ 250,000",
        category="Análisis de Productos"
    ),
}

def calculate_field(field_type: CalculatedFieldType, invoice_data: Dict[str, Any]) -> Any:
    """
    Función principal para calcular campos calculados
    
    Args:
        field_type: Tipo de campo calculado
        invoice_data: Datos de la factura
    
    Returns:
        Valor calculado o None si hay error
    """
    try:
        calculation_func = CALCULATION_FUNCTIONS.get(field_type)
        if calculation_func:
            return calculation_func(invoice_data)
        else:
            logger.warning(f"Función de cálculo no encontrada para: {field_type}")
            return None
    except Exception as e:
        logger.error(f"Error calculando campo {field_type}: {e}")
        return None

def get_calculated_fields_by_category() -> Dict[str, List[CalculatedFieldDefinition]]:
    """
    Organiza los campos calculados por categoría para la UI
    
    Returns:
        Diccionario con campos organizados por categoría
    """
    categories = {}
    for field_def in CALCULATED_FIELDS_DEFINITIONS.values():
        category = field_def.category
        if category not in categories:
            categories[category] = []
        categories[category].append(field_def)
    
    return categories