#!/usr/bin/env python3
"""
Purgar facturas v2 (invoice_headers + invoice_items) de un usuario específico.

Uso:
  python backend/scripts/purge_user_invoices.py --owner andyvercha@gmail.com [--dry-run]

Requiere variables de entorno MONGODB_URL y MONGODB_DATABASE, o tomará de settings.
"""

import argparse
import os
from typing import Any

from pymongo import MongoClient


def get_db() -> Any:
    mongo_url = os.getenv('MONGODB_URL') or os.getenv('MONGODB_CONNECTION_STRING')
    if not mongo_url:
        from app.config.settings import settings  # type: ignore
        mongo_url = settings.MONGODB_URL
        db_name = settings.MONGODB_DATABASE
    else:
        db_name = os.getenv('MONGODB_DATABASE') or 'cuenlyapp_warehouse'
    client = MongoClient(mongo_url)
    client.admin.command('ping')
    return client[db_name]


def purge_user(db, owner_email: str, dry_run: bool = False) -> None:
    owner = (owner_email or '').lower()
    if not owner:
        raise ValueError('owner_email requerido')

    headers = db['invoice_headers']
    items = db['invoice_items']

    # Contar
    h_query = {'owner_email': owner}
    i_query = {'owner_email': owner}
    h_count = headers.count_documents(h_query)
    i_count = items.count_documents(i_query)

    print(f"Encontradas {h_count} cabeceras y {i_count} ítems para owner={owner}")

    if dry_run:
        print('[DRY-RUN] No se borrará nada')
        return

    # Borrar ítems primero (por seguridad de integridad)
    i_res = items.delete_many(i_query)
    # Borrar cabeceras
    h_res = headers.delete_many(h_query)

    print(f"Ítems borrados: {i_res.deleted_count}")
    print(f"Cabeceras borradas: {h_res.deleted_count}")


def main():
    parser = argparse.ArgumentParser(description='Purgar facturas v2 de un usuario')
    parser.add_argument('--owner', required=True, help='Email del propietario (owner_email)')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar conteo, sin borrar')
    args = parser.parse_args()

    db = get_db()
    purge_user(db, args.owner, args.dry_run)


if __name__ == '__main__':
    main()

