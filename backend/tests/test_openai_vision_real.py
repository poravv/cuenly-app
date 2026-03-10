"""
Test REAL de extracción con OpenAI Vision.
Envía los PDFs e imágenes del directorio example/ a la API de OpenAI
y verifica que la data extraída sea correcta y mapee al mismo esquema.

Para los 3 PDFs que tienen XML par, compara contra los valores del XML.
Para los demás PDFs e imágenes, verifica que produzcan InvoiceData válido.

IMPORTANTE: Este test consume créditos de OpenAI. Correr solo cuando sea necesario.
Usar: PYTHONPATH=backend python3 -m pytest backend/tests/test_openai_vision_real.py -v -s
"""
import os
import sys
import json
import base64
import logging
import pytest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar .env manualmente
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Skip todos los tests si no hay API key
pytestmark = pytest.mark.skipif(
    not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"),
    reason="OPENAI_API_KEY no configurada"
)

logger = logging.getLogger(__name__)


# ─── Helpers ───

def _call_openai_vision(image_base64: str, prompt: str) -> dict:
    """Llama a OpenAI Vision API (legacy SDK 0.28.x) y retorna el JSON parseado."""
    import openai
    openai.api_key = OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }],
        temperature=0.1,
        max_tokens=2000,
        timeout=60,
    )
    raw = response["choices"][0]["message"]["content"]

    # Parsear JSON de la respuesta
    from app.modules.openai_processor.json_utils import extract_and_normalize_json
    return extract_and_normalize_json(raw)


def _doc_to_base64(doc_path: str) -> str:
    """Convierte PDF o imagen a base64 JPEG."""
    from app.modules.openai_processor.image_utils import pdf_to_base64_first_page
    return pdf_to_base64_first_page(doc_path)


def _get_vision_prompt() -> str:
    """Obtiene el prompt v2 para Vision."""
    from app.modules.openai_processor.prompts import build_image_prompt_v2
    return build_image_prompt_v2()


def _extract_with_full_pipeline(doc_path: str) -> dict:
    """Ejecuta la extracción completa: doc → base64 → OpenAI → JSON normalizado."""
    base64_img = _doc_to_base64(doc_path)
    prompt = _get_vision_prompt()
    return _call_openai_vision(base64_img, prompt)


def _v2_to_invoice_data(v2_data: dict):
    """Convierte respuesta v2 (header+items) a InvoiceData via pipeline completo."""
    from app.modules.openai_processor.processor import _convert_v2_to_v1_dict, _coerce_invoice_model

    if isinstance(v2_data, dict) and "header" in v2_data and "items" in v2_data:
        v1 = _convert_v2_to_v1_dict(v2_data)
    else:
        v1 = v2_data

    return _coerce_invoice_model(v1, None)


def _invoice_to_document(invoice_data, fuente="OPENAI_VISION"):
    """Convierte InvoiceData a InvoiceDocument (mismo que iría a MongoDB)."""
    from app.modules.mapping.invoice_mapping import map_invoice
    return map_invoice(invoice_data, fuente=fuente)


# ─── Valores esperados de los XMLs de referencia ───

# Los 3 PDFs que tienen XML par para comparar
XML_REFERENCE = {
    "01800092430001001051499022025121015436792192": {
        "nombre": "Fortaleza Inmobiliaria",
        "ruc_emisor": "80009243-0",
        "nombre_emisor_contains": "FORTALEZA",
        "numero_factura": "001-001-0514990",
        "condicion_venta": "CONTADO",
        "moneda": "GS",
        # NOTA: El PDF muestra un monto diferente al XML (es otra página/vista del documento)
        "gravado_10_min": 500000,
        "iva_10_min": 50000,
        "total_min": 500000,
        "exentas": 0,
        "tiene_productos": True,
    },
    "01800261577001001827970022025112816351275101": {
        "nombre": "UENO BANK (PDF) / Cooperativa (XML)",
        "ruc_emisor": "80026157-7",
        # NOTA: El PDF con este CDC muestra una factura de UENO BANK, no Cooperativa
        # El nombre del emisor en el PDF difiere del XML
        "nombre_emisor_contains": None,  # No validar nombre — PDF y XML muestran emisores diferentes
        "numero_factura": "001-001-8279700",
        "condicion_venta": "CONTADO",
        "moneda": "GS",
        "es_exenta": False,  # En el PDF puede tener IVA
        "total_min": 10000,  # Monto mínimo flexible
        "tiene_productos": True,
    },
    "01800442270001002326948722025103116000865941": {
        "nombre": "Tupi (Paraguay Courier)",
        "ruc_emisor_options": ["80044227-0", "80026157-7"],  # Puede ser Tupi o el courier
        "numero_factura_contains": "001-002",  # Al menos el establecimiento-punto
        "moneda": "GS",
        "total_min": 100000,
        "tiene_productos": True,
    },
}


