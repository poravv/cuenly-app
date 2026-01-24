import imaplib
import email
import logging
import socket
import time
from typing import List, Optional, Set
import unicodedata
from email.header import decode_header
from email.message import Message
import os  # legacy references removed; kept for compatibility if needed

logger = logging.getLogger(__name__)

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

        # Sin términos: búsqueda simple
        if not subject_terms:
            try:
                typ, data = self.conn.uid('SEARCH', *base_flag_args)
                if typ == 'OK':
                    uids |= set(_decode_ids(data))
            except Exception as e:
                logger.error(f"UID SEARCH error sin términos: {e}")
            return sorted(uids, key=lambda x: int(x))

        # Con términos: búsqueda por cada término
        for term in subject_terms:
            if not term:
                continue
                
            term_str = str(term).strip()
            
            # Decidir si usar CHARSET UTF-8 (si hay caracteres no ASCII)
            use_utf8 = False
            try:
                term_str.encode('ascii')
            except UnicodeEncodeError:
                use_utf8 = True
            
                try:
                # Construir argumentos de búsqueda
                if use_utf8:
                    # Usar CHARSET UTF-8
                    # Para evitar que imaplib intente codificar a ASCII (y falle), enviamos bytes explícitos.
                    # Convertimos TODOS los argumentos a bytes para consistencia.
                    
                    term_bytes = f'"{term_str}"'.encode('utf-8')
                    
                    # Convertir base flags a bytes
                    args = [b'CHARSET', b'UTF-8']
                    for flag in base_flag_args:
                        args.append(flag.encode('ascii'))
                    
                    args.append(b'SUBJECT')
                    args.append(term_bytes)
                    
                else:
                    # Búsqueda ASCII estándar (imaplib maneja str -> ascii)
                    # Comillas dobles para soportar espacios en términos ASCII (ej "invoice pdf")
                    args = base_flag_args + ['SUBJECT', f'"{term_str}"']
                
                logger.debug(f"IMAP UID SEARCH args: {args} (UTF-8={use_utf8})")
                
                # Timeout protegido
                old_timeout = None
                if hasattr(self.conn, 'sock') and self.conn.sock:
                    old_timeout = self.conn.sock.gettimeout()
                    self.conn.sock.settimeout(20.0)
                
                try:
                    # Ejecutar búsqueda
                    typ, data = self.conn.uid('SEARCH', *args)

                    if typ == 'OK':
                        uids |= set(_decode_ids(data))
                    else:
                        logger.warning(f"UID SEARCH falló para term '{term_str}': {typ}")
                        
                except Exception as e:
                    logger.error(f"Error en UID SEARCH para '{term_str}': {e}")
                finally:
                    if old_timeout is not None and hasattr(self.conn, 'sock') and self.conn.sock:
                        try:
                            self.conn.sock.settimeout(old_timeout)
                        except:
                            pass
                            
            except Exception as e:
                logger.error(f"Error general procesando búsqueda para '{term}': {e}")

        return sorted(uids, key=lambda x: int(x))

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
