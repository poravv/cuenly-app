#!/usr/bin/env python3
"""
Script de diagnóstico para verificar la creación de clientes en PagoPar
Uso: python test_pagopar_customer.py
"""

import asyncio
import hashlib
import httpx
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

PUBLIC_KEY = os.getenv("PAGOPAR_PUBLIC_KEY", "")
PRIVATE_KEY = os.getenv("PAGOPAR_PRIVATE_KEY", "")
BASE_URL = os.getenv("PAGOPAR_BASE_URL", "https://api.pagopar.com/api/pago-recurrente/3.0/")

def generate_token(operation: str = "PAGO-RECURRENTE") -> str:
    """Genera el token SHA1 requerido por PagoPar"""
    raw_string = f"{PRIVATE_KEY}{operation}"
    token = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()
    return token

async def test_add_customer(identifier: str, name: str, email: str, phone: str):
    """Prueba el endpoint agregar-cliente"""
    url = f"{BASE_URL.rstrip('/')}/agregar-cliente/"
    token = generate_token("PAGO-RECURRENTE")
    
    payload = {
        "token": token,
        "token_publico": PUBLIC_KEY,
        "identificador": identifier,
        "nombre_apellido": name,
        "email": email,
        "celular": phone
    }
    
    print(f"\n🔍 DIAGNÓSTICO - Agregar Cliente")
    print(f"=" * 60)
    print(f"URL: {url}")
    print(f"Identificador: {identifier}")
    print(f"Nombre: {name}")
    print(f"Email: {email}")
    print(f"Teléfono: {phone}")
    print(f"Token: {token[:20]}...")
    print(f"Public Key: {PUBLIC_KEY[:20]}...")
    print(f"\nPayload completo:")
    print(payload)
    print(f"=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            print(f"\n📊 RESPUESTA HTTP")
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            try:
                result = response.json()
                print(f"\n📦 RESPUESTA JSON:")
                print(result)
                
                if result.get("respuesta"):
                    print(f"\n✅ Cliente creado exitosamente!")
                    print(f"ID Comprador: {result.get('resultado', {}).get('id_comprador_comercio', 'N/A')}")
                    return True, result
                else:
                    print(f"\n❌ Error de PagoPar:")
                    print(f"Resultado: {result.get('resultado', 'Desconocido')}")
                    return False, result
                    
            except Exception as e:
                print(f"\n⚠️ Error parseando JSON: {e}")
                print(f"Respuesta raw: {response.text}")
                return False, {"error": str(e), "raw": response.text}
                
    except httpx.HTTPStatusError as e:
        print(f"\n❌ Error HTTP: {e}")
        print(f"Response: {e.response.text}")
        return False, {"error": str(e)}
    except Exception as e:
        print(f"\n💥 Error inesperado: {e}")
        return False, {"error": str(e)}

async def test_add_card(identifier: str, return_url: str, provider: str = "uPay"):
    """Prueba el endpoint agregar-tarjeta"""
    url = f"{BASE_URL.rstrip('/')}/agregar-tarjeta/"
    token = generate_token("PAGO-RECURRENTE")
    
    # Convertir a int si es un string numérico
    if isinstance(identifier, str) and identifier.isdigit():
        identifier = int(identifier)
    
    payload = {
        "token": token,
        "token_publico": PUBLIC_KEY,
        "identificador": identifier,
        "url": return_url,
        "proveedor": provider
    }
    
    print(f"\n🔍 DIAGNÓSTICO - Agregar Tarjeta")
    print(f"=" * 60)
    print(f"URL: {url}")
    print(f"Identificador: {identifier} (tipo: {type(identifier).__name__})")
    print(f"Return URL: {return_url}")
    print(f"Proveedor: {provider}")
    print(f"Token: {token[:20]}...")
    print(f"\nPayload completo:")
    print(payload)
    print(f"=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            print(f"\n📊 RESPUESTA HTTP")
            print(f"Status Code: {response.status_code}")
            
            try:
                result = response.json()
                print(f"\n📦 RESPUESTA JSON:")
                print(result)
                
                if result.get("respuesta"):
                    print(f"\n✅ Hash generado exitosamente!")
                    print(f"Hash: {result.get('resultado', 'N/A')}")
                    return True, result
                else:
                    print(f"\n❌ Error de PagoPar:")
                    print(f"Resultado: {result.get('resultado', 'Desconocido')}")
                    return False, result
                    
            except Exception as e:
                print(f"\n⚠️ Error parseando JSON: {e}")
                print(f"Respuesta raw: {response.text}")
                return False, {"error": str(e), "raw": response.text}
                
    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False, {"error": str(e)}

async def list_cards(identifier: str):
    """Prueba el endpoint listar-tarjeta"""
    url = f"{BASE_URL.rstrip('/')}/listar-tarjeta/"
    token = generate_token("PAGO-RECURRENTE")
    
    payload = {
        "token": token,
        "token_publico": PUBLIC_KEY,
        "identificador": identifier
    }
    
    print(f"\n🔍 DIAGNÓSTICO - Listar Tarjetas")
    print(f"=" * 60)
    print(f"URL: {url}")
    print(f"Identificador: {identifier}")
    print(f"=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            print(f"\n📦 RESPUESTA:")
            print(result)
            
            if result.get("respuesta"):
                cards = result.get("resultado", [])
                print(f"\n✅ Tarjetas encontradas: {len(cards)}")
                return True, result
            else:
                print(f"\n❌ Error: {result.get('resultado')}")
                return False, result
                
    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False, {"error": str(e)}

async def main():
    if not PUBLIC_KEY or not PRIVATE_KEY:
        print("❌ ERROR: PAGOPAR_PUBLIC_KEY y PAGOPAR_PRIVATE_KEY deben estar configurados")
        sys.exit(1)
    
    # Datos de prueba
    test_email = "andyvercha@gmail.com"
    test_identifier = str(int(hashlib.sha256(test_email.encode('utf-8')).hexdigest(), 16) % 10**8)
    test_name = "Andrés Valentín Vera Chávez"
    test_phone = "0981000000"
    test_return_url = "http://localhost:4200/payment-methods"
    
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO COMPLETO DE PAGOPAR")
    print("=" * 60)
    print(f"Email de prueba: {test_email}")
    print(f"Identificador generado: {test_identifier}")
    
    # Test 1: Agregar Cliente
    success_customer, result_customer = await test_add_customer(
        identifier=test_identifier,
        name=test_name,
        email=test_email,
        phone=test_phone
    )
    
    if not success_customer:
        print("\n⚠️ CONCLUSIÓN:")
        print("El cliente NO pudo ser registrado en PagoPar.")
        print("Este es el motivo del error 'No existe comprador'")
        print("\nPosibles causas:")
        print("1. El comercio no tiene habilitada la funcionalidad de pagos recurrentes")
        print("2. Las credenciales son incorrectas")
        print("3. El identificador ya existe (pero con datos diferentes)")
        print("4. Problemas con los permisos del comercio")
        
        # Intentar listar tarjetas para confirmar
        print("\nIntentando listar tarjetas del usuario...")
        await list_cards(test_identifier)
    else:
        print("\n✅ Cliente registrado exitosamente!")
        
        # Test 2: Agregar Tarjeta con uPay
        print("\n\nProcediendo a probar agregar tarjeta con uPay...")
        await asyncio.sleep(2)
        
        success_card, result_card = await test_add_card(
            identifier=test_identifier,
            return_url=test_return_url,
            provider="uPay"
        )
        
        if success_card:
            print("\n🎉 ¡TODO FUNCIONA CORRECTAMENTE!")
            print(f"Hash del iframe: {result_card.get('resultado')}")
        else:
            print("\n⚠️ El cliente existe pero agregar tarjeta falló")
    
    print("\n" + "=" * 60)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
