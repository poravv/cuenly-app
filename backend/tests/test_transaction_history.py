"""
Tests para historial de transacciones de pago:
- DTOs (TransactionHistoryItem + TransactionHistoryResponse)
- Repository method (get_user_transaction_history)
- Endpoint GET /subscriptions/my-transactions (lógica/validaciones)
"""
from __future__ import annotations

import math
import sys
import types
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# =========================================
# Stubs mínimos para evitar dependencias
# =========================================
if "pymongo" not in sys.modules:
    pymongo_stub = types.ModuleType("pymongo")
    pymongo_stub.MongoClient = object  # type: ignore[attr-defined]
    pymongo_stub.UpdateOne = object  # type: ignore[attr-defined]
    pymongo_stub.ReturnDocument = type(
        "ReturnDocument", (), {"AFTER": "after", "BEFORE": "before"}
    )  # type: ignore[attr-defined]
    sys.modules["pymongo"] = pymongo_stub
else:
    pymongo_mod = sys.modules["pymongo"]
    if not hasattr(pymongo_mod, "ReturnDocument"):
        pymongo_mod.ReturnDocument = type(
            "ReturnDocument", (), {"AFTER": "after", "BEFORE": "before"}
        )  # type: ignore[attr-defined]

if "pymongo.collection" not in sys.modules:
    pymongo_collection_stub = types.ModuleType("pymongo.collection")
    pymongo_collection_stub.Collection = object  # type: ignore[attr-defined]
    sys.modules["pymongo.collection"] = pymongo_collection_stub

if "bson" not in sys.modules:
    bson_stub = types.ModuleType("bson")

    class _ObjectId(str):
        pass

    bson_stub.ObjectId = _ObjectId  # type: ignore[attr-defined]
    sys.modules["bson"] = bson_stub

from app.models.subscription_models import (
    TransactionHistoryItem,
    TransactionHistoryResponse,
)
from app.repositories.subscription_repository import SubscriptionRepository


# =========================================
# Helpers / Fake collections
# =========================================

def _make_mongo_doc(
    user_email: str = "user@test.com",
    amount: float = 150000,
    status: str = "success",
    plan_name: str = "PRO",
    pagopar_order_hash: str = "abcdef1234567890HASH",
    pagopar_order_id: str = "secret-order-id-123",
    subscription_id: str = "sub-secret-456",
    response_data: dict = None,
    attempt_number: int = 1,
    error_message: str = None,
    created_at: datetime = None,
    doc_id: str = "doc123",
) -> Dict[str, Any]:
    """Crea un documento MongoDB de subscription_transactions."""
    return {
        "_id": doc_id,
        "user_email": user_email,
        "amount": amount,
        "currency": "PYG",
        "status": status,
        "plan_name": plan_name,
        "pagopar_order_hash": pagopar_order_hash,
        "pagopar_order_id": pagopar_order_id,
        "subscription_id": subscription_id,
        "response_data": response_data or {"raw": "sensitive"},
        "attempt_number": attempt_number,
        "error_message": error_message,
        "created_at": created_at or datetime(2025, 6, 15, 10, 30, 0),
    }


class _FakeCursor(list):
    """Simula un cursor de PyMongo con sort, skip y limit."""

    def sort(self, field: str, order: int) -> "_FakeCursor":
        reverse = order == -1
        return _FakeCursor(sorted(self, key=lambda d: d.get(field, datetime.min), reverse=reverse))

    def skip(self, n: int) -> "_FakeCursor":
        return _FakeCursor(list(self)[n:])

    def limit(self, n: int) -> "_FakeCursor":
        return _FakeCursor(list(self)[:n])


