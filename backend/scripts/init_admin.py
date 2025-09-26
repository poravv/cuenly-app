#!/usr/bin/env python3
"""
Script para inicializar el usuario administrador andyvercha@gmail.com
"""
import sys
import os
import logging
from datetime import datetime, timedelta

# Agregar el directorio padre al path para importaciones absolutas
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app.repositories.user_repository import UserRepository

def init_admin_user():
    """Inicializa el usuario administrador"""
    try:
        user_repo = UserRepository()
        
        admin_email = 'andyvercha@gmail.com'
        
        # Verificar si el usuario ya existe
        existing_user = user_repo.get_by_email(admin_email)
        
        if existing_user:
            print(f"✅ Usuario {admin_email} ya existe en la base de datos")
            print(f"   - Rol actual: {existing_user.get('role', 'user')}")
            print(f"   - Estado: {existing_user.get('status', 'active')}")
            
            # Actualizar a admin si no lo es
            if existing_user.get('role') != 'admin':
                user_repo.update_user_role(admin_email, 'admin')
                print(f"   - ✅ Rol actualizado a 'admin'")
            
            # Asegurar que está activo
            if existing_user.get('status') != 'active':
                user_repo.update_user_status(admin_email, 'active')
                print(f"   - ✅ Estado actualizado a 'active'")
                
        else:
            # Crear usuario administrador
            now = datetime.utcnow()
            admin_user = {
                'email': admin_email,
                'uid': 'admin_init',  # Se actualizará en el primer login
                'name': 'Andy Verza',
                'picture': None,
                'role': 'admin',
                'status': 'active',
                'created_at': now,
                'last_login': now,
                'is_trial_user': False,  # Admin no tiene trial
                'ai_invoices_processed': 0,
                'email_processing_start_date': now
            }
            
            user_repo.upsert_user(admin_user)
            print(f"✅ Usuario administrador {admin_email} creado exitosamente")
            print(f"   - Rol: admin")
            print(f"   - Estado: active")
            print(f"   - Sin límite de trial")
        
        print(f"\n🎉 Inicialización completada. {admin_email} tiene acceso de administrador.")
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando usuario administrador: {e}")
        logging.error(f"Error en init_admin_user: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Inicializando usuario administrador...")
    success = init_admin_user()
    if success:
        print("\n✅ Proceso completado exitosamente")
        sys.exit(0)
    else:
        print("\n❌ Proceso falló")
        sys.exit(1)