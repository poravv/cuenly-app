from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
import sys
import types

# El entorno de pruebas local puede no tener pymongo instalado.
# Stub mínimo para poder importar el repositorio y testear su lógica pura.
if "pymongo" not in sys.modules:
    pymongo_stub = types.ModuleType("pymongo")
    pymongo_stub.MongoClient = object  # type: ignore[attr-defined]
    pymongo_stub.UpdateOne = object  # type: ignore[attr-defined]
    sys.modules["pymongo"] = pymongo_stub

if "pymongo.collection" not in sys.modules:
    pymongo_collection_stub = types.ModuleType("pymongo.collection")
    pymongo_collection_stub.Collection = object  # type: ignore[attr-defined]
    sys.modules["pymongo.collection"] = pymongo_collection_stub

from app.models.export_template import (
    AVAILABLE_FIELDS,
    ExportField,
    FieldType,
    get_available_field_categories,
    get_invalid_template_field_keys,
)
from app.models.models import InvoiceData
from app.modules.mapping.sifen_field_matrix import SIFEN_FIELD_MATRIX
from app.repositories.mongo_invoice_repository import MongoInvoiceRepository


def test_available_fields_and_categories_are_consistent():
    categories = get_available_field_categories()
    available_keys = set(AVAILABLE_FIELDS.keys())

    assert categories, "Debe existir al menos una categoría de campos"

    category_keys: List[str] = []
    for category, keys in categories.items():
        assert keys, f"La categoría '{category}' no debe estar vacía"
        for key in keys:
            assert key in available_keys, f"Campo '{key}' en categoría '{category}' no existe en AVAILABLE_FIELDS"
            category_keys.append(key)

    duplicates = sorted({key for key in category_keys if category_keys.count(key) > 1})
    assert not duplicates, f"Hay campos duplicados entre categorías: {duplicates}"

    invoice_fields = set(InvoiceData.model_fields.keys())
    invalid_non_product_fields = sorted(
        key
        for key in available_keys
        if key != "productos" and not key.startswith("productos.") and key not in invoice_fields
    )
    assert not invalid_non_product_fields, (
        f"Campos exportables sin soporte en InvoiceData: {invalid_non_product_fields}"
    )

    missing_from_available = sorted(
        {
            row.export_field_key
            for row in SIFEN_FIELD_MATRIX
            if row.export_field_key and row.export_field_key not in available_keys
        }
    )
    assert not missing_from_available, (
        f"Campos exportables definidos en matriz y ausentes en AVAILABLE_FIELDS: {missing_from_available}"
    )


def test_invalid_template_field_keys_validation():
    fields = [
        ExportField(
            field_key="fecha",
            display_name="Fecha",
            field_type=FieldType.DATE,
            order=1,
        ),
        ExportField(
            field_key="campo.inexistente",
            display_name="Inexistente",
            field_type=FieldType.TEXT,
            order=2,
        ),
    ]

    invalid = get_invalid_template_field_keys(fields)
    assert invalid == ["campo.inexistente"]


class _FakeCursor(list):
    def sort(self, field: str, order: int):  # type: ignore[override]
        reverse = order == -1
        return _FakeCursor(sorted(self, key=lambda item: item.get(field), reverse=reverse))


class _FakeHeadersCollection:
    def __init__(self, headers: List[Dict[str, Any]]):
        self.headers = headers
        self.last_query: Dict[str, Any] | None = None

    def find(self, query: Dict[str, Any]):
        self.last_query = query
        return _FakeCursor(self.headers)


class _FakeItemsCollection:
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items

    def find(self, query: Dict[str, Any]):
        header_id = query.get("header_id")
        return [item for item in self.items if item.get("header_id") == header_id]