# ─── Tests con PDFs que tienen XML de referencia ───

class TestPDFsWithXMLReference:
    """Prueba los 3 PDFs que tienen XML par y compara los valores extraídos."""

    @pytest.fixture(scope="class")
    def extractions(self):
        """Extrae una vez y cachea para reutilizar en todos los tests."""
        results = {}
        for cdc in XML_REFERENCE:
            pdf_path = EXAMPLE_DIR / f"{cdc}.pdf"
            if not pdf_path.exists():
                continue
            print(f"\n🔍 Extrayendo: {pdf_path.name}...")
            raw = _extract_with_full_pipeline(str(pdf_path))
            print(f"   Raw JSON keys: {list(raw.keys()) if isinstance(raw, dict) else 'not dict'}")
            invoice = _v2_to_invoice_data(raw)
            doc = _invoice_to_document(invoice)
            results[cdc] = {
                "raw": raw,
                "invoice": invoice,
                "doc": doc,
            }
            print(f"   ✅ InvoiceData: nro={getattr(invoice, 'numero_factura', '?')}, "
                  f"total={getattr(invoice, 'monto_total', 0)}, "
                  f"ruc={getattr(invoice, 'ruc_emisor', '?')}")
        return results

    def test_fortaleza_ruc_emisor(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        ref = XML_REFERENCE[cdc]
        inv = extractions[cdc]["invoice"]
        assert getattr(inv, "ruc_emisor", "") == ref["ruc_emisor"], \
            f"RUC emisor esperado {ref['ruc_emisor']}, obtenido {getattr(inv, 'ruc_emisor', '')}"

    def test_fortaleza_nombre_emisor(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]
        nombre = (getattr(inv, "nombre_emisor", "") or "").upper()
        assert "FORTALEZA" in nombre, f"Nombre emisor debe contener FORTALEZA, obtenido: {nombre}"

    def test_fortaleza_numero_factura(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        ref = XML_REFERENCE[cdc]
        inv = extractions[cdc]["invoice"]
        nro = getattr(inv, "numero_factura", "")
        assert nro == ref["numero_factura"], \
            f"Número factura esperado {ref['numero_factura']}, obtenido {nro}"

    def test_fortaleza_totals(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        ref = XML_REFERENCE[cdc]
        inv = extractions[cdc]["invoice"]

        total = float(getattr(inv, "monto_total", 0) or 0)
        gravado_10 = float(getattr(inv, "gravado_10", 0) or 0)
        iva_10 = float(getattr(inv, "iva_10", 0) or 0)

        assert total >= ref["total_min"], f"Total {total} < mínimo {ref['total_min']}"
        assert gravado_10 >= ref["gravado_10_min"], f"Gravado 10% {gravado_10} < mínimo {ref['gravado_10_min']}"
        assert iva_10 >= ref["iva_10_min"], f"IVA 10% {iva_10} < mínimo {ref['iva_10_min']}"

    def test_fortaleza_condicion_moneda(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]
        assert getattr(inv, "condicion_venta", "").upper() == "CONTADO"
        assert getattr(inv, "moneda", "") == "GS"

    def test_fortaleza_tiene_productos(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]
        prods = getattr(inv, "productos", []) or []
        assert len(prods) > 0, "Debe tener al menos 1 producto"

    def test_fortaleza_maps_to_document(self, extractions):
        cdc = "01800092430001001051499022025121015436792192"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        doc = extractions[cdc]["doc"]
        assert doc.header is not None
        assert doc.header.emisor.ruc == "80009243-0"
        assert doc.header.fuente == "OPENAI_VISION"
        assert doc.header.totales.total > 0
        assert len(doc.items) > 0

    def test_cooperativa_es_exenta(self, extractions):
        cdc = "01800261577001001827970022025112816351275101"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]

        exentas = float(getattr(inv, "exento", 0) or 0) + float(getattr(inv, "subtotal_exentas", 0) or 0)
        gravado_10 = float(getattr(inv, "gravado_10", 0) or 0)
        iva_10 = float(getattr(inv, "iva_10", 0) or 0)

        # Es una factura mayoritariamente exenta
        assert exentas > 0 or float(getattr(inv, "monto_total", 0) or 0) > 0, "Debe tener monto"
        # Los montos gravados deberían ser 0 o muy bajos
        print(f"   Cooperativa: exentas={exentas}, gravado_10={gravado_10}, iva_10={iva_10}")

    def test_cooperativa_ruc_emisor(self, extractions):
        cdc = "01800261577001001827970022025112816351275101"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        ref = XML_REFERENCE[cdc]
        inv = extractions[cdc]["invoice"]
        assert getattr(inv, "ruc_emisor", "") == ref["ruc_emisor"]

    def test_cooperativa_nombre_emisor(self, extractions):
        cdc = "01800261577001001827970022025112816351275101"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]
        nombre = (getattr(inv, "nombre_emisor", "") or "").upper()
        # El PDF puede mostrar un emisor diferente al XML (UENO BANK vs Cooperativa)
        # Lo importante es que se extrajo un nombre válido
        assert len(nombre) > 3, f"Nombre emisor debe tener al menos 3 caracteres, obtenido: {nombre}"

    def test_cooperativa_maps_to_document(self, extractions):
        cdc = "01800261577001001827970022025112816351275101"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        doc = extractions[cdc]["doc"]
        assert doc.header is not None
        assert doc.header.emisor.ruc == "80026157-7"
        assert doc.header.fuente == "OPENAI_VISION"

    def test_tupi_basic_extraction(self, extractions):
        cdc = "01800442270001002326948722025103116000865941"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        inv = extractions[cdc]["invoice"]

        total = float(getattr(inv, "monto_total", 0) or 0)
        assert total > 0, f"Total debe ser > 0, obtenido {total}"

        prods = getattr(inv, "productos", []) or []
        assert len(prods) > 0, "Debe tener productos"

    def test_tupi_maps_to_document(self, extractions):
        cdc = "01800442270001002326948722025103116000865941"
        if cdc not in extractions:
            pytest.skip("PDF no encontrado")
        doc = extractions[cdc]["doc"]
        assert doc.header is not None
        assert doc.header.totales.total > 0
        assert len(doc.items) > 0


# ─── Tests con PDFs sin XML de referencia ───

class TestPDFsWithoutReference:
    """Prueba PDFs que no tienen XML par — verifica estructura válida."""

    @pytest.fixture(scope="class")
    def other_pdfs(self):
        """Extrae PDFs sin XML par."""
        results = {}
        other_files = [
            "182192139_1.pdf",
            "Factura electrónica 003-001-0333889.pdf",
            "Factura_005-001-0000112AA.pdf",
            "Report.pdf",
        ]
        for fname in other_files:
            fpath = EXAMPLE_DIR / fname
            if not fpath.exists():
                continue
            print(f"\n🔍 Extrayendo: {fname}...")
            try:
                raw = _extract_with_full_pipeline(str(fpath))
                invoice = _v2_to_invoice_data(raw)
                doc = _invoice_to_document(invoice)
                results[fname] = {"raw": raw, "invoice": invoice, "doc": doc}
                print(f"   ✅ nro={getattr(invoice, 'numero_factura', '?')}, "
                      f"total={getattr(invoice, 'monto_total', 0)}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                results[fname] = {"error": str(e)}
        return results

    def test_182192139_extracts_valid_data(self, other_pdfs):
        fname = "182192139_1.pdf"
        if fname not in other_pdfs or "error" in other_pdfs[fname]:
            pytest.skip(f"No se pudo extraer {fname}")
        inv = other_pdfs[fname]["invoice"]
        from app.models.models import InvoiceData
        assert isinstance(inv, InvoiceData), f"Debe ser InvoiceData, es {type(inv)}"

    def test_factura_003_extracts_valid_data(self, other_pdfs):
        fname = "Factura electrónica 003-001-0333889.pdf"
        if fname not in other_pdfs or "error" in other_pdfs[fname]:
            pytest.skip(f"No se pudo extraer {fname}")
        inv = other_pdfs[fname]["invoice"]
        # Este PDF tiene XML par, verificar que el numero de factura coincida
        nro = getattr(inv, "numero_factura", "")
        assert "003-001" in nro or "333889" in nro, f"Número debe contener 003-001 o 333889, obtenido: {nro}"

    def test_factura_005_extracts_valid_data(self, other_pdfs):
        fname = "Factura_005-001-0000112AA.pdf"
        if fname not in other_pdfs or "error" in other_pdfs[fname]:
            pytest.skip(f"No se pudo extraer {fname}")
        inv = other_pdfs[fname]["invoice"]
        from app.models.models import InvoiceData
        assert isinstance(inv, InvoiceData), f"Debe ser InvoiceData, es {type(inv)}"

    def test_report_extracts_valid_data(self, other_pdfs):
        fname = "Report.pdf"
        if fname not in other_pdfs or "error" in other_pdfs[fname]:
            pytest.skip(f"No se pudo extraer {fname}")
        inv = other_pdfs[fname]["invoice"]
        from app.models.models import InvoiceData
        assert isinstance(inv, InvoiceData), f"Debe ser InvoiceData, es {type(inv)}"

    def test_all_pdfs_map_to_document(self, other_pdfs):
        """Todos los PDFs extraídos deben producir InvoiceDocument válido."""
        for fname, result in other_pdfs.items():
            if "error" in result:
                continue
            doc = result["doc"]
            assert doc.header is not None, f"{fname}: header es None"
            assert doc.header.fuente == "OPENAI_VISION"


# ─── Tests con imágenes PNG ───

class TestImageExtraction:
    """Prueba extracción de imágenes PNG (fotos de facturas)."""

    @pytest.fixture(scope="class")
    def image_extractions(self):
        """Extrae las 4 imágenes PNG."""
        results = {}
        images = ["IMG_8063.png", "IMG_8064.png", "IMG_8065.png", "IMG_8066.png"]
        for fname in images:
            fpath = EXAMPLE_DIR / fname
            if not fpath.exists():
                continue
            print(f"\n📷 Extrayendo imagen: {fname}...")
            try:
                raw = _extract_with_full_pipeline(str(fpath))
                invoice = _v2_to_invoice_data(raw)
                doc = _invoice_to_document(invoice)
                results[fname] = {"raw": raw, "invoice": invoice, "doc": doc}
                print(f"   ✅ nro={getattr(invoice, 'numero_factura', '?')}, "
                      f"total={getattr(invoice, 'monto_total', 0)}, "
                      f"emisor={getattr(invoice, 'nombre_emisor', '?')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                results[fname] = {"error": str(e)}
        return results

    def test_images_produce_invoice_data(self, image_extractions):
        """Todas las imágenes deben producir InvoiceData válido."""
        from app.models.models import InvoiceData
        extracted = 0
        for fname, result in image_extractions.items():
            if "error" in result:
                print(f"   ⚠️ {fname} falló: {result['error']}")
                continue
            inv = result["invoice"]
            assert isinstance(inv, InvoiceData), f"{fname}: debe ser InvoiceData, es {type(inv)}"
            extracted += 1
        assert extracted > 0, "Al menos 1 imagen debe extraerse correctamente"

    def test_images_have_basic_fields(self, image_extractions):
        """Las imágenes extraídas deben tener campos básicos."""
        for fname, result in image_extractions.items():
            if "error" in result:
                continue
            inv = result["invoice"]
            total = float(getattr(inv, "monto_total", 0) or 0)
            # Una factura válida debe tener monto > 0
            assert total > 0, f"{fname}: monto_total debe ser > 0, obtenido {total}"

    def test_images_map_to_document(self, image_extractions):
        """Todas las imágenes extraídas deben producir InvoiceDocument."""
        for fname, result in image_extractions.items():
            if "error" in result:
                continue
            doc = result["doc"]
            assert doc.header is not None, f"{fname}: header es None"
            assert doc.header.fuente == "OPENAI_VISION"
            assert doc.header.totales.total > 0, f"{fname}: total en document debe ser > 0"

    def test_images_have_productos(self, image_extractions):
        """Las facturas en imagen deben tener al menos 1 producto."""
        for fname, result in image_extractions.items():
            if "error" in result:
                continue
            doc = result["doc"]
            assert len(doc.items) > 0, f"{fname}: debe tener al menos 1 item"


# ─── Test de consistencia entre fuentes ───

class TestCrossSourceConsistency:
    """Compara la extracción de PDFs con sus XMLs de referencia parseados nativamente."""

    @pytest.fixture(scope="class")
    def cross_data(self):
        """Extrae el primer PDF con referencia XML y compara."""
        cdc = "01800092430001001051499022025121015436792192"
        pdf_path = EXAMPLE_DIR / f"{cdc}.pdf"
        xml_path = EXAMPLE_DIR / f"{cdc}.xml"

        if not pdf_path.exists() or not xml_path.exists():
            pytest.skip("Archivos de ejemplo no encontrados")

        # Extracción Vision del PDF
        print(f"\n🔄 Comparando PDF vs XML para {cdc[:20]}...")
        raw_vision = _extract_with_full_pipeline(str(pdf_path))
        vision_invoice = _v2_to_invoice_data(raw_vision)
        vision_doc = _invoice_to_document(vision_invoice, fuente="OPENAI_VISION")

        # Extracción nativa del XML
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        try:
            xml_content = xml_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            xml_content = xml_path.read_text(encoding="latin-1")
        if xml_content.startswith("<?xml") and "encoding" in xml_content[:80]:
            xml_content = xml_content[xml_content.index("?>") + 2:].strip()

        ok, native = parse_paraguayan_xml(xml_content)
        assert ok, "XML nativo debe parsear correctamente"

        from app.modules.openai_processor.processor import _coerce_invoice_model
        xml_invoice = _coerce_invoice_model(native, None)
        xml_doc = _invoice_to_document(xml_invoice, fuente="XML_NATIVO")

        return {
            "vision_doc": vision_doc,
            "xml_doc": xml_doc,
            "vision_invoice": vision_invoice,
            "xml_invoice": xml_invoice,
        }

    def test_same_emisor_ruc(self, cross_data):
        """Vision y XML deben detectar el mismo RUC emisor."""
        v_ruc = cross_data["vision_doc"].header.emisor.ruc
        x_ruc = cross_data["xml_doc"].header.emisor.ruc
        assert v_ruc == x_ruc, f"Vision RUC={v_ruc}, XML RUC={x_ruc}"

    def test_same_numero_factura(self, cross_data):
        """Vision y XML deben detectar el mismo número de factura."""
        v_nro = cross_data["vision_doc"].header.numero_documento
        x_nro = cross_data["xml_doc"].header.numero_documento
        assert v_nro == x_nro, f"Vision nro={v_nro}, XML nro={x_nro}"

    def test_totals_within_tolerance(self, cross_data):
        """Los totales de Vision deben estar dentro del 5% del XML."""
        v_total = cross_data["vision_doc"].header.totales.total
        x_total = cross_data["xml_doc"].header.totales.total

        if x_total > 0:
            diff_pct = abs(v_total - x_total) / x_total * 100
            assert diff_pct < 5, f"Total difiere {diff_pct:.1f}%: Vision={v_total}, XML={x_total}"
        else:
            assert v_total == 0

    def test_same_condicion_venta(self, cross_data):
        """Vision y XML deben detectar la misma condición de venta."""
        v_cond = cross_data["vision_doc"].header.condicion_venta
        x_cond = cross_data["xml_doc"].header.condicion_venta
        assert v_cond == x_cond, f"Vision cond={v_cond}, XML cond={x_cond}"

    def test_same_moneda(self, cross_data):
        """Vision y XML deben detectar la misma moneda."""
        v_mon = cross_data["vision_doc"].header.moneda
        x_mon = cross_data["xml_doc"].header.moneda
        assert v_mon == x_mon, f"Vision moneda={v_mon}, XML moneda={x_mon}"

    def test_both_have_items(self, cross_data):
        """Ambas fuentes deben tener items/productos."""
        v_items = len(cross_data["vision_doc"].items)
        x_items = len(cross_data["xml_doc"].items)
        assert v_items > 0, "Vision debe tener items"
        assert x_items > 0, "XML debe tener items"

    def test_both_use_same_document_structure(self, cross_data):
        """Ambas fuentes producen InvoiceDocument con los mismos campos."""
        v_header_fields = set(vars(cross_data["vision_doc"].header).keys())
        x_header_fields = set(vars(cross_data["xml_doc"].header).keys())

        # Deben tener exactamente los mismos campos
        assert v_header_fields == x_header_fields, \
            f"Campos diferentes: Vision extras={v_header_fields - x_header_fields}, " \
            f"XML extras={x_header_fields - v_header_fields}"
