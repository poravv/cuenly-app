import os
import re
import time
import uuid
import hashlib
import logging
import io
from datetime import datetime
from typing import Tuple, Optional, Union
from dataclasses import dataclass

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    Minio = None
    S3Error = None

from app.config.settings import settings

logger = logging.getLogger(__name__)

_FALLBACK_DIR = "/tmp/cuenlyapp/temp_pdfs"

@dataclass
class StoragePath:
    local_path: str
    minio_key: str = ""
    minio_url: str = "" # Signed or public URL (optional usage)

    def __str__(self):
        return self.local_path

def _ensure_dir(path: str) -> bool:
    """Crea el directorio y valida escritura básica."""
    try:
        os.makedirs(path, exist_ok=True)
        # Verificar escritura
        test_path = os.path.join(path, ".write_test")
        try:
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            return True
        except FileNotFoundError:
            # Retry una vez si la creación fue tardía (por fs lento)
            try:
                os.makedirs(path, exist_ok=True)
                with open(test_path, "w") as f:
                    f.write("ok")
                os.remove(test_path)
                return True
            except Exception as e:
                logger.error(f"❌ No se pudo crear/escribir en {path} tras reintento: {e}")
                return False
    except PermissionError as e:
        logger.error(f"❌ Permiso denegado en {path}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ No se pudo crear/escribir en {path}: {e}")
        return False

def ensure_dirs() -> str:
    """Garantiza que exista un directorio usable para temporales.
    Intenta settings.TEMP_PDF_DIR y cae a /tmp si falla.
    """
    configured = settings.TEMP_PDF_DIR
    if _ensure_dir(configured):
        return configured

    logger.warning(f"⚠️ Usando directorio fallback para temporales: {_FALLBACK_DIR}")
    if _ensure_dir(_FALLBACK_DIR):
        # Persistir cambio en runtime para evitar logs repetitivos
        try:
            settings.TEMP_PDF_DIR = _FALLBACK_DIR
        except Exception:
            pass
        return _FALLBACK_DIR
    # Si todo falla, devolver el configurado aunque no funcione para que el llamador pueda manejarlo
    return configured

def sanitize_filename(filename: str, force_pdf: bool = False) -> str:
    """Limpia el nombre y fuerza .pdf si se requiere."""
    safe = re.sub(r'[<>:"/\\|?*]', '_', filename or "")
    safe = re.sub(r'[\x00-\x1f\x7f-\x9f]', '_', safe)
    safe = re.sub(r'\s+', '_', safe.strip())
    name, ext = os.path.splitext(safe)
    if len(name) > 100:
        name = name[:100]
    if force_pdf and not ext.lower().endswith(".pdf"):
        ext = ".pdf"
    return f"{name}{ext or ''}"

