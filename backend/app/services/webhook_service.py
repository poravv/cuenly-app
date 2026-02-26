import json
import logging
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional

from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

class WebhookService:
    """
    Servicio para disparar notificaciones B2B cuando se procesa exitosamente
    una factura electrónica.
    """
    def __init__(self):
        self.user_repo = UserRepository()

    def send_invoice_notification(self, owner_email: str, invoice_data: Dict[str, Any]) -> bool:
        """
        Busca si el usuario tiene un webhook configurado y dispara la notificación.
        Retorna True si la notificación fue enviada o no era necesaria.
        Retorna False si falló la entrega.
        """
        try:
            if not owner_email:
                return True
                
            user = self.user_repo.get_by_email(owner_email)
            if not user:
                return True
                
            webhook_url = user.get('webhook_url')
            webhook_secret = user.get('webhook_secret', '')
            
            if not webhook_url:
                # El usuario no configuró webhooks
                return True
                
            logger.info(f"🚀 Disparando webhook para {owner_email} hacia {webhook_url}")
            
            # Limpiar datos no serializables si los hay
            payload_str = json.dumps(invoice_data, default=str)
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Cuenly-Webhook/1.0',
            }
            
            # Si hay un secreto configurado, firmamos el payload
            if webhook_secret:
                signature = hmac.new(
                    webhook_secret.encode('utf-8'),
                    payload_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Cuenly-Signature'] = f"sha256={signature}"
                
            # Envío con timeout corto para no bloquear el worker principal
            response = requests.post(
                webhook_url,
                data=payload_str,
                headers=headers,
                timeout=10.0
            )
            
            if 200 <= response.status_code < 300:
                logger.info(f"✅ Webhook entregado exitosamente a {webhook_url} (Status {response.status_code})")
                return True
            else:
                logger.warning(f"⚠️ El webhook hacia {webhook_url} retornó HTTP {response.status_code}: {response.text[:200]}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout al intentar alcanzar el webhook {webhook_url} para {owner_email}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red al disparar webhook a {webhook_url}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado disparando webhook: {str(e)}", exc_info=True)
            return False
