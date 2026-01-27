import logging
import uuid
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from app.config.settings import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "email_configs"


def _get_client() -> MongoClient:
    mongo_url = getattr(settings, "MONGODB_URL", None) or "mongodb://localhost:27017/"
    client = MongoClient(
        mongo_url,
        serverSelectionTimeoutMS=60000,
        connectTimeoutMS=60000,
        socketTimeoutMS=120000,
        maxPoolSize=30,  # Aumentado para mejor concurrencia
        minPoolSize=3,   # Mínimo más alto para conexiones ready
    )
    # smoke test
    client.admin.command("ping")
    return client


def _get_collection() -> Collection:
    client = _get_client()
    db_name = getattr(settings, "MONGODB_DATABASE", "cuenlyapp_warehouse")
    db = client[db_name]
    coll = db[COLLECTION_NAME]
    try:
        coll.create_index("username")
        coll.create_index([("enabled", 1)])
        coll.create_index([("provider", 1)])
    except Exception:
        pass
    return coll


def list_configs(include_password: bool = False, owner_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all email configurations. Password is omitted by default."""
    coll = _get_collection()
    query: Dict[str, Any] = {}
    if owner_email:
        query['owner_email'] = owner_email.lower()
    docs = list(coll.find(query))
    results: List[Dict[str, Any]] = []
    for d in docs:
        item = {
            "id": str(d.get("_id")),
            "name": d.get("name") or "",
            "host": d.get("host") or "",
            "port": int(d.get("port") or 993),
            "username": d.get("username") or "",
            "use_ssl": bool(d.get("use_ssl", True)),
            "search_criteria": d.get("search_criteria") or "UNSEEN",
            "search_terms": d.get("search_terms") or [],
            "provider": d.get("provider") or "other",
            "enabled": bool(d.get("enabled", True)),
            # OAuth fields
            "auth_type": d.get("auth_type") or "password",
            "access_token": d.get("access_token") or "",
            "refresh_token": d.get("refresh_token") or "",
            "token_expiry": d.get("token_expiry") or "",
        }
        if include_password:
            item["password"] = d.get("password") or ""
        results.append(item)
    return results


def get_enabled_configs(include_password: bool = True, owner_email: Optional[str] = None, check_trial: bool = False, refresh_oauth_tokens: bool = True) -> List[Dict[str, Any]]:
    coll = _get_collection()
    q: Dict[str, Any] = {"enabled": True}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    docs = list(coll.find(q))
    configs = []
    
    # Si se solicita verificación de trial, filtrar por usuarios con acceso válido
    if check_trial:
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
    
    # OAuth manager para refrescar tokens expirados
    oauth_manager = None
    if refresh_oauth_tokens:
        try:
            from app.modules.oauth.google_oauth import get_google_oauth_manager
            oauth_manager = get_google_oauth_manager()
        except Exception as e:
            logger.warning(f"No se pudo cargar OAuth manager: {e}")
    
    for d in docs:
        # Verificar trial si está habilitado
        if check_trial:
            config_owner = d.get('owner_email', '').lower()
            if config_owner:
                trial_info = user_repo.get_trial_info(config_owner)
                if trial_info['is_trial_user'] and trial_info['trial_expired']:
                    logger.info(f"Omitiendo configuración de {config_owner} - trial expirado")
                    continue
        
        # Obtener tokens OAuth actuales
        auth_type = d.get("auth_type") or "password"
        access_token = d.get("access_token") or ""
        token_expiry_str = d.get("token_expiry") or ""
        refresh_token = d.get("refresh_token") or ""
        config_id = str(d.get("_id"))
        username = d.get("username") or ""
        
        # 🔄 AUTO-REFRESH: Si es OAuth2 y el token está expirado, refrescarlo
        if refresh_oauth_tokens and oauth_manager and auth_type == "oauth2" and refresh_token:
            try:
                from datetime import datetime, timezone
                token_expiry = None
                if token_expiry_str:
                    try:
                        # Manejar varios formatos de fecha ISO
                        expiry_str = token_expiry_str.replace('Z', '+00:00')
                        if '+' not in expiry_str and '-' not in expiry_str[-6:]:
                            # Sin timezone, asumir UTC
                            token_expiry = datetime.fromisoformat(expiry_str)
                        else:
                            # Con timezone
                            token_expiry = datetime.fromisoformat(expiry_str)
                            # Convertir a naive UTC para comparar con utcnow()
                            if token_expiry.tzinfo is not None:
                                token_expiry = token_expiry.replace(tzinfo=None)
                    except Exception as parse_err:
                        logger.warning(f"Error parseando token_expiry '{token_expiry_str}': {parse_err}")
                        token_expiry = None
                
                is_expired = oauth_manager.is_token_expired(token_expiry)
                logger.info(f"🔍 OAuth2 check para {username}: token_expiry={token_expiry}, is_expired={is_expired}")
                
                if is_expired:
                    logger.info(f"🔄 Token OAuth2 expirado para {username}, refrescando...")
                    try:
                        tokens = oauth_manager.refresh_access_token_sync(refresh_token)
                        new_access_token = tokens.get("access_token")
                        expires_in = tokens.get("expires_in", 3600)
                        new_expiry = oauth_manager.calculate_token_expiry(expires_in)
                        
                        # Actualizar en la base de datos
                        coll.update_one(
                            {"_id": config_id},
                            {"$set": {
                                "access_token": new_access_token,
                                "token_expiry": new_expiry.isoformat()
                            }}
                        )
                        
                        # Usar el nuevo token
                        access_token = new_access_token
                        token_expiry_str = new_expiry.isoformat()
                        logger.info(f"✅ Token OAuth2 refrescado exitosamente para {username}")
                        
                    except Exception as refresh_error:
                        logger.error(f"❌ Error refrescando token OAuth2 para {username}: {refresh_error}")
                        # Continuar con el token expirado, la conexión fallará
                        
            except Exception as e:
                logger.warning(f"Error verificando expiración de token para {username}: {e}")
        
        cfg = {
            "id": config_id,
            "name": d.get("name") or "",
            "host": d.get("host") or "",
            "port": int(d.get("port") or 993),
            "username": username,
            "use_ssl": bool(d.get("use_ssl", True)),
            "search_criteria": d.get("search_criteria") or "UNSEEN",
            "search_terms": d.get("search_terms") or [],
            "provider": d.get("provider") or "other",
            "enabled": True,
            "owner_email": d.get("owner_email", ""),
            # OAuth fields (posiblemente actualizados)
            "auth_type": auth_type,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": token_expiry_str,
        }
        if include_password:
            cfg["password"] = d.get("password") or ""
        configs.append(cfg)
    return configs


def create_config(data: Dict[str, Any], owner_email: Optional[str] = None) -> str:
    coll = _get_collection()
    payload = {
        "_id": data.get("id") or uuid.uuid4().hex,
        "name": data.get("name") or data.get("username") or "",
        "host": data.get("host") or "",
        "port": int(data.get("port") or 993),
        "username": data.get("username") or "",
        "password": data.get("password") or "",
        "use_ssl": bool(data.get("use_ssl", True)),
        "search_criteria": data.get("search_criteria") or "UNSEEN",
        "search_terms": data.get("search_terms") or [],
        "provider": data.get("provider") or "other",
        "enabled": bool(data.get("enabled", True)),
        "owner_email": (owner_email or data.get("owner_email") or "").lower(),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        # OAuth fields
        "auth_type": data.get("auth_type") or "password",
        "access_token": data.get("access_token") or "",
        "refresh_token": data.get("refresh_token") or "",
        "token_expiry": data.get("token_expiry") or "",
    }
    coll.insert_one(payload)
    return str(payload["_id"]) 


def update_config(config_id: str, data: Dict[str, Any], owner_email: Optional[str] = None) -> bool:
    coll = _get_collection()
    updates = {}
    for key in [
        "name",
        "host",
        "port",
        "username",
        "password",
        "use_ssl",
        "search_criteria",
        "search_terms",
        "provider",
        "enabled",
        "updated_at",
        # OAuth fields
        "auth_type",
        "access_token",
        "refresh_token",
        "token_expiry",
    ]:
        if key in data:
            updates[key] = data[key]
    if not updates:
        return False
    q = {"_id": config_id}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    res = coll.update_one(q, {"$set": updates})
    return res.matched_count > 0


def delete_config(config_id: str, owner_email: Optional[str] = None) -> bool:
    coll = _get_collection()
    q = {"_id": config_id}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    res = coll.delete_one(q)
    return res.deleted_count > 0


def set_enabled(config_id: str, enabled: bool, owner_email: Optional[str] = None) -> bool:
    coll = _get_collection()
    q = {"_id": config_id}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    res = coll.update_one(q, {"$set": {"enabled": bool(enabled)}})
    return res.matched_count > 0


def toggle_enabled(config_id: str, owner_email: Optional[str] = None) -> Optional[bool]:
    coll = _get_collection()
    q = {"_id": config_id}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    doc = coll.find_one(q, {"enabled": 1})
    if not doc:
        return None
    new_val = not bool(doc.get("enabled", True))
    coll.update_one(q, {"$set": {"enabled": new_val}})
    return new_val


def get_by_id(config_id: str, include_password: bool = True, owner_email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    coll = _get_collection()
    projection = None if include_password else {"password": 0}
    q = {"_id": config_id}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    d = coll.find_one(q, projection)
    if not d:
        return None
    return {
        "id": str(d.get("_id")),
        "name": d.get("name"),
        "host": d.get("host"),
        "port": int(d.get("port", 993)),
        "username": d.get("username"),
        "password": d.get("password") if include_password else None,
        "use_ssl": bool(d.get("use_ssl", True)),
        "search_criteria": d.get("search_criteria") or "UNSEEN",
        "search_terms": d.get("search_terms") or [],
        "provider": d.get("provider") or "other",
        "enabled": bool(d.get("enabled", True)),
        # OAuth fields
        "auth_type": d.get("auth_type") or "password",
        "access_token": d.get("access_token") or "",
        "refresh_token": d.get("refresh_token") or "",
        "token_expiry": d.get("token_expiry") or "",
    }


def get_by_username(username: str, include_password: bool = True, owner_email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    coll = _get_collection()
    projection = None if include_password else {"password": 0}
    q = {"username": username}
    if owner_email:
        q['owner_email'] = owner_email.lower()
    d = coll.find_one(q, projection)
    if not d:
        return None
    return {
        "id": str(d.get("_id")),
        "name": d.get("name"),
        "host": d.get("host"),
        "port": int(d.get("port", 993)),
        "username": d.get("username"),
        "password": d.get("password") if include_password else None,
        "use_ssl": bool(d.get("use_ssl", True)),
        "search_criteria": d.get("search_criteria") or "UNSEEN",
        "search_terms": d.get("search_terms") or [],
        "provider": d.get("provider") or "other",
        "enabled": bool(d.get("enabled", True)),
        # OAuth fields
        "auth_type": d.get("auth_type") or "password",
        "access_token": d.get("access_token") or "",
        "refresh_token": d.get("refresh_token") or "",
        "token_expiry": d.get("token_expiry") or "",
    }


def count_configs_by_owner(owner_email: str) -> int:
    """
    Cuenta cuántas configuraciones de correo tiene un usuario.
    Usado para validar límite de cuentas por plan.
    """
    coll = _get_collection()
    return coll.count_documents({"owner_email": owner_email.lower()})
