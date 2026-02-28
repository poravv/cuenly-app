from __future__ import annotations
import logging
import re
from typing import List, Optional
from datetime import datetime

from pymongo import MongoClient
from pymongo.collection import Collection

from app.models.invoice_v2 import InvoiceHeader, InvoiceDetail, InvoiceDocument
from app.repositories.invoice_repository import InvoiceRepository
from app.config.settings import settings

logger = logging.getLogger(__name__)
_CDC_TOKEN_RE = re.compile(r"\d{44}")


class MongoInvoiceRepository(InvoiceRepository):
    _indexes_ensured: bool = False

    def __init__(self,
                 connection_string: Optional[str] = None,
                 database_name: Optional[str] = None,
                 headers_collection: str = "invoice_headers",
                 items_collection: str = "invoice_items") -> None:
        self.conn_str = connection_string or settings.MONGODB_URL
        self.db_name = database_name or settings.MONGODB_DATABASE
        self.headers_collection_name = headers_collection
        self.items_collection_name = items_collection
        self._client: Optional[MongoClient] = None

    def _get_db(self):
        if not self._client:
            self._client = MongoClient(self.conn_str, serverSelectionTimeoutMS=60000)
            self._client.admin.command('ping')
            logger.info("✅ Conectado a MongoDB (repo)")
        return self._client[self.db_name]

    def _ensure_indexes(self) -> None:
        """Crea índices una sola vez por proceso."""
        if MongoInvoiceRepository._indexes_ensured:
            return
        try:
            hdr = self._get_db()[self.headers_collection_name]
            hdr.create_index([("emisor.ruc", 1), ("fecha_emision", -1)])
            hdr.create_index("emisor.nombre")
            hdr.create_index("receptor.nombre")
            hdr.create_index("mes_proceso")
            hdr.create_index("owner_email")
            hdr.create_index("message_id")
            hdr.create_index([("owner_email", 1), ("message_id", 1)])
            hdr.create_index("fecha_emision")
            hdr.create_index("fuente")
            hdr.create_index([("owner_email", 1), ("fecha_emision", -1)])

            desired_partial = {
                "owner_email": {"$exists": True, "$gt": ""},
                "cdc": {"$exists": True, "$gt": ""},
            }
            idx_name = "owner_email_1_cdc_1"
            idx_info = hdr.index_information().get(idx_name)
            if idx_info:
                current_partial = idx_info.get("partialFilterExpression")
                current_unique = bool(idx_info.get("unique"))
                if (not current_unique) or (current_partial != desired_partial):
                    hdr.drop_index(idx_name)

            hdr.create_index(
                [("owner_email", 1), ("cdc", 1)],
                name=idx_name,
                unique=True,
                partialFilterExpression=desired_partial,
            )

            itm = self._get_db()[self.items_collection_name]
            itm.create_index([("header_id", 1), ("linea", 1)], unique=True)
            itm.create_index("owner_email")

            MongoInvoiceRepository._indexes_ensured = True
            logger.info("Índices de invoice_headers/items asegurados")
        except Exception as e:
            logger.warning(f"No se pudieron crear/actualizar índices: {e}")

    def _headers(self) -> Collection:
        self._ensure_indexes()
        return self._get_db()[self.headers_collection_name]

    def _items(self) -> Collection:
        self._ensure_indexes()
        return self._get_db()[self.items_collection_name]

    def get_invoices_by_user(self, owner_email: str, filters: dict = None) -> List[dict]:
        """
        Obtiene facturas del usuario aplicando filtros opcionales
        """
        try:
            # Base query
            query = {"owner_email": owner_email}
            
            # Aplicar filtros
            if filters:
                if filters.get("fecha_inicio"):
                    if "fecha_emision" not in query:
                        query["fecha_emision"] = {}
                    query["fecha_emision"]["$gte"] = datetime.fromisoformat(filters["fecha_inicio"])
                    
                if filters.get("fecha_fin"):
                    if "fecha_emision" not in query:
                        query["fecha_emision"] = {}
                    query["fecha_emision"]["$lte"] = datetime.fromisoformat(filters["fecha_fin"])
                    
                if filters.get("ruc_emisor"):
                    query["emisor.ruc"] = filters["ruc_emisor"]
                    
                if filters.get("ruc_cliente"):
                    query["receptor.ruc"] = filters["ruc_cliente"]
                    
                if filters.get("monto_minimo"):
                    if "totales.total" not in query:
                        query["totales.total"] = {}
                    query["totales.total"]["$gte"] = float(filters["monto_minimo"])
                    
                if filters.get("monto_maximo"):
                    if "totales.total" not in query:
                        query["totales.total"] = {}
                    query["totales.total"]["$lte"] = float(filters["monto_maximo"])
            
            # Obtener headers
            headers = list(self._headers().find(query).sort("fecha_emision", -1))
            
            # Convertir a formato de respuesta
            invoices = []
            for header in headers:
                # Obtener items para esta factura
                items = list(self._items().find({"header_id": header["_id"]}))
                
                # Combinar header e items en estructura de factura compatible
                totales = header.get("totales", {}) or {}
                total_iva = totales.get("total_iva", None)
                if total_iva is None:
                    total_iva = (totales.get("iva_5", 0) or 0) + (totales.get("iva_10", 0) or 0)

                invoice = {
                    "_id": str(header["_id"]),
                    "numero_factura": header.get("numero_documento", ""),
                    "fecha": header.get("fecha_emision"),
                    "cdc": header.get("cdc", ""),
                    "timbrado": header.get("timbrado", ""),
                    "tipo_documento": header.get("tipo_documento", ""),
                    "tipo_documento_electronico": header.get("tipo_documento_electronico", ""),
                    "tipo_de_codigo": header.get("tipo_de_codigo", ""),
                    "ind_presencia": header.get("ind_presencia", ""),
                    "ind_presencia_codigo": header.get("ind_presencia_codigo", ""),
                    "cond_credito": header.get("cond_credito", ""),
                    "cond_credito_codigo": header.get("cond_credito_codigo", ""),
                    "plazo_credito_dias": header.get("plazo_credito_dias", 0),
                    "ciclo_facturacion": header.get("ciclo_facturacion", ""),
                    "ciclo_fecha_inicio": header.get("ciclo_fecha_inicio", ""),
                    "ciclo_fecha_fin": header.get("ciclo_fecha_fin", ""),
                    "transporte_modalidad": header.get("transporte_modalidad", ""),
                    "transporte_modalidad_codigo": header.get("transporte_modalidad_codigo", ""),
                    "transporte_resp_flete_codigo": header.get("transporte_resp_flete_codigo", ""),
                    "transporte_nro_despacho": header.get("transporte_nro_despacho", ""),
                    "qr_url": header.get("qr_url", ""),
                    "info_adicional": header.get("info_adicional", ""),
                    "ruc_emisor": header.get("emisor", {}).get("ruc", ""),
                    "nombre_emisor": header.get("emisor", {}).get("nombre", ""),
                    "direccion_emisor": header.get("emisor", {}).get("direccion", ""),
                    "telefono_emisor": header.get("emisor", {}).get("telefono", ""),
                    "email_emisor": header.get("emisor", {}).get("email", ""),
                    "actividad_economica": header.get("emisor", {}).get("actividad_economica", ""),
                    "ruc_cliente": header.get("receptor", {}).get("ruc", ""),
                    "nombre_cliente": header.get("receptor", {}).get("nombre", ""),
                    "direccion_cliente": header.get("receptor", {}).get("direccion", ""),
                    "telefono_cliente": header.get("receptor", {}).get("telefono", ""),
                    "email_cliente": header.get("receptor", {}).get("email", ""),
                    # Mapeo correcto desde modelo v2
                    "totales": totales,
                    "subtotal_exentas": totales.get("exentas", 0),
                    "exento": totales.get("monto_exento", 0) or totales.get("exentas", 0),
                    "subtotal_5": totales.get("gravado_5", 0),
                    "gravado_5": totales.get("gravado_5", 0),
                    "iva_5": totales.get("iva_5", 0),
                    "subtotal_10": totales.get("gravado_10", 0),
                    "gravado_10": totales.get("gravado_10", 0),
                    "iva_10": totales.get("iva_10", 0),
                    "monto_total": totales.get("total", 0),
                    # CRÍTICO: Campos faltantes para template export
                    "total_operacion": totales.get("total_operacion", 0) or totales.get("total", 0),
                    "monto_exento": totales.get("monto_exento", 0) or totales.get("exentas", 0),
                    "exonerado": totales.get("exonerado", 0),
                    "total_iva": total_iva,
                    "total_descuento": totales.get("total_descuento", 0),
                    "anticipo": totales.get("anticipo", 0),
                    "base_gravada_5": totales.get("gravado_5", 0),
                    "base_gravada_10": totales.get("gravado_10", 0),
                    "total_base_gravada": totales.get(
                        "total_base_gravada",
                        (totales.get("gravado_5", 0) or 0) + (totales.get("gravado_10", 0) or 0),
                    ),
                    "isc_total": totales.get("isc_total", 0),
                    "isc_base_imponible": totales.get("isc_base_imponible", 0),
                    "isc_subtotal_gravado": totales.get("isc_subtotal_gravado", 0),
                    "condicion_venta": header.get("condicion_venta", ""),
                    "moneda": header.get("moneda", "PYG"),
                    "tipo_cambio": header.get("tipo_cambio", 0.0),
                    "fuente": header.get("fuente", ""),
                    "email_origen": header.get("email_origen", ""),
                    "created_at": header.get("created_at"),
                    "mes_proceso": header.get("mes_proceso", ""),
                    "productos": [],
                }
                
                # Agregar productos con mapeo correcto
                for item in items:
                    producto = {
                        "codigo": item.get("codigo", ""),
                        "articulo": item.get("descripcion", ""),
                        "nombre": item.get("descripcion", ""),
                        "descripcion": item.get("descripcion", ""),
                        "cantidad": item.get("cantidad", 0),
                        "unidad": item.get("unidad", ""),
                        "precio_unitario": item.get("precio_unitario", 0),
                        "total": item.get("total", 0),
                        "iva": item.get("iva", 0)  # Esto ya es el tipo (5, 10)
                    }
                    invoice["productos"].append(producto)
                
                # Descripción de la factura (concatenación de productos)
                try:
                    descripciones = [p.get("descripcion", "") for p in invoice["productos"] if p.get("descripcion")]
                    if descripciones:
                        invoice["descripcion_factura"] = ", ".join(descripciones[:10])
                except Exception:
                    pass
                
                invoices.append(invoice)
            
            logger.info(f"✅ Obtenidas {len(invoices)} facturas para {owner_email}")
            return invoices
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo facturas: {e}")
            return []

    def upsert_header(self, header: InvoiceHeader) -> None:
        doc = header.model_dump()
        doc["updated_at"] = datetime.utcnow()
        self._headers().replace_one({"_id": header.id}, doc, upsert=True)

    def replace_items(self, header_id: str, items: List[InvoiceDetail]) -> int:
        items_coll = self._items()
        items_coll.delete_many({"header_id": header_id})
        if not items:
            return 0
        to_insert = [it.model_dump() for it in items]
        res = items_coll.insert_many(to_insert)
        return len(res.inserted_ids)

    # Priority Map definition
    PRIORITY_MAP = {
        "XML_NATIVO": 100,
        "XML_SIFEN": 100,
        "OPENAI_VISION": 50,
        "OPENAI_VISION_IMAGE": 40,
        "EMAIL": 10
    }

    def _get_priority(self, fuente: str) -> int:
        return self.PRIORITY_MAP.get(fuente, 0)

    @staticmethod
    def _is_minio_key_compatible_with_cdc(minio_key: str, cdc: str) -> bool:
        key = (minio_key or "").strip()
        if not key:
            return False
        cdc = (cdc or "").strip()
        if not cdc:
            return True
        tokens = _CDC_TOKEN_RE.findall(key)
        if not tokens:
            # Sin token CDC en nombre no podemos validarlo aquí.
            return False
        return cdc in tokens

    def _resolve_canonical_header_id(
        self,
        owner: str,
        current_id: str,
        cdc: str,
        message_id: str
    ) -> str:
        headers = self._headers()
        if owner and cdc:
            existing = headers.find_one(
                {"owner_email": owner, "cdc": cdc},
                {"_id": 1}
            )
            if existing and existing.get("_id"):
                return str(existing["_id"])

        if owner and message_id:
            existing = headers.find_one(
                {"owner_email": owner, "message_id": message_id},
                {"_id": 1}
            )
            if existing and existing.get("_id"):
                return str(existing["_id"])

        return f"{owner}:{current_id}" if owner else current_id

    # Override: asegurar unicidad por usuario + factura
    def save_document(self, doc: InvoiceDocument) -> None:
        """
        Guarda una factura asegurando que el _id del header sea único por usuario.
        Evita que el mismo comprobante entre distintos usuarios se reemplace entre sí.
        
        Aplica lógica de prioridad basada en la fuente:
        XML (100) > PDF (50) > IMAGEN (40) > EMAIL (10)
        """
        # Determinar owner
        owner = (getattr(doc.header, 'owner_email', '') or '').lower()
        # Si no viene owner en header, intentar deducir desde items
        if not owner and doc.items:
            try:
                owner = (getattr(doc.items[0], 'owner_email', '') or '').lower()
            except Exception:
                owner = ''

        original_id = str(doc.header.id)
        cdc = str(getattr(doc.header, "cdc", "") or "").strip()
        message_id = str(getattr(doc.header, "message_id", "") or "").strip()
        if cdc:
            doc.header.cdc = cdc
        if message_id:
            doc.header.message_id = message_id

        combined_id = self._resolve_canonical_header_id(
            owner=owner,
            current_id=original_id,
            cdc=cdc,
            message_id=message_id
        )

        # Mutar documento en memoria para mantener consistencia
        doc.header.id = combined_id
        if owner:
            doc.header.owner_email = owner
        # Asegurar que los items apunten al header_id combinado y tengan owner
        new_items: List[InvoiceDetail] = []
        for it in doc.items:
            it.header_id = combined_id
            if owner:
                it.owner_email = owner
            new_items.append(it)

        # Lógica de prioridad
        existing_header = self._headers().find_one({"_id": combined_id})
        if existing_header:
            existing_fuente = existing_header.get("fuente", "")
            new_fuente = doc.header.fuente or ""
            
            existing_priority = self._get_priority(existing_fuente)
            new_priority = self._get_priority(new_fuente)
            
            if new_priority < existing_priority:
                logger.info(f"⚠️ Saltando actualización de factura {combined_id}: Prioridad nueva ({new_fuente}={new_priority}) < Existente ({existing_fuente}={existing_priority})")
                return
            
            # Si actualizamos, preservamos ciertos campos si la nueva fuente es de menor calidad pero igual prioridad (edge case)
            # Pero la regla es simple: si new >= old, sobreescribimos.
            logger.info(f"🔄 Actualizando factura {combined_id}: Prioridad nueva ({new_fuente}={new_priority}) >= Existente ({existing_fuente}={existing_priority})")

            # No perder referencia al archivo ya subido por reprocesos sin adjunto.
            existing_minio_key = (existing_header.get("minio_key") or "").strip()
            new_minio_key = (getattr(doc.header, "minio_key", "") or "").strip()
            if existing_minio_key and not new_minio_key:
                header_cdc = str(getattr(doc.header, "cdc", "") or "").strip()
                if self._is_minio_key_compatible_with_cdc(existing_minio_key, header_cdc):
                    doc.header.minio_key = existing_minio_key
                    logger.info(f"♻️ Preservando minio_key existente para factura {combined_id}")
                else:
                    logger.warning(
                        "⚠️ No se preserva minio_key en %s por posible inconsistencia de CDC (%s)",
                        combined_id,
                        header_cdc or "sin_cdc",
                    )

        # Upsert de header e items
        self.upsert_header(doc.header)
        self.replace_items(doc.header.id, new_items)

    def close(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
