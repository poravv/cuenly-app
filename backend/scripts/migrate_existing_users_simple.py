#!/usr/bin/env python3
"""
Script para migrar usuarios existentes agregando información de trial
"""

import os
import sys
from datetime import datetime, timedelta
from pymongo import MongoClient

def get_mongo_connection():
    """Obtener conexión a MongoDB"""
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongodb:27017')
    db_name = os.getenv('DB_NAME', 'cuenlyapp')
    
    client = MongoClient(mongo_uri)
    return client[db_name]

def migrate_existing_users():
    """
    Migra usuarios existentes agregando información de trial
    """
    print("Iniciando migración de usuarios existentes...")
    
    try:
        # Obtener conexión a la base de datos
        db = get_mongo_connection()
        users_collection = db.users
        
        # Obtener todos los usuarios
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
                    
                    # Mostrar información del trial
                    days_remaining = (trial_end_date - datetime.utcnow()).days
                    print(f"  - Trial iniciado: {trial_start_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"  - Trial termina: {trial_end_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"  - Días restantes: {days_remaining}")
                else:
                    print(f"✗ Error migrando usuario {email}")
            else:
                # Mostrar información existente del trial
                trial_start = user_doc.get('trial_start_date')
                trial_end = user_doc.get('trial_end_date')
                if trial_end:
                    days_remaining = (trial_end - datetime.utcnow()).days
                    print(f"Usuario {email} ya tiene trial configurado ({days_remaining} días restantes)")
                else:
                    print(f"Usuario {email} ya tiene información de trial, saltando...")
        
        print(f"\nMigración completada:")
        print(f"- Usuarios procesados: {len(existing_users)}")
        print(f"- Usuarios actualizados: {updated_count}")
        print(f"- Usuarios ya migrados: {len(existing_users) - updated_count}")
        
    except Exception as e:
        print(f"Error durante la migración: {str(e)}")
        import traceback
        traceback.print_exc()
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