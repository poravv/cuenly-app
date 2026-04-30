"""
Endpoints de configuración de cuentas de correo IMAP y OAuth Google.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import logging

from app.api.deps import _get_current_user
from app.models.models import MultiEmailConfig, EmailConfigUpdate
from app.repositories.subscription_repository import SubscriptionRepository
from app.modules.email_processor.config_store import (
    list_configs as db_list_configs,
    create_config as db_create_config,
    update_config as db_update_config,
    delete_config as db_delete_config,
    set_enabled as db_set_enabled,
    toggle_enabled as db_toggle_enabled,
    get_by_id as db_get_by_id,
    get_by_username as db_get_by_username,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class ToggleEnabledPayload(BaseModel):
    enabled: bool


@router.post("/email-config/test")
async def test_email_config(config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Prueba la conexión a una configuración de correo.
    
    Args:
        config: Configuración de correo a probar
        
    Returns:
        dict: Resultado de la prueba
    """
    try:
        from app.modules.email_processor.email_processor import EmailProcessor
        from app.models.models import EmailConfig
        
        # Resolver password ausente con DB por id o username
        pwd = config.password
        if not pwd:
            db_cfg = None
            owner_email = (user.get('email') or '').lower()
            if config.id:
                db_cfg = db_get_by_id(config.id, include_password=True, owner_email=owner_email)
            if not db_cfg and config.username:
                db_cfg = db_get_by_username(config.username, include_password=True, owner_email=owner_email)
            if db_cfg and db_cfg.get("password"):
                pwd = db_cfg.get("password")

        # Crear configuración temporal para probar
        test_config = EmailConfig(
            host=config.host,
            port=config.port,
            username=config.username,
            password=pwd or "",
            search_criteria=config.search_criteria,
            search_terms=config.search_terms or [],
            search_synonyms=config.search_synonyms or {},
            fallback_sender_match=bool(config.fallback_sender_match),
            fallback_attachment_match=bool(config.fallback_attachment_match),
        )
        
        # Crear procesador temporal
        processor = EmailProcessor(test_config)
        
        # Intentar conectar
        success = processor.connect()
        processor.disconnect()
        
        if success:
            return {"success": True, "message": "Conexión exitosa"}
        else:
            return {"success": False, "message": "Error al conectar"}
            
    except Exception as e:
        logger.error(f"Error al probar configuración de correo: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}

@router.post("/email-configs/{config_id}/test")
async def test_email_config_by_id(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """Prueba una configuración guardada, identificada por su ID en MongoDB. Soporta OAuth2."""
    try:
        from app.modules.email_processor.imap_client import IMAPClient
        from app.modules.oauth.google_oauth import get_google_oauth_manager

        db_cfg = db_get_by_id(config_id, include_password=True, owner_email=(user.get('email') or '').lower())
        if not db_cfg:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        auth_type = db_cfg.get("auth_type", "password")
        access_token = db_cfg.get("access_token")
        
        # For OAuth configs, check if token needs refresh
        if auth_type == "oauth2" and access_token:
            token_expiry_str = db_cfg.get("token_expiry")
            if token_expiry_str:
                from datetime import datetime
                try:
                    token_expiry = datetime.fromisoformat(token_expiry_str.replace('Z', '+00:00'))
                    oauth_manager = get_google_oauth_manager()
                    if oauth_manager.is_token_expired(token_expiry):
                        # Try to refresh the token
                        refresh_token = db_cfg.get("refresh_token")
                        if refresh_token:
                            try:
                                tokens = await oauth_manager.refresh_access_token(refresh_token)
                                access_token = tokens.get("access_token")
                                # Update token in DB
                                new_expiry = oauth_manager.calculate_token_expiry(tokens.get("expires_in", 3600))
                                db_update_config(config_id, {
                                    "access_token": access_token,
                                    "token_expiry": new_expiry.isoformat()
                                }, owner_email=(user.get('email') or '').lower())
                            except Exception as e:
                                logger.warning(f"Could not refresh token: {e}")
                                return {"success": False, "message": "Token OAuth expirado. Por favor, reconecta la cuenta."}
                except Exception as e:
                    logger.warning(f"Error parsing token expiry: {e}")

        # Create IMAP client with OAuth support
        client = IMAPClient(
            host=db_cfg.get("host"),
            port=int(db_cfg.get("port", 993)),
            username=db_cfg.get("username"),
            password=db_cfg.get("password") or "",
            mailbox="INBOX",
            auth_type=auth_type,
            access_token=access_token if auth_type == "oauth2" else None
        )
        
        success = client.connect()
        client.close()

        if success:
            auth_method = "OAuth2" if auth_type == "oauth2" else "contraseña"
            return {"success": True, "message": f"Conexión exitosa ({auth_method})"}
        else:
            return {"success": False, "message": "Error al conectar"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al probar configuración por ID: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# -----------------------------
# Email Config CRUD (MongoDB)
# -----------------------------

@router.get("/email-configs")
async def list_email_configs(user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        owner_email = (user.get('email') or '').lower()
        cfgs = db_list_configs(include_password=False, owner_email=owner_email)
        
        # Obtener límites del plan para enviar al frontend
        from app.modules.email_processor.config_store import count_configs_by_owner
        from app.repositories.subscription_repository import SubscriptionRepository
        
        current_count = len(cfgs)
        sub_repo = SubscriptionRepository()
        subscription = await sub_repo.get_user_active_subscription(owner_email)
        
        max_accounts = 1  # Default para usuarios sin plan
        if subscription:
            plan_features = subscription.get('plan_features', {})
            max_accounts = plan_features.get('max_email_accounts', 2)
        
        return {
            "success": True, 
            "configs": cfgs, 
            "total": current_count,
            "max_allowed": max_accounts,
            "can_add_more": max_accounts == -1 or current_count < max_accounts,
            "has_active_plan": bool(subscription)
        }
    except Exception as e:
        logger.error(f"Error listando configuraciones de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudieron obtener configuraciones")


@router.post("/email-configs")
async def create_email_config(config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        owner_email = (user.get('email') or '').lower()
        
        # Validar que password esté presente al crear
        if not config.password:
            raise HTTPException(status_code=400, detail="La contraseña es obligatoria al crear una cuenta")
        
        # ✅ VALIDAR LÍMITE DE CUENTAS DE CORREO POR PLAN
        from app.modules.email_processor.config_store import count_configs_by_owner
        from app.repositories.subscription_repository import SubscriptionRepository
        
        # Contar cuentas actuales del usuario
        current_count = count_configs_by_owner(owner_email)
        
        # Obtener límite del plan del usuario
        sub_repo = SubscriptionRepository()
        subscription = await sub_repo.get_user_active_subscription(owner_email)
        
        if subscription:
            plan_features = subscription.get('plan_features', {})
            max_accounts = plan_features.get('max_email_accounts', 2)  # Default: 2 cuentas
            
            # -1 significa ilimitado
            if max_accounts != -1 and current_count >= max_accounts:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Has alcanzado el límite de {max_accounts} cuentas de correo de tu plan. Actualiza tu suscripción para agregar más."
                )
        else:
            # Usuario sin suscripción activa (trial o free)
            max_accounts = 1  # Solo 1 cuenta para usuarios sin plan
            if current_count >= max_accounts:
                raise HTTPException(
                    status_code=403,
                    detail="Has alcanzado el límite de cuentas de correo. Suscríbete a un plan para agregar más cuentas."
                )
        
        cfg_dict = config.model_dump()
        cfg_id = db_create_config(cfg_dict, owner_email=owner_email)
        
        logger.info(f"✅ Nueva cuenta de correo creada para {owner_email}: {current_count + 1}/{max_accounts}")
        
        return {"success": True, "id": cfg_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo crear configuración")


@router.put("/email-configs/{config_id}")
async def update_email_config(config_id: str, config: MultiEmailConfig, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        update_data = config.model_dump()
        # Evitar sobreescribir password a null si no se envía
        if update_data.get("password") in (None, ""):
            update_data.pop("password", None)
        ok = db_update_config(config_id, update_data, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "id": config_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar configuración")


@router.patch("/email-configs/{config_id}")
async def patch_email_config(config_id: str, config: EmailConfigUpdate, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Actualización parcial de configuración de email.
    Permite actualizar solo campos específicos sin requerir todos los campos.
    Especialmente útil para configuraciones OAuth2 donde solo se pueden editar search_terms.
    """
    try:
        # Solo incluir campos que fueron explícitamente enviados (no None)
        update_data = {k: v for k, v in config.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
        
        ok = db_update_config(config_id, update_data, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "id": config_id, "updated_fields": list(update_data.keys())}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en actualización parcial de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar configuración")


@router.delete("/email-configs/{config_id}")
async def delete_email_config(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        ok = db_delete_config(config_id, owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando configuración de correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo eliminar configuración")


@router.patch("/email-configs/{config_id}/enabled")
async def set_email_config_enabled(config_id: str, payload: ToggleEnabledPayload, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        ok = db_set_enabled(config_id, bool(payload.enabled), owner_email=(user.get('email') or '').lower())
        if not ok:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "enabled": bool(payload.enabled)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando 'enabled' de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado")


@router.post("/email-configs/{config_id}/toggle")
async def toggle_email_config_enabled(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    try:
        new_val = db_toggle_enabled(config_id, owner_email=(user.get('email') or '').lower())
        if new_val is None:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")
        return {"success": True, "enabled": new_val}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error alternando 'enabled' de configuración: {e}")
        raise HTTPException(status_code=500, detail="No se pudo alternar el estado")


# -----------------------------
# OAuth 2.0 for Gmail (XOAUTH2)
# -----------------------------

@router.get("/email-configs/oauth/google/status")
async def get_google_oauth_status(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Check if Google OAuth is configured and available.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    
    oauth_manager = get_google_oauth_manager()
    return {
        "configured": oauth_manager.is_configured(),
        "provider": "google",
        "message": "OAuth configurado correctamente" if oauth_manager.is_configured() else "OAuth no configurado. Configure GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET"
    }


@router.get("/email-configs/oauth/google/authorize")
async def initiate_google_oauth(
    request: Request,
    user: Dict[str, Any] = Depends(_get_current_user),
    login_hint: Optional[str] = Query(None, description="Email to pre-fill in Google sign-in")
):
    """
    Initiate Google OAuth flow for Gmail IMAP access.
    Returns an authorization URL to redirect the user to.
    
    The state parameter encodes the user's email for security validation on callback.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    import base64
    import json
    
    oauth_manager = get_google_oauth_manager()
    
    if not oauth_manager.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google OAuth no está configurado. Contacta al administrador."
        )
    
    owner_email = (user.get('email') or '').lower()
    
    # Get the host from the request to build the correct redirect URI
    # This allows the same backend to work for both local and production
    # Use X-Forwarded-Host (includes port) if available, fallback to host
    request_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    redirect_uri = oauth_manager.get_redirect_uri(request_host)
    
    # Create state with user info for CSRF protection
    # Include redirect_uri so callback can use the same one
    state_data = {
        "owner_email": owner_email,
        "redirect_uri": redirect_uri,
        "timestamp": datetime.now().isoformat(),
        "nonce": str(uuid.uuid4())
    }
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    auth_url = oauth_manager.generate_auth_url(
        state=state,
        login_hint=login_hint,
        redirect_uri=redirect_uri
    )
    
    logger.info(f"🔐 OAuth authorization initiated for {owner_email} (redirect: {redirect_uri})")
    
    return {
        "auth_url": auth_url,
        "state": state,
        "message": "Redirige al usuario a auth_url para autorizar acceso a Gmail"
    }


@router.get("/email-configs/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from Google if authorization failed")
):
    """
    Handle Google OAuth callback after user grants permission.
    Exchanges the authorization code for access and refresh tokens.
    
    This endpoint is called by Google after user authorization.
    It returns an HTML page that sends the result to the opener window.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    import base64
    import json
    
    # Handle error from Google
    if error:
        logger.error(f"Google OAuth error: {error}")
        return HTMLResponse(content=_oauth_popup_response(False, f"Error de autorización: {error}"))
    
    oauth_manager = get_google_oauth_manager()
    
    try:
        # Decode and validate state
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        owner_email = state_data.get("owner_email", "").lower()
        redirect_uri = state_data.get("redirect_uri", "")
        
        if not owner_email:
            raise ValueError("Invalid state: missing owner_email")
        
        # Exchange code for tokens using the same redirect_uri from authorization
        tokens = await oauth_manager.exchange_code_for_tokens(code, redirect_uri=redirect_uri)
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        if not access_token:
            raise ValueError("No access token received from Google")
        
        # Get user info to confirm the Gmail address
        user_info = await oauth_manager.get_user_info(access_token)
        gmail_address = user_info.get("email", "").lower()
        
        # Calculate token expiry
        token_expiry = oauth_manager.calculate_token_expiry(expires_in)
        
        # SAVE DIRECTLY TO DATABASE - no popup communication needed
        # Check if this Gmail account already exists for this owner
        existing_configs = db_list_configs(owner_email=owner_email)
        existing_gmail_config = next(
            (c for c in existing_configs if c.get("username", "").lower() == gmail_address),
            None
        )
        
        if existing_gmail_config:
            # Update existing config with new OAuth tokens
            update_data = {
                "auth_type": "oauth2",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry.isoformat(),
                "password": "",  # Clear password for OAuth
                "enabled": True
            }
            db_update_config(existing_gmail_config["id"], update_data, owner_email=owner_email)
            logger.info(f"✅ Updated existing Gmail config with OAuth for {gmail_address}")
        else:
            # Create new config as dict
            new_config_data = {
                "name": f"Gmail - {gmail_address}",
                "host": "imap.gmail.com",
                "port": 993,
                "username": gmail_address,
                "password": "",
                "use_ssl": True,
                "auth_type": "oauth2",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry.isoformat(),
                "oauth_email": gmail_address,
                "search_terms": ["factura", "invoice", "comprobante", "documento electronico"],
                "search_criteria": "UNSEEN",
                "provider": "gmail",
                "enabled": True,
                "owner_email": owner_email
            }
            db_create_config(new_config_data, owner_email=owner_email)
            logger.info(f"✅ Created new Gmail OAuth config for {gmail_address}")
        
        logger.info(f"✅ Google OAuth successful for {gmail_address} (owner: {owner_email})")
        
        return HTMLResponse(content=_oauth_popup_response(True, "Cuenta Gmail conectada exitosamente. Puedes cerrar esta ventana.", None))
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return HTMLResponse(content=_oauth_popup_response(False, f"Error procesando autorización: {str(e)}"))


def _oauth_popup_response(success: bool, message: str, data: dict = None) -> str:
    """
    Generate an HTML response for the OAuth popup.
    Since we save directly to DB, we just show success/error and close.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Autorización Google - Cuenly</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.1);
                border-radius: 16px;
                backdrop-filter: blur(10px);
            }}
            .icon {{ font-size: 48px; margin-bottom: 20px; }}
            .message {{ font-size: 18px; margin-bottom: 10px; }}
            .submessage {{ font-size: 14px; opacity: 0.8; }}
            .btn {{
                margin-top: 20px;
                padding: 12px 24px;
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                color: white;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .btn:hover {{ background: rgba(255,255,255,0.3); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">{'✅' if success else '❌'}</div>
            <div class="message">{message}</div>
            <div class="submessage">{'Refresca la página de configuración para ver tu cuenta.' if success else 'Intenta nuevamente.'}</div>
            <button class="btn" onclick="window.close()">Cerrar ventana</button>
        </div>
        <script>
            // Notify parent to refresh if possible
            if (window.opener && !window.opener.closed) {{
                try {{
                    window.opener.postMessage({{ type: 'GOOGLE_OAUTH_COMPLETE', success: {'true' if success else 'false'} }}, '*');
                }} catch(e) {{}}
            }}
            // Auto close after 3 seconds if successful
            if ({'true' if success else 'false'}) {{
                setTimeout(() => window.close(), 3000);
            }}
        </script>
    </body>
    </html>
    """


@router.post("/email-configs/{config_id}/oauth/refresh")
async def refresh_oauth_token(config_id: str, user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Refresh the OAuth access token for a saved email configuration.
    """
    from app.modules.oauth.google_oauth import get_google_oauth_manager
    
    owner_email = (user.get('email') or '').lower()
    
    # Get the config from database
    db_cfg = db_get_by_id(config_id, include_password=True, owner_email=owner_email)
    if not db_cfg:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    
    if db_cfg.get("auth_type") != "oauth2":
        raise HTTPException(status_code=400, detail="Esta configuración no usa OAuth")
    
    refresh_token = db_cfg.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No hay refresh token almacenado")
    
    oauth_manager = get_google_oauth_manager()
    
    try:
        # Refresh the token
        tokens = await oauth_manager.refresh_access_token(refresh_token)
        
        new_access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in", 3600)
        token_expiry = oauth_manager.calculate_token_expiry(expires_in)
        
        # Update the config in database
        update_data = {
            "access_token": new_access_token,
            "token_expiry": token_expiry.isoformat()
        }
        
        ok = db_update_config(config_id, update_data, owner_email=owner_email)
        if not ok:
            raise HTTPException(status_code=500, detail="No se pudo actualizar el token")
        
        logger.info(f"✅ OAuth token refreshed for config {config_id}")
        
        return {
            "success": True,
            "token_expiry": token_expiry.isoformat(),
            "message": "Token actualizado exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing OAuth token: {e}")
        raise HTTPException(status_code=500, detail=f"Error renovando token: {str(e)}")


@router.post("/email-configs/oauth/save")
async def save_oauth_email_config(
    gmail_address: str = Body(..., embed=True),
    access_token: str = Body(..., embed=True),
    refresh_token: str = Body(..., embed=True),
    token_expiry: str = Body(..., embed=True),
    name: Optional[str] = Body("", embed=True),
    search_terms: Optional[List[str]] = Body(None, embed=True),
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """
    Save a new email configuration with OAuth tokens after successful Google authorization.
    """
    from app.modules.email_processor.config_store import count_configs_by_owner
    from app.repositories.subscription_repository import SubscriptionRepository
    
    owner_email = (user.get('email') or '').lower()
    
    # Validate subscription limits
    current_count = count_configs_by_owner(owner_email)
    sub_repo = SubscriptionRepository()
    subscription = await sub_repo.get_user_active_subscription(owner_email)
    
    if subscription:
        plan_features = subscription.get('plan_features', {})
        max_accounts = plan_features.get('max_email_accounts', 2)
        
        if max_accounts != -1 and current_count >= max_accounts:
            raise HTTPException(
                status_code=403,
                detail=f"Has alcanzado el límite de {max_accounts} cuentas de correo de tu plan."
            )
    else:
        if current_count >= 1:
            raise HTTPException(
                status_code=403,
                detail="Has alcanzado el límite de cuentas de correo. Suscríbete a un plan para agregar más."
            )
    
    # Verificar si ya existe config para este email para preservar settings
    existing_config = None
    try:
        from app.modules.email_processor.config_store import get_by_username
        existing_config = get_by_username(gmail_address, owner_email=owner_email)
    except Exception as e:
        logger.warning(f"Error checking existing config for {gmail_address}: {e}")

    # Preservar search_terms si existen y no se enviaron nuevos
    final_search_terms = search_terms
    if not final_search_terms:
        if existing_config and existing_config.get("search_terms"):
            final_search_terms = existing_config.get("search_terms")
        else:
            final_search_terms = ["factura", "invoice", "comprobante"]

    # Create the email config with OAuth
    config_data = {
        "name": name or (existing_config.get("name") if existing_config else f"Gmail - {gmail_address}"),
        "host": "imap.gmail.com",
        "port": 993,
        "username": gmail_address,
        "password": None,  # No password needed for OAuth
        "use_ssl": True,
        "search_criteria": "UNSEEN",
        "search_terms": final_search_terms,
        "provider": "gmail",
        "enabled": True,
        "auth_type": "oauth2",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": token_expiry,
        "oauth_email": gmail_address
    }
    
    try:
        config_id = db_create_config(config_data, owner_email=owner_email)
        logger.info(f"✅ OAuth email config created for {gmail_address} (owner: {owner_email})")
        
        return {
            "success": True,
            "id": config_id,
            "message": "Cuenta de Gmail configurada exitosamente con OAuth"
        }
    except Exception as e:
        logger.error(f"Error creating OAuth email config: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for container health checks.
    Verifica que la aplicación esté lista para recibir requests.
    
    Returns:
        dict: Simple health status.
    """
    try:
        # Verificación básica de que la aplicación está funcionando
        current_time = datetime.now().isoformat()
        
        # Verificar que el invoice_sync esté inicializado
        if not invoice_sync:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "invoice_sync not initialized", "timestamp": current_time}
            )
        
        # Verificación simple de conectividad MongoDB (opcional, sin bloquear)
        try:
            from app.repositories.user_repository import UserRepository
            # Test rápido de conexión (timeout muy corto)
            UserRepository()._get_collection().find_one({}, {"_id": 1})
        except Exception:
            # No fallar health check por MongoDB temporalmente no disponible
            pass
        
        return {"status": "healthy", "timestamp": current_time}
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": str(e), "timestamp": datetime.now().isoformat()}
        )

@router.get("/email-processing/config")
async def get_email_processing_config(user: Dict[str, Any] = Depends(_get_current_user)):
    """
    Obtiene la configuración actual de procesamiento de emails.
    """
    from app.config.settings import settings
    
    return {
        "process_all_dates": settings.EMAIL_PROCESS_ALL_DATES,
        "description": "Si es true, procesa todos los correos sin restricción de fecha. Si es false, solo procesa desde fecha de alta del usuario.",
        "current_setting": "Procesando TODOS los correos" if settings.EMAIL_PROCESS_ALL_DATES else "Procesando solo desde fecha de alta"
    }

