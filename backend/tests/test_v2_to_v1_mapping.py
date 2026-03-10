"""
Test que verifica que la conversión v2→v1 (respuesta OpenAI Vision → InvoiceData)
produce exactamente el mismo esquema que el parser XML nativo.

Ambas fuentes (XML nativo y OpenAI Vision) deben terminar en la misma tabla
(invoice_headers + invoice_items) con campos idénticos.
"""
import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock módulos no instalados localmente antes de importar processor
for mod_name in ['tenacity', 'openai', 'redis']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from app.modules.openai_processor.processor import _convert_v2_to_v1_dict, _coerce_invoice_model
from app.models.models import InvoiceData
from app.modules.mapping.invoice_mapping import map_invoice


# ─── Simulaciones de respuestas OpenAI Vision (formato v2) ───

VISION_RESPONSE_FACTURA_CONTADO = {
    "header": {
        "cdc": "01800092430001001051499022025121015436792192",
        "tipo_documento": "CO",
        "establecimiento": "001",
        "punto": "001",
        "numero": "0514990",
        "numero_documento": "001-001-0514990",
        "fecha_emision": "2025-12-10",
        "condicion_venta": "CONTADO",
        "moneda": "GS",
        "tipo_cambio": 0,
        "timbrado": "17149524",
        "emisor": {
            "ruc": "80009243-0",
            "nombre": "FORTALEZA S.A. INMOBILIARIA Y SERVICIOS",
            "email": ""
        },
        "receptor": {
            "ruc": "5379057-0",
            "nombre": "COOPERATIVA UNIVERSITARIA LTDA",
            "email": ""
        },
        "totales": {
            "exentas": 0,
            "gravado_5": 0,
            "iva_5": 0,
            "gravado_10": 4500000,
            "iva_10": 450000,
            "total_iva": 450000,
            "total": 4500000
        }
    },
    "items": [
        {
            "linea": 1,
            "descripcion": "Alquiler oficina piso 3",
            "cantidad": 1,
            "unidad": "UNI",
            "precio_unitario": 4500000,
            "total": 4500000,
            "iva": 10
        }
    ]
}

VISION_RESPONSE_FACTURA_EXENTA = {
    "header": {
        "cdc": "01800261577001001827970022025112816351275101",
        "tipo_documento": "CO",
        "numero_documento": "001-001-8279700",
        "fecha_emision": "2025-11-28",
        "condicion_venta": "CONTADO",
        "moneda": "GS",
        "tipo_cambio": 0,
        "timbrado": "16839816",
        "emisor": {
            "ruc": "80026157-7",
            "nombre": "COOPERATIVA UNIVERSITARIA LTDA",
            "email": ""
        },
        "receptor": {
            "ruc": "80009243-0",
            "nombre": "FORTALEZA S.A.",
            "email": ""
        },
        "totales": {
            "exentas": 2500000,
            "gravado_5": 0,
            "iva_5": 0,
            "gravado_10": 0,
            "iva_10": 0,
            "total_iva": 0,
            "total": 2500000
        }
    },
    "items": [
        {
            "linea": 1,
            "descripcion": "Cuota social mensual",
            "cantidad": 1,
            "unidad": "UNI",
            "precio_unitario": 2500000,
            "total": 2500000,
            "iva": 0
        }
    ]
}

VISION_RESPONSE_FACTURA_USD = {
    "header": {
        "tipo_documento": "CO",
        "numero_documento": "INV-2025-001",
        "fecha_emision": "2025-10-15",
        "condicion_venta": "CONTADO",
        "moneda": "USD",
        "tipo_cambio": 7500,
        "timbrado": "",
        "cdc": "",
        "emisor": {
            "ruc": "",
            "nombre": "ACME Corp (USA)",
            "email": "billing@acme.com"
        },
        "receptor": {
            "ruc": "5379057-0",
            "nombre": "COOPERATIVA UNIVERSITARIA LTDA",
            "email": ""
        },
        "totales": {
            "exentas": 1500.00,
            "gravado_5": 0,
            "iva_5": 0,
            "gravado_10": 0,
            "iva_10": 0,
            "total_iva": 0,
            "total": 1500.00
        }
    },
    "items": [
        {
            "linea": 1,
            "descripcion": "Software License Annual",
            "cantidad": 1,
            "unidad": "UNI",
            "precio_unitario": 1500.00,
            "total": 1500.00,
            "iva": 0
        }
    ]
}

