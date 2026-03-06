#!/usr/bin/env python3
"""
Seed script for the RG-90 COMPRAS system template.

Creates the RG-90 Libro de Compras template in MongoDB for use with
the SET (Subsecretaria de Estado de Tributacion) Marangatu system.

Usage:
    cd backend
    python -m scripts.seed_rg90_template
"""
import sys
import os
import logging

# Add parent directory to path for absolute imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app.repositories.export_template_repository import ExportTemplateRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_CODE = "rg90_compras"

RG90_COMPRAS_TEMPLATE = {
    "name": "RG 90 - Libro de Compras (SET)",
    "description": "Planilla de compras para la Resolucion General 90 de la SET. Formato compatible con Marangatu.",
    "sheet_name": "COMPRAS",
    "include_header": True,
    "include_totals": False,
    "is_system": True,
    "system_code": SYSTEM_CODE,
    "is_default": False,
    "fields": [
        {
            "field_key": "tipo_registro",
            "display_name": "Tipo Registro",
            "field_type": "TEXT",
            "order": 1,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "2"}},
        },
        {
            "field_key": "tipo_id_proveedor",
            "display_name": "Tipo ID Proveedor",
            "field_type": "TEXT",
            "order": 2,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "1"}},
        },
        {
            "field_key": "ruc_emisor",
            "display_name": "RUC Proveedor",
            "field_type": "TEXT",
            "order": 3,
            "is_visible": True,
            "transform": {"type": "ruc_body", "params": {}},
        },
        {
            "field_key": "nombre_emisor",
            "display_name": "Nombre Proveedor",
            "field_type": "TEXT",
            "order": 4,
            "is_visible": True,
        },
        {
            "field_key": "tipo_de_codigo",
            "display_name": "Tipo Comprobante",
            "field_type": "TEXT",
            "order": 5,
            "is_visible": True,
        },
        {
            "field_key": "fecha",
            "display_name": "Fecha Emision",
            "field_type": "DATE",
            "order": 6,
            "is_visible": True,
            "transform": {"type": "date_format", "params": {"format": "DD/MM/YYYY"}},
        },
        {
            "field_key": "timbrado",
            "display_name": "Timbrado",
            "field_type": "TEXT",
            "order": 7,
            "is_visible": True,
        },
        {
            "field_key": "numero_factura",
            "display_name": "Nro Comprobante",
            "field_type": "TEXT",
            "order": 8,
            "is_visible": True,
        },
        {
            "field_key": "gravado_10",
            "display_name": "Gravado 10% (IVA incl.)",
            "field_type": "CURRENCY",
            "order": 9,
            "is_visible": True,
            "transform": {"type": "sum_fields", "params": {"fields": ["gravado_10", "iva_10"]}},
        },
        {
            "field_key": "gravado_5",
            "display_name": "Gravado 5% (IVA incl.)",
            "field_type": "CURRENCY",
            "order": 10,
            "is_visible": True,
            "transform": {"type": "sum_fields", "params": {"fields": ["gravado_5", "iva_5"]}},
        },
        {
            "field_key": "monto_exento",
            "display_name": "Exento",
            "field_type": "CURRENCY",
            "order": 11,
            "is_visible": True,
        },
        {
            "field_key": "monto_total",
            "display_name": "Monto Total",
            "field_type": "CURRENCY",
            "order": 12,
            "is_visible": True,
        },
        {
            "field_key": "condicion_venta",
            "display_name": "Condicion Compra",
            "field_type": "TEXT",
            "order": 13,
            "is_visible": True,
            "transform": {
                "type": "map_values",
                "params": {
                    "mapping": {"CONTADO": "1", "CREDITO": "2"},
                    "default": "1",
                },
            },
        },
        {
            "field_key": "moneda",
            "display_name": "Moneda Extranjera",
            "field_type": "TEXT",
            "order": 14,
            "is_visible": True,
            "transform": {
                "type": "boolean_flag",
                "params": {"condition": "not_in", "values": ["PYG", "GS"]},
            },
        },
        {
            "field_key": "imputa_iva",
            "display_name": "Imputa IVA",
            "field_type": "TEXT",
            "order": 15,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "S"}},
        },
        {
            "field_key": "imputa_ire",
            "display_name": "Imputa IRE",
            "field_type": "TEXT",
            "order": 16,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "S"}},
        },
        {
            "field_key": "imputa_irp",
            "display_name": "Imputa IRP-RSP",
            "field_type": "TEXT",
            "order": 17,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "N"}},
        },
        {
            "field_key": "no_imputa",
            "display_name": "No Imputa",
            "field_type": "TEXT",
            "order": 18,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": "N"}},
        },
        {
            "field_key": "comprobante_asociado",
            "display_name": "Comprobante Asociado",
            "field_type": "TEXT",
            "order": 19,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": ""}},
        },
        {
            "field_key": "timbrado_asociado",
            "display_name": "Timbrado Asociado",
            "field_type": "TEXT",
            "order": 20,
            "is_visible": True,
            "transform": {"type": "constant", "params": {"value": ""}},
        },
    ],
}


def seed_rg90_template():
    """Create the RG-90 COMPRAS system template if it does not exist."""
    try:
        repo = ExportTemplateRepository()

        # Check if already exists
        existing = repo.get_system_template_by_code(SYSTEM_CODE)
        if existing:
            logger.info(f"System template '{SYSTEM_CODE}' already exists (id={existing.id}). Skipping.")
            return existing.id

        template_id = repo.create_system_template(RG90_COMPRAS_TEMPLATE)
        logger.info(f"System template '{SYSTEM_CODE}' created successfully (id={template_id})")
        return template_id

    except Exception as e:
        logger.error(f"Error seeding RG-90 template: {e}")
        raise


if __name__ == "__main__":
    seed_rg90_template()
