import imaplib
import email
import logging
import socket
import time
import re
from typing import Any, Callable, Dict, List, Optional, Set
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime

from .subject_matcher import compile_match_terms, match_email_candidate
from app.config.settings import settings

logger = logging.getLogger(__name__)

def decode_mime_header(header_value: str) -> str:
    """Decodifica cabeceras MIME (Asunto, De, etc) a un string limpio."""
    if not header_value:
        return ""
    try:
        fragments = decode_header(header_value)
        decoded_text = ""
        for fragment, charset in fragments:
            if isinstance(fragment, bytes):
                try:
                    if charset:
                        decoded_text += fragment.decode(charset, errors='replace')
                    else:
                        decoded_text += fragment.decode('utf-8', errors='replace')
                except LookupError:
                    decoded_text += fragment.decode('utf-8', errors='replace')
            else:
                decoded_text += str(fragment)
        return decoded_text.strip()
    except Exception:
        return str(header_value).strip()


_ATTACHMENT_PARAM_RE = re.compile(rb'"(?:NAME|FILENAME)\*?"\s+"([^"]+)"', re.IGNORECASE)
_ATTACHMENT_EXT_RE = re.compile(r'"([^"]+\.(?:xml|pdf|zip|jpg|jpeg|png))"', re.IGNORECASE)
_XML_URL_RE = re.compile(r'https?://[^\s<>"\']+\.xml(?:[?#][^\s<>"\']*)?', re.IGNORECASE)
_INVOICE_FILE_URL_RE = re.compile(
    r'https?://[^\s<>"\']+\.(?:xml|pdf|jpg|jpeg|png)(?:[?#][^\s<>"\']*)?',
    re.IGNORECASE
)


def _extract_attachment_names_from_fetch_meta(fetch_meta: Any) -> List[str]:
    """
    Extrae nombres de adjuntos desde BODYSTRUCTURE en la metadata IMAP FETCH.
    No baja el cuerpo completo del correo.
    """
    if not fetch_meta:
        return []

    if isinstance(fetch_meta, bytes):
        raw = fetch_meta
    else:
        raw = str(fetch_meta).encode("utf-8", errors="ignore")

    names: List[str] = []

    for match in _ATTACHMENT_PARAM_RE.findall(raw):
        text = decode_mime_header(match.decode("utf-8", errors="replace")).strip()
        if text:
            names.append(text)

    if not names:
        raw_text = raw.decode("utf-8", errors="ignore")
        for candidate in _ATTACHMENT_EXT_RE.findall(raw_text):
            decoded = decode_mime_header(candidate).strip()
            if decoded:
                names.append(decoded)

    deduped: List[str] = []
    seen: Set[str] = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)
    return deduped


def _has_xml_url_hint(text: str) -> bool:
    """Detecta enlaces XML o frases comunes relacionadas en texto libre."""
    if not text:
        return False
    lowered = text.lower()
    if _XML_URL_RE.search(lowered):
        return True
    return any(
        marker in lowered
        for marker in ("descargar xml", "adjunto xml", "archivo xml", "comprobante xml")
    )


def _has_invoice_url_hint(text: str) -> bool:
    """Detecta enlaces a archivos de factura (xml/pdf/imagen) o frases comunes."""
    if not text:
        return False
    lowered = text.lower()
    if _INVOICE_FILE_URL_RE.search(lowered):
        return True
    return any(
        marker in lowered
        for marker in (
            "descargar xml",
            "descargar pdf",
            "adjunto xml",
            "adjunto pdf",
            "archivo xml",
            "archivo pdf",
            "comprobante",
            "factura electronica",
            "factura electrónica",
        )
    )


def _has_xml_attachment_hint(fetch_meta: Any, attachment_names: List[str]) -> bool:
    """Determina si la metadata IMAP indica presencia de XML adjunto."""
    for name in attachment_names or []:
        lname = (name or "").lower()
        if ".xml" in lname:
            return True

    raw_text = (
        fetch_meta.decode("utf-8", errors="ignore")
        if isinstance(fetch_meta, (bytes, bytearray))
        else str(fetch_meta or "")
    ).lower()
    if not raw_text:
        return False

    if any(
        marker in raw_text
        for marker in (
            '"application" "xml"',
            '"text" "xml"',
            "application/xml",
            "text/xml",
            "+xml",
        )
    ):
        return True

    return bool(_XML_URL_RE.search(raw_text))


