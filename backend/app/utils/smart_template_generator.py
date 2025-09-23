#!/usr/bin/env python3
"""
Generador de Templates Inteligentes con Agrupación Automática
Simplifica la creación de templates con configuraciones predefinidas
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from app.models.export_template import (
    ExportTemplate, ExportField, FieldType, FieldAlignment,
    CalculatedFieldType
)
from typing import List, Dict

class SmartTemplateGenerator:
    """Generador de templates inteligentes con grupos predefinidos"""
    
    def __init__(self):
        self.template_presets = {
            'contable': self._create_contable_preset(),
            'ejecutivo': self._create_ejecutivo_preset(), 
            'detallado': self._create_detallado_preset(),
            'simple': self._create_simple_preset()
        }
    
    def _create_field(self, field_key: str, display_name: str, field_type: FieldType, 
                     order: int, calculated_type: CalculatedFieldType = None) -> ExportField:
        """Helper para crear campos de manera consistente"""
        return ExportField(
            field_key=field_key,
            display_name=display_name,
            field_type=field_type,
            alignment=FieldAlignment.RIGHT if field_type in [FieldType.CURRENCY, FieldType.NUMBER, FieldType.PERCENTAGE] else FieldAlignment.LEFT,
            order=order,
            is_visible=True,
            is_calculated=calculated_type is not None,
            calculated_type=calculated_type
        )
    
    def _create_contable_preset(self) -> Dict:
        """Template para contadores - enfoque en IVA y declaraciones"""
        fields = [
            self._create_field("fecha", "Fecha", FieldType.DATE, 1),
            self._create_field("numero_factura", "N° Factura", FieldType.TEXT, 2),
            self._create_field("ruc_cliente", "RUC Cliente", FieldType.TEXT, 3),
            self._create_field("nombre_cliente", "Cliente", FieldType.TEXT, 4),
            
            # Bases gravadas (sin IVA)
            self._create_field("calculated_MONTO_SIN_IVA_5", "Base Gravada 5%", FieldType.CURRENCY, 5, CalculatedFieldType.MONTO_SIN_IVA_5),
            self._create_field("calculated_MONTO_SIN_IVA_10", "Base Gravada 10%", FieldType.CURRENCY, 6, CalculatedFieldType.MONTO_SIN_IVA_10),
            self._create_field("monto_exento", "Monto Exento", FieldType.CURRENCY, 7),
            
            # IVA específico para declaraciones
            self._create_field("calculated_TOTAL_IVA_5_ONLY", "IVA 5%", FieldType.CURRENCY, 8, CalculatedFieldType.TOTAL_IVA_5_ONLY),
            self._create_field("calculated_TOTAL_IVA_10_ONLY", "IVA 10%", FieldType.CURRENCY, 9, CalculatedFieldType.TOTAL_IVA_10_ONLY),
            self._create_field("calculated_TOTAL_IVA_GENERAL", "Total IVA", FieldType.CURRENCY, 10, CalculatedFieldType.TOTAL_IVA_GENERAL),
            
            self._create_field("monto_total", "Total Factura", FieldType.CURRENCY, 11),
        ]
        
        return {
            'name': 'Reporte Contable',
            'description': 'Template optimizado para contadores con desglose detallado de IVA para declaraciones tributarias',
            'sheet_name': 'Declaración IVA',
            'fields': fields,
            'group_type': 'contable',
            'auto_features': ['iva_breakdown', 'totals_row']
        }
    
    def _create_ejecutivo_preset(self) -> Dict:
        """Template para ejecutivos - métricas clave y análisis"""
        fields = [
            self._create_field("fecha", "Fecha", FieldType.DATE, 1),
            self._create_field("nombre_cliente", "Cliente", FieldType.TEXT, 2),
            
            # Análisis de composición
            self._create_field("calculated_SUBTOTAL_GRAVADO", "Ventas Gravadas", FieldType.CURRENCY, 3, CalculatedFieldType.SUBTOTAL_GRAVADO),
            self._create_field("monto_exento", "Ventas Exentas", FieldType.CURRENCY, 4),
            self._create_field("calculated_TOTAL_IVA_GENERAL", "IVA Cobrado", FieldType.CURRENCY, 5, CalculatedFieldType.TOTAL_IVA_GENERAL),
            self._create_field("monto_total", "Total Facturado", FieldType.CURRENCY, 6),
            
            # Análisis porcentual
            self._create_field("calculated_PORCENTAJE_IVA_5", "% IVA 5%", FieldType.PERCENTAGE, 7, CalculatedFieldType.PORCENTAJE_IVA_5),
            self._create_field("calculated_PORCENTAJE_IVA_10", "% IVA 10%", FieldType.PERCENTAGE, 8, CalculatedFieldType.PORCENTAJE_IVA_10),
            
            # Métricas de productos
            self._create_field("calculated_CANTIDAD_PRODUCTOS", "# Productos", FieldType.NUMBER, 9, CalculatedFieldType.CANTIDAD_PRODUCTOS),
            self._create_field("calculated_VALOR_PROMEDIO_PRODUCTO", "Valor Promedio", FieldType.CURRENCY, 10, CalculatedFieldType.VALOR_PROMEDIO_PRODUCTO),
        ]
        
        return {
            'name': 'Resumen Ejecutivo',
            'description': 'Template para análisis rápido de ventas con métricas clave y composición de negocio',
            'sheet_name': 'Dashboard Ventas',
            'fields': fields,
            'group_type': 'ejecutivo',
            'auto_features': ['percentage_analysis', 'product_metrics']
        }
    
    def _create_detallado_preset(self) -> Dict:
        """Template completo - todos los campos importantes"""
        fields = [
            # Básicos
            self._create_field("fecha", "Fecha", FieldType.DATE, 1),
            self._create_field("numero_factura", "N° Factura", FieldType.TEXT, 2),
            self._create_field("ruc_cliente", "RUC Cliente", FieldType.TEXT, 3),
            self._create_field("nombre_cliente", "Cliente", FieldType.TEXT, 4),
            
            # Montos originales
            self._create_field("base_gravada_5", "Base Original 5%", FieldType.CURRENCY, 5),
            self._create_field("base_gravada_10", "Base Original 10%", FieldType.CURRENCY, 6),
            self._create_field("iva_5", "IVA 5% Original", FieldType.CURRENCY, 7),
            self._create_field("iva_10", "IVA 10% Original", FieldType.CURRENCY, 8),
            
            # Campos calculados para verificación
            self._create_field("calculated_MONTO_CON_IVA_5", "Total con IVA 5%", FieldType.CURRENCY, 9, CalculatedFieldType.MONTO_CON_IVA_5),
            self._create_field("calculated_MONTO_CON_IVA_10", "Total con IVA 10%", FieldType.CURRENCY, 10, CalculatedFieldType.MONTO_CON_IVA_10),
            
            # Totales y análisis
            self._create_field("calculated_SUBTOTAL_GRAVADO", "Subtotal Gravado", FieldType.CURRENCY, 11, CalculatedFieldType.SUBTOTAL_GRAVADO),
            self._create_field("calculated_SUBTOTAL_NO_GRAVADO", "Subtotal No Gravado", FieldType.CURRENCY, 12, CalculatedFieldType.SUBTOTAL_NO_GRAVADO),
            self._create_field("monto_total", "Total Final", FieldType.CURRENCY, 13),
            
            # Productos agrupados (evita duplicación)
            self._create_field("calculated_CANTIDAD_PRODUCTOS", "Cantidad Items", FieldType.NUMBER, 14, CalculatedFieldType.CANTIDAD_PRODUCTOS),
            self._create_field("productos.nombre", "Productos", FieldType.ARRAY, 15),
        ]
        
        return {
            'name': 'Análisis Completo',
            'description': 'Template detallado con todos los campos para auditorías y análisis profundo',
            'sheet_name': 'Análisis Completo',
            'fields': fields,
            'group_type': 'detallado',
            'auto_features': ['all_calculations', 'product_grouping', 'verification_columns']
        }
    
    def _create_simple_preset(self) -> Dict:
        """Template simple para usuarios básicos"""
        fields = [
            self._create_field("fecha", "Fecha", FieldType.DATE, 1),
            self._create_field("nombre_cliente", "Cliente", FieldType.TEXT, 2),
            self._create_field("numero_factura", "N° Factura", FieldType.TEXT, 3),
            self._create_field("monto_total", "Total", FieldType.CURRENCY, 4),
            self._create_field("calculated_TOTAL_IVA_GENERAL", "IVA Total", FieldType.CURRENCY, 5, CalculatedFieldType.TOTAL_IVA_GENERAL),
        ]
        
        return {
            'name': 'Reporte Simple',
            'description': 'Template básico con solo la información esencial',
            'sheet_name': 'Facturas',
            'fields': fields,
            'group_type': 'simple',
            'auto_features': ['basic_totals']
        }
    
    def create_template_from_preset(self, preset_name: str, custom_name: str = None) -> ExportTemplate:
        """Crea un ExportTemplate a partir de un preset"""
        if preset_name not in self.template_presets:
            raise ValueError(f"Preset '{preset_name}' no existe")
        
        preset = self.template_presets[preset_name]
        
        return ExportTemplate(
            name=custom_name or preset['name'],
            description=preset['description'],
            sheet_name=preset['sheet_name'],
            include_header=True,
            include_totals=True,
            fields=preset['fields']
        )
    
    def get_available_presets(self) -> Dict:
        """Retorna información de todos los presets disponibles"""
        return {
            name: {
                'name': preset['name'],
                'description': preset['description'],
                'field_count': len(preset['fields']),
                'calculated_fields': len([f for f in preset['fields'] if f.is_calculated]),
                'group_type': preset['group_type'],
                'features': preset['auto_features']
            }
            for name, preset in self.template_presets.items()
        }

def demo_smart_templates():
    """Demostración de templates inteligentes"""
    generator = SmartTemplateGenerator()
    
    print("🚀 GENERADOR DE TEMPLATES INTELIGENTES")
    print("=" * 50)
    
    presets = generator.get_available_presets()
    
    for preset_id, info in presets.items():
        print(f"\n📋 {info['name'].upper()}")
        print("-" * 30)
        print(f"   🎯 Uso: {info['description'][:60]}...")
        print(f"   📊 Campos: {info['field_count']} total ({info['calculated_fields']} calculados)")
        print(f"   ⚡ Características: {', '.join(info['features'])}")
        
        # Crear el template
        template = generator.create_template_from_preset(preset_id)
        print(f"   ✅ Template creado: '{template.name}'")
    
    print("\n" + "=" * 50)
    print("💡 BENEFICIOS:")
    print("   ✅ Usuarios eligen por caso de uso, no por campos técnicos")
    print("   ✅ Cero duplicación - cada preset está optimizado")
    print("   ✅ Agrupación automática de productos")
    print("   ✅ Campos calculados incluidos inteligentemente")
    print("   ✅ Templates listos para usar en 2 clics")

if __name__ == "__main__":
    demo_smart_templates()