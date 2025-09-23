#!/usr/bin/env python3
"""
Prueba del formateo sin comas para Excel
"""

import sys
import os

# Agregar el path del proyecto
sys.path.append('/Users/andresvera/Desktop/Proyectos/cuenly/backend')

from app.models.export_template import FieldType
from app.modules.excel_exporter.template_exporter import ExcelExporter

class MockField:
    """Mock de ExportField para pruebas"""
    def __init__(self, field_type, field_key="test"):
        self.field_type = field_type
        self.field_key = field_key

def test_number_formatting():
    """Probar que los números salen sin comas"""
    
    print("🧪 PRUEBA DE FORMATEO SIN COMAS")
    print("=" * 50)
    
    exporter = ExcelExporter()
    
    # Datos de prueba
    test_values = [
        (47500, FieldType.CURRENCY, "Monto con IVA 10%"),
        (43182, FieldType.CURRENCY, "Monto sin IVA 10%"),
        (4318, FieldType.CURRENCY, "IVA 10% únicamente"),
        (1234567, FieldType.CURRENCY, "Monto grande"),
        (0, FieldType.CURRENCY, "Monto cero"),
        (123.45, FieldType.NUMBER, "Número decimal"),
        (15.75, FieldType.PERCENTAGE, "Porcentaje")
    ]
    
    print("📋 RESULTADOS DEL FORMATEO:")
    print("-" * 50)
    
    all_correct = True
    
    for value, field_type, description in test_values:
        mock_field = MockField(field_type)
        formatted = exporter._format_field_value(value, mock_field)
        
        # Verificar que no tenga comas
        has_comma = "," in formatted
        
        if has_comma:
            print(f"❌ {description}: {formatted} (TIENE COMAS)")
            all_correct = False
        else:
            print(f"✅ {description}: {formatted} (SIN COMAS)")
    
    print("\n" + "=" * 50)
    
    if all_correct:
        print("🎉 ¡PERFECTO! Todos los números salen sin comas")
        print("✅ Excel podrá hacer cálculos correctamente")
        print("✅ Los valores son numéricos puros")
        
        print("\n📊 EJEMPLO DE EXPORT ESPERADO:")
        print("Número de Factura\tMonto IVA 10% (Con impuesto)\tMonto IVA 10% (Sin impuesto)\tTotal IVA 10% únicamente")
        print("026-006-0231130\t47500\t43182\t4318")
        print("001-005-0751652\t0\t0\t0")
        
    else:
        print("⚠️ ALGUNOS NÚMEROS AÚN TIENEN COMAS")
        print("❌ Necesita más correcciones")
    
    print("\n💡 VENTAJAS DEL NUEVO FORMATO:")
    print("  • Excel reconoce los números como valores numéricos")
    print("  • Se pueden hacer sumas, restas, multiplicaciones")
    print("  • Se pueden aplicar formatos de número en Excel")
    print("  • Compatibilidad con fórmulas y funciones")

if __name__ == "__main__":
    test_number_formatting()