def _has_invoice_attachment_hint(fetch_meta: Any, attachment_names: List[str]) -> bool:
    """Determina si la metadata IMAP indica adjuntos de factura (xml/pdf/imagen)."""
    allowed_exts = (".xml", ".pdf", ".jpg", ".jpeg", ".png")
    for name in attachment_names or []:
        lname = (name or "").lower()
        if any(ext in lname for ext in allowed_exts):
            return True

    raw_text = (
        fetch_meta.decode("utf-8", errors="ignore")
        if isinstance(fetch_meta, (bytes, bytearray))
        else str(fetch_meta or "")
    ).lower()
    if not raw_text:
        return False

    if any(
        marker in raw_text
        for marker in (
            '"application" "xml"',
            '"text" "xml"',
            "application/xml",
            "text/xml",
            "+xml",
            '"application" "pdf"',
            "application/pdf",
            '"image" "jpeg"',
            '"image" "jpg"',
            '"image" "png"',
            "image/jpeg",
            "image/jpg",
            "image/png",
        )
    ):
        return True

    return bool(_INVOICE_FILE_URL_RE.search(raw_text))


def _decode_snippet_bytes(payload: bytes) -> str:
    """Decodifica un fragmento de texto de correo para heurísticas rápidas."""
    if not payload:
        return ""
    for charset in ("utf-8", "latin-1", "windows-1252"):
        try:
            return payload.decode(charset, errors="ignore")
        except Exception:
            continue
    return payload.decode("utf-8", errors="ignore")

