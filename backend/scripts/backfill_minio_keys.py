#!/usr/bin/env python3
"""
Backfill de minio_key en invoice_headers cuando quedó vacío.

Uso:
  python scripts/backfill_minio_keys.py --owner andyvercha@gmail.com --apply
  python scripts/backfill_minio_keys.py --owner andyvercha@gmail.com --dry-run
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from minio import Minio
from pymongo import MongoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill minio_key en invoice_headers")
    parser.add_argument("--owner", help="Filtrar por owner_email", default="")
    parser.add_argument("--dry-run", action="store_true", help="No escribe cambios")
    parser.add_argument("--apply", action="store_true", help="Aplica cambios en MongoDB")
    parser.add_argument("--limit", type=int, default=0, help="Limita cantidad de headers a evaluar")
    parser.add_argument("--start-year", type=int, default=2018, help="Año inicial para buscar en MinIO")
    return parser.parse_args()


def required_env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise RuntimeError(f"Falta variable de entorno requerida: {name}")
    return value


def load_owner_keys(
    client: Minio,
    bucket: str,
    owner_email: str,
    start_year: int,
) -> List[str]:
    current_year = datetime.utcnow().year + 1
    seen = set()
    keys: List[str] = []
    for year in range(current_year, start_year - 1, -1):
        prefix = f"{year}/{owner_email}/"
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            key = obj.object_name
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def _ext_rank(key: str) -> int:
    lname = key.lower()
    if lname.endswith(".pdf"):
        return 3
    if lname.endswith(".xml"):
        return 2
    if lname.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return 1
    return 0


def find_best_key(keys: List[str], cdc: str, numero: str, ruc: str) -> Tuple[str, str]:
    # Política estricta: solo mapear por CDC exacto (sin inferir por numero_documento).
    cdc_candidates = [k for k in keys if cdc and cdc in k]
    if cdc_candidates:
        cdc_candidates.sort(key=lambda k: (_ext_rank(k), k), reverse=True)
        return cdc_candidates[0], "cdc"
    return "", ""


def main() -> int:
    args = parse_args()
    if not args.apply and not args.dry_run:
        args.dry_run = True

    mongo_url = required_env("MONGODB_URL")
    minio_endpoint = required_env("MINIO_ENDPOINT")
    minio_access = required_env("MINIO_ACCESS_KEY")
    minio_secret = required_env("MINIO_SECRET_KEY")
    minio_bucket = required_env("MINIO_BUCKET")
    minio_region = os.getenv("MINIO_REGION", "py-east-1")
    minio_secure = os.getenv("MINIO_SECURE", "true").lower() in ("1", "true", "yes")

    mongo = MongoClient(mongo_url)
    db_name = mongo_url.rsplit("/", 1)[-1].split("?")[0]
    db = mongo[db_name]
    headers = db["invoice_headers"]

    query: Dict[str, object] = {
        "status": "DONE",
        "minio_key": {"$in": ["", None]},
    }
    if args.owner:
        query["owner_email"] = args.owner.lower()

    projection = {"_id": 1, "owner_email": 1, "cdc": 1, "numero_documento": 1, "emisor.ruc": 1}
    cursor = headers.find(query, projection)
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)
    docs = list(cursor)

    print(f"Headers a evaluar: {len(docs)}")
    if not docs:
        return 0

    owners = sorted({(d.get("owner_email") or "").strip().lower() for d in docs if d.get("owner_email")})
    print(f"Owners involucrados: {len(owners)}")

    minio = Minio(
        minio_endpoint,
        access_key=minio_access,
        secret_key=minio_secret,
        secure=minio_secure,
        region=minio_region,
    )

    owner_keys: Dict[str, List[str]] = {}
    for owner in owners:
        keys = load_owner_keys(minio, minio_bucket, owner, args.start_year)
        owner_keys[owner] = keys
        print(f"  - {owner}: {len(keys)} objetos MinIO")

    stats = defaultdict(int)
    updates: List[Tuple[str, str]] = []

    for doc in docs:
        owner = (doc.get("owner_email") or "").strip().lower()
        cdc = (doc.get("cdc") or "").strip()
        numero = (doc.get("numero_documento") or "").strip()
        keys = owner_keys.get(owner, [])
        ruc = str((doc.get("emisor") or {}).get("ruc") or "").strip()
        best_key, match_type = find_best_key(keys, cdc, numero, ruc)
        if not best_key:
            stats["unmatched"] += 1
            continue

        stats["matched"] += 1
        if match_type == "cdc":
            stats["matched_cdc"] += 1
        elif match_type in ("numero_ruc", "numero_unique"):
            stats["matched_num_exact"] += 1

        updates.append((str(doc["_id"]), best_key))

    print(f"Matched: {stats['matched']}")
    print(f"  - CDC: {stats['matched_cdc']}")
    print(f"  - Numero exacto: {stats['matched_num_exact']}")
    print(f"Unmatched: {stats['unmatched']}")

    if args.dry_run and not args.apply:
        print("DRY RUN: sin cambios en MongoDB")
        print("Ejemplos:")
        for invoice_id, key in updates[:20]:
            print(f"  {invoice_id} -> {key}")
        return 0

    updated = 0
    for invoice_id, key in updates:
        result = headers.update_one(
            {"_id": invoice_id, "minio_key": {"$in": ["", None]}},
            {"$set": {"minio_key": key, "updated_at": datetime.utcnow()}},
        )
        if result.modified_count:
            updated += 1

    print(f"Actualizados: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