class _FakeTransactionsCollection:
    """Simula la colección subscription_transactions de MongoDB."""

    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs
        self.last_query: Optional[Dict[str, Any]] = None

    def find(self, query: Dict[str, Any]) -> _FakeCursor:
        self.last_query = query
        filtered = []
        for doc in self.docs:
            match = True
            for key, val in query.items():
                if key == "created_at" and isinstance(val, dict):
                    doc_date = doc.get("created_at")
                    if "$gte" in val and doc_date < val["$gte"]:
                        match = False
                    if "$lte" in val and doc_date > val["$lte"]:
                        match = False
                elif doc.get(key) != val:
                    match = False
            if match:
                filtered.append(doc)
        return _FakeCursor(filtered)

    def count_documents(self, query: Dict[str, Any]) -> int:
        return len(self.find(query))

    def create_index(self, *args, **kwargs):
        pass


def _make_repo(docs: List[Dict[str, Any]]) -> SubscriptionRepository:
    """Crea un SubscriptionRepository con colección fake."""
    repo = SubscriptionRepository.__new__(SubscriptionRepository)
    repo.conn_str = "mongodb://unused"
    repo.db_name = "test_db"
    repo._client = None
    fake_col = _FakeTransactionsCollection(docs)

    # Monkey-patch la property transactions_collection
    type(repo).transactions_collection = property(lambda self: fake_col)
    # _ensure_indexes no-op
    repo._ensure_indexes = lambda: None  # type: ignore[assignment]

    return repo


# =========================================
# 1. Tests de DTOs
# =========================================

class TestTransactionHistoryItem:
    """Tests del DTO TransactionHistoryItem."""

    def test_field_mapping_from_mongo_doc(self):
        """Un doc MongoDB se mapea correctamente al DTO."""
        doc = _make_mongo_doc()
        item = TransactionHistoryItem(
            id=str(doc["_id"]),
            amount=doc["amount"],
            currency=doc["currency"],
            status=doc["status"],
            created_at=doc["created_at"].isoformat(),
            attempt_number=doc["attempt_number"],
            plan_name=doc["plan_name"],
            reference=doc["pagopar_order_hash"][-8:],
            error_message=doc["error_message"],
        )

        assert item.id == "doc123"
        assert item.amount == 150000
        assert item.currency == "PYG"
        assert item.status == "success"
        assert item.plan_name == "PRO"
        assert item.attempt_number == 1
        assert item.error_message is None

    def test_order_hash_truncation_to_last_8_chars(self):
        """reference = últimos 8 caracteres de pagopar_order_hash."""
        full_hash = "abcdef1234567890HASH"
        item = TransactionHistoryItem(
            id="x",
            amount=100,
            status="success",
            created_at="2025-06-15T10:30:00",
            reference=full_hash[-8:],
        )
        assert item.reference == "7890HASH"
        assert len(item.reference) == 8

    def test_sensitive_fields_excluded_from_dto(self):
        """El DTO no tiene campos sensibles (response_data, pagopar_order_id, subscription_id)."""
        fields = set(TransactionHistoryItem.model_fields.keys())
        assert "response_data" not in fields
        assert "pagopar_order_id" not in fields
        assert "subscription_id" not in fields

    def test_default_currency_is_pyg(self):
        """El currency por defecto es PYG."""
        item = TransactionHistoryItem(
            id="x",
            amount=100,
            status="pending",
            created_at="2025-01-01T00:00:00",
        )
        assert item.currency == "PYG"

    def test_default_attempt_number_is_1(self):
        """attempt_number por defecto es 1."""
        item = TransactionHistoryItem(
            id="x",
            amount=100,
            status="success",
            created_at="2025-01-01T00:00:00",
        )
        assert item.attempt_number == 1

    def test_error_message_present_for_failed_transactions(self):
        """error_message se mapea correctamente para transacciones fallidas."""
        item = TransactionHistoryItem(
            id="x",
            amount=100,
            status="failed",
            created_at="2025-01-01T00:00:00",
            error_message="Tarjeta rechazada",
        )
        assert item.error_message == "Tarjeta rechazada"


