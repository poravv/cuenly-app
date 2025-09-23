#!/usr/bin/env python3
"""Script temporal para probar el parser XML"""

import asyncio
import os
import sys
sys.path.append('/Users/andresvera/Desktop/Proyectos/cuenly/backend')

from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

async def test_parser():
    xml_file = "/Users/andresvera/Desktop/Proyectos/cuenly/data/temp_pdfs/20250922201429626_c54d9f5b_01800092430001001041121322025050917848239468.xml"
    
    if not os.path.exists(xml_file):
        print(f"Archivo no encontrado: {xml_file}")
        return
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    print("Procesando XML...")
    success, data = parse_paraguayan_xml(xml_content)
    
    if success:
        print("✅ XML procesado exitosamente")
        print(f"Total operación: {data.get('total_operacion', 'NO EXISTE')}")
        print(f"Monto exento: {data.get('monto_exento', 'NO EXISTE')}")
        print(f"Exento: {data.get('exento', 'NO EXISTE')}")
        print(f"Monto total: {data.get('monto_total', 'NO EXISTE')}")
        print(f"Gravado 5%: {data.get('gravado_5', 'NO EXISTE')}")
        print(f"Gravado 10%: {data.get('gravado_10', 'NO EXISTE')}")
    else:
        print("❌ Error procesando XML")
        print(f"Datos: {data}")

if __name__ == "__main__":
    asyncio.run(test_parser())