VISION_RESPONSE_CREDITO = {
    "header": {
        "cdc": "01800442270001002326948722025103116000865941",
        "tipo_documento": "CR",
        "numero_documento": "001-002-3269487",
        "fecha_emision": "2025-10-31",
        "condicion_venta": "CREDITO",
        "moneda": "GS",
        "tipo_cambio": 0,
        "timbrado": "16495321",
        "emisor": {
            "ruc": "80044227-0",
            "nombre": "TUPI S.A.",
            "email": ""
        },
        "receptor": {
            "ruc": "80009243-0",
            "nombre": "FORTALEZA S.A.",
            "email": ""
        },
        "totales": {
            "exentas": 0,
            "gravado_5": 1000000,
            "iva_5": 50000,
            "gravado_10": 3000000,
            "iva_10": 300000,
            "total_iva": 350000,
            "total": 4000000
        }
    },
    "items": [
        {
            "linea": 1,
            "descripcion": "Producto A",
            "cantidad": 2,
            "unidad": "UNI",
            "precio_unitario": 500000,
            "total": 1000000,
            "iva": 5
        },
        {
            "linea": 2,
            "descripcion": "Producto B",
            "cantidad": 3,
            "unidad": "UNI",
            "precio_unitario": 1000000,
            "total": 3000000,
            "iva": 10
        }
    ]
}


