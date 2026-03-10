"""
Tests de extracción XML SIFEN con archivos reales del directorio example/.
Verifica el pipeline completo: XML → parser nativo → InvoiceData → InvoiceDocument (v2).
"""
import os
import sys
import pytest
from pathlib import Path

# Los archivos de ejemplo con sus valores esperados
EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"


def _read_xml_safe(filepath: Path) -> str:
    """Lee un archivo XML manejando encodings mixtos (UTF-8 / Latin-1)."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = filepath.read_text(encoding="latin-1")
    # Remover declaración XML si tiene encoding incompatible con ET
    if content.startswith("<?xml") and "encoding" in content[:80]:
        content = content[content.index("?>") + 2:].strip()
    return content

# Definición de los XMLs de prueba con los valores esperados extraídos manualmente
XML_TEST_CASES = {
    "01800092430001001051499022025121015436792192.xml": {
        "cdc": "01800092430001001051499022025121015436792192",
        "fecha": "2025-12-10",
        "numero_factura": "001-001-0514990",
        "ruc_emisor": "80009243-0",
        "nombre_emisor": "FORTALEZA INMUEBLES SAE",
        "ruc_cliente": "5379057-0",
        "nombre_cliente": "ANDRES VALENTIN VERA CHAVEZ",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "15290986",
        "monto_total": 807500.0,
        "gravado_10": 734090.90909091,
        "iva_10": 73409.0909,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 0.0,
        "total_iva": 73409.0909,
        "productos_count": 2,
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "1",
        "tipo_de_codigo": "1",
    },
    "documento electronico.xml": {
        "cdc": "01800009584001004121856922025102810841369856",
        "fecha": "2025-10-28",
        "numero_factura": "001-004-1218569",
        "ruc_emisor": "80000958-4",
        "nombre_emisor": "Cooperativa Universitaria de Ahorro, Crédito y Servicios Ltda.",
        "ruc_cliente": "5379057-0",
        "nombre_cliente": "VERA CHAVEZ, ANDRES VALENTIN",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "16056490",
        "monto_total": 50992.0,
        "gravado_10": 0.0,
        "iva_10": 0.0,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 50992.0,
        "total_iva": 0.0,
        "productos_count": 2,
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "1",
        "tipo_de_codigo": "1",
    },
    "Factura electrónica 003-001-0333889.xml": {
        "cdc": "01800319702003001033388922024101018446212444",
        "fecha": "2024-10-10",
        "numero_factura": "003-001-0333889",
        "ruc_emisor": "80031970-2",
        "nombre_emisor": "TUPI RAMOS GENERALES S.A.",
        "ruc_cliente": "5379057-0",
        "nombre_cliente": "VERA CHAVEZ, ANDRES VALENTIN",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "16012519",
        "monto_total": 369000.0,
        "gravado_10": 335455.0,
        "iva_10": 33545.0,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 0.0,
        "total_iva": 33545.0,
        "productos_count": 1,
        "producto_desc_contains": "FREIDORA AIR FRYER",
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "2",
        "tipo_de_codigo": "1",
    },
    "Factura_005-001-0000112AA.xml": {
        "cdc": "01800847806005001000011222025063010105996221",
        "fecha": "2025-06-30",
        "numero_factura": "005-001-0000112",
        "ruc_emisor": "80084780-6",
        "nombre_emisor": "PARAGUAY COURIER SRL",
        "nombre_cliente": "CONSUMIDOR FINAL",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "17953815",
        "monto_total": 167740.65,
        "gravado_10": 40912.353659,
        "iva_10": 4091.235366,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 122737.060976,
        "total_iva": 4091.235366,
        "productos_count": 1,
        "producto_desc_contains": "Air Service",
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "1",
        "tipo_de_codigo": "1",
    },
    "01800261577001001827970022025112816351275101.xml": {
        "cdc": "01800261577001001827970022025112816351275101",
        "fecha": "2025-11-28",
        "numero_factura": "001-001-8279700",
        "ruc_emisor": "80026157-7",
        "nombre_emisor": "UENO BANK",
        "nombre_cliente": "ANDRES VALENTIN VERA CHAVEZ",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "16045146",
        "monto_total": 32714.0,
        "gravado_10": 29740.0,
        "iva_10": 2974.0,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 0.0,
        "total_iva": 2974.0,
        "productos_count_min": 1,
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "5",
        "tipo_de_codigo": "1",
    },
    "01800442270001002326948722025103116000865941.xml": {
        "cdc": "01800442270001002326948722025103116000865941",
        "fecha": "2025-10-31",
        "numero_factura": "001-002-3269487",
        "ruc_emisor": "80044227-0",
        "nombre_emisor": "Banco GNB",
        "ruc_cliente": "5379057-0",
        "nombre_cliente": "ANDRES VALENTIN VERA CHAVEZ",
        "email_cliente": "andyvercha@gmail.com",
        "condicion_venta": "Contado",
        "moneda": "PYG",
        "timbrado": "14976221",
        "monto_total": 55000.0,
        "gravado_10": 50000.0,
        "iva_10": 5000.0,
        "iva_5": 0.0,
        "gravado_5": 0.0,
        "exento": 0.0,
        "total_iva": 5000.0,
        "productos_count_min": 1,
        "qr_url_contains": "ekuatia.set.gov.py",
        "ind_presencia_codigo": "5",
        "tipo_de_codigo": "1",
        "encoding": "latin-1",
    },
}


class TestXMLParserWithRealFiles:
    """Tests del parser XML nativo con archivos reales SIFEN."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Verificar que el directorio de ejemplos existe."""
        if not EXAMPLE_DIR.exists():
            pytest.skip(f"Directorio de ejemplos no encontrado: {EXAMPLE_DIR}")

    def _read_xml(self, filename: str) -> str:
        filepath = EXAMPLE_DIR / filename
        if not filepath.exists():
            pytest.skip(f"Archivo no encontrado: {filepath}")
        # Manejar encoding del test case o probar utf-8 → latin-1
        expected = XML_TEST_CASES.get(filename, {})
        enc = expected.get("encoding", "utf-8")
        try:
            content = filepath.read_text(encoding=enc)
        except UnicodeDecodeError:
            content = filepath.read_text(encoding="latin-1")
        # Remover declaración XML si tiene encoding incompatible con ET
        if content.startswith("<?xml") and "encoding" in content[:80]:
            content = content[content.index("?>") + 2:].strip()
        return content

    @pytest.mark.parametrize("filename,expected", list(XML_TEST_CASES.items()))
    def test_parse_xml_native(self, filename, expected):
        """Verifica que el parser nativo extraiga correctamente los campos SIFEN."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        xml_content = self._read_xml(filename)
        success, data = parse_paraguayan_xml(xml_content)

        assert success, f"Parser nativo falló para {filename}"
        assert data, f"Parser devolvió datos vacíos para {filename}"

        # CDC (44 dígitos)
        assert data.get("cdc") == expected["cdc"], \
            f"CDC incorrecto: {data.get('cdc')} != {expected['cdc']}"

        # Datos básicos
        assert data.get("fecha") == expected["fecha"], \
            f"Fecha incorrecta: {data.get('fecha')} != {expected['fecha']}"
        assert data.get("numero_factura") == expected["numero_factura"], \
            f"Número factura incorrecto: {data.get('numero_factura')} != {expected['numero_factura']}"
        assert data.get("timbrado") == expected["timbrado"], \
            f"Timbrado incorrecto: {data.get('timbrado')} != {expected['timbrado']}"

        # Emisor
        assert data.get("ruc_emisor") == expected["ruc_emisor"], \
            f"RUC emisor incorrecto: {data.get('ruc_emisor')} != {expected['ruc_emisor']}"
        assert expected["nombre_emisor"] in (data.get("nombre_emisor") or ""), \
            f"Nombre emisor incorrecto: {data.get('nombre_emisor')}"

        # Cliente
        if "ruc_cliente" in expected:
            assert data.get("ruc_cliente") == expected["ruc_cliente"], \
                f"RUC cliente incorrecto: {data.get('ruc_cliente')} != {expected['ruc_cliente']}"
        assert expected["nombre_cliente"] in (data.get("nombre_cliente") or ""), \
            f"Nombre cliente incorrecto: {data.get('nombre_cliente')}"
        if "email_cliente" in expected:
            assert data.get("email_cliente") == expected["email_cliente"]

        # Operación
        assert "contado" in (data.get("condicion_venta") or "").lower(), \
            f"Condición venta incorrecta: {data.get('condicion_venta')}"
        assert data.get("moneda") == expected["moneda"]

    @pytest.mark.parametrize("filename,expected", list(XML_TEST_CASES.items()))
    def test_totales_correctos(self, filename, expected):
        """Verifica que los totales y desglose IVA sean correctos."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        xml_content = self._read_xml(filename)
        success, data = parse_paraguayan_xml(xml_content)
        assert success

        # Monto total
        assert abs(data.get("monto_total", 0) - expected["monto_total"]) < 0.1, \
            f"[{filename}] monto_total: {data.get('monto_total')} != {expected['monto_total']}"

        # Gravado 10%
        assert abs(data.get("gravado_10", 0) - expected["gravado_10"]) < 1.0, \
            f"[{filename}] gravado_10: {data.get('gravado_10')} != {expected['gravado_10']}"

        # IVA 10%
        assert abs(data.get("iva_10", 0) - expected["iva_10"]) < 1.0, \
            f"[{filename}] iva_10: {data.get('iva_10')} != {expected['iva_10']}"

        # Gravado 5%
        assert abs(data.get("gravado_5", 0) - expected["gravado_5"]) < 1.0, \
            f"[{filename}] gravado_5: {data.get('gravado_5')} != {expected['gravado_5']}"

        # IVA 5%
        assert abs(data.get("iva_5", 0) - expected["iva_5"]) < 1.0, \
            f"[{filename}] iva_5: {data.get('iva_5')} != {expected['iva_5']}"

        # Exento
        assert abs(data.get("exento", 0) - expected["exento"]) < 1.0, \
            f"[{filename}] exento: {data.get('exento')} != {expected['exento']}"

        # Total IVA
        assert abs(data.get("total_iva", 0) - expected["total_iva"]) < 1.0, \
            f"[{filename}] total_iva: {data.get('total_iva')} != {expected['total_iva']}"

    @pytest.mark.parametrize("filename,expected", list(XML_TEST_CASES.items()))
    def test_productos_extraidos(self, filename, expected):
        """Verifica que los productos/ítems se extraigan correctamente."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        xml_content = self._read_xml(filename)
        success, data = parse_paraguayan_xml(xml_content)
        assert success

        productos = data.get("productos", [])
        if "productos_count" in expected:
            assert len(productos) == expected["productos_count"], \
                f"[{filename}] Productos: {len(productos)} != {expected['productos_count']}"
        elif "productos_count_min" in expected:
            assert len(productos) >= expected["productos_count_min"], \
                f"[{filename}] Productos: {len(productos)} < {expected['productos_count_min']}"

        # Verificar estructura de cada producto
        for i, prod in enumerate(productos):
            assert "articulo" in prod or "descripcion" in prod or "nombre" in prod, \
                f"[{filename}] Producto {i} sin descripción"
            assert "cantidad" in prod, f"[{filename}] Producto {i} sin cantidad"
            assert "iva" in prod, f"[{filename}] Producto {i} sin iva"

        # Verificar descripción de producto si se especifica
        if "producto_desc_contains" in expected:
            all_descs = " ".join(
                str(p.get("articulo", "") or p.get("descripcion", ""))
                for p in productos
            )
            assert expected["producto_desc_contains"] in all_descs, \
                f"[{filename}] Descripción '{expected['producto_desc_contains']}' no encontrada en: {all_descs}"

    @pytest.mark.parametrize("filename,expected", list(XML_TEST_CASES.items()))
    def test_campos_sifen_v150(self, filename, expected):
        """Verifica campos SIFEN v150: QR URL, indicador de presencia, tipo de documento."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        xml_content = self._read_xml(filename)
        success, data = parse_paraguayan_xml(xml_content)
        assert success

        # QR URL
        qr = data.get("qr_url", "")
        assert expected["qr_url_contains"] in qr, \
            f"[{filename}] QR URL no contiene '{expected['qr_url_contains']}': {qr[:80]}"

        # Indicador de presencia
        assert data.get("ind_presencia_codigo") == expected["ind_presencia_codigo"], \
            f"[{filename}] ind_presencia_codigo: {data.get('ind_presencia_codigo')} != {expected['ind_presencia_codigo']}"

        # Tipo de documento electrónico
        assert data.get("tipo_de_codigo") == expected["tipo_de_codigo"], \
            f"[{filename}] tipo_de_codigo: {data.get('tipo_de_codigo')} != {expected['tipo_de_codigo']}"


