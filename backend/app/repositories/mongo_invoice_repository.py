from __future__ import annotations
import logging
from typing import List, Optional
from datetime import datetime

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

from app.models.invoice_v2 import InvoiceHeader, InvoiceDetail, InvoiceDocument
from app.repositories.invoice_repository import InvoiceRepository
from app.config.settings import settings

logger = logging.getLogger(__name__)


class MongoInvoiceRepository(InvoiceRepository):
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

    def _headers(self) -> Collection:
        coll = self._get_db()[self.headers_collection_name]
        try:
            coll.create_index("_id", unique=True)
            coll.create_index([("emisor.ruc", 1), ("fecha_emision", -1)])
            coll.create_index("emisor.nombre")
            coll.create_index("receptor.nombre")
            coll.create_index("mes_proceso")
            coll.create_index("owner_email")
        except Exception:
            pass
        return coll

    def _items(self) -> Collection:
        coll = self._get_db()[self.items_collection_name]
        try:
            coll.create_index([("header_id", 1), ("linea", 1)], unique=True)
            coll.create_index("owner_email")
        except Exception:
            pass
        return coll

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
                    if "total_monto" not in query:
                        query["total_monto"] = {}
                    query["total_monto"]["$gte"] = float(filters["monto_minimo"])
                    
                if filters.get("monto_maximo"):
                    if "total_monto" not in query:
                        query["total_monto"] = {}
                    query["total_monto"]["$lte"] = float(filters["monto_maximo"])
            
            # Obtener headers
            headers = list(self._headers().find(query).sort("fecha_emision", -1))
            
            # Convertir a formato de respuesta
            invoices = []
            for header in headers:
                # Obtener items para esta factura
                items = list(self._items().find({"header_id": header["_id"]}))
                
                # Combinar header e items en estructura de factura compatible
                invoice = {
                    "_id": str(header["_id"]),
                    "numero_factura": header.get("numero_documento", ""),
                    "fecha": header.get("fecha_emision"),
                    "cdc": header.get("cdc", ""),
                    "timbrado": header.get("timbrado", ""),
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
                    "totales": header.get("totales", {}),
                    "subtotal_exentas": header.get("totales", {}).get("exentas", 0),
                    "exento": header.get("totales", {}).get("exentas", 0),
                    "subtotal_5": header.get("totales", {}).get("gravado_5", 0),
                    "gravado_5": header.get("totales", {}).get("gravado_5", 0),
                    "iva_5": header.get("totales", {}).get("iva_5", 0),
                    "subtotal_10": header.get("totales", {}).get("gravado_10", 0),
                    "gravado_10": header.get("totales", {}).get("gravado_10", 0),
                    "iva_10": header.get("totales", {}).get("iva_10", 0),
                    "monto_total": header.get("totales", {}).get("total", 0),
                    # CRÍTICO: Campos faltantes para template export
                    "total_operacion": header.get("totales", {}).get("total_operacion", 0),
                    "monto_exento": header.get("totales", {}).get("exentas", 0),  # Usar exentas como fuente principal
                    "exonerado": header.get("totales", {}).get("exonerado", 0),
                    "total_iva": header.get("totales", {}).get("total_iva", 0),
                    "total_descuento": header.get("totales", {}).get("total_descuento", 0),
                    "anticipo": header.get("totales", {}).get("anticipo", 0),
                    "base_gravada_5": header.get("totales", {}).get("gravado_5", 0),
                    "base_gravada_10": header.get("totales", {}).get("gravado_10", 0),
                    # Calcular total_base_gravada siempre como suma
                    "total_base_gravada": header.get("totales", {}).get("gravado_5", 0) + header.get("totales", {}).get("gravado_10", 0),
                    "condicion_venta": header.get("condicion_venta", ""),
                    "moneda": header.get("moneda", "PYG"),
                    "tipo_cambio": header.get("tipo_cambio", 0.0),
                    "fuente": header.get("fuente", ""),
                    "processing_quality": header.get("processing_quality", ""),
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

        original_id = doc.header.id
        # Construir ID compuesto solo si hay owner; si no, mantener comportamiento actual
        combined_id = f"{owner}:{original_id}" if owner else original_id

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

        # Upsert de header e items
        self.upsert_header(doc.header)
        self.replace_items(doc.header.id, new_items)

    def close(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
