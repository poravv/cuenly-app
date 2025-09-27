"""
Middleware para verificar límites de usuarios de prueba
"""
from typing import Dict, Any
from fastapi import HTTPException
from app.repositories.user_repository import UserRepository
import logging

logger = logging.getLogger(__name__)

class TrialLimitError(HTTPException):
    """Excepción específica para límites de prueba excedidos"""
    def __init__(self, message: str = "Tu período de prueba ha expirado"):
        super().__init__(status_code=402, detail=message)

class AILimitError(HTTPException):
    """Excepción específica para límite de IA excedido"""
    def __init__(self, message: str = "Has alcanzado el límite de facturas con IA"):
        super().__init__(status_code=402, detail=message)

def check_trial_limits(user_claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifica si el usuario puede acceder a funcionalidades (solo verifica trial, no IA)
    
    Args:
        user_claims: Claims del token Firebase
        
    Returns:
        Dict con información del trial
        
    Raises:
        TrialLimitError: Si el período de prueba ha expirado
    """
    if not user_claims or not user_claims.get('email'):
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    user_repo = UserRepository()
    trial_info = user_repo.get_trial_info(user_claims['email'])
    
    # Log para debugging
    logger.info(f"Trial info for {user_claims['email']}: {trial_info}")
    
    # Si el usuario es de prueba y ha expirado, bloquear acceso
    if trial_info['is_trial_user'] and trial_info['trial_expired']:
        raise TrialLimitError(
            f"Tu período de prueba de 15 días ha expirado. "
            f"Contacta al administrador para continuar usando el sistema."
        )
    
    return trial_info

def check_ai_limits(user_claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifica si el usuario puede usar IA (incluye verificación de trial + límite de IA)
    
    Args:
        user_claims: Claims del token Firebase
        
    Returns:
        Dict con información del trial
        
    Raises:
        TrialLimitError: Si el período de prueba ha expirado
        AILimitError: Si ha excedido el límite de IA
    """
    if not user_claims or not user_claims.get('email'):
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    user_repo = UserRepository()
    trial_info = user_repo.get_trial_info(user_claims['email'])
    ai_check = user_repo.can_use_ai(user_claims['email'])
    
    # Log para debugging
    logger.info(f"AI check for {user_claims['email']}: {ai_check}")
    
    # Verificar si puede usar AI
    if not ai_check['can_use']:
        if ai_check['reason'] == 'trial_expired':
            raise TrialLimitError(ai_check['message'])
        elif ai_check['reason'] == 'ai_limit_reached':
            raise AILimitError(ai_check['message'])
        elif ai_check['reason'] in ['subscription_inactive', 'subscription_check_error']:
            raise HTTPException(status_code=402, detail=ai_check['message'])
    
    return trial_info

def check_trial_limits_optional(user_claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versión opcional que no lanza excepción, solo retorna información
    """
    if not user_claims or not user_claims.get('email'):
        return {
            'is_trial_user': True,
            'trial_expired': True,
            'days_remaining': 0,
            'trial_expires_at': None,
            'ai_invoices_processed': 0,
            'ai_invoices_limit': 50,
            'ai_limit_reached': True
        }
    
    user_repo = UserRepository()
    return user_repo.get_trial_info(user_claims['email'])
