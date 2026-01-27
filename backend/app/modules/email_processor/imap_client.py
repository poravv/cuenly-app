import imaplib2 as imaplib
import email
import logging
import socket
import time
import re
from typing import List, Optional, Set
import unicodedata
from email.header import decode_header
from email.message import Message
import os  # legacy references removed; kept for compatibility if needed

logger = logging.getLogger(__name__)


def remove_accents(input_str: str) -> str:
    """Elimina acentos y caracteres especiales para normalizar a ASCII."""
    if not input_str:
        return ""
    # Normalizar unicode caracteres compuestos
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    # Filtrar caracteres non-spacing mark y codificar a ASCII
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

class IMAPClient:
    """
    Envoltura mínima: conecta, busca por asunto, fetch por UID y marca como leído por UID.
    Pensado para cPanel y Gmail. (Asumiendo términos SIN acentos en .env)
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

    def search(self, subject_terms: List[str], unread_only: Optional[bool] = None, since_date=None, before_date=None) -> List[str]:
        """
        Devuelve UIDs de correos que coincidan con cualquiera de los términos de asunto.
        El parámetro unread_only controla si buscar solo no leídos (True) o todos (False).
        El parámetro since_date filtra correos desde una fecha específica.
        Usa CHARSET UTF-8 para soportar acentos y caracteres especiales correctamente.
        """
        if not self.conn and not self.connect():
            return []

        if unread_only is None:
            unread_only = True
        
        # Base flags
        base_flag_args = ['UNSEEN'] if unread_only else ['ALL']
        
        # Filtros de fecha
        if since_date:
            from datetime import datetime
            date_str = since_date.strftime("%d-%b-%Y")
            base_flag_args.append('SINCE')
            base_flag_args.append(date_str)
        
        if before_date:
            from datetime import datetime
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

        if not subject_terms:
            # Sin términos: búsqueda simple sin filtrado de asunto
            try:
                typ, data = self.conn.uid('SEARCH', *base_flag_args)
                if typ == 'OK':
                    uids |= set(_decode_ids(data))
            except Exception as e:
                logger.error(f"UID SEARCH error sin términos: {e}")
            return sorted(uids, key=lambda x: int(x))

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
            # Analizar un máximo razonable de candidatos (ej. 200) para no colgar el fetch
            # Si el usuario tiene 5000 correos sin leer, solo miraremos los 200 más recientes.
            max_candidates = 200
            if len(candidate_uids) > max_candidates:
                 logger.info(f"Limstando análisis de asuntos a los {max_candidates} correos más recientes (de {len(candidate_uids)} encontrados)")
                 candidate_uids = candidate_uids[:max_candidates]
            
            # 2. Fetch SUBJECTS en batch
            # Convertir lista de UIDs a string separado por comas para el fetch
            uid_str = ",".join(candidate_uids)
            # Descargar solo cabeceras SUBJECT
            status, fetch_data = self.conn.uid('FETCH', uid_str, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
            
            if status != 'OK':
                logger.error(f"Error fetching subjects: {status}")
                return []
            
            # 3. Procesar y Filtrar
            # Normalizar términos de búsqueda
            normalized_terms = [remove_accents(t).lower() for t in subject_terms if t]
            
            matched_uids = set()
            
            for response_part in fetch_data:
                if isinstance(response_part, tuple):
                    # Estructura típica: (b'UID (BODY[HEADER.FIELDS (SUBJECT)] {len}', b'Subject: ...')
                    # Necesitamos parsear el UID y el Subject
                    
                    try:
                        # Parsear UID de la cabecera de respuesta
                        msg_header = response_part[0] # b'123 (UID 456 BODY...)'
                        # Extraer UID usando regex o split
                        # imaplib devuelve: b'seq (UID uid BODY...)'
                        uid_match = re.search(rb'UID (\d+)', msg_header)
                        if not uid_match:
                            continue
                        uid = uid_match.group(1).decode()
                        
                        # Extraer Subject cuerpo
                        raw_subject = response_part[1]
                        # Decodificar Subject MIME (ej: =?UTF-8?B?...)
                        subject_obj = email.message_from_bytes(raw_subject)
                        subject_header = subject_obj.get('Subject', '')
                        
                        # Decodificar fragmentos MIME
                        decoded_fragments = decode_header(subject_header)
                        subject_text = ""
                        for fragment, charset in decoded_fragments:
                            if isinstance(fragment, bytes):
                                try:
                                    if charset:
                                        subject_text += fragment.decode(charset, errors='replace')
                                    else:
                                        subject_text += fragment.decode('utf-8', errors='replace')
                                except LookupError:
                                    subject_text += fragment.decode('utf-8', errors='replace')
                            else:
                                subject_text += str(fragment)
                        
                        # Normalizar subject del correo
                        subject_normalized = remove_accents(subject_text).lower()
                        
                        # Verificar coincidencias
                        for term in normalized_terms:
                            if term in subject_normalized:
                                logger.debug(f"✅ Match encontrado! term='{term}' in subject='{subject_normalized}' (UID: {uid})")
                                matched_uids.add(uid)
                                break # Basta con que coincida uno
                                
                    except Exception as e:
                        logger.warning(f"Error procesando header de mensaje: {e}")
                        continue

            uids = matched_uids
            logger.info(f"Filtrado local completado: {len(uids)} correos coinciden con términos {normalized_terms}")

        except Exception as e:
            logger.error(f"Error en estrategia Fetch-Python: {e}")
            return []

        return sorted(list(uids), key=lambda x: int(x))

    def fetch_message(self, email_uid: str) -> Optional[Message]:
        if not self.conn:
            return None
        try:
            # Aplicar timeout específico para fetch
            old_timeout = None
            if hasattr(self.conn, 'sock') and self.conn.sock:
                old_timeout = self.conn.sock.gettimeout()
                self.conn.sock.settimeout(20.0)  # 20 segundos para fetch
            
            try:
                status, data = self.conn.uid('FETCH', email_uid, '(RFC822)')
                # data esperado: [(b'<uid> (RFC822 {<len>}', b'<raw>'), b')']
                if status != 'OK' or not data:
                    logger.error(f"❌ Error al obtener el correo UID {email_uid}: {status}")
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


def decode_mime_header(header: str) -> str:
    if not header:
        return ""
    try:
        parts = []
        for part, enc in decode_header(header):
            if isinstance(part, bytes):
                parts.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                parts.append(str(part))
        return "".join(parts)
    except Exception as e:
        logger.warning(f"Error al decodificar encabezado '{header}': {str(e)}")
        return header
