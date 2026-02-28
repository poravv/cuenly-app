"""
Migración: Agregar billing_day_of_month a suscripciones activas existentes.

Usa el día de started_at (o created_at) como billing_day_of_month.
Ejecutar una sola vez en producción.

Uso:
    PYTHONPATH=backend python3 scripts/migrate_billing_day.py
"""

import os
import sys
from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "cuenlyapp")


def migrate():
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=10000)
    db = client[MONGODB_DATABASE]
    coll = db["user_subscriptions"]

    subs = list(coll.find({
        "status": "active",
        "billing_day_of_month": {"$exists": False}
    }))

    print(f"Encontradas {len(subs)} suscripciones activas sin billing_day_of_month")

    updated = 0
    for sub in subs:
        started = sub.get("started_at") or sub.get("created_at")
        if not started:
            print(f"  SKIP {sub['_id']} — sin fecha de inicio")
            continue

        day = started.day
        coll.update_one(
            {"_id": sub["_id"]},
            {"$set": {"billing_day_of_month": day}}
        )
        print(f"  OK {sub.get('user_email', '?')} → billing_day_of_month={day}")
        updated += 1

    print(f"\nMigración completada: {updated}/{len(subs)} actualizadas")
    client.close()


if __name__ == "__main__":
    migrate()
