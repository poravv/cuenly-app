"""
Firebase Admin SDK — Singleton de inicialización.

Soporta dos modos de autenticación:
1. FIREBASE_SERVICE_ACCOUNT_JSON: JSON de cuenta de servicio (directo o en base64).
2. GOOGLE_APPLICATION_CREDENTIALS: Credenciales de aplicación por defecto (ADC).
"""
import json
import logging
import base64
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from app.config.settings import settings

logger = logging.getLogger(__name__)

_firebase_app: Optional[firebase_admin.App] = None
_firestore_client = None


def get_firebase_app() -> firebase_admin.App:
    """
    Obtiene (o inicializa) el Firebase Admin App singleton.

    Returns:
        firebase_admin.App: La instancia inicializada.

    Raises:
        Exception: Si las credenciales son inválidas o Firebase falla al arrancar.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    service_account_json = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if service_account_json:
        # Puede venir como JSON directo o como base64
        try:
            sa_dict = json.loads(service_account_json)
        except json.JSONDecodeError:
            sa_dict = json.loads(base64.b64decode(service_account_json).decode())
        cred = credentials.Certificate(sa_dict)
    else:
        # Fallback: GOOGLE_APPLICATION_CREDENTIALS env var (ADC)
        cred = credentials.ApplicationDefault()

    _firebase_app = firebase_admin.initialize_app(cred, {
        "projectId": getattr(settings, "FIREBASE_PROJECT_ID", "cuenly-app")
    })
    logger.info(
        "Firebase Admin SDK inicializado (proyecto: %s)",
        getattr(settings, "FIREBASE_PROJECT_ID", "cuenly-app"),
    )

    return _firebase_app


def get_firestore_client():
    """
    Obtiene el cliente Firestore singleton.

    Returns:
        google.cloud.firestore.Client: Cliente Firestore listo para usar.
    """
    global _firestore_client
    if _firestore_client is None:
        get_firebase_app()  # Garantiza inicialización del app
        _firestore_client = firestore.client()
    return _firestore_client
