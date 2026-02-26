from __future__ import annotations

from pathlib import Path
from datetime import datetime
import unicodedata

from app.models.export_template import AVAILABLE_FIELDS
from app.models.invoice_v2 import InvoiceHeader, Totales, Party
from app.models.models import InvoiceData
from app.modules.mapping.invoice_mapping import map_invoice
from app.modules.mapping.sifen_field_matrix import SIFEN_FIELD_MATRIX
from app.modules.openai_processor.xml_parser import parse_paraguayan_xml


def _repo_root() -> Path:
    # backend/tests -> backend -> repo
    return Path(__file__).resolve().parents[2]


def _load_enterprise_sample_xml() -> str:
    xml_path = _repo_root() / "docs" / "cuenly-enterprise" / "Extructura xml_DE.xml"
    return xml_path.read_text(encoding="utf-8")


def _norm_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().upper()


def test_enterprise_xml_end_to_end_mapping_pipeline():
    xml_content = _load_enterprise_sample_xml()
    success, normalized = parse_paraguayan_xml(xml_content)

    assert success is True
    assert normalized["fecha"] == "2020-05-07"
    assert normalized["numero_factura"] == "001-001-1000050"
    assert normalized["ruc_emisor"] == "00000001-9"
    assert normalized["ruc_cliente"] == "00000002-7"
    assert normalized["tipo_documento_electronico"] == "Factura electrónica"
    assert normalized["ind_presencia"] == "Operación presencial"
    assert normalized["cond_credito"] == "Plazo"
    assert normalized["ciclo_facturacion"] == "DICIEMBRE"
    assert normalized["transporte_modalidad_codigo"] == "1"
    assert normalized["monto_total"] == 2200000.0
    assert normalized["total_base_gravada"] == 2000000.0
    assert normalized["monto_exento"] == 0.0
    assert str(normalized["qr_url"]).startswith("https://ekuatia.set.gov.py/consultas-test/qr")
    assert len(normalized.get("productos", [])) == 2

    invoice = InvoiceData.from_dict(normalized, email_metadata={"sender": "qa@cuenly.test"})
    doc = map_invoice(invoice, fuente="XML_NATIVO", minio_key="tests/enterprise.xml")
    header = doc.header

    assert header.numero_documento == "001-001-1000050"
    assert header.cdc == "01000000019001001100005022020050710000000231"
    assert header.emisor is not None and header.emisor.ruc == "00000001-9"
    assert header.receptor is not None and header.receptor.ruc == "00000002-7"
    assert header.tipo_documento_electronico == "Factura electrónica"
    assert "CREDITO" in _norm_text(header.condicion_venta or "")
    assert header.ind_presencia == "Operación presencial"
    assert header.cond_credito == "Plazo"
    assert header.ciclo_facturacion == "DICIEMBRE"
    assert header.transporte_modalidad == "Terrestre"
    assert header.transporte_nro_despacho == "1234567891asfdcs"
    assert str(header.qr_url).startswith("https://ekuatia.set.gov.py/consultas-test/qr")

    assert header.totales.gravado_5 == 0.0
    assert header.totales.gravado_10 == 2000000.0
    assert header.totales.iva_5 == 0.0
    assert header.totales.iva_10 == 200000.0
    assert header.totales.total_iva == 200000.0
    assert header.totales.total_operacion == 2200000.0
    assert header.totales.total_descuento == 0.0
    assert header.totales.total_base_gravada == 2000000.0
    assert header.totales.monto_exento == 0.0
    assert header.totales.total == 2200000.0

    assert len(doc.items) == 2
    assert doc.items[0].descripcion == "CUENTAS ACTIVAS"
    assert doc.items[1].descripcion == "TARJETA URGENTE"
    assert doc.items[0].iva == 10
    assert doc.items[1].iva == 10


def test_map_invoice_uses_invoice_minio_key_when_param_missing():
    invoice = InvoiceData(
        fecha=datetime(2026, 2, 1),
        numero_factura="001-001-0000001",
        ruc_emisor="80012345-6",
        nombre_emisor="Proveedor SA",
        minio_key="2026/owner@test.py/02/010101_demo.pdf",
    )

    doc = map_invoice(invoice, fuente="EMAIL_BATCH_PROCESSOR")
    assert doc.header.minio_key == "2026/owner@test.py/02/010101_demo.pdf"


def test_map_invoice_prefers_explicit_minio_key():
    invoice = InvoiceData(
        fecha=datetime(2026, 2, 1),
        numero_factura="001-001-0000002",
        ruc_emisor="80012345-6",
        nombre_emisor="Proveedor SA",
        minio_key="2026/owner@test.py/02/010101_old.pdf",
    )

    doc = map_invoice(
        invoice,
        fuente="EMAIL_BATCH_PROCESSOR",
        minio_key="2026/owner@test.py/02/010101_new.pdf",
    )
    assert doc.header.minio_key == "2026/owner@test.py/02/010101_new.pdf"


def test_sifen_matrix_alignment_with_models_and_export_fields():
    invoice_fields = set(InvoiceData.model_fields.keys())
    header_fields = set(InvoiceHeader.model_fields.keys())
    totales_fields = set(Totales.model_fields.keys())
    party_fields = set(Party.model_fields.keys())

    for row in SIFEN_FIELD_MATRIX:
        assert row.invoice_data_field in invoice_fields, f"InvoiceData missing field: {row.invoice_data_field}"

        root, *rest = row.v2_field_path.split(".")
        if root == "totales":
            assert rest and rest[0] in totales_fields, f"Totales missing field: {row.v2_field_path}"
        elif root in ("emisor", "receptor"):
            assert rest and rest[0] in party_fields, f"Party missing field: {row.v2_field_path}"
        else:
            assert root in header_fields, f"InvoiceHeader missing field: {row.v2_field_path}"

        if row.export_field_key:
            assert row.export_field_key in AVAILABLE_FIELDS, (
                f"Export template missing field '{row.export_field_key}' for XML tag {row.xml_tag}"
            )


def test_enterprise_sample_covers_required_matrix_fields():
    success, normalized = parse_paraguayan_xml(_load_enterprise_sample_xml())
    assert success is True

    missing_keys = []
    empty_values = []
    for row in SIFEN_FIELD_MATRIX:
        if not row.required_in_enterprise_sample:
            continue
        if row.normalized_key not in normalized:
            missing_keys.append(row.normalized_key)
            continue
        value = normalized.get(row.normalized_key)
        if value is None:
            empty_values.append(row.normalized_key)
        elif isinstance(value, str) and not value.strip():
            empty_values.append(row.normalized_key)

    assert not missing_keys, f"Campos requeridos ausentes en muestra enterprise: {missing_keys}"
    assert not empty_values, f"Campos requeridos vacíos en muestra enterprise: {empty_values}"
