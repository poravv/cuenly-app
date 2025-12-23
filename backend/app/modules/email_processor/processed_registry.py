import json
import logging
import os
import threading
import time
from typing import Dict, Any

from app.config.settings import settings

logger = logging.getLogger(__name__)

_REGISTRY_PATH = (
    getattr(settings, "PROCESSED_EMAILS_FILE", "") or os.path.join(os.path.dirname(settings.TEMP_PDF_DIR), "processed_emails.json")
)
_TTL_SECONDS = int(getattr(settings, "PROCESSED_EMAIL_TTL_DAYS", 30)) * 24 * 60 * 60
_MAX_ENTRIES = int(getattr(settings, "PROCESSED_EMAIL_MAX_ENTRIES", 20000))

_lock = threading.Lock()
_registry: Dict[str, Dict[str, Any]] = {}
_loaded = False


def _ensure_parent_dir(path: str) -> None:
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo garantizar el directorio para el registro de correos procesados: {e}")


def _load() -> None:
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        _ensure_parent_dir(_REGISTRY_PATH)
        try:
            if os.path.exists(_REGISTRY_PATH):
                with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        _registry.update(data)
            _purge_locked()
            _loaded = True
        except Exception as e:
            logger.warning(f"⚠️ No se pudo cargar registro de correos procesados: {e}")
            _loaded = True  # evitar reintentos constantes


def _save_locked() -> None:
    try:
        tmp_path = _REGISTRY_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_registry, f)
        os.replace(tmp_path, _REGISTRY_PATH)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo guardar registro de correos procesados: {e}")


def _purge_locked() -> None:
    now = time.time()
    changed = False

    for key, meta in list(_registry.items()):
        ts = float(meta.get("ts", 0) or 0)
        if ts and now - ts > _TTL_SECONDS:
            _registry.pop(key, None)
            changed = True

    if len(_registry) > _MAX_ENTRIES:
        oldest = sorted(_registry.items(), key=lambda kv: float(kv[1].get("ts", 0) or 0))
        surplus = len(_registry) - _MAX_ENTRIES
        for k, _ in oldest[:surplus]:
            _registry.pop(k, None)
            changed = True

    if changed:
        _save_locked()


def build_key(email_uid: str, username: str, owner_email: str | None = None) -> str:
    owner = (owner_email or "").lower()
    return f"{owner}::{username or ''}::{email_uid}"


def was_processed(key: str) -> bool:
    _load()
    with _lock:
        _purge_locked()
        return key in _registry


def mark_processed(key: str, status: str = "done") -> None:
    _load()
    with _lock:
        _purge_locked()
        _registry[key] = {"ts": time.time(), "status": status}
        _purge_locked()
        _save_locked()
