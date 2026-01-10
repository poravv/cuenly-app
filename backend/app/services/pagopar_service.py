import hashlib
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.config.settings import settings

logger = logging.getLogger(__name__)

class PagoparService:
    def __init__(self):
        self.public_key = settings.PAGOPAR_PUBLIC_KEY
        self.private_key = settings.PAGOPAR_PRIVATE_KEY
        self.base_url = settings.PAGOPAR_BASE_URL.rstrip('/')
        
        if self.public_key:
            self.public_key = self.public_key.strip()
        if self.private_key:
            self.private_key = self.private_key.strip()
            
        if not self.public_key or not self.private_key:
            logger.warning("Pagopar credentials are not set or empty. Payment features will fail.")

    def _generate_token(self, operation: str = "PAGO-RECURRENTE") -> str:
        """Generates the SHA1 token required by Pagopar: sha1(Private_key + "PAGO-RECURRENTE")"""
        # Note: The PDF documentation specifies "PAGO-RECURRENTE" for all recurring endpoints (add customer, add card, etc).
        # We allow overriding just in case, but default is PAGO-RECURRENTE.
        raw_string = f"{self.private_key}{operation}"
        token = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()
        # logger.debug(f"Generating token for op: {operation}. Hash(*** + {operation}) = {token}")
        return token

    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to send POST requests to Pagopar API"""
        url = f"{self.base_url}/{endpoint}/"
        
        # Inject public key if not present
        if "token_publico" not in data:
            data["token_publico"] = self.public_key

        # Inject token if not present (default PAGO-RECURRENTE)
        if "token" not in data:
            data["token"] = self._generate_token()
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # logger.info(f"Sending request to Pagopar: {url}")
                response = await client.post(url, json=data)
                response.raise_for_status()
                result = response.json()
                
                # Check Pagopar application-level success flag
                if not result.get("respuesta"):
                    error_msg = result.get("resultado", "Unknown error from Pagopar")
                    logger.error(f"Pagopar API Error ({endpoint}): {error_msg}")
                    # You might want to raise a custom exception here
                    raise Exception(f"Pagopar Error: {error_msg}")
                    
                return result
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Error interacting with Pagopar: {e.response.text}")
                raise e
            except Exception as e:
                logger.error(f"Error interacting with Pagopar: {str(e)}")
                raise e

    async def add_customer(self, identifier: str, name: str, email: str, phone: str = "") -> Dict[str, Any]:
        """
        Registra un cliente en Pagopar.
        endpoint: agregar-cliente/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier,
            "nombre_apellido": name,
            "email": email,
            "celular": phone
        }
        return await self._post("agregar-cliente", payload)

    async def init_add_card(self, identifier: str, redirect_url: str, provider: str = "Bancard") -> str:
        """
        Solicita añadir una tarjeta. Retorna el hash (resultado) necesario para el iframe.
        endpoint: agregar-tarjeta/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier,
            "url": redirect_url,
            "proveedor": provider
        }
        response = await self._post("agregar-tarjeta", payload)
        return response.get("resultado", "")

    async def confirm_card(self, identifier: str, redirect_url: str) -> bool:
        """
        Confirma el catastro de una tarjeta.
        endpoint: confirmar-tarjeta/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier,
            "url": redirect_url
        }
        try:
            await self._post("confirmar-tarjeta", payload)
            return True
        except Exception:
            return False

    async def list_cards(self, identifier: str) -> List[Dict[str, Any]]:
        """
        Lista las tarjetas catastradas para un usuario.
        endpoint: listar-tarjeta/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier
        }
        try:
            response = await self._post("listar-tarjeta", payload)
            return response.get("resultado", [])
        except Exception as e:
            logger.error(f"Error listing cards for {identifier}: {e}")
            return []

    async def delete_card(self, identifier: str, card_token: str) -> bool:
        """
        Elimina una tarjeta usando su token temporal (alias_token).
        endpoint: eliminar-tarjeta/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier,
            "tarjeta": card_token
        }
        try:
            await self._post("eliminar-tarjeta", payload)
            return True
        except Exception:
            try:
                # Try typo "elliminar" just in case based on doc warning
                await self._post("elliminar-tarjeta", payload)
                return True
            except Exception:
                return False

    async def get_card_alias_token(self, identifier: str) -> Optional[str]:
        """
        Obtiene el alias_token temporal (válido ~15 min) de la primera tarjeta del usuario.
        Debe llamarse justo antes de cobrar.
        """
        try:
            cards = await self.list_cards(identifier)
            if cards and len(cards) > 0:
                alias_token = cards[0].get("alias_token")
                if alias_token:
                    logger.info(f"🃏 Alias token obtenido para usuario {identifier}")
                    return alias_token
                else:
                    logger.warning(f"Usuario {identifier} tiene tarjeta pero sin alias_token")
                    return None
            else:
                logger.warning(f"Usuario {identifier} no tiene tarjetas catastradas")
                return None
        except Exception as e:
            logger.error(f"Error obteniendo alias_token para {identifier}: {e}")
            return None

    async def create_order(
        self, 
        identifier: str, 
        amount: float, 
        description: str, 
        ref_id: str
    ) -> Optional[str]:
        """
        Crea un pedido usando la API V1.1 de Pagopar.
        Retorna el hash del pedido necesario para procesar el pago.
        
        endpoint: comercios/2.0/iniciar-transaccion
        Token: SHA1(private_key + order_id + str(int(amount)))
        """
        try:
            # Generar ID único del pedido
            order_id = f"SUB-{ref_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Token para iniciar-transaccion
            amount_int = int(amount)
            raw_token = f"{self.private_key}{order_id}{amount_int}"
            token = hashlib.sha1(raw_token.encode('utf-8')).hexdigest()
            
            # Buyer info mínimo requerido
            buyer_info = {
                "ruc": "",
                "email": f"user{identifier}@cuenly.com",  # Email del usuario
                "ciudad": "1",
                "nombre": f"Usuario {identifier}",
                "telefono": "+595981000000",
                "direccion": "",
                "documento": str(identifier),
                "coordenadas": "",
                "razon_social": "",
                "tipo_documento": "CI",
                "direccion_referencia": ""
            }
            
            payload = {
                "token": token,
                "public_key": self.public_key,
                "monto_total": amount,
                "tipo_pedido": "VENTA-COMERCIO",
                "id_pedido_comercio": order_id,
                "descripcion_resumen": description,
                "fecha_maxima_pago": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
                "forma_pago": 9,  # Bancard
                "comprador": buyer_info,
                "compras_items": [
                    {
                        "nombre": description,
                        "cantidad": 1,
                        "precio_total": amount,
                        "id_producto": 1,
                        "descripcion": description,
                        "url_imagen": "",
                        "ciudad": "1",
                        "categoria": "909",
                        "public_key": self.public_key,
                        "vendedor_direccion": "",
                        "vendedor_telefono": "",
                        "vendedor_direccion_referencia": "",
                        "vendedor_direccion_coordenadas": ""
                    }
                ]
            }
            
            url = "https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if data.get("respuesta"):
                    resultado = data.get("resultado", [])
                    if resultado and len(resultado) > 0:
                        order_hash = resultado[0].get("data", "")
                        logger.info(f"✅ Pedido creado: {order_id} -> {order_hash}")
                        return order_hash
                    else:
                        logger.error(f"Respuesta de Pagopar sin resultado: {data}")
                        return None
                else:
                    error_msg = data.get("resultado", "Error desconocido")
                    logger.error(f"Error creando pedido en Pagopar: {error_msg}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creando pedido: {e}")
            return None

    async def process_payment(self, identifier: str, order_hash: str, card_token: str) -> bool:
        """
        Procesa el pago.
        endpoint: pagar/
        Token: SHA1(private + "PAGO-RECURRENTE")
        """
        payload = {
            "identificador": identifier,
            "hash_pedido": order_hash,
            "tarjeta": card_token 
        }
        try:
            await self._post("pagar", payload)
            return True
        except Exception:
            return False

    async def create_order_v11(self, order_id: str, amount: float, description: str, buyer: Dict[str, Any]) -> str:
        """
        Crea un pedido V1.1 Standard.
        endpoint: comercios/2.0/iniciar-transaccion
        Token: SHA1(private_key + order_id + str(int(amount)))
        """
        # Token formula for iniciar-transaccion (from Error PDF):
        # sha1(private_key + idPedido + str(amount))
        # IMPORTANTE: amount debe ser entero, no float
        amount_int = int(amount)
        raw_token = f"{self.private_key}{order_id}{amount_int}"
        token = hashlib.sha1(raw_token.encode('utf-8')).hexdigest()
        
        logger.info(f"🔐 Token generado para pedido {order_id}: {token}")
        logger.debug(f"Raw token string: {raw_token}")

        payload = {
            "token": token,
            "public_key": self.public_key,
            "monto_total": amount,
            "tipo_pedido": "VENTA-COMERCIO",
            "compras_items": [
                {
                    "nombre": description,
                    "cantidad": 1,
                    "precio_total": amount,
                    "id_producto": 1,
                    "descripcion": description,
                    "url_imagen": "",
                    "ciudad": "1",  # Required field
                    "categoria": "909",  # Required field  
                    "public_key": self.public_key,  # Required in items too
                    "vendedor_direccion": "",
                    "vendedor_telefono": "",
                    "vendedor_direccion_referencia": "",
                    "vendedor_direccion_coordenadas": ""
                }
            ],
            "id_pedido_comercio": order_id,
            "descripcion_resumen": description,
            "fecha_maxima_pago": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "comprador": {
                **buyer,
                "coordenadas": buyer.get("coordenadas", "")  # Add if not present
            }
        }

        url = "https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get("respuesta"):
                # Return the hash from resultado[0]['data']
                resultado = data.get("resultado", [])
                if resultado and len(resultado) > 0:
                    return resultado[0].get("data", "")
                return ""
            else:
                raise Exception(f"Pagopar V1.1 Error: {data.get('resultado')}")

    async def check_order_status(self, order_hash: str) -> Dict[str, Any]:
        """
        Verifica estado de pedido V1.1.
        endpoint: pedidos/1.1/traer
        Token: SHA1(private_key + "CONSULTA")
        """
        token = self._generate_token("CONSULTA")
        
        payload = {
            "token": token,
            "token_publico": self.public_key,
            "hash_pedido": order_hash
        }
        
        url = "https://api.pagopar.com/api/pedidos/1.1/traer"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

