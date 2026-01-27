from __future__ import annotations
import base64
import logging

logger = logging.getLogger(__name__)

def pdf_to_base64_first_page(doc_path: str) -> str:
    """
    Convierte la primera página del PDF a JPEG base64 (300dpi aprox)
    O lee/redimensiona si es imagen (JPEG/PNG/WEBP) para optimizar tokens.
    """
    try:
        lower_path = doc_path.lower()
        if lower_path.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            from PIL import Image, ImageOps
            import io
            
            with Image.open(doc_path) as img:
                # Corregir orientación según EXIF (si existe)
                img = ImageOps.exif_transpose(img)
                
                # Convertir a RGB y aplicar autocontraste para mejorar fotos "feas"
                img = img.convert("RGB")
                try:
                    img = ImageOps.autocontrast(img, cutoff=0.5)
                except Exception:
                    pass  # Ignorar si falla el contraste
                
                # Redimensionar si es muy grande (max 2048x2048) para OpenAI vision
                max_dim = 2048
                if max(img.size) > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
                # Guardar como JPEG optimizado
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                return base64.b64encode(buf.getvalue()).decode("utf-8")
            
        import fitz  # PyMuPDF
        doc = fitz.open(doc_path)
        page = doc[0]
        # Matrix(2, 2) ~ 144dpi, Matrix(3, 3) ~ 216dpi
        # Usamos 2.5 para balance entre calidad OCR y tamaño
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
        img_bytes = pix.tobytes("jpeg")
        doc.close()
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        logger.error("Error convirtiendo documento a imagen base64: %s", e)
        raise

def ocr_from_base64_image(base64_image: str, lang: str = "spa") -> str:
    """
    OCR sobre imagen base64 (JPEG/PNG).
    Requiere Pillow + pytesseract + tesseract binario.
    """
    try:
        import io
        import pytesseract
        from PIL import Image

        image_bytes = base64.b64decode(base64_image)
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except Exception as e:
        logger.error("Error en OCR base64: %s", e)
        return ""