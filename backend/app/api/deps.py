from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
from app.utils.firebase_auth import verify_firebase_token, extract_bearer_token
from app.utils.trial_middleware import check_trial_limits_optional, check_trial_limits, check_ai_limits
from app.repositories.user_repository import UserRepository
from app.utils.observability import observability_logger
from app.middleware.observability_middleware import BusinessEventLogger
from app.config.settings import settings

def _get_current_user(request: Request) -> Dict[str, Any]:
    """Valida token Firebase y retorna claims. Upserta usuario en DB."""
    token = extract_bearer_token(request)
    if not token:
        if settings.AUTH_REQUIRE:
            raise HTTPException(status_code=401, detail="Authorization requerido")
        return {}
    claims = verify_firebase_token(token)
    
    # Intentar registrar/actualizar usuario en DB con manejo de errores mejorado
    try:
        user_repo = UserRepository()
        user_repo.upsert_user({
            'email': claims.get('email'),
            'uid': claims.get('user_id'),
            'name': claims.get('name'),
            'picture': claims.get('picture') or claims.get('photoURL'),
        })
        user_email = claims.get('email', '')
        observability_logger.log_business_event(
            "user_authentication_success",
            user_email=user_email,
            auth_method="firebase",
            user_name=claims.get('name'),
            user_uid=claims.get('user_id')
        )
        BusinessEventLogger.log_user_authentication(user_email, True)
    except Exception as e:
        user_email = claims.get('email', '')
        observability_logger.log_error(
            "user_registration_error",
            str(e),
            user_email=user_email,
            user_uid=claims.get('user_id'),
            auth_method="firebase"
        )
        BusinessEventLogger.log_user_authentication(user_email, False)
        # No fallar la autenticación, pero loggear el error para diagnóstico
    # Realizar verificación de suspensión fuera del try/except
    try:
        user_repo = UserRepository()
        db_user = user_repo.get_by_email(claims.get('email'))
        if db_user and db_user.get('status') == 'suspended':
            raise HTTPException(status_code=403, detail="Tu cuenta está suspendida. Contacta al administrador.")
    except HTTPException:
        # Propagar bloqueo explícito
        raise
    except Exception as e:
        user_email = claims.get('email', '')
        observability_logger.log_error(
            "user_status_check_error",
            str(e),
            user_email=user_email,
            endpoint="/api/user/status"
        )
    return claims

def _get_current_user_with_trial_info(request: Request) -> Dict[str, Any]:
    """Valida token Firebase y retorna claims con información de trial."""
    claims = _get_current_user(request)
    if not claims:
        return claims
    
    # Agregar información del trial
    trial_info = check_trial_limits_optional(claims)
    claims['trial_info'] = trial_info
    return claims

def _get_current_user_with_trial_check(request: Request) -> Dict[str, Any]:
    """Valida token Firebase y verifica que el trial esté válido. Lanza excepción si expiró."""
    claims = _get_current_user(request)
    if not claims:
        return claims
    
    # Verificar límites de trial (lanza excepción si expiró)
    trial_info = check_trial_limits(claims)
    claims['trial_info'] = trial_info
    return claims

def _get_current_user_with_ai_check(request: Request) -> Dict[str, Any]:
    """Valida token Firebase y verifica que pueda usar IA. Lanza excepción si no puede."""
    claims = _get_current_user(request)
    if not claims:
        return claims
    
    # Verificar límites de trial + IA (lanza excepción si no puede usar IA)
    trial_info = check_ai_limits(claims)
    claims['trial_info'] = trial_info
    return claims

def _get_current_admin(request: Request) -> Dict[str, Any]:
    """Valida token Firebase y verifica que sea admin. Lanza excepción si no es admin."""
    claims = _get_current_user(request)
    if not claims:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    # Verificar si es administrador
    user_repo = UserRepository()
    if not user_repo.is_admin(claims.get('email', '')):
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requieren permisos de administrador.")
    
    return claims
    
# Alias for compatibility if needed
_get_current_admin_user = _get_current_admin
