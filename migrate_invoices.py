#!/usr/bin/env python3
"""Script de migración para corregir campos faltantes en facturas existentes"""

import asyncio
import os
import sys
import json
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.append('/app')

from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

class InvoiceMigration:
    def __init__(self):
        self.repo = MongoInvoiceRepository()
        
    async def migrate_invoices_simple(self, owner_email: str, limit: int = 100):
        """Migración simple: corregir total_operacion = monto_total cuando falta"""
        print(f"🔄 Iniciando migración simple para {owner_email}")
        
        # Obtener facturas del usuario
        invoices = self.repo.get_invoices_by_user(owner_email)
        
        corrected_count = 0
        
        for invoice in invoices[:limit]:
            # Verificar si necesita corrección
            total_operacion = invoice.get('total_operacion', 0)
            monto_total = invoice.get('monto_total', 0)
            monto_exento = invoice.get('monto_exento', 0)
            exento = invoice.get('exento', 0)
            
            needs_correction = (
                (total_operacion == 0 and monto_total > 0) or
                (monto_exento == 0 and exento > 0)
            )
            
            if needs_correction:
                numero_factura = invoice.get('numero_factura', 'N/A')
                print(f"🔧 Corrigiendo factura {numero_factura}")
                
                # Preparar actualizaciones directas en MongoDB
                updates = {}
                
                if total_operacion == 0 and monto_total > 0:
                    updates['totales.total_operacion'] = monto_total
                    print(f"  - total_operacion: 0 → {monto_total}")
                
                if monto_exento == 0 and exento > 0:
                    updates['totales.monto_exento'] = exento
                    print(f"  - monto_exento: 0 → {exento}")
                
                # Actualizar directamente en MongoDB
                if updates:
                    await self._update_invoice_direct(invoice['_id'], updates)
                    corrected_count += 1
                    print(f"✅ Factura {numero_factura} corregida")
        
        print(f"🎉 Migración completada: {corrected_count} facturas corregidas")
        
    async def migrate_invoices_with_xml(self, owner_email: str, limit: int = 50):
        """Migrar facturas que tienen XML disponible para reprocesarlas"""
        print(f"� Iniciando migración con XML para {owner_email}")
        
        invoices = self.repo.get_invoices_by_user(owner_email)
        xml_dir = "/app/data/temp_pdfs"
        corrected_count = 0
        
        for invoice in invoices[:limit]:
            # Verificar si necesita corrección
            needs_correction = (
                invoice.get('total_operacion', 0) == 0 or
                invoice.get('monto_exento', 0) == 0
            )
            
            if not needs_correction:
                continue
            
            # Buscar XML correspondiente
            cdc = invoice.get('cdc', '')
            numero_factura = invoice.get('numero_factura', '')
            
            xml_file = self._find_xml_file(xml_dir, cdc, numero_factura)
            
            if xml_file:
                print(f"� Procesando XML para factura {numero_factura}")
                
                # Procesar XML
                corrected_data = await self._process_xml_file(xml_file)
                
                if corrected_data:
                    # Preparar actualizaciones desde XML
                    updates = {}
                    
                    if corrected_data.get('total_operacion', 0) > 0:
                        updates['totales.total_operacion'] = corrected_data['total_operacion']
                    
                    if corrected_data.get('monto_exento', 0) > 0:
                        updates['totales.monto_exento'] = corrected_data['monto_exento']
                        updates['totales.exentas'] = corrected_data['monto_exento']
                    
                    if corrected_data.get('exonerado', 0) > 0:
                        updates['totales.exonerado'] = corrected_data['exonerado']
                    
                    if corrected_data.get('total_iva', 0) > 0:
                        updates['totales.total_iva'] = corrected_data['total_iva']
                    
                    # Actualizar en MongoDB
                    if updates:
                        await self._update_invoice_direct(invoice['_id'], updates)
                        corrected_count += 1
                        print(f"✅ Factura {numero_factura} corregida desde XML")
        
        print(f"🎉 Migración XML completada: {corrected_count} facturas corregidas")
    
    def _find_xml_file(self, xml_dir: str, cdc: str, numero_factura: str) -> Optional[str]:
        """Buscar archivo XML por CDC o número de factura"""
        if not os.path.exists(xml_dir):
            return None
        
        for filename in os.listdir(xml_dir):
            if filename.endswith('.xml'):
                filepath = os.path.join(xml_dir, filename)
                
                # Buscar por CDC en nombre de archivo
                if cdc and len(cdc) > 10 and cdc in filename:
                    return filepath
        
        return None
    
    async def _process_xml_file(self, xml_file: str) -> Optional[Dict[str, Any]]:
        """Procesar archivo XML y extraer datos corregidos"""
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            success, data = parse_paraguayan_xml(xml_content)
            if success:
                return data
        except Exception as e:
            print(f"Error procesando XML {xml_file}: {e}")
        
        return None
    
    async def _update_invoice_direct(self, invoice_id: str, updates: Dict[str, Any]):
        """Actualizar factura directamente en MongoDB"""
        try:
            from bson import ObjectId
            headers_coll = self.repo._headers()
            
            # Convertir string ID a ObjectId si es necesario
            if isinstance(invoice_id, str):
                invoice_id = ObjectId(invoice_id)
            
            # Agregar timestamp de actualización
            updates['updated_at'] = datetime.utcnow()
            
            # Actualizar documento
            result = headers_coll.update_one(
                {"_id": invoice_id},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                print(f"  📝 Actualización exitosa en MongoDB")
            else:
                print(f"  ⚠️ No se pudo actualizar en MongoDB")
                
        except Exception as e:
            print(f"  ❌ Error actualizando MongoDB: {e}")

async def main():
    migration = InvoiceMigration()
    owner_email = "andyvercha@gmail.com"
    
    print("🚀 INICIANDO MIGRACIÓN DE FACTURAS")
    print("="*50)
    
    # Paso 1: Migración simple (total_operacion = monto_total)
    await migration.migrate_invoices_simple(owner_email, limit=100)
    
    print("\n" + "="*50)
    
    # Paso 2: Migración con XML (más precisa)
    await migration.migrate_invoices_with_xml(owner_email, limit=50)
    
    print("\n🎉 MIGRACIÓN COMPLETADA")

if __name__ == "__main__":
    asyncio.run(main())