class TestV2ToV1Conversion:
    """Verifica que _convert_v2_to_v1_dict produce un dict compatible con InvoiceData.from_dict"""

    def test_contado_basic_fields(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        assert v1["fecha"] == "2025-12-10"
        assert v1["numero_factura"] == "001-001-0514990"
        assert v1["ruc_emisor"] == "80009243-0"
        assert v1["nombre_emisor"] == "FORTALEZA S.A. INMOBILIARIA Y SERVICIOS"
        assert v1["condicion_venta"] == "CONTADO"
        assert v1["tipo_documento"] == "CO"
        assert v1["moneda"] == "GS"

    def test_contado_totals(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        assert v1["subtotal_10"] == 4500000
        assert v1["gravado_10"] == 4500000
        assert v1["iva_10"] == 450000
        assert v1["subtotal_5"] == 0
        assert v1["iva_5"] == 0
        assert v1["subtotal_exentas"] == 0
        assert v1["monto_total"] == 4500000
        assert v1["total_iva"] == 450000

    def test_contado_productos(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        assert len(v1["productos"]) == 1
        p = v1["productos"][0]
        assert p["articulo"] == "Alquiler oficina piso 3"
        assert p["cantidad"] == 1
        assert p["precio_unitario"] == 4500000
        assert p["total"] == 4500000
        assert p["iva"] == 10

    def test_contado_receptor(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        assert v1["ruc_cliente"] == "5379057-0"
        assert v1["nombre_cliente"] == "COOPERATIVA UNIVERSITARIA LTDA"

    def test_contado_identifiers(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        assert v1["cdc"] == "01800092430001001051499022025121015436792192"
        assert v1["timbrado"] == "17149524"

    def test_exenta_totals(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_EXENTA)
        assert v1["subtotal_exentas"] == 2500000
        assert v1["exento"] == 2500000
        assert v1["monto_exento"] == 2500000
        assert v1["gravado_10"] == 0
        assert v1["iva_10"] == 0
        assert v1["monto_total"] == 2500000
        assert v1["total_iva"] == 0

    def test_credito_tipo_documento(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        assert v1["condicion_venta"] == "CREDITO"
        assert v1["tipo_documento"] == "CR"

    def test_credito_mixed_iva(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        assert v1["gravado_5"] == 1000000
        assert v1["iva_5"] == 50000
        assert v1["gravado_10"] == 3000000
        assert v1["iva_10"] == 300000
        assert v1["total_iva"] == 350000
        assert v1["monto_total"] == 4000000

    def test_credito_multiple_items(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        assert len(v1["productos"]) == 2
        assert v1["productos"][0]["iva"] == 5
        assert v1["productos"][1]["iva"] == 10

    def test_usd_foreign_invoice(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_USD)
        assert v1["moneda"] == "USD"
        assert v1["tipo_cambio"] == 7500
        assert v1["subtotal_exentas"] == 1500.00
        assert v1["gravado_10"] == 0
        assert v1["iva_10"] == 0
        assert v1["monto_total"] == 1500.00

    def test_descripcion_factura_generated(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        assert "Producto A" in v1["descripcion_factura"]
        assert "Producto B" in v1["descripcion_factura"]


class TestV2ToInvoiceData:
    """Verifica que el dict v1 se convierte exitosamente a InvoiceData"""

    def test_contado_creates_invoice_data(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        invoice = _coerce_invoice_model(v1, None)
        assert isinstance(invoice, InvoiceData)
        assert invoice.numero_factura == "001-001-0514990"
        assert invoice.ruc_emisor == "80009243-0"
        assert invoice.gravado_10 == 4500000
        assert invoice.iva_10 == 450000
        assert invoice.monto_total == 4500000

    def test_exenta_creates_invoice_data(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_EXENTA)
        invoice = _coerce_invoice_model(v1, None)
        assert isinstance(invoice, InvoiceData)
        assert invoice.exento == 2500000
        assert invoice.subtotal_exentas == 2500000
        assert invoice.gravado_10 == 0

    def test_credito_creates_invoice_data(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        invoice = _coerce_invoice_model(v1, None)
        assert isinstance(invoice, InvoiceData)
        assert invoice.condicion_venta == "CREDITO"
        assert invoice.tipo_documento == "CR"
        assert invoice.gravado_5 == 1000000
        assert invoice.gravado_10 == 3000000

    def test_usd_creates_invoice_data(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_USD)
        invoice = _coerce_invoice_model(v1, None)
        assert isinstance(invoice, InvoiceData)
        assert invoice.moneda == "USD"
        assert invoice.tipo_cambio == 7500

    def test_productos_mapped_correctly(self):
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        invoice = _coerce_invoice_model(v1, None)
        assert isinstance(invoice, InvoiceData)
        assert len(invoice.productos) == 2
        assert invoice.productos[0].nombre == "Producto A"
        assert invoice.productos[0].iva == 5
        assert invoice.productos[1].nombre == "Producto B"
        assert invoice.productos[1].iva == 10


class TestUnifiedMapping:
    """
    Verifica que tanto XML nativo como OpenAI Vision terminan en el MISMO esquema
    InvoiceDocument (header + items) → misma tabla MongoDB.
    """

    def test_vision_maps_to_invoice_document(self):
        """OpenAI Vision response → InvoiceData → InvoiceDocument"""
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        invoice_data = _coerce_invoice_model(v1, None)
        doc = map_invoice(invoice_data, fuente="OPENAI_VISION", minio_key="test/vision.pdf")

        h = doc.header
        assert h.id == "01800092430001001051499022025121015436792192"  # CDC as ID
        assert h.cdc == "01800092430001001051499022025121015436792192"
        assert h.numero_documento == "001-001-0514990"
        assert h.emisor.ruc == "80009243-0"
        assert h.emisor.nombre == "FORTALEZA S.A. INMOBILIARIA Y SERVICIOS"
        assert h.receptor.ruc == "5379057-0"
        assert h.totales.gravado_10 == 4500000
        assert h.totales.iva_10 == 450000
        assert h.totales.total == 4500000
        assert h.fuente == "OPENAI_VISION"
        assert h.minio_key == "test/vision.pdf"

        assert len(doc.items) == 1
        assert doc.items[0].descripcion == "Alquiler oficina piso 3"
        assert doc.items[0].iva == 10

    def test_xml_native_maps_to_same_schema(self):
        """XML nativo → InvoiceData → InvoiceDocument (mismo esquema que Vision)"""
        # Simular salida del parser XML nativo (formato plano)
        xml_native_output = {
            "fecha": "2025-12-10",
            "numero_factura": "001-001-0514990",
            "ruc_emisor": "80009243-0",
            "nombre_emisor": "FORTALEZA S.A. INMOBILIARIA Y SERVICIOS",
            "condicion_venta": "CONTADO",
            "moneda": "GS",
            "subtotal_exentas": 0,
            "subtotal_5": 0,
            "iva_5": 0,
            "subtotal_10": 4500000,
            "iva_10": 450000,
            "monto_total": 4500000,
            "timbrado": "17149524",
            "cdc": "01800092430001001051499022025121015436792192",
            "ruc_cliente": "5379057-0",
            "nombre_cliente": "COOPERATIVA UNIVERSITARIA LTDA",
            "productos": [
                {"articulo": "Alquiler oficina piso 3", "cantidad": 1, "precio_unitario": 4500000, "total": 4500000, "iva": 10}
            ]
        }

        invoice_data = _coerce_invoice_model(xml_native_output, None)
        doc = map_invoice(invoice_data, fuente="XML_NATIVO", minio_key="test/native.xml")

        h = doc.header
        assert h.id == "01800092430001001051499022025121015436792192"
        assert h.cdc == "01800092430001001051499022025121015436792192"
        assert h.numero_documento == "001-001-0514990"
        assert h.emisor.ruc == "80009243-0"
        assert h.totales.gravado_10 == 4500000
        assert h.totales.iva_10 == 450000
        assert h.totales.total == 4500000
        assert h.fuente == "XML_NATIVO"

        assert len(doc.items) == 1
        assert doc.items[0].iva == 10

    def test_both_sources_produce_identical_structure(self):
        """Verifica que XML y Vision producen el MISMO set de campos en InvoiceDocument"""
        # Vision path
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_CONTADO)
        vision_data = _coerce_invoice_model(v1, None)
        vision_doc = map_invoice(vision_data, fuente="OPENAI_VISION")

        # XML path
        xml_output = {
            "fecha": "2025-12-10",
            "numero_factura": "001-001-0514990",
            "ruc_emisor": "80009243-0",
            "nombre_emisor": "FORTALEZA S.A. INMOBILIARIA Y SERVICIOS",
            "condicion_venta": "CONTADO",
            "moneda": "GS",
            "subtotal_exentas": 0, "subtotal_5": 0, "iva_5": 0,
            "subtotal_10": 4500000, "iva_10": 450000,
            "monto_total": 4500000,
            "timbrado": "17149524",
            "cdc": "01800092430001001051499022025121015436792192",
            "ruc_cliente": "5379057-0",
            "nombre_cliente": "COOPERATIVA UNIVERSITARIA LTDA",
            "productos": [{"articulo": "Alquiler oficina piso 3", "cantidad": 1, "precio_unitario": 4500000, "total": 4500000, "iva": 10}]
        }
        xml_data = _coerce_invoice_model(xml_output, None)
        xml_doc = map_invoice(xml_data, fuente="XML_NATIVO")

        # Ambos deben tener el mismo ID (CDC)
        assert vision_doc.header.id == xml_doc.header.id

        # Mismos campos en header (excepto fuente)
        vh = vision_doc.header
        xh = xml_doc.header
        assert vh.cdc == xh.cdc
        assert vh.numero_documento == xh.numero_documento
        assert vh.condicion_venta == xh.condicion_venta
        assert vh.moneda == xh.moneda
        assert vh.emisor.ruc == xh.emisor.ruc
        assert vh.emisor.nombre == xh.emisor.nombre
        assert vh.receptor.ruc == xh.receptor.ruc
        assert vh.totales.gravado_10 == xh.totales.gravado_10
        assert vh.totales.iva_10 == xh.totales.iva_10
        assert vh.totales.total == xh.totales.total
        assert vh.totales.exentas == xh.totales.exentas

        # Solo difiere en fuente
        assert vh.fuente == "OPENAI_VISION"
        assert xh.fuente == "XML_NATIVO"

        # Mismos items
        assert len(vision_doc.items) == len(xml_doc.items)
        assert vision_doc.items[0].descripcion == xml_doc.items[0].descripcion
        assert vision_doc.items[0].iva == xml_doc.items[0].iva

    def test_exenta_vision_maps_correctly(self):
        """Factura 100% exenta desde Vision → misma tabla"""
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_EXENTA)
        invoice = _coerce_invoice_model(v1, None)
        doc = map_invoice(invoice, fuente="OPENAI_VISION")

        assert doc.header.totales.exentas == 2500000
        assert doc.header.totales.gravado_10 == 0
        assert doc.header.totales.iva_10 == 0
        assert doc.header.totales.total == 2500000

    def test_credito_vision_maps_correctly(self):
        """Factura crédito con IVA mixto desde Vision"""
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_CREDITO)
        invoice = _coerce_invoice_model(v1, None)
        doc = map_invoice(invoice, fuente="OPENAI_VISION")

        assert doc.header.condicion_venta == "CREDITO"
        assert doc.header.tipo_documento == "CR"
        assert doc.header.totales.gravado_5 == 1000000
        assert doc.header.totales.iva_5 == 50000
        assert doc.header.totales.gravado_10 == 3000000
        assert doc.header.totales.iva_10 == 300000
        assert len(doc.items) == 2

    def test_usd_vision_maps_correctly(self):
        """Factura extranjera en USD desde Vision"""
        v1 = _convert_v2_to_v1_dict(VISION_RESPONSE_FACTURA_USD)
        invoice = _coerce_invoice_model(v1, None)
        doc = map_invoice(invoice, fuente="OPENAI_VISION")

        assert doc.header.moneda == "USD"
        assert doc.header.tipo_cambio == 7500
        assert doc.header.totales.exentas == 1500.00
        assert doc.header.totales.gravado_10 == 0
        assert doc.header.totales.total == 1500.00


class TestEdgeCases:
    """Casos borde de la conversión v2→v1"""

    def test_missing_header(self):
        """Si el header está vacío, no debe crashear"""
        v1 = _convert_v2_to_v1_dict({"header": None, "items": []})
        assert v1["fecha"] == ""
        assert v1["monto_total"] == 0
        assert v1["productos"] == []

    def test_missing_totales(self):
        """Si totales está vacío, todos los montos deben ser 0"""
        v1 = _convert_v2_to_v1_dict({
            "header": {"fecha_emision": "2025-01-01", "totales": None, "emisor": None, "receptor": None},
            "items": []
        })
        assert v1["gravado_10"] == 0
        assert v1["iva_10"] == 0
        assert v1["subtotal_exentas"] == 0
        assert v1["monto_total"] == 0

    def test_missing_emisor_receptor(self):
        """Si emisor/receptor están vacíos"""
        v1 = _convert_v2_to_v1_dict({
            "header": {"emisor": None, "receptor": None, "totales": {}},
            "items": []
        })
        assert v1["ruc_emisor"] == ""
        assert v1["nombre_emisor"] == ""
        assert v1["ruc_cliente"] == ""
        assert v1["nombre_cliente"] == ""

    def test_item_with_missing_fields(self):
        """Items con campos faltantes no deben crashear"""
        v1 = _convert_v2_to_v1_dict({
            "header": {"totales": {}, "emisor": {}, "receptor": {}},
            "items": [{"descripcion": "Test"}]  # Solo descripcion, sin otros campos
        })
        assert len(v1["productos"]) == 1
        assert v1["productos"][0]["articulo"] == "Test"
        assert v1["productos"][0]["cantidad"] == 0
        assert v1["productos"][0]["precio_unitario"] == 0

    def test_total_iva_calculated_when_missing(self):
        """total_iva debe calcularse como iva_5+iva_10 si no viene explícito"""
        v1 = _convert_v2_to_v1_dict({
            "header": {
                "totales": {"iva_5": 50000, "iva_10": 300000},
                "emisor": {}, "receptor": {}
            },
            "items": []
        })
        assert v1["total_iva"] == 350000

    def test_total_operacion_fallback_to_total(self):
        """total_operacion debe usar total si no viene explícito"""
        v1 = _convert_v2_to_v1_dict({
            "header": {
                "totales": {"total": 5000000},
                "emisor": {}, "receptor": {}
            },
            "items": []
        })
        assert v1["total_operacion"] == 5000000

    def test_v1_dict_can_always_create_invoice_data(self):
        """Cualquier salida de _convert_v2_to_v1_dict debe ser compatible con InvoiceData"""
        test_cases = [
            VISION_RESPONSE_FACTURA_CONTADO,
            VISION_RESPONSE_FACTURA_EXENTA,
            VISION_RESPONSE_FACTURA_USD,
            VISION_RESPONSE_CREDITO,
            {"header": None, "items": []},
            {"header": {"totales": {}, "emisor": {}, "receptor": {}}, "items": []},
        ]
        for v2 in test_cases:
            v1 = _convert_v2_to_v1_dict(v2)
            result = _coerce_invoice_model(v1, None)
            # Debe ser InvoiceData o al menos un dict (nunca None para datos válidos)
            assert result is not None, f"Failed for: {v2}"


class TestPromptSchemaAlignment:
    """Verifica que el prompt v2 pide los mismos campos que el converter espera"""

    def test_v2_schema_has_total_iva(self):
        from app.modules.openai_processor.prompts import v2_header_detail_schema
        schema = v2_header_detail_schema()
        totales = schema["header"]["totales"]
        assert "total_iva" in totales, "El schema v2 debe incluir total_iva"

    def test_v2_schema_has_all_required_total_fields(self):
        from app.modules.openai_processor.prompts import v2_header_detail_schema
        schema = v2_header_detail_schema()
        totales = schema["header"]["totales"]
        required = ["exentas", "gravado_5", "iva_5", "gravado_10", "iva_10", "total", "total_iva"]
        for field in required:
            assert field in totales, f"Campo '{field}' faltante en schema v2 totales"

    def test_v2_schema_items_have_iva_type(self):
        from app.modules.openai_processor.prompts import v2_header_detail_schema
        schema = v2_header_detail_schema()
        item = schema["items"][0]
        assert "iva" in item, "Items deben tener campo 'iva'"
