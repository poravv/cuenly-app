from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.collection import Collection
from app.config.settings import settings


class UserRepository:
    def __init__(self, conn_str: Optional[str] = None, db_name: Optional[str] = None, collection: str = "auth_users"):
        self.conn_str = conn_str or settings.MONGODB_URL
        self.db_name = db_name or settings.MONGODB_DATABASE
        self.collection = collection
        self._client: Optional[MongoClient] = None

    def _coll(self) -> Collection:
        if not self._client:
            self._client = MongoClient(self.conn_str, serverSelectionTimeoutMS=5000)
            self._client.admin.command('ping')
        db = self._client[self.db_name]
        coll = db[self.collection]
        try:
            coll.create_index('email', unique=True)
            coll.create_index('uid')
        except Exception:
            pass
        return coll

    def upsert_user(self, user: Dict[str, Any]) -> None:
        now = datetime.utcnow()
        email = (user.get('email') or '').lower()
        
        # Verificar si es un usuario nuevo
        existing_user = self._coll().find_one({'email': email})
        is_new_user = existing_user is None
        
        payload = {
            'email': email,
            'uid': user.get('uid') or user.get('user_id'),
            'name': user.get('name') or user.get('displayName'),
            'picture': user.get('picture') or user.get('photoURL'),
            'last_login': now,
        }
        
        # Si es un usuario nuevo, establecer fecha límite de uso y límites de IA
        if is_new_user:
            payload['trial_expires_at'] = now + timedelta(days=15)
            payload['is_trial_user'] = True
            payload['ai_invoices_processed'] = 0  # Contador de facturas procesadas con IA
            payload['ai_invoices_limit'] = 50     # Límite de facturas con IA para trial
        
        self._coll().update_one(
            {'email': email}, 
            {
                '$setOnInsert': {
                    'created_at': now,
                    'trial_expires_at': payload.get('trial_expires_at'),
                    'is_trial_user': payload.get('is_trial_user', False),
                    'ai_invoices_processed': payload.get('ai_invoices_processed', 0),
                    'ai_invoices_limit': payload.get('ai_invoices_limit', 50)
                }, 
                '$set': {k: v for k, v in payload.items() if k not in ['trial_expires_at', 'is_trial_user', 'ai_invoices_processed', 'ai_invoices_limit']}
            }, 
            upsert=True
        )

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self._coll().find_one({'email': email.lower()})

    def is_trial_expired(self, email: str) -> bool:
        """Verifica si el período de prueba del usuario ha expirado"""
        user = self.get_by_email(email)
        if not user:
            return True  # Usuario no existe, considerar expirado
        
        # Si no es usuario de prueba, no tiene límite
        if not user.get('is_trial_user', False):
            return False
            
        trial_expires_at = user.get('trial_expires_at')
        if not trial_expires_at:
            return True  # Sin fecha de expiración, considerar expirado
            
        return datetime.utcnow() > trial_expires_at

    def get_trial_info(self, email: str) -> Dict[str, Any]:
        """Obtiene información del período de prueba del usuario"""
        user = self.get_by_email(email)
        if not user:
            return {
                'is_trial_user': True,
                'trial_expired': True,
                'days_remaining': 0,
                'trial_expires_at': None,
                'ai_invoices_processed': 0,
                'ai_invoices_limit': 50,
                'ai_limit_reached': True
            }
        
        is_trial_user = user.get('is_trial_user', False)
        trial_expires_at = user.get('trial_expires_at')
        ai_processed = user.get('ai_invoices_processed', 0)
        ai_limit = user.get('ai_invoices_limit', 50)
        
        if not is_trial_user:
            return {
                'is_trial_user': False,
                'trial_expired': False,
                'days_remaining': -1,  # -1 indica usuario sin límite
                'trial_expires_at': None,
                'ai_invoices_processed': ai_processed,
                'ai_invoices_limit': -1,  # -1 indica sin límite
                'ai_limit_reached': False
            }
        
        if not trial_expires_at:
            return {
                'is_trial_user': True,
                'trial_expired': True,
                'days_remaining': 0,
                'trial_expires_at': None,
                'ai_invoices_processed': ai_processed,
                'ai_invoices_limit': ai_limit,
                'ai_limit_reached': True
            }
        
        now = datetime.utcnow()
        is_expired = now > trial_expires_at
        days_remaining = max(0, (trial_expires_at - now).days)
        ai_limit_reached = ai_processed >= ai_limit
        
        return {
            'is_trial_user': True,
            'trial_expired': is_expired,
            'days_remaining': days_remaining,
            'trial_expires_at': trial_expires_at.isoformat() if trial_expires_at else None,
            'ai_invoices_processed': ai_processed,
            'ai_invoices_limit': ai_limit,
            'ai_limit_reached': ai_limit_reached
        }

    def upgrade_to_premium(self, email: str) -> bool:
        """Convierte un usuario de prueba a premium (sin límite de tiempo)"""
        result = self._coll().update_one(
            {'email': email.lower()},
            {
                '$set': {'is_trial_user': False},
                '$unset': {'trial_expires_at': '', 'ai_invoices_limit': ''}
            }
        )
        return result.modified_count > 0

    def increment_ai_usage(self, email: str, count: int = 1) -> Dict[str, Any]:
        """Incrementa el contador de facturas procesadas con IA"""
        email = email.lower()
        result = self._coll().update_one(
            {'email': email},
            {'$inc': {'ai_invoices_processed': count}}
        )
        
        if result.modified_count > 0:
            # Retornar información actualizada
            return self.get_trial_info(email)
        else:
            return {'error': 'Usuario no encontrado'}

    def can_use_ai(self, email: str) -> Dict[str, Any]:
        """Verifica si el usuario puede usar IA (no ha excedido el límite)"""
        trial_info = self.get_trial_info(email)
        
        # Si ya expiró el trial, no puede usar nada
        if trial_info['trial_expired']:
            return {
                'can_use': False,
                'reason': 'trial_expired',
                'message': 'Tu período de prueba ha expirado'
            }
        
        # Si no es usuario de prueba (premium), puede usar sin límites
        if not trial_info['is_trial_user']:
            return {
                'can_use': True,
                'reason': 'premium',
                'message': 'Usuario premium - sin límites'
            }
        
        # Si es usuario de prueba, verificar límite de IA
        if trial_info['ai_limit_reached']:
            return {
                'can_use': False,
                'reason': 'ai_limit_reached',
                'message': f'Has alcanzado el límite de {trial_info["ai_invoices_limit"]} facturas con IA. Usa el procesador XML nativo o upgradeate a premium.'
            }
        
        return {
            'can_use': True,
            'reason': 'trial_valid',
            'message': f'Puedes procesar {trial_info["ai_invoices_limit"] - trial_info["ai_invoices_processed"]} facturas más con IA'
        }