class IMAPClient:
    """
    Envoltura mínima: conecta, busca por asunto, fetch por UID y marca como leído por UID.
    Pensado para cPanel y Gmail.
    Soporta autenticación tradicional (password) y OAuth 2.0 XOAUTH2.
    """
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        auth_type: str = "password",
        access_token: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.auth_type = auth_type  # "password" or "oauth2"
        self.access_token = access_token  # For OAuth2 XOAUTH2
        self.conn: Optional[imaplib.IMAP4_SSL] = None
        self.is_gmail: bool = False

    def _has_invoice_url_in_body_snippet(self, email_uid: str, max_bytes: int = 8192) -> bool:
        """
        Detecta URLs de archivo de factura (xml/pdf/imagen) en el cuerpo sin descargar el correo completo.
        Hace un FETCH parcial de texto (primeros bytes).
        """
        if not self.conn:
            return False
        try:
            status, data = self.conn.uid('FETCH', email_uid, f'(BODY.PEEK[TEXT]<0.{max_bytes}>)')
            if status != 'OK' or not data:
                return False

            parts: List[str] = []
            for item in data:
                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                    parts.append(_decode_snippet_bytes(item[1]))

            if not parts:
                return False

            snippet_text = "\n".join(parts)
            return _has_invoice_url_hint(snippet_text)
        except Exception:
            return False

    def _has_xml_url_in_body_snippet(self, email_uid: str, max_bytes: int = 8192) -> bool:
        """
        Detecta específicamente URLs XML en cuerpo (sin descargar correo completo).
        """
        if not self.conn:
            return False
        try:
            status, data = self.conn.uid('FETCH', email_uid, f'(BODY.PEEK[TEXT]<0.{max_bytes}>)')
            if status != 'OK' or not data:
                return False

            parts: List[str] = []
            for item in data:
                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                    parts.append(_decode_snippet_bytes(item[1]))

            if not parts:
                return False

            snippet_text = "\n".join(parts)
            return _has_xml_url_hint(snippet_text)
        except Exception:
            return False

    def _xoauth2_callback(self, challenge: bytes) -> bytes:
        """
        Callback for IMAP XOAUTH2 authentication.
        Returns the XOAUTH2 authentication string.
        """
        # The challenge is empty for initial auth, we just return the auth string
        auth_string = f"user={self.username}\x01auth=Bearer {self.access_token}\x01\x01"
        return auth_string.encode()

    def connect(self) -> bool:
        """Conecta con retry automático y timeouts robustos. Soporta OAuth2 XOAUTH2."""
        max_retries = 3
        retry_delay = 2  # segundos
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Intento de conexión {attempt + 1}/{max_retries} - host: {self.host}, port: {self.port}, username: {self.username}, auth_type: {self.auth_type}")

                self.is_gmail = "imap.gmail.com" in (self.host or "").lower()
                
                # Crear conexión con timeout real en handshake para evitar bloqueos prolongados
                try:
                    self.conn = imaplib.IMAP4_SSL(self.host, self.port, timeout=30)
                except (socket.timeout, socket.gaierror, socket.error, OSError) as e:
                    logger.warning(f"Error de conexión de red (intento {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Fallo de conexión después de {max_retries} intentos")
                        return False
                    time.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
                    continue
                
                # Configurar timeout de socket para operaciones IMAP
                if hasattr(self.conn, 'sock') and self.conn.sock:
                    self.conn.sock.settimeout(30.0)  # 30 segundos timeout
                
                # Autenticación: OAuth2 XOAUTH2 o password tradicional
                try:
                    if self.auth_type == "oauth2" and self.access_token:
                        # Use XOAUTH2 authentication for Gmail
                        logger.info(f"🔐 Usando autenticación OAuth2 XOAUTH2 para {self.username}")
                        self.conn.authenticate("XOAUTH2", self._xoauth2_callback)
                        logger.info(f"✅ Autenticación XOAUTH2 exitosa para {self.username}")
                    else:
                        # Traditional password login
                        self.conn.login(self.username, self.password)
                    
                    # Habilitar debug máximo para ver tráfico IMAP
                    self.conn.debug = 4
                except (socket.timeout, socket.error, imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                    logger.warning(f"Error de autenticación IMAP (intento {attempt + 1}): {e}")
                    try:
                        self.conn.close()
                        self.conn.logout()
                    except:
                        pass
                    self.conn = None
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Error de autenticación después de {max_retries} intentos")
                        return False
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                # Seleccionar mailbox
                try:
                    typ, _ = self.conn.select(self.mailbox)
                    if typ != "OK":
                        raise RuntimeError(f"No se pudo seleccionar mailbox: {self.mailbox}")
                except (socket.timeout, socket.error, imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                    logger.warning(f"Error seleccionando mailbox (intento {attempt + 1}): {e}")
                    try:
                        self.conn.close()
                        self.conn.logout()
                    except:
                        pass
                    self.conn = None
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Error seleccionando mailbox después de {max_retries} intentos")
                        return False
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                auth_method = "XOAUTH2" if self.auth_type == "oauth2" else "password"
                logger.info(f"✅ Conexión exitosa al correo {self.username} | is_gmail={self.is_gmail} | auth={auth_method}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error inesperado en conexión (intento {attempt + 1}): {e}")
                self.conn = None
                if attempt == max_retries - 1:
                    return False
                time.sleep(retry_delay * (attempt + 1))
        
        return False

    def close(self):
        """Cierra la conexión de forma segura."""
        if not self.conn:
            return
        try:
            # Configurar timeout corto para cierre
            if hasattr(self.conn, 'sock') and self.conn.sock:
                self.conn.sock.settimeout(5.0)  # 5 segundos para cierre
            
            try:
                self.conn.close()
            except (socket.timeout, socket.error, imaplib.IMAP4.abort, imaplib.IMAP4.error):
                # Ignorar errores de cierre
                pass
            
            try:
                self.conn.logout()
                logger.info("✅ Desconexión exitosa del servidor de correo")
            except (socket.timeout, socket.error, imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                logger.warning(f"⚠️ Error menor al desconectar del servidor de correo: {str(e)}")
                
        except Exception as e:
            logger.error(f"❌ Error inesperado al desconectar del servidor de correo: {str(e)}")
        finally:
            self.conn = None

    def search(
        self,
        subject_terms: List[str],
        unread_only: Optional[bool] = None,
        since_date=None,
        before_date=None,
        search_synonyms: Optional[Any] = None,
        fallback_sender_match: bool = False,
        fallback_attachment_match: bool = False,
        on_match_batch: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca correos por criterios base IMAP + matcher local robusto:
        - normalización unicode/acentos/puntuación
        - sinónimos por tenant
        - fallback opcional por remitente y/o nombre de adjunto
        """
        if not self.conn and not self.connect():
            return []

        if unread_only is None:
            unread_only = True
        
        # Base flags
        base_flag_args = ['UNSEEN'] if unread_only else ['ALL']
        
        # Filtros de fecha
        if since_date:
            date_str = since_date.strftime("%d-%b-%Y")
            base_flag_args.append('SINCE')
            base_flag_args.append(date_str)
        
        if before_date:
            date_str = before_date.strftime("%d-%b-%Y")
            base_flag_args.append('BEFORE')
            base_flag_args.append(date_str)

        uids: Set[str] = set()
        
        def _decode_ids(data) -> List[str]:
            if not data:
                return []
            first = data[0]
            payload = first.decode('utf-8', errors='ignore').strip() if isinstance(first, (bytes, bytearray)) else str(first).strip()
            return payload.split() if payload else []

        compiled_terms = compile_match_terms(subject_terms or [], search_synonyms=search_synonyms)

        if not compiled_terms:
            # Sin términos: búsqueda simple sin filtrado de asunto
            try:
                typ, data = self.conn.uid('SEARCH', *base_flag_args)
                if typ == 'OK':
                    uids |= set(_decode_ids(data))
            except Exception as e:
                logger.error(f"UID SEARCH error sin términos: {e}")
            
            # Nota: sin términos no bajamos metadatos en batch aquí para no complicar,
            # pero devolvemos lista de dicts mínimos para consistencia
            return [{"uid": uid, "subject": "(Sin términos)"} for uid in sorted(uids, key=lambda x: int(x))]

        # Con términos: Estrategia "Traer todo y filtrar en casa"
        # 1. Buscar todos los mensajes que cumplan los criterios base (UNSEEN, fechas)
        # 2. Bajar los SUBJECTS
        # 3. Filtrar en Python normalizando ambos lados
        
        try:
            # 1. Obtener candidatos
            logger.info(f"🔍 Obteniendo candidatos base con flags: {base_flag_args}")
            typ, data = self.conn.uid('SEARCH', *base_flag_args)
            
            if typ != 'OK':
                logger.warning(f"UID SEARCH base falló: {typ}")
                return []
                
            candidate_uids = _decode_ids(data)
            if not candidate_uids:
                logger.debug("No se encontraron correos candidatos con los filtros base.")
                return []
            
            # Limitar a los N más recientes para evitar sobrecarga si hay miles.
            # Para sincronización histórica por rango (ALL + fechas), el límite se
            # controla por setting dedicado y por defecto se deja sin límite.
            # Ordenamos descendente (más recientes primero).
            candidate_uids.sort(key=lambda x: int(x), reverse=True)

            is_historical_range = (not unread_only) and (since_date is not None or before_date is not None)
            if is_historical_range:
                max_candidates = int(getattr(settings, "IMAP_SEARCH_MAX_CANDIDATES_RANGE", 0) or 0)
            else:
                max_candidates = int(getattr(settings, "IMAP_SEARCH_MAX_CANDIDATES", 10000) or 10000)

            if max_candidates > 0 and len(candidate_uids) > max_candidates:
                logger.info(
                    "⚠️ Limitando análisis de asuntos a los %s correos más recientes (de %s encontrados)",
                    max_candidates,
                    len(candidate_uids),
                )
                candidate_uids = candidate_uids[:max_candidates]
            
            # 2. Fetch SUBJECTS/FROM/DATE en batch (y BODYSTRUCTURE si aplica fallback por adjunto)
            # Convertir lista de UIDs a string separado por comas para el fetch
            matched_items = []  # List of dicts
            source_counts = {"xml_hint": 0, "subject": 0, "sender": 0, "attachment": 0}
            uid_regex = re.compile(rb'UID (\d+)')
            compiled_terms_debug = [term.normalized for term in compiled_terms]
            invoice_candidate_count = 0
            invoice_filtered_out = 0
            body_probe_count = 0
            body_probe_hits = 0
            # Limitar sondas de cuerpo para no atrasar el time-to-first-queue-event.
            # Se puede ajustar por env/settings si hace falta más cobertura.
            body_probe_budget = int(getattr(settings, "IMAP_BODY_PROBE_BUDGET", 600) or 600)
            
            total_candidates = len(candidate_uids)
            logger.info(
                "🔍 Analizando %s correos candidatos con matcher robusto | "
                "fallback_sender=%s fallback_attachment=%s",
                total_candidates,
                fallback_sender_match,
                fallback_attachment_match,
            )

            # Batch de FETCH configurable para acelerar "time-to-first-queue-event"
            # en rangos grandes. Valores más chicos -> feedback más temprano.
            fetch_batch_size = int(getattr(settings, "IMAP_SEARCH_FETCH_BATCH_SIZE", 100) or 100)
            fetch_batch_size = max(25, min(fetch_batch_size, 500))

            for start_idx in range(0, total_candidates, fetch_batch_size):
                batch_uids = candidate_uids[start_idx : start_idx + fetch_batch_size]
                uid_str = ",".join(batch_uids)
                batch_matched_items: List[Dict[str, Any]] = []

                # Siempre traer BODYSTRUCTURE para aplicar filtro inicial por señal de factura.
                fetch_query = '(BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])'

                status, fetch_data = self.conn.uid('FETCH', uid_str, fetch_query)
                
                if status != 'OK':
                    logger.error(f"Error fetching metadata batch: {status}")
                    continue
                
                for response_part in fetch_data:
                    if isinstance(response_part, tuple):
                        try:
                            # Parsear UID
                            msg_header = response_part[0]
                            uid_match = uid_regex.search(msg_header)
                            if not uid_match:
                                continue
                            uid = uid_match.group(1).decode()
                            
                            # Extraer headers
                            raw_headers = response_part[1]
                            msg_obj = email.message_from_bytes(raw_headers)
                            
                            subject_text = decode_mime_header(msg_obj.get('Subject', ''))
                            sender_text = decode_mime_header(msg_obj.get('From', ''))
                            date_str = msg_obj.get('Date', '')
                            
                            email_dt = None
                            if date_str:
                                try:
                                    email_dt = parsedate_to_datetime(date_str)
                                except Exception:
                                    pass

                            attachment_names = _extract_attachment_names_from_fetch_meta(msg_header)
                            fetch_meta_text = (
                                msg_header.decode("utf-8", errors="ignore")
                                if isinstance(msg_header, (bytes, bytearray))
                                else str(msg_header)
                            )
                            has_invoice_attachment = _has_invoice_attachment_hint(msg_header, attachment_names)
                            has_xml_attachment = _has_xml_attachment_hint(msg_header, attachment_names)
                            has_invoice_url = _has_invoice_url_hint(subject_text) or _has_invoice_url_hint(fetch_meta_text)
                            has_invoice_signal = has_invoice_attachment or has_invoice_url
                            has_xml_url = _has_xml_url_hint(subject_text) or _has_xml_url_hint(fetch_meta_text)
                            has_xml_signal = has_xml_attachment or has_xml_url

                            # Fallback XML: detectar URL XML en cuerpo con FETCH parcial.
                            if not has_xml_signal and body_probe_count < body_probe_budget:
                                body_probe_count += 1
                                if self._has_xml_url_in_body_snippet(uid):
                                    has_xml_signal = True
                                    body_probe_hits += 1

                            # Regla de negocio:
                            # 1) Si hay XML (adjunto o URL), encolar sí o sí.
                            # 2) Si NO hay XML, validar por términos configurados.
                            if has_xml_signal:
                                matched = True
                                matched_source = "xml_hint"
                                matched_term = "__xml_native__"
                                invoice_candidate_count += 1
                            else:
                                matched, matched_source, matched_term = match_email_candidate(
                                    subject=subject_text,
                                    sender=sender_text,
                                    attachment_names=attachment_names,
                                    terms=compiled_terms,
                                    fallback_sender_match=fallback_sender_match,
                                    fallback_attachment_match=fallback_attachment_match,
                                )
                                if not matched:
                                    invoice_filtered_out += 1
                                    continue
                            if matched:
                                if matched_source in source_counts:
                                    source_counts[matched_source] += 1
                                matched_doc = {
                                    "uid": uid,
                                    "subject": subject_text,
                                    "sender": sender_text,
                                    "date": email_dt,
                                    "has_invoice_signal": bool(has_invoice_signal),
                                    "has_xml_signal": bool(has_xml_signal),
                                    "match_source": matched_source,
                                    "matched_term": matched_term,
                                }
                                matched_items.append(matched_doc)
                                batch_matched_items.append(matched_doc)

                                # Flush incremental dentro del mismo batch para que
                                # la capa superior pueda encolar temprano.
                                if on_match_batch and len(batch_matched_items) >= 10:
                                    try:
                                        on_match_batch(batch_matched_items)
                                        batch_matched_items = []
                                    except Exception as cb_err:
                                        logger.error(f"Error en callback on_match_batch: {cb_err}")
                        except Exception as e:
                            logger.error(f"Error parseando metadatos de UID en batch: {e}")

                # Envío progresivo: permite que capas superiores encolen sin esperar
                # a que termine el análisis de TODO el rango.
                if on_match_batch and batch_matched_items:
                    try:
                        on_match_batch(batch_matched_items)
                    except Exception as cb_err:
                        logger.error(f"Error en callback on_match_batch: {cb_err}")

                logger.info(
                    "📊 Progreso matcher robusto: %s/%s candidatos analizados, %s matches acumulados",
                    min(start_idx + len(batch_uids), total_candidates),
                    total_candidates,
                    len(matched_items),
                )

            uids_with_subjects = matched_items
            logger.info(
                "✅ Filtrado local completado: %s correos | términos=%s | "
                "xml_candidates=%s filtered_out=%s body_probe=%s body_hits=%s | "
                "xml_hint=%s subject=%s sender=%s attachment=%s",
                len(uids_with_subjects),
                compiled_terms_debug,
                invoice_candidate_count,
                invoice_filtered_out,
                body_probe_count,
                body_probe_hits,
                source_counts["xml_hint"],
                source_counts["subject"],
                source_counts["sender"],
                source_counts["attachment"],
            )

        except Exception as e:
            logger.error(f"Error en estrategia Fetch-Python: {e}")
            return []

        return sorted(uids_with_subjects, key=lambda x: int(x['uid']), reverse=True)

    def fetch_rfc822_message_id(self, email_uid: str) -> Optional[str]:
        """
        Fetch ONLY the Message-ID header for a specific UID.
        Highly optimized for deduplication checks without downloading full body.
        """
        if not self.conn:
            return None
        try:
            status, data = self.conn.uid('FETCH', email_uid, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
            if status != 'OK' or not data:
                return None
            
            for item in data:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw_header = item[1]
                    # Parse using email parser for robustness
                    msg = email.message_from_bytes(raw_header)
                    msg_id = msg.get('Message-ID', '')
                    if msg_id:
                        return msg_id.strip()
            return None
        except Exception as e:
            logger.error(f"Error fetching Message-ID for UID {email_uid}: {e}")
            return None

    def fetch_message(self, email_uid: str) -> Optional[Message]:
        if not self.conn:
            return None
        try:
            # Aplicar timeout específico para fetch
            old_timeout = None
            if hasattr(self.conn, 'sock') and self.conn.sock:
                old_timeout = self.conn.sock.gettimeout()
                self.conn.sock.settimeout(60.0)  # 60 segundos para fetch (aumentado para adjuntos grandes)
            
            try:
                status, data = self.conn.uid('FETCH', email_uid, '(BODY.PEEK[])')
                # data esperado: [(b'<uid> (BODY[] {<len>}', b'<raw>'), b')']
                if status != 'OK' or not data:
                    logger.error(f"❌ Error al obtener el correo UID {email_uid}: {status} - Data: {data}")
                    return None
                # Busca el tuple con el contenido real
                for item in data:
                    if isinstance(item, tuple) and len(item) >= 2:
                        return email.message_from_bytes(item[1])
                        
                logger.error(f"❌ Formato inesperado en FETCH UID {email_uid}: {data!r}")
                return None
                
            except (socket.timeout, socket.error) as e:
                logger.error(f"Timeout/error de red en FETCH UID {email_uid}: {e}")
                return None
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                logger.error(f"Error IMAP en FETCH UID {email_uid}: {e}")
                return None
            finally:
                # Restaurar timeout original
                if old_timeout is not None and hasattr(self.conn, 'sock') and self.conn.sock:
                    try:
                        self.conn.sock.settimeout(old_timeout)
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"❌ Error inesperado al hacer FETCH UID {email_uid}: {e}")
            return None

    def mark_seen(self, email_uid: str) -> bool:
        if not self.conn:
            return False
        try:
            # Aplicar timeout específico para mark_seen
            old_timeout = None
            if hasattr(self.conn, 'sock') and self.conn.sock:
                old_timeout = self.conn.sock.gettimeout()
                self.conn.sock.settimeout(10.0)  # 10 segundos para mark_seen
            
            try:
                # ✅ Usar UID STORE
                status, _ = self.conn.uid('STORE', email_uid, '+FLAGS', '(\\Seen)')
                ok = status == 'OK'
                if ok:
                    logger.info(f"✅ Correo UID {email_uid} marcado como leído")
                else:
                    logger.error(f"❌ Error al marcar como leído UID {email_uid}: {status}")
                return ok
                
            except (socket.timeout, socket.error) as e:
                logger.error(f"Timeout/error de red al marcar como leído UID {email_uid}: {e}")
                return False
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                logger.error(f"Error IMAP al marcar como leído UID {email_uid}: {e}")
                return False
            finally:
                # Restaurar timeout original
                if old_timeout is not None and hasattr(self.conn, 'sock') and self.conn.sock:
                    try:
                        self.conn.sock.settimeout(old_timeout)
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"❌ Error inesperado al marcar el correo UID {email_uid} como leído: {str(e)}")
            return False