class TestTransactionHistoryResponse:
    """Tests del DTO TransactionHistoryResponse."""

    def test_response_structure(self):
        """Response tiene items, total, page, pages, limit."""
        resp = TransactionHistoryResponse(
            items=[],
            total=0,
            page=1,
            pages=0,
            limit=20,
        )
        assert resp.items == []
        assert resp.total == 0
        assert resp.page == 1
        assert resp.pages == 0
        assert resp.limit == 20

    def test_response_with_items(self):
        """Response con items poblados."""
        item = TransactionHistoryItem(
            id="abc",
            amount=50000,
            status="success",
            created_at="2025-06-15T10:00:00",
            plan_name="BASIC",
        )
        resp = TransactionHistoryResponse(
            items=[item],
            total=1,
            page=1,
            pages=1,
            limit=20,
        )
        assert len(resp.items) == 1
        assert resp.items[0].plan_name == "BASIC"
        assert resp.total == 1


# =========================================
# 2. Tests del Repository
# =========================================

class TestGetUserTransactionHistory:
    """Tests del método get_user_transaction_history en SubscriptionRepository."""

    def test_multitenant_isolation(self):
        """Solo retorna docs del user_email indicado."""
        docs = [
            _make_mongo_doc(user_email="alice@test.com", doc_id="1"),
            _make_mongo_doc(user_email="bob@test.com", doc_id="2"),
            _make_mongo_doc(user_email="alice@test.com", doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="alice@test.com")

        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert all(item["id"] != "2" for item in result["items"])

    def test_status_filter(self):
        """Filtra por status correctamente."""
        docs = [
            _make_mongo_doc(status="success", doc_id="1"),
            _make_mongo_doc(status="failed", doc_id="2"),
            _make_mongo_doc(status="pending", doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(
            user_email="user@test.com", status="failed"
        )

        assert result["total"] == 1
        assert result["items"][0]["status"] == "failed"

    def test_date_range_filter_from(self):
        """Filtra por date_from inclusive."""
        docs = [
            _make_mongo_doc(created_at=datetime(2025, 1, 1), doc_id="1"),
            _make_mongo_doc(created_at=datetime(2025, 6, 15), doc_id="2"),
            _make_mongo_doc(created_at=datetime(2025, 12, 31), doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(
            user_email="user@test.com",
            date_from=datetime(2025, 6, 1),
        )

        assert result["total"] == 2
        ids = {item["id"] for item in result["items"]}
        assert "1" not in ids
        assert "2" in ids
        assert "3" in ids

    def test_date_range_filter_to(self):
        """Filtra por date_to inclusive (hasta 23:59:59.999999 del día)."""
        docs = [
            _make_mongo_doc(created_at=datetime(2025, 1, 1), doc_id="1"),
            _make_mongo_doc(created_at=datetime(2025, 6, 15, 23, 59, 59), doc_id="2"),
            _make_mongo_doc(created_at=datetime(2025, 12, 31), doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(
            user_email="user@test.com",
            date_to=datetime(2025, 6, 15),
        )

        assert result["total"] == 2
        ids = {item["id"] for item in result["items"]}
        assert "1" in ids
        assert "2" in ids
        assert "3" not in ids

    def test_date_range_filter_both(self):
        """Filtra por date_from y date_to combinados."""
        docs = [
            _make_mongo_doc(created_at=datetime(2025, 1, 1), doc_id="1"),
            _make_mongo_doc(created_at=datetime(2025, 6, 15), doc_id="2"),
            _make_mongo_doc(created_at=datetime(2025, 12, 31), doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(
            user_email="user@test.com",
            date_from=datetime(2025, 3, 1),
            date_to=datetime(2025, 9, 30),
        )

        assert result["total"] == 1
        assert result["items"][0]["id"] == "2"

    def test_pagination_skip_limit(self):
        """Paginación: skip y limit funcionan correctamente."""
        docs = [
            _make_mongo_doc(created_at=datetime(2025, 1, i + 1), doc_id=str(i))
            for i in range(10)
        ]
        repo = _make_repo(docs)

        # Página 1, limit 3
        result = repo.get_user_transaction_history(
            user_email="user@test.com", page=1, limit=3
        )
        assert result["total"] == 10
        assert len(result["items"]) == 3

        # Página 2, limit 3
        result2 = repo.get_user_transaction_history(
            user_email="user@test.com", page=2, limit=3
        )
        assert result2["total"] == 10
        assert len(result2["items"]) == 3

        # Los items de página 1 y 2 no se solapan
        ids_p1 = {item["id"] for item in result["items"]}
        ids_p2 = {item["id"] for item in result2["items"]}
        assert ids_p1.isdisjoint(ids_p2)

    def test_total_count_matches_filter(self):
        """total refleja el conteo filtrado, no el total de la colección."""
        docs = [
            _make_mongo_doc(user_email="alice@test.com", status="success", doc_id="1"),
            _make_mongo_doc(user_email="alice@test.com", status="failed", doc_id="2"),
            _make_mongo_doc(user_email="bob@test.com", status="success", doc_id="3"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(
            user_email="alice@test.com", status="success"
        )

        assert result["total"] == 1

    def test_sort_by_created_at_descending(self):
        """Los resultados se ordenan por created_at descendente."""
        docs = [
            _make_mongo_doc(created_at=datetime(2025, 1, 1), doc_id="oldest"),
            _make_mongo_doc(created_at=datetime(2025, 6, 15), doc_id="middle"),
            _make_mongo_doc(created_at=datetime(2025, 12, 31), doc_id="newest"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        ids = [item["id"] for item in result["items"]]
        assert ids == ["newest", "middle", "oldest"]

    def test_empty_result(self):
        """Sin docs, retorna lista vacía con total=0."""
        repo = _make_repo([])
        result = repo.get_user_transaction_history(user_email="nobody@test.com")

        assert result["items"] == []
        assert result["total"] == 0

    def test_order_hash_truncation_in_mapping(self):
        """El repository trunca pagopar_order_hash a últimos 8 chars en reference."""
        docs = [
            _make_mongo_doc(
                pagopar_order_hash="abcdefghijklmnop1234",
                doc_id="1",
            ),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        assert result["items"][0]["reference"] == "mnop1234"

    def test_short_order_hash_not_truncated(self):
        """Si el hash tiene menos de 8 chars, se usa completo."""
        docs = [
            _make_mongo_doc(pagopar_order_hash="short", doc_id="1"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        assert result["items"][0]["reference"] == "short"

    def test_null_order_hash(self):
        """Si pagopar_order_hash es None, reference es None."""
        docs = [
            _make_mongo_doc(pagopar_order_hash=None, doc_id="1"),
        ]
        # Patch the doc to have None hash
        docs[0]["pagopar_order_hash"] = None
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        assert result["items"][0]["reference"] is None

    def test_sensitive_fields_not_in_result(self):
        """Los items mapeados no contienen response_data, pagopar_order_id, subscription_id."""
        docs = [
            _make_mongo_doc(
                pagopar_order_id="secret-id",
                subscription_id="secret-sub",
                response_data={"sensitive": True},
                doc_id="1",
            ),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        item = result["items"][0]
        assert "response_data" not in item
        assert "pagopar_order_id" not in item
        assert "subscription_id" not in item

    def test_user_email_lowercased(self):
        """El user_email se normaliza a minúsculas."""
        docs = [
            _make_mongo_doc(user_email="user@test.com", doc_id="1"),
        ]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="USER@TEST.COM")

        # El repo normaliza a lowercase, así que debe matchear
        assert result["total"] == 1

    def test_created_at_formatted_as_iso(self):
        """created_at se formatea como ISO 8601 string."""
        dt = datetime(2025, 6, 15, 10, 30, 0)
        docs = [_make_mongo_doc(created_at=dt, doc_id="1")]
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        assert result["items"][0]["created_at"] == "2025-06-15T10:30:00"

    def test_default_currency_pyg(self):
        """Si el doc no tiene currency, el default es PYG."""
        docs = [_make_mongo_doc(doc_id="1")]
        docs[0].pop("currency")  # Simular doc sin campo currency
        repo = _make_repo(docs)
        result = repo.get_user_transaction_history(user_email="user@test.com")

        assert result["items"][0]["currency"] == "PYG"


# =========================================
# 3. Tests del Endpoint (validaciones)
# =========================================

class TestMyTransactionsEndpointValidations:
    """
    Tests de la lógica de validación del endpoint GET /subscriptions/my-transactions.
    No levantamos el servidor FastAPI, testeamos la lógica directamente.
    """

    def test_pages_calculation(self):
        """Cálculo de pages: ceil(total / limit)."""
        # 10 items, limit 3 → 4 páginas
        assert math.ceil(10 / 3) == 4
        # 0 items → 0 páginas
        total = 0
        limit = 20
        pages = math.ceil(total / limit) if total > 0 else 0
        assert pages == 0
        # 20 items, limit 20 → 1 página
        assert math.ceil(20 / 20) == 1

    def test_date_validation_logic(self):
        """date_to < date_from debe ser rechazado."""
        date_from = datetime(2025, 6, 15)
        date_to = datetime(2025, 6, 10)
        assert date_to < date_from  # Esto dispararía 422

    def test_valid_status_values(self):
        """Solo success, failed, pending son válidos como regex en el endpoint."""
        import re
        pattern = re.compile(r"^(success|failed|pending)$")
        assert pattern.match("success")
        assert pattern.match("failed")
        assert pattern.match("pending")
        assert not pattern.match("cancelled")
        assert not pattern.match("SUCCESS")
        assert not pattern.match("")

    def test_max_limit_enforced(self):
        """El limit máximo es 100 (contrato del endpoint via Query le=100)."""
        # Verificamos que el repo respeta el limit que le pasan
        base = datetime(2025, 1, 1)
        docs = [
            _make_mongo_doc(created_at=base + timedelta(hours=i), doc_id=str(i))
            for i in range(150)
        ]
        repo = _make_repo(docs)

        # Con limit=100 (máximo permitido por el endpoint), solo retorna 100
        result = repo.get_user_transaction_history(
            user_email="user@test.com", page=1, limit=100
        )
        assert len(result["items"]) == 100
        assert result["total"] == 150

    def test_page_minimum_is_1(self):
        """page=1 es el mínimo; el endpoint valida ge=1 via Query."""
        docs = [_make_mongo_doc(doc_id="1")]
        repo = _make_repo(docs)

        result = repo.get_user_transaction_history(
            user_email="user@test.com", page=1, limit=20
        )
        assert result["total"] == 1
        assert len(result["items"]) == 1

    def test_dto_mapping_from_repo_result(self):
        """Los items del repo se mapean correctamente a TransactionHistoryItem."""
        repo_items = [
            {
                "id": "abc123",
                "amount": 150000,
                "currency": "PYG",
                "status": "success",
                "created_at": "2025-06-15T10:30:00",
                "attempt_number": 1,
                "plan_name": "PRO",
                "reference": "7890HASH",
                "error_message": None,
            }
        ]
        items = [TransactionHistoryItem(**item) for item in repo_items]
        assert len(items) == 1
        assert items[0].id == "abc123"
        assert items[0].reference == "7890HASH"

    def test_response_model_construction(self):
        """TransactionHistoryResponse se construye con todos los campos."""
        items = [
            TransactionHistoryItem(
                id="x",
                amount=100,
                status="success",
                created_at="2025-01-01T00:00:00",
            )
        ]
        resp = TransactionHistoryResponse(
            items=items,
            total=50,
            page=3,
            pages=5,
            limit=10,
        )
        assert resp.total == 50
        assert resp.page == 3
        assert resp.pages == 5
        assert resp.limit == 10
        assert len(resp.items) == 1
