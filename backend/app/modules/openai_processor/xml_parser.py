#!/usr/bin/env python3
"""
Parser XML nativo para facturas electrónicas paraguayas (SIFEN v150)
Más rápido y eficiente que OpenAI para estructuras estándar
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple, List
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class ParaguayanXMLParser:
    """Parser nativo para facturas electrónicas paraguayas"""

    def __init__(self):
        self.namespaces = {
            'sifen': 'http://ekuatia.set.gov.py/sifen/xsd',
            'dsig': 'http://www.w3.org/2000/09/xmldsig#'
        }

    # -----------------------
    # Helpers numéricos robustos
    # -----------------------
    def _to_float(self, value: Optional[str]) -> float:
        """Convierte strings con formato ES/EN a float.
        Acepta 7400.00 o 7400,00 o 1.234,56 o 1,234.56.
        """
        if value is None:
            return 0.0
        s = str(value).strip().replace(' ', '')
        if not s:
            return 0.0
        try:
            if ',' in s and '.' in s:
                # El último separador es el decimal
                if s.rfind(',') > s.rfind('.'):
                    # decimal=',' → quitar puntos, coma→punto
                    s = s.replace('.', '')
                    s = s.replace(',', '.')
                else:
                    # decimal='.' → quitar comas
                    s = s.replace(',', '')
            elif ',' in s:
                # solo coma → decimal
                s = s.replace(',', '.')
            # else: solo punto o ninguno
            return float(s)
        except Exception:
            import re
            s2 = re.sub(r'[^0-9\.-]', '', s)
            try:
                return float(s2)
            except Exception:
                return 0.0

    def can_parse(self, xml_content: str) -> bool:
        """Verifica si el XML es compatible con el parser SIFEN."""
        try:
            root = ET.fromstring(xml_content)
            
            # Verificar si es estructura SIFEN (rLoteDE o rDE)
            if any(tag in root.tag for tag in ['rDE', 'rLoteDE']):
                return True
                
            # Buscar elemento DE en cualquier lugar del documento
            if self._find_de_element_anywhere(root) is not None:
                return True
                
            logger.warning("XML nativo: no se encontró estructura SIFEN compatible")
            return False
            
        except Exception as e:
            logger.warning(f"XML nativo: error al parsear/leer XML: {e}")
            # Intento de recuperación: parsear solo el fragmento <DE>...</DE>
            frag = self._extract_de_fragment(xml_content)
            if frag:
                try:
                    ET.fromstring(frag)
                    logger.info("XML nativo: recuperación por fragmento <DE> exitosa")
                    return True
                except Exception as e2:
                    logger.warning(f"XML nativo: recuperación por fragmento falló: {e2}")
            return False

    def _find_de_element_anywhere(self, element: ET.Element) -> Optional[ET.Element]:
        """Busca el elemento DE en cualquier parte del árbol XML."""
        # Verificar si el elemento actual es DE
        if isinstance(element.tag, str) and element.tag.split('}')[-1] == 'DE':
            return element
        
        # Buscar recursivamente en los hijos
        for child in element:
            result = self._find_de_element_anywhere(child)
            if result is not None:
                return result
        
        return None

    def _find_element_by_name(self, element: ET.Element, name: str) -> Optional[ET.Element]:
        """Busca un elemento por nombre sin namespace."""
        for child in element:
            if isinstance(child.tag, str) and child.tag.split('}')[-1] == name:
                return child
        return None

    def _find_elements_by_name(self, element: ET.Element, name: str) -> List[ET.Element]:
        """Busca todos los elementos con el nombre especificado."""
        elements = []
        for child in element:
            if isinstance(child.tag, str) and child.tag.split('}')[-1] == name:
                elements.append(child)
        return elements

    def _find_element_by_name_in_de(self, de_element: ET.Element, name: str) -> Optional[ET.Element]:
        """
        Busca descendiente por localname exacto dentro del nodo DE.
        Optimizado para manejar namespaces SIFEN correctamente.
        """
        # Primero intentar búsqueda directa con namespace
        if hasattr(de_element, 'find'):
            try:
                # Buscar con namespace SIFEN
                element = de_element.find(f'.//{{{self.namespaces["sifen"]}}}{name}')
                if element is not None:
                    return element
                
                # Buscar recursivamente con namespace
                element = de_element.find(f'.//sifen:{name}', self.namespaces)
                if element is not None:
                    return element
            except Exception:
                pass
        
        # Fallback: búsqueda por localname (método original)
        for child in de_element.iter():
            try:
                local = child.tag.split('}')[-1] if isinstance(child.tag, str) else ''
                if local == name:
                    return child
            except Exception:
                continue
        return None

    def parse_xml(self, xml_content: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            try:
                root = ET.fromstring(xml_content)
            except Exception:
                frag = self._extract_de_fragment(xml_content)
                if not frag:
                    logger.warning("XML nativo: no se pudo recuperar fragmento <DE>")
                    return False, {}
                root = ET.fromstring(frag)
                
            # Buscar elemento DE usando la nueva función mejorada
            de_element = self._find_de_element_anywhere(root)
            if de_element is None:
                logger.warning("XML nativo: estructura SIFEN inválida: falta elemento 'DE'")
                return False, {}
                
            data = self._extract_basic_data(de_element)
            self._extract_operation_data(de_element, data)
            self._extract_entity_data(de_element, data)
            self._extract_items(de_element, data)
            self._extract_items_and_totals(de_element, data)
            try:
                logger.debug(f"XML (raw extract) -> {data}")
            except Exception:
                pass
            if self._validate_minimum_data(data):
                logger.info("✅ XML parseado exitosamente de forma nativa")
                return True, data
            else:
                logger.warning("⚠️ XML nativo: parseado pero faltan datos mínimos requeridos (fecha, numero_factura, ruc_emisor)")
                return False, data
        except Exception as e:
            logger.error(f"Error parseando XML nativamente: {e}")
            return False, {}

    def _extract_basic_data(self, de_element: ET.Element) -> Dict[str, Any]:
        """
        Extrae datos básicos del elemento DE con manejo optimizado de namespaces.
        """
        data = {}
        
        # Fecha de emisión - buscar en múltiples ubicaciones
        fecha_emision = self._find_element_by_name_in_de(de_element, 'dFeEmiDE')
        if fecha_emision is not None and fecha_emision.text:
            data['fecha'] = fecha_emision.text[:10] if len(fecha_emision.text) >= 10 else fecha_emision.text
        
        # Número de factura - construir desde componentes
        num_doc = self._find_element_by_name_in_de(de_element, 'dNumDoc')
        dEst = self._find_element_by_name_in_de(de_element, 'dEst')
        dPunExp = self._find_element_by_name_in_de(de_element, 'dPunExp')
        
        if all([dEst is not None, dPunExp is not None, num_doc is not None]) and all([dEst.text, dPunExp.text, num_doc.text]):
            data['numero_factura'] = f"{dEst.text}-{dPunExp.text}-{num_doc.text}"
        
        # Timbrado
        num_tim = self._find_element_by_name_in_de(de_element, 'dNumTim')
        if num_tim is not None and num_tim.text:
            data['timbrado'] = num_tim.text
        
        # CDC: usar exclusivamente el atributo Id del nodo DE (44 dígitos numéricos)
        cdc_attr = de_element.attrib.get('Id')
        try:
            if cdc_attr and cdc_attr.isdigit() and len(cdc_attr) == 44:
                data['cdc'] = cdc_attr
            else:
                logger.debug(f"CDC no válido en atributo Id: {cdc_attr}")
        except Exception:
            logger.debug("No se pudo validar CDC desde atributo Id")
        
        return data

    def _extract_operation_data(self, de_element: ET.Element, data: Dict[str, Any]):
        tipo_tra = self._find_element_by_name_in_de(de_element, 'iTipTra')
        if tipo_tra is not None and tipo_tra.text:
            if tipo_tra.text == "1":
                data['tipo_transaccion'] = "Venta de mercadería"
            elif tipo_tra.text == "2":
                data['tipo_transaccion'] = "Prestación de servicios"
        cond_ope = self._find_element_by_name_in_de(de_element, 'dDCondOpe')
        if cond_ope is not None and cond_ope.text:
            data['condicion_venta'] = cond_ope.text
        moneda = self._find_element_by_name_in_de(de_element, 'cMoneOpe')
        if moneda is not None and moneda.text:
            data['moneda'] = moneda.text
        # Tipo de cambio (si viene en el XML SIFEN)
        ti_cam = self._find_element_by_name_in_de(de_element, 'dTiCam')
        if ti_cam is not None and ti_cam.text:
            try:
                data['tipo_cambio'] = float(str(ti_cam.text).replace(',', '.'))
            except Exception:
                pass

    def _extract_entity_data(self, de_element: ET.Element, data: Dict[str, Any]):
        ruc_em = self._find_element_by_name_in_de(de_element, 'dRucEm')
        dv_em = self._find_element_by_name_in_de(de_element, 'dDVEmi')
        if ruc_em is not None and ruc_em.text:
            if dv_em is not None and dv_em.text:
                data['ruc_emisor'] = f"{ruc_em.text}-{dv_em.text}"
            else:
                data['ruc_emisor'] = ruc_em.text
        nom_em = self._find_element_by_name_in_de(de_element, 'dNomEmi')
        if nom_em is not None and nom_em.text:
            data['nombre_emisor'] = nom_em.text
        act_eco = self._find_element_by_name_in_de(de_element, 'cActEco')
        if act_eco is not None and act_eco.text:
            data['actividad_economica'] = act_eco.text
        ruc_rec = self._find_element_by_name_in_de(de_element, 'dRucRec')
        dv_rec = self._find_element_by_name_in_de(de_element, 'dDVRec')
        if ruc_rec is not None and ruc_rec.text:
            if dv_rec is not None and dv_rec.text:
                data['ruc_cliente'] = f"{ruc_rec.text}-{dv_rec.text}"
            else:
                data['ruc_cliente'] = ruc_rec.text
        nom_rec = self._find_element_by_name_in_de(de_element, 'dNomRec')
        if nom_rec is not None and nom_rec.text:
            data['nombre_cliente'] = nom_rec.text
        email_rec = self._find_element_by_name_in_de(de_element, 'dEmailRec')
        if email_rec is not None and email_rec.text:
            data['email_cliente'] = email_rec.text

    def _extract_items(self, de_element: ET.Element, data: Dict[str, Any]):
        """
        Extrae los productos del XML y los carga como una lista en data['productos'],
        en formato compatible con ProductoFactura (modelo Pydantic).
        """
        productos = []
        # Buscar elementos gCamItem
        items_elements = self._find_elements_by_name(de_element, 'gCamItem')
        # Iterar ignorando namespace
        for item_element in items_elements:
            producto = {}
            # Mapeo directo XML SIFEN -> Modelo unificado
            # dCodInt -> codigo
            producto['codigo'] = self._get_text(item_element, 'dCodInt') or ""
            
            # dDesProSer -> articulo/descripcion/nombre
            desc = self._get_text(item_element, 'dDesProSer') or ""
            producto['articulo'] = desc
            producto['descripcion'] = desc  # Campo descripción
            producto['nombre'] = desc  # Para modelo v2
            
            # dCantProSer -> cantidad
            producto['cantidad'] = self._get_float(item_element, 'dCantProSer') or 0.0
            
            # dDesUniMed -> unidad
            producto['unidad'] = self._get_text(item_element, 'dDesUniMed') or ""
            
            # Valores del ítem desde gValorItem
            valor_item = self._find_element_by_name(item_element, 'gValorItem')
            if valor_item is not None:
                # dPUniProSer -> precio_unitario
                producto['precio_unitario'] = self._get_float(valor_item, 'dPUniProSer') or 0.0
                
                # Buscar total en gValorRestaItem primero, luego dTotBruOpeItem
                valor_resta = self._find_element_by_name(valor_item, 'gValorRestaItem')
                if valor_resta is not None:
                    producto['total'] = self._get_float(valor_resta, 'dTotOpeItem') or 0.0
                else:
                    producto['total'] = self._get_float(valor_item, 'dTotBruOpeItem') or 0.0
            
            # Información de IVA desde gCamIVA
            cam_iva = self._find_element_by_name(item_element, 'gCamIVA')
            if cam_iva is not None:
                # dTasaIVA -> iva (como entero: 0, 5, 10)
                tasa = self._get_float(cam_iva, 'dTasaIVA')
                try:
                    producto['iva'] = int(float(tasa or 0))
                except Exception:
                    producto['iva'] = 0
                    
                # Agregar campos adicionales de IVA
                producto['afecta_iva'] = self._get_text(cam_iva, 'dDesAfecIVA') or ""
                producto['base_gravada'] = self._get_float(cam_iva, 'dBasGravIVA') or 0.0
                producto['monto_iva'] = self._get_float(cam_iva, 'dLiqIVAItem') or 0.0

            productos.append(producto)

        data['productos'] = productos

    # Métodos auxiliares recomendados dentro de la clase:
    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """
        Busca elemento por tag con manejo optimizado de namespace.
        """
        # Primero intentar con namespace completo
        try:
            if not tag.startswith('{'):
                # Intentar con namespace SIFEN
                el = element.find(f'{{{self.namespaces["sifen"]}}}{tag}')
                if el is not None and el.text:
                    return el.text.strip()
                
                # Intentar con prefijo namespace
                el = element.find(f'sifen:{tag}', self.namespaces)
                if el is not None and el.text:
                    return el.text.strip()
        except Exception:
            pass
        
        # Fallback al método original
        el = self._find_element_by_name(element, tag)
        return el.text.strip() if el is not None and el.text else None

    def _get_float(self, element: ET.Element, tag: str) -> Optional[float]:
        txt = self._get_text(element, tag)
        return self._to_float(txt)

    def _extract_items_and_totals(self, de_element: ET.Element, data: Dict[str, Any]):
        """
        Extrae items y totales del XML con mapeo optimizado para el modelo de datos.
        Manejo robusto de namespaces para todos los campos.
        """
        # Extraer items
        items = []
        
        # Buscar elementos gCamItem con namespace
        for item_element in de_element.iter():
            if not (isinstance(item_element.tag, str) and 
                   (item_element.tag.endswith('gCamItem') or 'gCamItem' in item_element.tag)):
                continue
                
            item = {}
            
            # Información básica del item
            item['codigo'] = self._get_text(item_element, 'dCodInt')
            item['descripcion'] = self._get_text(item_element, 'dDesProSer')
            
            # Cantidad y unidad
            item['cantidad'] = self._get_float(item_element, 'dCantProSer')
            item['unidad'] = self._get_text(item_element, 'dDesUniMed')
            
            # Valores con búsqueda anidada optimizada
            item['precio_unitario'] = self._extract_nested_float(item_element, ['gValorItem', 'dPUniProSer'])
            item['total_bruto'] = self._extract_nested_float(item_element, ['gValorItem', 'dTotBruOpeItem'])
            item['total_operacion'] = self._extract_nested_float(item_element, ['gValorItem', 'gValorRestaItem', 'dTotOpeItem'])
            
            # Información de IVA con búsqueda anidada
            iva_info = self._extract_iva_info(item_element)
            item.update(iva_info)
            
            items.append(item)
        
        data['items'] = items
        
        # Extraer totales con mapeo optimizado
        totals = self._extract_totals_optimized(de_element)
        data.update(totals)
        
        return data
    
    def _extract_nested_float(self, element: ET.Element, path: list) -> float:
        """
        Extrae un valor float siguiendo un path anidado de elementos.
        """
        current = element
        for tag in path:
            found = None
            # Intentar con namespace completo
            try:
                found = current.find(f'{{{self.namespaces["sifen"]}}}{tag}')
            except Exception:
                pass
            
            # Fallback a búsqueda por localname
            if found is None:
                found = self._find_element_by_name(current, tag)
            
            if found is None:
                return 0.0
            current = found
        
        return self._to_float(current.text) if current.text else 0.0
    
    def _extract_iva_info(self, item_element: ET.Element) -> Dict[str, Any]:
        """
        Extrae información de IVA de un item.
        CRÍTICO: Mapea tasa_iva al campo 'iva' para consistencia con modelo.
        """
        iva_info = {}
        
        # Buscar elemento gCamIVA
        iva_element = None
        try:
            iva_element = item_element.find(f'{{{self.namespaces["sifen"]}}}gCamIVA')
        except Exception:
            pass
        
        if iva_element is None:
            iva_element = self._find_element_by_name(item_element, 'gCamIVA')
        
        if iva_element is not None:
            iva_info['afectacion_iva'] = self._get_text(iva_element, 'dDesAfecIVA')
            tasa = self._get_float(iva_element, 'dTasaIVA')
            iva_info['tasa_iva'] = tasa
            
            # CRÍTICO: Mapear tasa de IVA al campo 'iva' (tipo: 0, 5 o 10)
            try:
                iva_info['iva'] = int(float(tasa or 0))
            except Exception:
                iva_info['iva'] = 0
                
            iva_info['base_gravada'] = self._get_float(iva_element, 'dBasGravIVA')
            iva_info['liquidacion_iva'] = self._get_float(iva_element, 'dLiqIVAItem')
            iva_info['base_exenta'] = self._get_float(iva_element, 'dBasExe')
        else:
            # Si no hay información de IVA, establecer valores por defecto
            iva_info['iva'] = 0
        
        return iva_info
    
    def _extract_totals_optimized(self, de_element: ET.Element) -> Dict[str, Any]:
        """
        Extrae totales con mapeo optimizado para el modelo de datos.
        Mapea correctamente XML SIFEN a modelo con nomenclatura unificada.
        """
        totals = {}
        
        # Buscar elemento gTotSub
        totals_element = None
        try:
            totals_element = de_element.find(f'.//{{{self.namespaces["sifen"]}}}gTotSub')
        except Exception:
            pass
        
        if totals_element is None:
            totals_element = self._find_element_by_name_in_de(de_element, 'gTotSub')
        
        if totals_element is not None:
            # Mapeo directo XML SIFEN -> Modelo de datos
            # dSubExe -> subtotal_exentas/exento
            exento = self._get_float(totals_element, 'dSubExe') or 0.0
            totals['exento'] = exento
            totals['subtotal_exentas'] = exento  # Subtotal exento
            
            # dBaseGrav5 -> gravado_5/subtotal_5 (base sin IVA)
            base5 = self._get_float(totals_element, 'dBaseGrav5') or 0.0
            totals['gravado_5'] = base5
            totals['subtotal_5'] = base5  # Subtotal gravado 5%
            
            # dBaseGrav10 -> gravado_10/subtotal_10 (base sin IVA)
            base10 = self._get_float(totals_element, 'dBaseGrav10') or 0.0
            totals['gravado_10'] = base10
            totals['subtotal_10'] = base10  # Subtotal gravado 10%
            
            # dIVA5 -> iva_5
            totals['iva_5'] = self._get_float(totals_element, 'dIVA5') or 0.0
            
            # dIVA10 -> iva_10
            totals['iva_10'] = self._get_float(totals_element, 'dIVA10') or 0.0
            
            # dTotGralOpe -> monto_total/total_general
            total_general = self._get_float(totals_element, 'dTotGralOpe') or 0.0
            totals['total_general'] = total_general
            totals['monto_total'] = total_general  # Monto total de la factura
            
            # Campos adicionales del XML SIFEN
            totals['exonerado'] = self._get_float(totals_element, 'dSubExo') or 0.0
            totals['total_iva'] = self._get_float(totals_element, 'dTotIVA') or 0.0
            totals['total_operacion'] = self._get_float(totals_element, 'dTotOpe') or 0.0
            totals['total_descuento'] = self._get_float(totals_element, 'dTotDesc') or 0.0
            totals['anticipo'] = self._get_float(totals_element, 'dAnticipo') or 0.0
            totals['total_base_gravada'] = self._get_float(totals_element, 'dTBasGraIVA') or 0.0
        
        return totals

    def _validate_minimum_data(self, data: Dict[str, Any]) -> bool:
        required_fields = ['fecha', 'numero_factura', 'ruc_emisor']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            logger.warning(f"XML nativo: faltan campos mínimos: {missing}")
            return False
        return True

    def normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza al contrato esperado por InvoiceData.from_dict con mapeo optimizado.
        Mapea correctamente gravado_5/10 e iva_5/10 desde XML SIFEN al modelo de datos.
        'subtotal_5' y 'subtotal_10' representan la BASE (gravado), sin IVA.
        'gravado_5' y 'gravado_10' son los mismos valores para compatibilidad.
        """
        normalized: Dict[str, Any] = {}

        # Copiar campos directos
        for k in ['fecha', 'numero_factura', 'ruc_emisor', 'nombre_emisor',
                  'condicion_venta', 'moneda', 'tipo_cambio', 'monto_total',
                  'timbrado', 'cdc', 'ruc_cliente', 'nombre_cliente', 'email_cliente']:
            if k in data:
                normalized[k] = data[k]

        # Mapeo optimizado de bases e IVA desde XML
        # Preferir campos directos del XML (gravado_5/10, iva_5/10)
        base5 = data.get('gravado_5')
        base10 = data.get('gravado_10') 
        iva5 = data.get('iva_5')
        iva10 = data.get('iva_10')
        exento = data.get('exento', 0.0)
        exonerado = data.get('exonerado', 0.0)

        # Fallback a campos alternativos si los principales no están
        if base5 is None:
            base5 = data.get('base_gravada_5') or data.get('subtotal_5')
        if base10 is None:
            base10 = data.get('base_gravada_10') or data.get('subtotal_10')
        if iva5 is None:
            iva5 = data.get('total_iva_5') or 0.0
        if iva10 is None:
            iva10 = data.get('total_iva_10') or 0.0

        # Asignar bases gravadas (valores sin IVA)
        if base5 is not None:
            normalized['subtotal_5'] = float(base5) if base5 else 0.0
            normalized['gravado_5'] = normalized['subtotal_5']  # Campo gravado 5%
        else:
            normalized['subtotal_5'] = 0.0
            normalized['gravado_5'] = 0.0

        if base10 is not None:
            normalized['subtotal_10'] = float(base10) if base10 else 0.0
            normalized['gravado_10'] = normalized['subtotal_10']  # Campo gravado 10%
        else:
            normalized['subtotal_10'] = 0.0
            normalized['gravado_10'] = 0.0

        # Asignar IVAs calculados
        normalized['iva_5'] = float(iva5) if iva5 else 0.0
        normalized['iva_10'] = float(iva10) if iva10 else 0.0

        # Asignar exentos y exonerados
        normalized['exento'] = float(exento) if exento else 0.0
        normalized['exonerado'] = float(exonerado) if exonerado else 0.0
        
        # Para compatibilidad con campos legacy
        normalized['subtotal_exentas'] = normalized['exento']

        # Totales calculados
        total_iva = normalized['iva_5'] + normalized['iva_10']
        total_base = normalized['gravado_5'] + normalized['gravado_10']
        total_general = total_base + total_iva + normalized['exento'] + normalized['exonerado']
        
        normalized['total_iva'] = total_iva
        normalized['total_base_gravada'] = total_base
        normalized['total_general'] = data.get('total_general', total_general)
        
        # Asignar monto_total - usar total_operacion del XML o calcular si no existe
        if 'monto_total' not in normalized:
            # Priorizar total_operacion del XML (dTotOpe) o usar total_general calculado
            normalized['monto_total'] = data.get('total_operacion', total_general)

        # Productos al formato del modelo
        productos = []
        for p in data.get('productos', []) or data.get('items', []) or []:
            # Mapear tanto 'articulo'/'descripcion' como 'codigo'/'descripcion'
            articulo = (p.get('articulo') or p.get('descripcion') or p.get('codigo') or '')
            try:
                # Mapear tasa_iva a campo iva
                iva_val = int(float(p.get('iva', 0) or p.get('tasa_iva', 0) or 0))
            except Exception:
                iva_val = 0
            
            producto = {
                'articulo': articulo,
                'cantidad': p.get('cantidad', 0),
                'precio_unitario': p.get('precio_unitario', 0),
                'total': p.get('total', p.get('total_operacion', 0)),
                'iva': iva_val,
            }
            productos.append(producto)
            
        if productos:
            normalized['productos'] = productos

        # descripcion_factura: concatenación breve de artículos
        if productos and not normalized.get('descripcion_factura'):
            articulos = [str(p.get('articulo', '')).strip() for p in productos if p.get('articulo')]
            if articulos:
                normalized['descripcion_factura'] = ', '.join(articulos[:10])  # limitar a 10 ítems

        # Log para debug del mapeo optimizado
        logger.info(f"XML normalizado - Base 5%: {normalized.get('gravado_5', 0)}, "
                   f"Base 10%: {normalized.get('gravado_10', 0)}, "
                   f"IVA 5%: {normalized.get('iva_5', 0)}, "
                   f"IVA 10%: {normalized.get('iva_10', 0)}, "
                   f"Exento: {normalized.get('exento', 0)}")

        return normalized