class TestXMLToInvoiceDataMapping:
    """Tests del mapeo XML normalizado → InvoiceData model."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not EXAMPLE_DIR.exists():
            pytest.skip(f"Directorio de ejemplos no encontrado: {EXAMPLE_DIR}")

    def _parse_xml(self, filename: str):
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        expected = XML_TEST_CASES.get(filename, {})
        enc = expected.get("encoding", "utf-8")
        try:
            content = (EXAMPLE_DIR / filename).read_text(encoding=enc)
        except UnicodeDecodeError:
            content = (EXAMPLE_DIR / filename).read_text(encoding="latin-1")
        if content.startswith("<?xml") and "encoding" in content[:80]:
            content = content[content.index("?>") + 2:].strip()
        return parse_paraguayan_xml(content)

    @pytest.mark.parametrize("filename", list(XML_TEST_CASES.keys()))
    def test_invoice_data_creation(self, filename):
        """Verifica que los datos del parser se conviertan correctamente a InvoiceData."""
        from app.models.models import InvoiceData

        success, data = self._parse_xml(filename)
        assert success

        invoice = InvoiceData.from_dict(data, None)

        # Campos obligatorios presentes
        assert invoice.fecha is not None, f"[{filename}] fecha es None"
        assert invoice.numero_factura, f"[{filename}] numero_factura vacío"
        assert invoice.ruc_emisor, f"[{filename}] ruc_emisor vacío"
        assert invoice.nombre_emisor, f"[{filename}] nombre_emisor vacío"
        assert invoice.monto_total > 0, f"[{filename}] monto_total = {invoice.monto_total}"

        # Coherencia IVA: gravado_10 + iva_10 ~ subtotal_10 en XML (dSub10)
        # El total debe cuadrar: exento + gravado_5 + iva_5 + gravado_10 + iva_10 ≈ monto_total
        expected = XML_TEST_CASES[filename]
        assert abs(invoice.monto_total - expected["monto_total"]) < 1.0, \
            f"[{filename}] InvoiceData.monto_total: {invoice.monto_total} != {expected['monto_total']}"

    @pytest.mark.parametrize("filename", list(XML_TEST_CASES.keys()))
    def test_invoice_to_v2_mapping(self, filename):
        """Verifica el mapeo completo: XML → InvoiceData → InvoiceDocument (v2)."""
        from app.models.models import InvoiceData
        from app.modules.mapping.invoice_mapping import map_invoice

        success, data = self._parse_xml(filename)
        assert success

        invoice = InvoiceData.from_dict(data, None)
        doc = map_invoice(invoice, fuente="XML_NATIVO")

        expected = XML_TEST_CASES[filename]

        # Header
        assert doc.header is not None
        assert doc.header.cdc == expected["cdc"], \
            f"[{filename}] v2.header.cdc: {doc.header.cdc} != {expected['cdc']}"
        assert doc.header.fecha_emision is not None
        assert doc.header.timbrado == expected["timbrado"]

        # Emisor
        assert doc.header.emisor.ruc == expected["ruc_emisor"]
        assert expected["nombre_emisor"] in (doc.header.emisor.nombre or "")

        # Receptor
        if "ruc_cliente" in expected:
            assert doc.header.receptor.ruc == expected["ruc_cliente"]

        # Totales
        assert abs(doc.header.totales.total - expected["monto_total"]) < 1.0, \
            f"[{filename}] v2.totales.total: {doc.header.totales.total} != {expected['monto_total']}"
        assert abs(doc.header.totales.gravado_10 - expected["gravado_10"]) < 1.0, \
            f"[{filename}] v2.totales.gravado_10: {doc.header.totales.gravado_10} != {expected['gravado_10']}"
        assert abs(doc.header.totales.iva_10 - expected["iva_10"]) < 1.0, \
            f"[{filename}] v2.totales.iva_10: {doc.header.totales.iva_10} != {expected['iva_10']}"
        assert abs(doc.header.totales.exentas - expected["exento"]) < 1.0, \
            f"[{filename}] v2.totales.exentas: {doc.header.totales.exentas} != {expected['exento']}"

        # Items
        if "productos_count" in expected:
            assert len(doc.items) == expected["productos_count"], \
                f"[{filename}] v2.items count: {len(doc.items)} != {expected['productos_count']}"
        elif "productos_count_min" in expected:
            assert len(doc.items) >= expected["productos_count_min"], \
                f"[{filename}] v2.items count: {len(doc.items)} < {expected['productos_count_min']}"

        for item in doc.items:
            assert item.descripcion, f"[{filename}] Item sin descripción"
            assert item.header_id == doc.header.id

        # Campos v150
        assert doc.header.qr_url, f"[{filename}] v2 sin qr_url"
        assert doc.header.tipo_de_codigo == expected["tipo_de_codigo"]
        assert doc.header.ind_presencia_codigo == expected["ind_presencia_codigo"]

        # Fuente
        assert doc.header.fuente == "XML_NATIVO"


class TestXMLParserEdgeCases:
    """Tests de casos borde del parser XML."""

    def test_xml_invalido(self):
        """XML no válido debe retornar False."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        success, data = parse_paraguayan_xml("<html><body>No es SIFEN</body></html>")
        assert not success

    def test_xml_vacio(self):
        """XML vacío debe retornar False."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        success, data = parse_paraguayan_xml("")
        assert not success

    def test_xml_sin_campos_minimos(self):
        """XML SIFEN sin campos mínimos (fecha, numero, ruc) debe retornar False."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        xml = '''<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd">
            <dVerFor>150</dVerFor>
            <DE Id="12345678901234567890123456789012345678901234">
                <gTimb><dNumTim>123</dNumTim></gTimb>
            </DE>
        </rDE>'''
        success, data = parse_paraguayan_xml(xml)
        assert not success

    def test_parser_numeros_formato_europeo(self):
        """El parser debe manejar números con formato europeo (1.234,56)."""
        from app.modules.openai_processor.xml_parser import ParaguayanXMLParser
        parser = ParaguayanXMLParser()
        assert parser._to_float("1.234,56") == 1234.56
        assert parser._to_float("7400.00") == 7400.0
        assert parser._to_float("7400,00") == 7400.0
        assert parser._to_float("1,234.56") == 1234.56
        assert parser._to_float(None) == 0.0
        assert parser._to_float("") == 0.0

    def test_coherencia_totales_iva(self):
        """Verifica que gravado + IVA sea coherente con el total."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        if not EXAMPLE_DIR.exists():
            pytest.skip("Directorio de ejemplos no encontrado")

        for filename in XML_TEST_CASES:
            filepath = EXAMPLE_DIR / filename
            if not filepath.exists():
                continue

            xml_content = _read_xml_safe(filepath)
            success, data = parse_paraguayan_xml(xml_content)
            if not success:
                continue

            # El total debe ser ≈ exento + gravado_5 + iva_5 + gravado_10 + iva_10
            # En SIFEN: dTotGralOpe ≈ dSubExe + dSub5 + dSub10
            # donde dSub5 = gravado_5 + iva_5, dSub10 = gravado_10 + iva_10
            exento = data.get("exento", 0)
            g5 = data.get("gravado_5", 0)
            i5 = data.get("iva_5", 0)
            g10 = data.get("gravado_10", 0)
            i10 = data.get("iva_10", 0)
            total = data.get("monto_total", 0)
            exonerado = data.get("exonerado", 0)

            # En SIFEN, dSub10 = base + iva (no solo base), así que:
            # total = exento + exonerado + sub5 + sub10
            # Pero nuestro parser extrae gravado_X = dBaseGravX (base sin IVA)
            # Entonces: total ≈ exento + exonerado + (g5 + i5) + (g10 + i10)
            calculated = exento + exonerado + g5 + i5 + g10 + i10
            assert abs(total - calculated) < 2.0, \
                f"[{filename}] Total no cuadra: {total} != {calculated} " \
                f"(exento={exento}, g5={g5}, i5={i5}, g10={g10}, i10={i10}, exo={exonerado})"


class TestRemainingXMLFiles:
    """Tests para los XMLs restantes del directorio example/."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not EXAMPLE_DIR.exists():
            pytest.skip("Directorio de ejemplos no encontrado")

    def test_all_xmls_parse_successfully(self):
        """Todos los archivos XML del directorio example/ deben parsearse exitosamente."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml

        xml_files = list(EXAMPLE_DIR.glob("*.xml"))
        assert len(xml_files) >= 6, f"Se esperan al menos 6 XMLs, encontrados: {len(xml_files)}"

        for xml_file in xml_files:
            xml_content = _read_xml_safe(xml_file)
            success, data = parse_paraguayan_xml(xml_content)
            assert success, f"Parser falló para {xml_file.name}"
            assert data.get("fecha"), f"Sin fecha en {xml_file.name}"
            assert data.get("numero_factura"), f"Sin numero_factura en {xml_file.name}"
            assert data.get("ruc_emisor"), f"Sin ruc_emisor en {xml_file.name}"
            assert data.get("cdc"), f"Sin CDC en {xml_file.name}"
            assert len(data.get("cdc", "")) == 44, f"CDC no tiene 44 dígitos en {xml_file.name}: {len(data.get('cdc', ''))}"
            assert data.get("monto_total", 0) > 0, f"monto_total = 0 en {xml_file.name}"

    def test_all_xmls_map_to_invoice_data(self):
        """Todos los XMLs deben mapearse a InvoiceData sin errores."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        from app.models.models import InvoiceData

        xml_files = list(EXAMPLE_DIR.glob("*.xml"))
        for xml_file in xml_files:
            xml_content = _read_xml_safe(xml_file)
            success, data = parse_paraguayan_xml(xml_content)
            assert success, f"Parser falló para {xml_file.name}"

            invoice = InvoiceData.from_dict(data, None)
            assert invoice is not None, f"InvoiceData es None para {xml_file.name}"
            assert invoice.fecha is not None, f"fecha es None para {xml_file.name}"
            assert invoice.ruc_emisor, f"ruc_emisor vacío para {xml_file.name}"

    def test_all_xmls_map_to_v2(self):
        """Todos los XMLs deben mapearse al esquema v2 (InvoiceDocument) sin errores."""
        from app.modules.openai_processor.xml_parser import parse_paraguayan_xml
        from app.models.models import InvoiceData
        from app.modules.mapping.invoice_mapping import map_invoice

        xml_files = list(EXAMPLE_DIR.glob("*.xml"))
        for xml_file in xml_files:
            xml_content = _read_xml_safe(xml_file)
            success, data = parse_paraguayan_xml(xml_content)
            assert success, f"Parser falló para {xml_file.name}"

            invoice = InvoiceData.from_dict(data, None)
            doc = map_invoice(invoice, fuente="XML_NATIVO")

            assert doc.header is not None, f"v2 header es None para {xml_file.name}"
            assert doc.header.cdc, f"v2 sin CDC para {xml_file.name}"
            assert doc.header.emisor.ruc, f"v2 sin RUC emisor para {xml_file.name}"
            assert doc.header.totales.total > 0, f"v2 total=0 para {xml_file.name}"
            assert len(doc.items) > 0, f"v2 sin items para {xml_file.name}"
            assert doc.header.fuente == "XML_NATIVO"
