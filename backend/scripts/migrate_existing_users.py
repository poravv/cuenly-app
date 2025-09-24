#!/usr/bin/env python3
"""
Script para migrar usuarios existentes agregando información de trial
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar el directorio padre al path para importar módulos de la app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import get_database
from app.repositories.user_repository import UserRepository
from app.models.user import User

def migrate_existing_users():
    """
    Migra usuarios existentes agregando información de trial
    """
    print("Iniciando migración de usuarios existentes...")
    
    try:
        # Obtener conexión a la base de datos
        db = get_database()
        user_repository = UserRepository(db)
        
        # Obtener todos los usuarios
        users_collection = db.users
        existing_users = list(users_collection.find({}))
        
        print(f"Encontrados {len(existing_users)} usuarios para migrar")
        
        updated_count = 0
        
        for user_doc in existing_users:
            user_id = user_doc.get('_id')
            email = user_doc.get('email', 'desconocido')
            
            # Verificar si el usuario ya tiene información de trial
            if user_doc.get('trial_start_date') is None:
                print(f"Migrando usuario: {email}")
                
                # Configurar información de trial
                trial_start_date = datetime.utcnow()
                trial_end_date = trial_start_date + timedelta(days=15)
                
                # Actualizar el documento del usuario
                update_data = {
                    'is_trial_user': True,
                    'trial_start_date': trial_start_date,
                    'trial_end_date': trial_end_date,
                    'subscription_active': False,
                    'subscription_type': None,
                    'updated_at': datetime.utcnow()
                }
                
                result = users_collection.update_one(
                    {'_id': user_id},
                    {'$set': update_data}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✓ Usuario {email} migrado exitosamente")
                else:
                    print(f"✗ Error migrando usuario {email}")
            else:
                print(f"Usuario {email} ya tiene información de trial, saltando...")
        
        print(f"\nMigración completada:")
        print(f"- Usuarios procesados: {len(existing_users)}")
        print(f"- Usuarios actualizados: {updated_count}")
        print(f"- Usuarios ya migrados: {len(existing_users) - updated_count}")
        
    except Exception as e:
        print(f"Error durante la migración: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_existing_users()
    if success:
        print("\n✅ Migración completada exitosamente!")
        sys.exit(0)
    else:
        print("\n❌ La migración falló!")
        sys.exit(1)