def parse_paraguayan_xml(xml_content: str) -> Tuple[bool, Dict[str, Any]]:
    parser = ParaguayanXMLParser()
    if not parser.can_parse(xml_content):
        logger.warning("XML nativo: no compatible con SIFEN o estructura inválida")
        return False, {}
    success, raw_data = parser.parse_xml(xml_content)
    if success:
        return True, parser.normalize_data(raw_data)
    return False, raw_data

    # -------- Helpers de recuperación ---------
def _find_fragment(content: str, start_tag: str, end_tag: str) -> Optional[str]:
    try:
        i = content.find(start_tag)
        if i == -1:
            return None
        j = content.find(end_tag, i)
        if j == -1:
            return None
        return content[i:j+len(end_tag)]
    except Exception:
        return None

def _strip_ns_declaration(fragment: str) -> str:
    # No modificamos namespaces; retornamos tal cual
    return fragment

def _wrap_if_needed(fragment: str) -> str:
    # Si el fragmento empieza con <DE ...> podemos parsearlo solo
    return fragment

def _safe_de_fragment(xml_content: str) -> Optional[str]:
    frag = _find_fragment(xml_content, '<DE ', '</DE>')
    if frag:
        return _wrap_if_needed(_strip_ns_declaration(frag))
    return None

setattr(ParaguayanXMLParser, "_extract_de_fragment", staticmethod(_safe_de_fragment))
