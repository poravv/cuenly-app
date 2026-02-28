"""
Script de migración one-shot: normaliza status de suscripciones a minúsculas.

Uso:
  # Dry-run (solo muestra qué haría):
  python scripts/migrate_subscription_status.py

  # Ejecutar migración real:
  python scripts/migrate_subscription_status.py --apply

Requiere MONGODB_URL como variable de entorno o usa la de settings.
"""
import sys
import os

# Agregar el path del backend para importar settings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from pymongo import MongoClient

# Intentar importar settings, o usar env var directamente
try:
    from app.config.settings import settings
    MONGODB_URL = settings.MONGODB_URL
    MONGODB_DATABASE = settings.MONGODB_DATABASE
except Exception:
    MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "cuenly")

COLLECTION = "user_subscriptions"

STATUS_MAP = {
    "ACTIVE": "active",
    "PAST_DUE": "past_due",
    "CANCELLED": "cancelled",
    "EXPIRED": "expired",
}


def migrate(apply: bool = False):
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DATABASE]
    coll = db[COLLECTION]

    print(f"Conectado a: {MONGODB_DATABASE}")
    print(f"Colección: {COLLECTION}")
    print(f"Modo: {'APLICAR CAMBIOS' if apply else 'DRY-RUN (solo lectura)'}")
    print("=" * 60)

    total_updated = 0

    for old_status, new_status in STATUS_MAP.items():
        count = coll.count_documents({"status": old_status})
        if count > 0:
            print(f"  '{old_status}' → '{new_status}': {count} documentos")
            if apply:
                result = coll.update_many(
                    {"status": old_status},
                    {"$set": {"status": new_status}}
                )
                print(f"    → Actualizados: {result.modified_count}")
                total_updated += result.modified_count
        else:
            print(f"  '{old_status}' → '{new_status}': 0 documentos (OK)")

    print("=" * 60)

    if apply:
        print(f"Total actualizados: {total_updated}")
    else:
        print("Dry-run completado. Ejecuta con --apply para aplicar cambios.")

    # Resumen final de status en BD
    print("\nDistribución actual de status:")
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    for doc in coll.aggregate(pipeline):
        print(f"  {doc['_id']}: {doc['count']}")

    client.close()


if __name__ == "__main__":
    do_apply = "--apply" in sys.argv
    migrate(apply=do_apply)