def test_repository_export_payload_includes_extended_sifen_fields():
    header_id = "owner@tenant.test:sample-cdc-001"
    headers = [
        {
            "_id": header_id,
            "fecha_emision": datetime(2020, 5, 7, 8, 30, 0),
            "numero_documento": "001-001-1000050",
            "cdc": "01000000019001001100005022020050710000000231",
            "timbrado": "12562496",
            "owner_email": "owner@tenant.test",
            "tipo_documento": "CR",
            "tipo_documento_electronico": "Factura electrónica",
            "tipo_de_codigo": "1",
            "ind_presencia": "Operación presencial",
            "ind_presencia_codigo": "1",
            "condicion_venta": "CREDITO",
            "cond_credito": "Plazo",
            "cond_credito_codigo": "1",
            "plazo_credito_dias": 30,
            "ciclo_facturacion": "DICIEMBRE",
            "ciclo_fecha_inicio": "2020-12-01",
            "ciclo_fecha_fin": "2020-12-31",
            "transporte_modalidad": "Terrestre",
            "transporte_modalidad_codigo": "1",
            "transporte_resp_flete_codigo": "1",
            "transporte_nro_despacho": "1234567891asfdcs",
            "qr_url": "https://ekuatia.set.gov.py/consultas-test/qr?nVersion=150",
            "info_adicional": "observación de prueba",
            "fuente": "XML_NATIVO",
            "email_origen": "proveedor@test.py",
            "mes_proceso": "2020-05",
            "created_at": datetime(2020, 5, 7, 10, 0, 0),
            "emisor": {
                "ruc": "00000001-9",
                "nombre": "EMPRESA DE PRUEBA",
                "direccion": "Dirección emisor",
                "telefono": "0981000000",
                "email": "emisor@test.py",
                "actividad_economica": "Servicios",
            },
            "receptor": {
                "ruc": "00000002-7",
                "nombre": "CLIENTE DE PRUEBA",
                "direccion": "Dirección receptor",
                "telefono": "0982000000",
                "email": "cliente@test.py",
            },
            "moneda": "GS",
            "tipo_cambio": 1.0,
            "totales": {
                "exentas": 0.0,
                "monto_exento": 0.0,
                "gravado_5": 0.0,
                "iva_5": 0.0,
                "gravado_10": 2_000_000.0,
                "iva_10": 200_000.0,
                "total_iva": 200_000.0,
                "total_operacion": 2_200_000.0,
                "total_descuento": 0.0,
                "anticipo": 0.0,
                "total_base_gravada": 2_000_000.0,
                "total": 2_200_000.0,
                "exonerado": 0.0,
                "isc_total": 0.0,
                "isc_base_imponible": 0.0,
                "isc_subtotal_gravado": 0.0,
            },
        }
    ]
    items = [
        {
            "header_id": header_id,
            "descripcion": "CUENTAS ACTIVAS",
            "cantidad": 1,
            "unidad": "UNI",
            "precio_unitario": 1_000_000.0,
            "total": 1_000_000.0,
            "iva": 10,
            "codigo": "P-001",
        }
    ]

    fake_headers = _FakeHeadersCollection(headers)
    fake_items = _FakeItemsCollection(items)

    repo = MongoInvoiceRepository(connection_string="mongodb://unused", database_name="unused")
    repo._headers = lambda: fake_headers  # type: ignore[method-assign]
    repo._items = lambda: fake_items  # type: ignore[method-assign]

    invoices = repo.get_invoices_by_user(
        owner_email="owner@tenant.test",
        filters={"monto_minimo": 1000, "monto_maximo": 5_000_000},
    )

    assert fake_headers.last_query is not None
    assert fake_headers.last_query["owner_email"] == "owner@tenant.test"
    assert fake_headers.last_query["totales.total"]["$gte"] == 1000.0
    assert fake_headers.last_query["totales.total"]["$lte"] == 5_000_000.0

    assert len(invoices) == 1
    invoice = invoices[0]

    assert invoice["tipo_documento_electronico"] == "Factura electrónica"
    assert invoice["ind_presencia"] == "Operación presencial"
    assert invoice["cond_credito"] == "Plazo"
    assert invoice["plazo_credito_dias"] == 30
    assert invoice["ciclo_facturacion"] == "DICIEMBRE"
    assert invoice["transporte_modalidad"] == "Terrestre"
    assert invoice["transporte_nro_despacho"] == "1234567891asfdcs"
    assert str(invoice["qr_url"]).startswith("https://ekuatia.set.gov.py/consultas-test/qr")

    assert invoice["monto_exento"] == 0.0
    assert invoice["total_base_gravada"] == 2_000_000.0
    assert invoice["total_operacion"] == 2_200_000.0
    assert invoice["total_iva"] == 200_000.0
    assert invoice["isc_total"] == 0.0
    assert invoice["isc_base_imponible"] == 0.0
    assert invoice["isc_subtotal_gravado"] == 0.0
