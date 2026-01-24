"""
Invoice Factory - Creación centralizada de objetos InvoiceData.

Encapsula la lógica de coerción y normalización de datos de factura
de diferentes fuentes (OpenAI, XML, cache).

Uso:
    from app.modules.openai_processor.invoice_factory import InvoiceFactory
    
    # Desde respuesta OpenAI (v2 o v1)
    invoice = InvoiceFactory.from_openai_response(data, email_metadata)
    
    # Desde cache
    invoice = InvoiceFactory.from_cached(cached_data)
    
    # Desde diccionario genérico
    invoice = InvoiceFactory.from_dict(data)
"""
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class InvoiceFactory:
    """
    Factory centralizada para crear objetos InvoiceData.
    
    Responsabilidades:
    - Detectar formato de entrada (v1, v2, raw)
    - Normalizar campos
    - Crear InvoiceData con manejo de errores
    - Enriquecer con metadata de email
    """
    
    @staticmethod
    def from_dict(
        data: Dict[str, Any],
        email_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Crea InvoiceData desde un diccionario genérico.
        
        Args:
            data: Diccionario con datos de factura (v1 o v2 format).
            email_metadata: Metadata del email origen (opcional).
            
        Returns:
            InvoiceData si es exitoso, dict enriquecido si falla, None si data es inválido.
        """
        if not isinstance(data, dict):
            logger.error(f"❌ InvoiceFactory.from_dict recibió tipo inválido: {type(data).__name__}")
            return None
        
        if not data:
            logger.warning("⚠️ InvoiceFactory.from_dict recibió dict vacío")
            return None
            
        try:
            from app.models.models import InvoiceData
            inv = InvoiceData.from_dict(data, email_metadata)
            logger.debug(f"✅ InvoiceData creado: {inv.numero_factura}")
            return inv
        except Exception as e:
            logger.warning(f"⚠️ Fallo creando InvoiceData: {str(e)[:200]}. Retornando dict enriquecido.")
            # Fallback: devolver dict enriquecido
            if email_metadata:
                data = {**data, "_email_meta": email_metadata}
            return data
    
    @staticmethod
    def from_openai_response(
        data: Dict[str, Any],
        email_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Crea InvoiceData desde respuesta de OpenAI.
        Detecta automáticamente formato v1 o v2.
        
        Args:
            data: Respuesta JSON de OpenAI.
            email_metadata: Metadata del email origen.
            
        Returns:
            InvoiceData o dict enriquecido.
        """
        if not isinstance(data, dict):
            return None
        
        # Detectar formato v2 (header+items)
        if "header" in data and isinstance(data.get("header"), dict):
            data = InvoiceFactory._convert_v2_to_v1(data)
        
        return InvoiceFactory.from_dict(data, email_metadata)
    
    @staticmethod
    def from_cached(cached_data: Dict[str, Any]) -> Optional[Any]:
        """
        Reconstruye InvoiceData desde datos cacheados.
        
        Args:
            cached_data: Datos recuperados del cache.
            
        Returns:
            InvoiceData o dict.
        """
        # Cache guarda datos ya normalizados en formato v1
        return InvoiceFactory.from_dict(cached_data, None)
    
    @staticmethod
    def _convert_v2_to_v1(v2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte formato v2 (header+items) a formato v1 plano.
        
        El formato v2 es el retornado por prompts nuevos de OpenAI:
        {
            "header": { "emisor": {...}, "receptor": {...}, "totales": {...} },
            "items": [...]
        }
        
        El formato v1 es plano, compatible con InvoiceData.from_dict.
        """
        h = v2.get("header") or {}
        t = h.get("totales") or {}
        emisor = h.get("emisor") or {}
        receptor = h.get("receptor") or {}
        items = v2.get("items") or []
        
        numero_doc = h.get("numero_documento") or ""
        fecha = h.get("fecha_emision") or ""
        condicion = (h.get("condicion_venta") or "CONTADO").upper()
        tipo_doc = (h.get("tipo_documento") or ("CR" if "CREDITO" in condicion else "CO")).upper()
        moneda = (h.get("moneda") or "GS").upper()
        
        # Convertir items
        productos = []
        for it in items:
            try:
                productos.append({
                    "articulo": it.get("descripcion", ""),
                    "cantidad": float(it.get("cantidad", 0) or 0),
                    "precio_unitario": float(it.get("precio_unitario", 0) or 0),
                    "total": float(it.get("total", 0) or 0),
                    "iva": int(it.get("iva", 0) or 0)
                })
            except (ValueError, TypeError):
                continue
        
        v1 = {
            "fecha": fecha,
            "numero_factura": numero_doc,
            "ruc_emisor": emisor.get("ruc", ""),
            "nombre_emisor": emisor.get("nombre", ""),
            "condicion_venta": condicion,
            "tipo_documento": tipo_doc,
            "tipo_cambio": float(h.get("tipo_cambio", 0) or 0),
            "moneda": moneda,
            # Totales
            "subtotal_exentas": float(t.get("exentas", 0) or 0),
            "exento": float(t.get("exentas", 0) or 0),
            "monto_exento": float(t.get("exentas", 0) or 0),
            "subtotal_5": float(t.get("gravado_5", 0) or 0),
            "gravado_5": float(t.get("gravado_5", 0) or 0),
            "iva_5": float(t.get("iva_5", 0) or 0),
            "subtotal_10": float(t.get("gravado_10", 0) or 0),
            "gravado_10": float(t.get("gravado_10", 0) or 0),
            "iva_10": float(t.get("iva_10", 0) or 0),
            "monto_total": float(t.get("total", 0) or 0),
            "total_operacion": float(t.get("total_operacion", 0) or t.get("total", 0) or 0),
            "total_iva": float(t.get("total_iva", 0) or 0),
            "exonerado": float(t.get("exonerado", 0) or 0),
            "total_descuento": float(t.get("total_descuento", 0) or 0),
            "anticipo": float(t.get("anticipo", 0) or 0),
            # Campos adicionales
            "timbrado": h.get("timbrado", ""),
            "cdc": h.get("cdc", ""),
            "ruc_cliente": receptor.get("ruc", ""),
            "nombre_cliente": receptor.get("nombre", ""),
            "email_cliente": receptor.get("email", ""),
            "productos": productos
        }
        
        # Generar descripcion_factura desde productos
        if productos:
            articulos = [str(p.get('articulo', '')).strip() for p in productos if p.get('articulo')]
            if articulos:
                v1['descripcion_factura'] = ', '.join(articulos[:10])
        
        return v1
    
    @staticmethod
    def normalize_totals(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza campos numéricos de totales.
        Útil para datos que vienen con formatos inconsistentes.
        """
        numeric_fields = [
            'monto_total', 'total_operacion', 'total_iva',
            'subtotal_exentas', 'exento', 'monto_exento',
            'subtotal_5', 'gravado_5', 'iva_5',
            'subtotal_10', 'gravado_10', 'iva_10',
            'exonerado', 'total_descuento', 'anticipo', 'tipo_cambio'
        ]
        
        result = data.copy()
        for field in numeric_fields:
            if field in result:
                try:
                    result[field] = float(result[field] or 0)
                except (ValueError, TypeError):
                    result[field] = 0.0
        
        return result
