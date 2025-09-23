#!/usr/bin/env python3
"""Script para actualizar templates existentes eliminando campo total_operacion"""

import asyncio
import sys
sys.path.append('/app')

from app.repositories.export_template_repository import ExportTemplateRepository

async def update_templates():
    """Actualizar templates existentes eliminando total_operacion"""
    print("🔄 Actualizando templates existentes...")
    
    repo = ExportTemplateRepository()
    owner_email = "andyvercha@gmail.com"
    
    # Obtener todos los templates del usuario (método síncrono)
    templates = repo.get_templates_by_user(owner_email)
    
    updated_count = 0
    
    for template in templates:
        original_fields_count = len(template.fields)
        
        # Filtrar campos para eliminar exento (redundante con monto_exento)
        updated_fields = [
            field for field in template.fields 
            if field.field_key != "exento"
        ]
        
        if len(updated_fields) < original_fields_count:
            print(f"📝 Actualizando template '{template.name}'")
            print(f"   - Eliminando campo 'exento' (redundante con monto_exento)")
            print(f"   - Campos: {original_fields_count} → {len(updated_fields)}")
            
            # Reordenar campos después de la eliminación
            for i, field in enumerate(updated_fields, start=1):
                field.order = i
            
            # Actualizar template (método síncrono)
            template.fields = updated_fields
            repo.update_template(template.id, template)
            
            updated_count += 1
            print(f"✅ Template '{template.name}' actualizado")
        else:
            print(f"ℹ️ Template '{template.name}' no necesita cambios")
    
    print(f"\n🎉 Actualización completada: {updated_count} templates actualizados")

if __name__ == "__main__":
    asyncio.run(update_templates())