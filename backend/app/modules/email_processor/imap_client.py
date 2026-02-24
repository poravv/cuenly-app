import imaplib
import email
import logging
import socket
import time
import re
from typing import Any, Dict, List, Optional, Set
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime

from .subject_matcher import compile_match_terms, match_email_candidate

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
                
                # Crear conexión con timeout de socket más agresivo
                try:
                    self.conn = imaplib.IMAP4_SSL(self.host, self.port)
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
            
            # Limitar a los N más recientes para evitar sobrecarga si hay miles
            # (aunque process-direct tiene su propio límite, aquí filtramos subjects)
            # Ordenamos descendente (más recientes primero)
            candidate_uids.sort(key=lambda x: int(x), reverse=True)
            # Analizar un máximo generoso para sincronización histórica o deep sync
            max_candidates = 10000 
            if len(candidate_uids) > max_candidates:
                 logger.info(f"⚠️ Limitando análisis de asuntos a los {max_candidates} correos más recientes (de {len(candidate_uids)} encontrados)")
                 candidate_uids = candidate_uids[:max_candidates]
            
            # 2. Fetch SUBJECTS/FROM/DATE en batch (y BODYSTRUCTURE si aplica fallback por adjunto)
            # Convertir lista de UIDs a string separado por comas para el fetch
            matched_items = []  # List of dicts
            source_counts = {"subject": 0, "sender": 0, "attachment": 0}
            uid_regex = re.compile(rb'UID (\d+)')
            compiled_terms_debug = [term.normalized for term in compiled_terms]
            
            total_candidates = len(candidate_uids)
            logger.info(
                "🔍 Analizando %s correos candidatos con matcher robusto | "
                "fallback_sender=%s fallback_attachment=%s",
                total_candidates,
                fallback_sender_match,
                fallback_attachment_match,
            )
            
            for start_idx in range(0, total_candidates, 500):
                batch_uids = candidate_uids[start_idx : start_idx + 500]
                uid_str = ",".join(batch_uids)

                fetch_query = '(BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])'
                if not fallback_attachment_match:
                    fetch_query = '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])'

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

                            attachment_names = []
                            if fallback_attachment_match:
                                attachment_names = _extract_attachment_names_from_fetch_meta(msg_header)

                            matched, matched_source, matched_term = match_email_candidate(
                                subject=subject_text,
                                sender=sender_text,
                                attachment_names=attachment_names,
                                terms=compiled_terms,
                                fallback_sender_match=fallback_sender_match,
                                fallback_attachment_match=fallback_attachment_match,
                            )
                            if matched:
                                if matched_source in source_counts:
                                    source_counts[matched_source] += 1
                                matched_items.append({
                                    "uid": uid,
                                    "subject": subject_text,
                                    "sender": sender_text,
                                    "date": email_dt,
                                    "match_source": matched_source,
                                    "matched_term": matched_term,
                                })
                        except Exception as e:
                            logger.error(f"Error parseando metadatos de UID en batch: {e}")

            uids_with_subjects = matched_items
            logger.info(
                "✅ Filtrado local completado: %s correos | términos=%s | "
                "subject=%s sender=%s attachment=%s",
                len(uids_with_subjects),
                compiled_terms_debug,
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