def unique_name(clean_name: str) -> str:
    """timestamp + uuid + base."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    uid = uuid.uuid4().hex[:8]
    name, ext = os.path.splitext(clean_name)
    return f"{ts}_{uid}_{name}{ext}"

def _optimize_image(content: bytes) -> bytes:
    """Redimensiona y optimiza imagen para reducir tamaño (max 2048px, JPEG q='85')."""
    try:
        from PIL import Image, ImageOps, ImageFilter
        import io
        
        # Si es muy pequeño (<1MB), quizás no vale la pena el costo de CPU
        # Pero si queremos estandarizar (ej. PNG a JPEG o rotación), lo hacemos igual.
        
        with Image.open(io.BytesIO(content)) as img:
            # 1. Corregir orientación
            img = ImageOps.exif_transpose(img)
            
            # 2. Convertir a RGB
            img = img.convert("RGB")
            
            # 3. Redimensionar si es muy grande (Aumentado a 2500 para mejor OCR)
            max_dim = 2500
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            # 4. Guardar como JPEG
            buf = io.BytesIO()
            # Conservar calidad alta, sin optimización agresiva de filtros
            img.save(buf, format="JPEG", quality=85, optimize=True)
            return buf.getvalue()
    except Exception as e:
        logger.warning(f"⚠️ Falló optimización de imagen en storage: {e}")
        return content

def _resolve_base_dir() -> str:
    # Intentar usar el configurado; si no se puede escribir, usar fallback
    return ensure_dirs()

def upload_to_minio(content: bytes, filename: str, owner_email: Optional[str] = None, date_obj: Optional[datetime] = None) -> Tuple[str, str]:
    """Sube archivo a MinIO y retorna (key, url). Si falla retorna ('', '')."""
    if not Minio or not settings.MINIO_ACCESS_KEY:
        return "", ""

    try:
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION
        )

        # Structure: /YYYY/user_id/month/filename
        # user_id sanitizado
        clean_user = re.sub(r"[^a-zA-Z0-9_\-\.@]", "_", owner_email or "anonymous")
        dt = date_obj or datetime.now()
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
        clean_fname = sanitize_filename(filename)
        
        # Generar nombre único si es necesario, pero intentamos mantener nombre original si se puede
        # Agregamos timestamp minúsculo al principio para evitar colisiones en nombres comunes
        ts_small = datetime.now().strftime("%d%H%M")
        object_name = f"{year}/{clean_user}/{month}/{ts_small}_{clean_fname}"

        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
        
        # Determine Content-Type
        lname = filename.lower()
        if lname.endswith(".pdf"):
            ctype = "application/pdf"
        elif lname.endswith(".xml"):
            ctype = "application/xml"
        elif lname.endswith((".jpg", ".jpeg")):
            ctype = "image/jpeg"
        elif lname.endswith(".png"):
            ctype = "image/png"
        elif lname.endswith(".webp"):
            ctype = "image/webp"
        else:
            ctype = "application/octet-stream"

        # Upload
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            io.BytesIO(content),
            len(content),
            content_type=ctype
        )
        
        logger.info(f"☁️ Subido a MinIO: {object_name}")
        return object_name, "" # URL will be generated on demand via presigned url
        
    except Exception as e:
        logger.error(f"❌ MinIO upload error: {e}")
        return "", ""

def save_binary(
    content: bytes, 
    filename: str, 
    force_pdf: bool = False, 
    owner_email: Optional[str] = None, 
    date_obj: Optional[datetime] = None
) -> StoragePath:
    """Guarda bytes en /temp_pdfs y opcionalmente en MinIO. Retorna StoragePath."""
    try:
        # 0. Optimizar si es imagen y no forzamos PDF
        if not force_pdf and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            content = _optimize_image(content)
            # Cambiar extensión a .jpeg si se optimizó
            if not filename.lower().endswith(('.jpg', '.jpeg')):
                base, _ = os.path.splitext(filename)
                filename = f"{base}.jpeg"

        # 1. Guardar Localmente (Temp)
        base_dir = ensure_dirs()
        clean = sanitize_filename(filename, force_pdf=force_pdf)
        candidate = unique_name(clean)
        local_path = os.path.join(base_dir, candidate)
        
        with open(local_path, "wb") as f:
            f.write(content)
        logger.info(f"🗂 Archivo temp guardado (size={len(content)}): {local_path}")
        
        # 2. Subir a MinIO (si configurado)
        minio_key = ""
        if settings.MINIO_ACCESS_KEY:
             minio_key, _ = upload_to_minio(content, clean, owner_email, date_obj)
             
        return StoragePath(local_path=local_path, minio_key=minio_key)
        
    except Exception as e:
        logger.error(f"❌ Error al guardar archivo {filename}: {e}")
        return StoragePath(local_path="")

def cleanup_temp_dir(older_than_hours: int = 24) -> int:
    """Elimina archivos en el dir temporal más viejo que X horas."""
    import time
    base_dir = _resolve_base_dir()
    cutoff = time.time() - older_than_hours * 3600
    removed = 0
    try:
        for name in os.listdir(base_dir):
            p = os.path.join(base_dir, name)
            try:
                if not os.path.isfile(p):
                    continue
                st = os.stat(p)
                if st.st_mtime < cutoff:
                    os.remove(p)
                    removed += 1
            except Exception:
                continue
    except Exception:
        pass
    return removed

def filename_from_url(url: str, extension: str) -> str:
    """Intenta construir nombre informativo desde la URL; fallback a dominio+hash."""
    ts = int(time.time())
    from urllib.parse import urlparse, parse_qs
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)
        ruc = _first_contains(qs, "ruc")
        cdc = _first_contains_any(qs, ["cdc", "codigo", "code", "document", "doc"])
        num = _first_contains_any(qs, ["factura", "invoice", "numero", "number", "num"])

        parts = []
        if ruc: parts.append(f"ruc_{_clean_id(ruc)}")
        if cdc: parts.append(f"cdc_{_clean_id(cdc)[:12]}")
        if num: parts.append(f"num_{_clean_id(num)[:10]}")

        if parts:
            return f"factura_{'_'.join(parts)}_{ts}.{extension}"
    except Exception as e:
        logger.warning(f"Error parseando URL para nombre: {e}")

    try:
        p = urlparse(url)
        domain = (p.netloc or "unknown").replace(".", "_").replace(":", "_")[:20]
        domain = re.sub(r'[^\w\-_]', '', domain)
    except:
        domain = "unknown"
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"factura_{domain}_{url_hash}_{ts}.{extension}"

def _first_contains(qs: dict, key: str) -> str:
    for k, v in qs.items():
        if key in k.lower() and v:
            return v[0]
    return ""

def _first_contains_any(qs: dict, keys) -> str:
    for k, v in qs.items():
        lk = k.lower()
        if any(kk in lk for kk in keys) and v:
            return v[0]
    return ""

def _clean_id(s: str) -> str:
    return re.sub(r"[^\w\-]", "", s or "")
