#!/usr/bin/env python3
"""Script para reprocesar facturas XML y actualizar BD con campos faltantes"""

import asyncio
import os
import sys
sys.path.append('/app')

from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
from app.models.models import InvoiceData

async def reprocess_xml_invoice():
    """Reprocesar una factura XML específica y actualizar BD"""
    xml_file = "/app/data/temp_pdfs/20250922201429626_c54d9f5b_01800092430001001041121322025050917848239468.xml"
    
    if not os.path.exists(xml_file):
        print(f"Archivo no encontrado: {xml_file}")
        return
    
    # Leer y procesar XML
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    print("Procesando XML...")
    success, data = parse_paraguayan_xml(xml_content)
    
    if not success:
        print("❌ Error procesando XML")
        return
    
    print("✅ XML procesado exitosamente")
    print(f"Total operación: {data.get('total_operacion', 'NO EXISTE')}")
    print(f"Monto exento: {data.get('monto_exento', 'NO EXISTE')}")
    print(f"Exento: {data.get('exento', 'NO EXISTE')}")
    print(f"Subtotal exentas: {data.get('subtotal_exentas', 'NO EXISTE')}")
    
    print("\n=== DATOS COMPLETOS DEL PARSER ===")
    for key, value in data.items():
        if 'exento' in key.lower() or 'operacion' in key.lower() or 'total' in key.lower():
            print(f"{key}: {value}")
    print("==================================\n")
    
    # Buscar factura existente en BD por número o CDC
    numero_factura = data.get('numero_factura')
    cdc = data.get('cdc')
    
    if not numero_factura and not cdc:
        print("❌ No se puede identificar la factura (sin número ni CDC)")
        return
    
    # Conectar a BD y buscar factura
    repo = MongoInvoiceRepository()
    try:
        # Simular búsqueda por número de factura o CDC
        owner_email = "andyvercha@gmail.com"
        
        # Crear modelo de factura actualizado
        data['owner_email'] = owner_email
        data['created_at'] = data.get('created_at', '2025-09-23T10:00:00')
        
        invoice = InvoiceData.from_dict(data)
        
        print("Datos de factura actualizados:")
        print(f"- Número: {invoice.numero_factura}")
        print(f"- Total operación: {invoice.total_operacion}")
        print(f"- Monto exento: {invoice.monto_exento}")
        print(f"- Exento: {invoice.exento}")
        print(f"- CDC: {invoice.cdc}")
        
        print("NOTA: Este script solo muestra los datos corregidos.")
        print("Para actualizar la BD real, sería necesario implementar la lógica de update.")
        
    except Exception as e:
        print(f"❌ Error procesando: {e}")

if __name__ == "__main__":
    asyncio.run(reprocess_xml_invoice())