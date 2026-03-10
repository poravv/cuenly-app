"""
Script de inspección: muestra TODOS los campos críticos extraídos por OpenAI Vision
para cada PDF e imagen del directorio example/.
"""
import os
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

from openai import OpenAI

from app.modules.openai_processor.image_utils import pdf_to_base64_first_page
from app.modules.openai_processor.prompts import build_image_prompt_v2
from app.modules.openai_processor.json_utils import extract_and_normalize_json
from app.modules.openai_processor.processor import _convert_v2_to_v1_dict, _coerce_invoice_model
from app.modules.mapping.invoice_mapping import map_invoice

client = OpenAI(api_key=OPENAI_API_KEY, timeout=60)


def extract_and_inspect(doc_path: str):
    base64_img = pdf_to_base64_first_page(doc_path)
    prompt = build_image_prompt_v2()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]
        }],
        temperature=0.1,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    data = extract_and_normalize_json(raw_text)

    # Mostrar JSON crudo de OpenAI
    print(f"\n{'='*80}")
    print(f"📄 {Path(doc_path).name}")
    print(f"{'='*80}")
    print(f"\n🔹 JSON crudo de OpenAI:")
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    # Convertir a InvoiceData
    if isinstance(data, dict) and "header" in data and "items" in data:
        v1 = _convert_v2_to_v1_dict(data)
    else:
        v1 = data

    invoice = _coerce_invoice_model(v1, None)
    doc = map_invoice(invoice, fuente="OPENAI_VISION")
    h = doc.header
    t = h.totales

    print(f"\n🔹 Campos críticos extraídos:")
    print(f"   CDC:              {h.cdc or '❌ NO DETECTADO'}")
    print(f"   Timbrado:         {h.timbrado or '❌ NO DETECTADO'}")
    print(f"   Nro Factura:      {h.numero_documento}")
    print(f"   Fecha:            {h.fecha_emision}")
    print(f"   RUC Emisor:       {h.emisor.ruc}")
    print(f"   Nombre Emisor:    {h.emisor.nombre}")
    print(f"   RUC Cliente:      {h.receptor.ruc}")
    print(f"   Nombre Cliente:   {h.receptor.nombre}")
    print(f"   Condición:        {h.condicion_venta}")
    print(f"   Moneda:           {h.moneda}")
    print(f"   ─── Totales ───")
    print(f"   Exentas:          {t.exentas:,.0f}")
    print(f"   Gravado 5%:       {t.gravado_5:,.0f}")
    print(f"   IVA 5%:           {t.iva_5:,.0f}")
    print(f"   Gravado 10%:      {t.gravado_10:,.0f}")
    print(f"   IVA 10%:          {t.iva_10:,.0f}")
    print(f"   Total IVA:        {t.total_iva:,.0f}")
    print(f"   Total:            {t.total:,.0f}")
    print(f"   ─── Items ({len(doc.items)}) ───")
    for item in doc.items:
        print(f"   [{item.linea}] {item.descripcion[:50]:50s} cant={item.cantidad} pu={item.precio_unitario:,.0f} total={item.total:,.0f} iva={item.iva}%")

    return data, invoice, doc


if __name__ == "__main__":
    # Todos los PDFs
    pdfs = sorted([f for f in EXAMPLE_DIR.iterdir() if f.suffix == ".pdf"])
    # Todas las imágenes
    imgs = sorted([f for f in EXAMPLE_DIR.iterdir() if f.suffix == ".png"])

    all_files = pdfs + imgs
    print(f"\n🚀 Inspeccionando {len(all_files)} archivos con OpenAI Vision...\n")

    for fpath in all_files:
        try:
            extract_and_inspect(str(fpath))
        except Exception as e:
            print(f"\n❌ ERROR en {fpath.name}: {e}")
