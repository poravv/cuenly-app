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
            self._client = MongoClient(self.conn_str, serverSelectionTimeoutMS=60000)
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
        
        # Determinar rol - andyvercha@gmail.com siempre es admin
        is_admin = email == 'andyvercha@gmail.com'
        role = 'admin' if is_admin else 'user'
        
        # Datos básicos del usuario que siempre se actualizan
        basic_payload = {
            'email': email,
            'uid': user.get('uid') or user.get('user_id'),
            'name': user.get('name') or user.get('displayName'),
            'picture': user.get('picture') or user.get('photoURL'),
            'last_login': now,
            'role': role,
            'status': 'active',  # active, suspended
        }
        
        if is_new_user:
            # Para nuevos usuarios, configurar como trial por defecto
            trial_payload = {
                'created_at': now,
                'is_trial_user': True,
                'trial_expires_at': now + timedelta(days=15),
                'ai_invoices_processed': 0,
                'ai_invoices_limit': 50,
                'email_processing_start_date': now
            }
            
            # Combinar todos los datos para nuevos usuarios
            full_payload = {**basic_payload, **trial_payload}
            
            self._coll().insert_one(full_payload)
        else:
            # Para usuarios existentes, verificar si necesitan información de trial
            needs_trial_setup = (
                existing_user.get('trial_expires_at') is None and 
                existing_user.get('is_trial_user') is None
            )
            
            if needs_trial_setup:
                # Usuario existente sin información de trial - configurar automáticamente
                trial_payload = {
                    'is_trial_user': True,
                    'trial_expires_at': now + timedelta(days=15),
                    'ai_invoices_processed': existing_user.get('ai_invoices_processed', 0),
                    'ai_invoices_limit': 50,
                    'email_processing_start_date': existing_user.get('email_processing_start_date', existing_user.get('created_at', now))
                }
                
                # Actualizar con datos básicos + información de trial
                update_payload = {**basic_payload, **trial_payload}
                print(f"Configurando trial automático para usuario existente: {email}")
            else:
                # Usuario existente con información de trial ya configurada
                # Solo actualizar datos básicos
                update_payload = basic_payload
            
            self._coll().update_one(
                {'email': email},
                {'$set': update_payload}
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

    def get_email_processing_start_date(self, email: str) -> Optional[datetime]:
        """Obtiene la fecha desde la cual debe procesar correos para este usuario"""
        user = self.get_by_email(email)
        if not user:
            return None
        
        # Retornar fecha de inicio de procesamiento o fecha de creación como fallback
        start_date = user.get('email_processing_start_date') or user.get('created_at')
        return start_date

    def update_email_processing_start_date(self, email: str, start_date: datetime = None) -> bool:
        """Actualiza la fecha de inicio de procesamiento de correos para un usuario"""
        if start_date is None:
            start_date = datetime.utcnow()
        
        result = self._coll().update_one(
            {'email': email.lower()},
            {'$set': {'email_processing_start_date': start_date}}
        )
        
        return result.modified_count > 0

    # Métodos de administración
    def is_admin(self, email: str) -> bool:
        """Verifica si el usuario es administrador"""
        user = self.get_by_email(email)
        return user and user.get('role') == 'admin'

    def get_all_users(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Obtiene todos los usuarios con paginación (solo para admins)"""
        skip = (page - 1) * page_size
        
        # Contar total de usuarios
        total = self._coll().count_documents({})
        
        # Obtener usuarios con paginación
        users = list(
            self._coll().find({}, {
                'password': 0  # Excluir campos sensibles
            }).sort('created_at', -1).skip(skip).limit(page_size)
        )
        
        return {
            'users': users,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }

    def update_user_role(self, email: str, role: str) -> bool:
        """Actualiza el rol de un usuario (admin/user)"""
        if role not in ['admin', 'user']:
            return False
            
        result = self._coll().update_one(
            {'email': email.lower()},
            {'$set': {'role': role}}
        )
        return result.modified_count > 0

    def update_user_status(self, email: str, status: str) -> bool:
        """Actualiza el estado de un usuario (active/suspended)"""
        if status not in ['active', 'suspended']:
            return False
            
        result = self._coll().update_one(
            {'email': email.lower()},
            {'$set': {'status': status}}
        )
        return result.modified_count > 0

    def get_user_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de usuarios"""
        pipeline = [
            {
                '$group': {
                    '_id': None,
                    'total_users': {'$sum': 1},
                    'active_users': {
                        '$sum': {'$cond': [{'$eq': ['$status', 'active']}, 1, 0]}
                    },
                    'admin_users': {
                        '$sum': {'$cond': [{'$eq': ['$role', 'admin']}, 1, 0]}
                    },
                    'trial_users': {
                        '$sum': {'$cond': [{'$eq': ['$is_trial_user', True]}, 1, 0]}
                    }
                }
            }
        ]
        
        result = list(self._coll().aggregate(pipeline))
        if result:
            stats = result[0]
            stats.pop('_id', None)
            return stats
        
        return {
            'total_users': 0,
            'active_users': 0,
            'admin_users': 0,
            'trial_users': 0
        }
