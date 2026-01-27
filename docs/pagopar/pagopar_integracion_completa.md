# PagoPar — Documentación Unificada de Integración (Comercios)

> Documento consolidado a partir de los PDFs provistos por el usuario.  
> Última generación: 2026-01-10 21:56:17

## Objetivo

Unificar **toda** la documentación entregada (sin omisiones) en un solo archivo, y además **relacionarla** en un **paso a paso** para una integración eficiente de PagoPar en un sitio web, e-commerce o marketplace.

---

## Mapa de integración (alto nivel)

### Flujo base de cobro (Checkout PagoPar)
1. Obtener **public_key** y **private_key** en PagoPar (opción “Integrar con mi sitio web”).
2. Crear un **pedido** en PagoPar (API).
3. Redirigir al comprador al **Checkout** de PagoPar usando el **hash_pedido**.
4. Recibir **notificación** del pago (server-to-server) y/o el **redirect** a tu URL de resultado.
5. Consultar el estado del pedido si lo necesitás (traer/consulta).
6. Operaciones post: modificar pedido, reversar, tracking, etc.

### Módulos adicionales (según tu caso)
- **Pickup/Delivery (AEX, Mobi)**: cálculo de envíos, creación de pedido con datos de retiro/entrega y consulta de tracking.
- **Sincronización de productos**: catálogo/productos.
- **Suscripciones / Links**: link de suscripción.
- **Pagos recurrentes (Bancard)**: listar/eliminar tarjetas, preautorización/catastro, etc.
- **Pagopar Login**: vinculación “comercio hijo” ↔ “comercio padre” para marketplace y split billing.
- **Pase a producción**: entornos y checklist.
- **Seguridad**: reporte de vulnerabilidad (adjunto).

---

## Convenciones de autenticación (patrón general)

En varios endpoints PagoPar solicita:
- `token_publico`: clave pública del comercio (desde “Integrar con mi sitio web”).
- `token` (hash SHA1): se genera concatenando el `token_privado` con un *string fijo* según el endpoint (ej.: `CONSULTA`, `CAMBIAR-PEDIDO`, `PEDIDO-REVERSAR`, `PAGO-RECURRENTE`, etc.) y aplicando `sha1(...)`.

> **Importante:** el *string fijo* cambia por endpoint. En cada sección debajo se especifica el string exacto según la documentación.

---

# Paso a paso recomendado (integración eficiente)

## 0) Preparación
- Definir si tu integración será:
  - **E-commerce simple** (un solo comercio cobrando), o
  - **Marketplace / Split** (comercio padre + comercios hijo; usar Pagopar Login).
- Definir si usarás **envíos** integrados (AEX/Mobi) y/o **tracking**.
- Definir si requerís **pagos recurrentes** (Bancard) o **suscripciones**.

## 1) Obtener credenciales
1. Ingresar a PagoPar.
2. Ir a la opción **“Integrar con mi sitio web”**.
3. Obtener:
   - `public_key` (o `token_publico` dependiendo del endpoint)
   - `private_key` (token privado)

Estas claves son usadas en:
- Integración de medios de pago / iniciar transacción.
- Consulta / tracking.
- Cambiar datos del pedido.
- Reversión.
- Pagos recurrentes (Bancard).
- etc.

## 2) Crear pedido / iniciar transacción (Checkout PagoPar)
- Implementar el endpoint de creación de pedido / iniciar transacción según la guía “API - Integración de medios de pagos”.
- Al crear el pedido, PagoPar retorna un `hash_pedido` para construir la URL de checkout.
- Redirigir al cliente al Checkout de PagoPar.

> En integración con Pickup/Delivery, el “crear pedido” se apoya además en el cálculo de flete y la versión `comercios/2.0/iniciar-transaccion`.

## 3) Manejar notificación y redirect
- Configurar:
  - Endpoint en tu backend para recibir la notificación de PagoPar sobre el pago.
  - URL de resultado/retorno para mostrar al usuario el estado (aprobado/rechazado/pending).
- Como buena práctica: **validar estado consultando** el pedido (server-to-server) antes de marcar como pagado.

## 4) Consultas y operaciones post-pago
### 4.1) Modificar un pedido (si todavía aplica a tu negocio)
- Endpoint: `/api/pedidos/1.1/cambiar-datos/`
- Token: `sha1(token_privado + 'CAMBIAR-PEDIDO')`

### 4.2) Reversar un pedido pagado (según condiciones)
- Endpoint: `/api/pedidos/1.1/reversar`
- Token: `sha1(token_privado + 'PEDIDO-REVERSAR')`
- Consideraciones:
  - Disponible para medios específicos (Bancard y otros listados).
  - Debe solicitarse el mismo día para reversión inmediata; si no, puede quedar **agendada**.

### 4.3) Tracking (si usaste couriers AEX/Mobi)
- Endpoint: `/api/pedidos/1.1/tracking`
- Token: `sha1(private_key + 'CONSULTA')`
- Soporta `hash_pedido` y opcional `id_producto`.

## 5) Integración Pickup/Delivery (AEX/Mobi)
Si usás couriers desde PagoPar:
- Seguir el documento “Integración de servicios de pickup/delivery”.
- La documentación describe un flujo por pasos (cálculo → selección → creación del pedido → iniciar transacción).
- Nota clave: cuando hay varios productos con misma dirección de pickup y misma opción de envío, el costo se agrupa (primer ítem suma, el resto queda 0) según la guía.

## 6) Sincronización de productos
- Implementar endpoints de sincronización para mantener catálogo/productos alineados con PagoPar (ver PDF correspondiente).
- Recomendación: ejecutar sincronización incremental cuando:
  - Cambia precio/stock,
  - Se crea o elimina producto,
  - Cambia información relevante para el checkout/envío.

## 7) Suscripciones / Link de suscripción
- Implementar “Link Suscripción” según PDF si el modelo de negocio requiere suscripción del cliente.

## 8) Pagos recurrentes (Bancard)
- Para cobrar recurrentemente:
  - Revisar “Catastro de tarjetas / preautorización” y “Pagos recurrentes vía Bancard”.
  - Implementar endpoints de listar/eliminar tarjeta y/o acciones indicadas.
  - Token común en endpoints recurrentes: `sha1(private_key + 'PAGO-RECURRENTE')` (ver detalle en el PDF).

## 9) Pagopar Login (Marketplace / Split Billing)
Si tu plataforma es marketplace:
- Integrar Pagopar Login para vincular la cuenta del usuario de tu plataforma con el comercio de PagoPar.
- El flujo incluye:
  - Pantalla informativa + botón de vinculación.
  - URL de vinculación con parámetros (`hash_comercio`, `usuario_id`, `url_redirect`, `plan` opcional).
  - Redireccionamiento con parámetro adicional (hash comercio hijo, etc.).
  - Confirmación y obtención de datos del comercio hijo.

## 10) Datos del comercio
- Usar el endpoint/guía “Datos del comercio” para obtener información del comercio vinculado (útil con Pagopar Login y validaciones internas).

## 11) Errores al iniciar transacción
- Implementar manejo explícito de errores usando el documento “Listado de errores al iniciar transacción”.
- Recomendación:
  - Loguear request/response (sin exponer private_key en logs).
  - Mostrar mensajes amigables al usuario y guardar el detalle técnico para soporte.

## 12) Pase a producción
- Seguir el documento “Entornos / pase a producción”.
- Asegurar:
  - Keys correctas por entorno,
  - URLs de notificación/redirect finales,
  - Validación funcional completa,
  - Checklist de seguridad y configuración.

---

# Documentación completa (fuente original, sin omisiones)

A continuación se incluye el contenido extraído de **cada PDF** en el orden recomendado.  
**No se omite información**: se adjunta todo el texto página por página para referencia y auditoría.




---

# Fuente: api-integracion-medios-pagos.pdf


---

## Página 1

Pagopar
API - Integración de medios de pagos
Flujo normal de compra
Paso #1: El comercio crea un pedido en Pagopar
Paso #2: El comercio redirecciona a la página de Checkout de Pagopar
Paso #3: Pagopar notifica al comercio sobre el pago
Paso #4: Pagopar redirecciona a la página del resultado de pago del Comercio
Paso #1: El comercio crea un pedido en Pagopar
Descripción
El comercio genera un pedido en Pagopar, Pagopar retorna un hash que servirá para armar una URL
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
En PHP:
<?php sha1($datos['comercio_token_privado'] . $idPedido . strval(floatval($j['monto_total']))); ?>
¿Vas a utilizar medios de envíos tercerizados ofrecidos por Pagopar?
Para ello, debes seguir estos pasos adicionales explicados en la documentación.
URL: https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d",
  "comprador": {
    "ruc": "1234567-8",
    "email": "mailcomprador@gmail.com",
    "ciudad": null,
    "nombre": "Enrique González",
    "telefono": "0971111234",
    "direccion": "",
    "documento": "1234567",
    "coordenadas": "",
    "razon_social": "Enrique González",
    "tipo_documento": "CI",
    "direccion_referencia": null
  },
  "public_key": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "monto_total": 100000,
  "tipo_pedido": "VENTA-COMERCIO",
  "compras_items": [
    {
Para facilidad de integración, contamos con un proyecto en POSTMAN con los endpoints utilizados en esta documentación.
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 2

"ciudad": "1",
      "nombre": "Ticket virtual a evento Ejemplo 2017",
      "cantidad": 1,
      "categoria": "909",
      "public_key": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
      "url_imagen": "http://www.example.com/d7/wordpress/wp-content/uploads/2017/10/ticket.png",
      "descripcion": "Ticket virtual a evento Ejemplo 2017",
      "id_producto": 895,
      "precio_total": 100000,
      "vendedor_telefono": "",
      "vendedor_direccion": "",
      "vendedor_direccion_referencia": "",
      "vendedor_direccion_coordenadas": ""
    }
  ],
  "fecha_maxima_pago": "2018-01-04 14:14:48",
  "id_pedido_comercio": "1134",
  "descripcion_resumen": "",
  "forma_pago": 9
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma:
sha1($datos['comercio_token_privado'] . $idPedido .
strval(floatval($j['monto_total'])));
ef4f7ebd763e205a45a9fae5e5d8d7508235778d
comprador.ruc
Ruc del comprador. El campo debe estar presente, si no
tiene ruc, debe ir con el valor vacío ("")
1234567-8
comprador.email
E-mail del comprador. Campo obligatorio.
mailcomprador@gmail.com
comprador.ciudad
Si no está utilizando los servicios de couriers ofrecidos
por pagopar (Sólo para productos físicos), debe enviar
de todas formas el campo con el valor 1. De lo contrario
utilizar la documentación de integración de couriers para
obtener el ID de ciudad
1
comprador.nombre
Nombre del comprador. Campo obligatorio.
Enrique González
comprador.telefono
Número de teléfono en formato internacional.
+595971111234
comprador.direccion
Dirección del comprador. El campo debe estar presente,
si no tiene dirección, enviar el valor vacío ("").
comprador.documento
Número de cédula. Campo obligatorio. En caso que la
forma de pago sea PIX se debe enviar el CPF o CPNJ
1234567
comprador.coordenadas
Coordenadas de la dirección del comprador, si no tiene,
enviar con el valor vacío.
comprador.razon_social
Razón social del comprador, si no tiene, enviar el campo
con el valor vacío.
comprador.tipo_documento
Tipo de documento del comprador, por el momento
siempre debe enviarse el valor "CI" inclusive si la forma
de pago sea PIX.
CI
comprador.direccion_referencia
Referencia de la dirección del comprador. El campo
debe estar presente, si no tiene referencia, enviar vacío.
public_key
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
63820974a40fe7c5c5c53c429af8b25bed599dbf
monto_total
Monto total que se va a transaccionar, en guaranies
(PYG).
100000
tipo_pedido
Si se trata de una transacción simple, debe enviarse el
valor "VENTA-COMERCIO". Si es split billing
"COMERCIO-HEREDADO". 
VENTA-COMERCIO
compras_items.[0].ciudad
La ciudad del comprador, si no tiene, enviar el valor 1.
1
compras_items.[0].nombre
Nombre del producto o servicio que se está comprando.
Obligatorio.
Ticket virtual a evento Ejemplo 2017
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 3

compras_items.[0].cantidad
Cantidad del producto que se está comprando, solo con
fines informativos.
1
compras_items.[0].categoria
Si no está utilizando los servicios de couriers ofrecidos
por pagopar (Sólo para productos físicos), debe enviar
de todas formas el campo con el valor 909. De lo
contrario utilizar la documentación de integración de
couriers para obtener el ID de la categoría
909
compras_items.[0].public_key
Clave publica del vendedor, si no es una transacción
split billing, será el mismo valor que el campo
public_key.
63820974a40fe7c5c5c53c429af8b25bed599dbf
compras_items.[0].url_imagen
URL de la imagen del producto. Si no tiene imagen,
enviar el campo con el valor vacío.
http://www.example.com/d7/wordpress/wp-
content/uploads/2017/10/ticket.png
compras_items.[0].descripcion
Descripción del producto que se está comprando.
Ticket virtual a evento Ejemplo 2017
compras_items.[0].id_producto
Identificador del producto/servicio que se está
comprando.
895
compras_items.[0].precio_total
Precio total del producto/servicio que se está comprando
(No es el precio unitario, sino el precio total agrupado
por producto)
100000
compras_items.[0].vendedor_telefono
Telefono del vendedor. Si no tiene, debe enviarse el
valor vacío.
compras_items.[0].vendedor_direccion
Dirección del vendedor. Si no tiene, debe enviarse el
valor vacío. 
compras_items.[0].vendedor_direccion_referencia
Referencia de la dirección del vendedor. Si no tiene,
debe enviarse el valor vacío.
compras_items.[0].vendedor_direccion_coordenadas
Coordenadas de la dirección del vendedor. Si no tiene,
debe enviarse el valor vacío.
fecha_maxima_pago
Es la fecha máxima que tiene el comprador para pagar el
pedido, una vez que llegue a la fecha establecida, el
pedido automáticamente se cancela y ya no puede
pagarse.
2018-01-04 14:14:48
id_pedido_comercio
ID del pedido/transacción del comercio. Debe ser único
tanto en entorno de Desarrollo y Producción.
Alfanumérico.
1134
descripcion_resumen
Descripción breve del pedido, puede coincidir con el
valor de compras_items.[0].nombre o enviar con el valor
vacío.
Ticket virtual a evento Ejemplo 2017
forma_pago
Forma de pago en la que se pagará el pedido creado
9
Datos de ejemplo que Pagopar retornaría en caso de éxito (retorna el hash de pedido):
   
{
    "respuesta": true,
    "resultado": [
        {
            "data": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
   
   
        }
    ]
}
   
           "pedido": "1750"
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 4

Datos de ejemplo que Pagopar retornaría en caso de error:
   
{
    "respuesta": false,
   
   "resultado": "Token no coincide."
   
}
   
Puede ver el detalle de los  distintos tipos de errores que pudiera retornar la ejecución del endpoint iniciar-transacción.
Paso #2: El comercio redirecciona a la página de Checkout de Pagopar
Descripción
El comercio redirecciona a la página de Checkout de Pagopar, con el dato obtenido en el paso anterior. Antes de redireccionar, se debe asociar el identificador de pedido del
comercio con el hash del Pedido de Pagopar.
Ejemplo en PHP:
<?php header('Location: https://www.pagopar.com/pagos/ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn'); exit(); ?>
Página de Checkout de Pagopar:
El campo 'data' es el que utilizará en su base de datos para relacionar los datos de cada pedido, este campo es obligatorio almacenarlo. En cambio el campo 'pedido'
tiene un uso meramente informativo 
A tener en cuenta, el valor de resultado.data es el identificador del pedido.
Para cobrar con divisa en dólares: En lugar de utilizar el endpoint iniciar-transaccion, debes utilizar el endpoint iniciar-transaccion-divisa para iniciar una transacción
en dólares estadounidenses.
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 5

¿Tenés permiso de redireccionamiento automático?
Esta caracteristica sólo la tienen algunos comercios previa solicitud y aprobación. Esto sirve para “saltar” la pantalla de Pagopar implementando los medios de pagos en el sitio
del comercio, de tal forma, que el cliente final selecciona el medio de pago en el sitio de comercio, le da “finalizar compra” y no verá la pantalla de Pagopar, simplemente verá
la página del vPos para abonar con tarjeta de crédito (en caso que haya seleccionado tarjeta de crédito), y en caso de que haya seleccionado alguna boca de cobranza verá la
pantalla de redireccionamiento del sitio del comercio, no así la de pagopar.
Para indicar qué medio de pago seleccionó la persona, simplemente hay que agregar el parámetro al momento de redireccionar a la plataforma de Pagopar
 https://www.pagopar.com/pagos/$hash?forma_pago=' + idFormaPago; 
Lista de formas de pago
Identificador
Forma de Pago
URL Imagen
9
Bancard - Tarjetas de
crédito/débito
(Acepta Visa, Mastercard,
American Express, Discover,
Diners Club y Credifielco.)
https://cdn.pagopar.com/assets/im
credito.png
1
Procard - Tarjetas de
crédito/débito
(Acepta Visa, Mastercard,
Credicard y Unica)
https://cdn.pagopar.com/assets/im
credito.png
2
Aqui Pago
https://cdn.pagopar.com/assets/im
aquipago.png
3
Pago Express
https://cdn.pagopar.com/assets/im
pagoexpress.png
4
Practipago
https://cdn.pagopar.com/assets/im
practipago.png
10
Tigo Money
https://cdn.pagopar.com/assets/im
tigo-money.png
11
Transferencia Bancaria
https://pago.pagopar.com/assets/images/metodos-
pago/pago-manual.png
12
Billetera Personal
https://cdn.pagopar.com/assets/im
billetera-personal.png
13
Pago Móvil
https://cdn.pagopar.com/assets/im
infonet-pago-movil.png
15
Infonet Cobranzas
https://cdn.pagopar.com/assets/im
infonet.png
18
Zimple
https://cdn.pagopar.com/assets/images/pago-
zimple.png
20
Wally
https://cdn.pagopar.com/assets/images/wally.png
 22
 Wepa
https://cdn.pagopar.com/assets/images/wepa.png
23
Giros Claro
https://cdn.pagopar.com/assets/images/logos_Giros_Claro.png
 24
Pago QR
https://cdn.pagopar.com/assets/images/pago-
qr-app.png
25
PIX
https://cdn.pagopar.com/assets/images/pago-
pix-beeteller.png
Lista de formas de pago vía WS
Token para este endpoint se genera:
 sha1(Private_key + “FORMA-PAGO”) 
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 6

En PHP: sha1($datos['comercio_token_privado'] . “FORMA-PAGO”)
URL: https://api.pagopar.com/api/forma-pago/1.1/traer/
Método: POST
Datos de ejemplo que el comercio enviará a Pagopar:
Contenido:
{
    "token": "56c042541873efa67da5fa085cab8c6b4b41ca66",
    "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf"
}
Datos de ejemplo que Pagopar retornará para la petición anterior:
Contenido:
{
    "respuesta": true,
    "resultado": [
        {
            "forma_pago": "25",
            "titulo": "PIX",
            "descripcion": "PIX vía QR",
            "monto_minimo": "1000",
            "porcentaje_comision": "3.00"
        },
        {
            "forma_pago": "24",
            "titulo": "Pago QR",
            "descripcion": "Pagá con la app de tu banco, financiera o cooperativa a través de un QR",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "18",
            "titulo": "Zimple",
            "descripcion": "Utilice sus fondos de Zimple",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "9",
            "titulo": "Tarjetas de crédito",
            "descripcion": "Acepta Visa, Mastercard, American Express, Cabal, Panal, Discover, Diners Club.",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82",
            "pagos_internacionales": false
        },
        {
            "forma_pago": "10",
            "titulo": "Tigo Money",
            "descripcion": "Utilice sus fondos de Tigo Money",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "11",
            "titulo": "Transferencia Bancaria",
            "descripcion": "Pago con transferencias bancarias. Los pagos se procesan de 08:30 a 17:30 hs.",
            "monto_minimo": "1000",
            "porcentaje_comision": "3.30"
        },
        {
            "forma_pago": "12",
            "titulo": "Billetera Personal",
            "descripcion": "Utilice sus fondos de Billetera Personal",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 7

{
            "forma_pago": "13",
            "titulo": "Pago Móvil",
            "descripcion": "Usando la App Pago Móvil / www.infonet.com.py",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "20",
            "titulo": "Wally",
            "descripcion": "Utilice sus fondos de Wally",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "23",
            "titulo": "Giros Claro",
            "descripcion": "Utilice sus fondos de Billetera Claro",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "22",
            "titulo": "Wepa",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "2",
            "titulo": "Aqui Pago",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "3",
            "titulo": "Pago Express",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "15",
            "titulo": "Infonet Cobranzas",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        }
    ]
}
Paso #3: Pagopar notifica al comercio sobre el pago
Descripción
Pagopar realiza una petición a la URL de respuesta especificada en la opción “Integrar con mi sitio web” de Pagopar.com. En este endpoint, el comercio debe poner como
“pagado” un pedido específico en su sistema, por tanto, este punto es crítico, ya que si alguna persona supiera la URL de Respuesta, conociendo el API y el funcionamiento del
mismo, podría poner como pagado en el sistema del comercio ciertos pedidos arbitrariamente. Para evitar esto, es extrictamente necesario hacer una validación del token antes
de actualizar el estado del pedido a Pagado. Con esto se evita lo anteriormente mencionado, ya que para generar el token se utiliza la clave privada que nunca debe ser
compartida ni expuesta.
El comercio debe retornar Código 200, en caso de que el comercio no retorne dicho código de estado, ya sea por un problema de conectividad, servidor caído o similar,
Pagopar volverá a avisar sobre el pago cada 10 minutos hasta obtener la respuesta correcta. Esta notificación puede demorar hasta 2 minutos en realizarse, para ver el estado
real del pedido debe consultar al endpoint especificado en el Paso #4.
Observación
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 8

El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: sha1(private_key + hash_pedido)
URL: https://api.misitio.com/pagopar/respuesta/
Método: POST
Datos de ejemplo que Pagopar enviaría al Comercio en caso de pedido pagado:
Contenido:
{
  "resultado": [
    {
      "pagado": true,
      "numero_comprobante_interno": "8230473",
      "ultimo_mensaje_error": null,
      "forma_pago": "Tarjetas de crédito/débito",
      "fecha_pago": "2023-06-07 09:11:49.52895",
      "monto": "100000.00",
      "fecha_maxima_pago": "2023-06-14 09:11:32",
      "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
      "numero_pedido": "1746",
      "cancelado": false,
      "forma_pago_identificador": "1",
      "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
    }
  ],
  "respuesta": true
}
Datos de ejemplo que el Comercio debe responder a Pagopar en caso de pedido pagado:
Contenido:
[
    {
      "pagado": true,
      "numero_comprobante_interno": "8230473",
      "ultimo_mensaje_error": null,
      "forma_pago": "Tarjetas de crédito/débito",
      "fecha_pago": "2023-06-07 09:11:49.52895",
      "monto": "100000.00",
      "fecha_maxima_pago": "2023-06-14 09:11:32",
      "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
      "numero_pedido": "1746",
      "cancelado": false,
      "forma_pago_identificador": "1",
      "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
    }
  ]
Datos de ejemplo que Pagopar enviaría al Comercio en caso de reversión:
Contenido:
{
    "resultado": [
        {
            "pagado": false,
            "numero_comprobante_interno": "8230473",
            "ultimo_mensaje_error": null,
            "forma_pago": "Tarjetas de crédito/débito",
            "fecha_pago": null,
            "monto": "100000.00",
            "fecha_maxima_pago": "2018-01-04 23:40:36",
            "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
            "numero_pedido": "1746",
            "cancelado": false,
            "forma_pago_identificador": "1",
            "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
        }
    ],
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 9

"respuesta": true
}
Datos de ejemplo que el Comercio debe responder a Pagopar en caso de pedido reversado:
Contenido:
[
    {
        "pagado": false,
        "numero_comprobante_interno": "8230473",
        "ultimo_mensaje_error": null,
        "forma_pago": "Tarjetas de crédito/débito",
        "fecha_pago": null,
        "monto": "100000.00",
        "fecha_maxima_pago": "2018-01-04 23:40:36",
        "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
        "numero_pedido": "1746",
        "cancelado": false,
        "forma_pago_identificador": "1",
        "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
    }
]
Datos de ejemplo que Pagopar enviaría al Comercio en caso de pedido confirmado (pendiente de pago) para reversión:
Contenido:
{
    "resultado": [
        {
            "pagado": false,
            "numero_comprobante_interno": "8230473",
            "ultimo_mensaje_error": null,
            "forma_pago": "Pagoexpress",
            "fecha_pago": null,
            "monto": "100000.00",
            "fecha_maxima_pago": "2018-01-04 23:40:36",
            "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
            "numero_pedido": "1746",
            "cancelado": false,
            "forma_pago_identificador": "3",
            "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
        }
    ],
    "respuesta": true
}
Ejemplo de la validación del Token en Woocommerce/PHP:
Contenido:
<?php $rawInput = file_get_contents('php://input');
 $json_pagopar = json_decode($rawInput, true); 
global $wpdb; 
#Obtenemos el ID de Pedido 
$order_db = $wpdb->get_results($wpdb->prepare( "SELECT id FROM wp_transactions_pagopar WHERE hash = %s ORDER BY id DESC LIMIT 1", $json_p
#Obtenemos key privado 
A nivel de código: Recomendamos que el comercio retorne directamente el contenido del resultado del JSON enviado por Pagopar, de este modo se evita armar el
JSON manualmente optimizando el código y el funcionamiento (se evitará hacer ajustes adicionales al armado del JSON en caso de que hayan actualizaciones en la
estructura del JSON enviado por Pagopar).
Obs.: Estas notificaciones de pago son realizadas únicamente cuando se hace el pago del pedido y se hacen conforme al estado de la transacción (pagado/reversado).
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 10

$db = new DBPagopar(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, "wp_transactions_pagopar"); 
$pedidoPagopar = new Pagopar(null, $db, $origin_pagopar); 
$payments = WC()->payment_gateways->payment_gateways(); 
# Si coinciden los token, esta validación es extrictamente obligatoria para evitar el uso malisioso de este endpoint 
if (sha1($payments['pagopar']->settings['private_key'] . $json_pagopar['resultado'][0]['hash_pedido']) === $json_pagopar['resultado'][0]
# Marcamos como pagado en caso de que ya se haya pagado 
if (isset($order_db[0]->id)) { 
if ($json_pagopar['resultado'][0]['pagado'] === true) { 
$order_id = $order_db[0]->id; 
global $woocommerce; 
$customer_order = new WC_Order((int) $order_id); 
// Marcamos el pedido como Pagado 
$customer_order->payment_complete(); 
$customer_order->update_status('completed', 'Pedido Completado/Pagado.'); 
} elseif ($json_pagopar['resultado'][0]['pagado'] === false) { 
// Marcamos el pedido como Pendiente 
            } 
      } 
} else { 
echo 'Token no coincide'; 
return ''; 
} 
echo json_encode($json_pagopar['resultado']); 
?>
Paso #4: Pagopar redirecciona a la página del resultado de pago del Comercio
Descripción
Pagopar redirecciona a la página de resultado especificada en la opción “Integrar con mi sitio web” de Pagopar.com, con el hash de pedido. En ese momento, el Comercio
realiza una petición a Pagopar para saber el estado de dicho pedido en tiempo real del pedido, y de acuerdo a eso le muestra el mensaje de Pagado/Error al pagar/Pendiente de
Pago.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: Sha1(Private_key + "CONSULTA")
URL de ejemplo a la que Pagopar redireccionará: https:// www.misitio.com/pagopar/resultado/
Método: GET
URL a la que el Comercio hará la petición: https://api.pagopar.com/api/pedidos/1.1/traer
Es sumamente importante hacer el control de que el token que envía pagopar es igual al token que genera el comercio, para evitar que personas que puedan conocer su
URL de respuesta pueda hacer peticiones e impactar en el estado de sus pedidos, ejemplo, marcando como Pagado. 
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 11

Método: POST
Datos de ejemplo que el comercio enviará a Pagopar:
Contenido
{
  "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
  "token": "4f10caab2c4b757b37786ded541732f314166186",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf"
}
Datos de ejemplo que Pagopar retornará para la petición anterior:
Contenido:
{
  "respuesta": true,
  "resultado": [
    {
      "pagado": false,
      "forma_pago": "Pago Express",
      "fecha_pago": null,
      "monto": "100000.00",
      "fecha_maxima_pago": "2018-01-05 02:09:37",
      "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
      "numero_pedido": "1750",
      "cancelado": true,
      "forma_pago_identificador": "3",
      "token": "4f10caab2c4b757b37786ded541732f314166186",
      "mensaje_resultado_pago": {
        "titulo": "Pedido pendiente de pago",
        "descripcion": "<ul><li>  Eligió pagar con Pago Express, recuerde que tiene hasta las
             02:09:37 del 05/01/2018 para pagar.</li><li>  Debe ir a boca de cobranza de Pago Express,
             decir que quiere pagar el comercio <strong>Pagopar</strong>, mencionando su cédula <strong>
            0</strong> o número de pedido <strong>1.750</strong>.</li></ul>"
      }
    }
  ]
}
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos


---

## Página 12

Posterior a finalizar los pasos de esta documentación solo faltaría hacer el pase a producción .
https://soporte.pagopar.com/portal/es/kb/articles/api-integracion-medios-pagos



---

# Fuente: version-ingles-api-integración-de-medios-de-pagos.pdf


---

## Página 1

Pagopar
(Versión Inglés) API - Steps to integrate Pagopar to my website
Normal flow of purchase
Step # 1: The shop creates an order in Pagopar. 
Step # 2: The shop redirects to the Pagopar checkout page.  
Step # 3: Pagopar notifies the shop of the payment.
Step # 4: Pagopar redirects to the shop´s payment result page. 
Step # 1: The shop creates an order in Pagopar.  
Description
The shop generates an order in Pagopar, Pagopar returns a hash that will be used to build a URL.
Obs.
The value of public key and private key is obtained from the option “integrate with my website” from  Pagopar.com  
Token from this endpoint is generated: 
In PHP:
<?php sha1($datos['comercio_token_privado'] . $idPedido . strval(floatval($j['monto_total']))); ?>
Are you going to use third-party shipping methods offered by Pagopar? 
To do so, you must follow these additional steps explained in the documentation.
URL: https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion
Method: POST
Sample data that the commerce would send to Pagopar: 
Content:
{
  "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d",
  "comprador": {
    "ruc": "1234567-8",
    "email": "mailcomprador@gmail.com",
    "ciudad": null,
    "nombre": "Enrique González",
    "telefono": "0971111234",
    "direccion": "",
    "documento": "1234567",
    "coordenadas": "",
    "razon_social": "Enrique González",
    "tipo_documento": "CI",
    "direccion_referencia": null
  },
  "public_key": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "monto_total": 100000,
  "tipo_pedido": "VENTA-COMERCIO",
  "compras_items": [
    {
      "ciudad": "1",
      "nombre": "Ticket virtual a evento Ejemplo 2017",
      "cantidad": 1,
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 2

Explanation of data to be sent  
Field
Description
Example
token
It is generated as follows:
sha1($datos['comercio_token_privado'] . $idPedido .
strval(floatval($j['monto_total'])));
ef4f7ebd763e205a45a9fae5e5d8d7508235778d
comprador.ruc
Buyer's Tax ID. The field must be present; if there is no
Tax ID, it should be provided with an empty value ('')
1234567-8
comprador.email
Buyer's Email. Mandatory field
mailcomprador@gmail.com
comprador.ciudad
If you are not using the courier services offered by
Pagopar (Only for physical products), you must still
send the field with the value 1. Otherwise, refer to the
courier integration documentation to obtain the city ID.
1
comprador.nombre
Buyer's Name. Mandatory field.
Enrique González
comprador.telefono
Phone number in international format.
+595971111234
comprador.direccion
Buyer's Address. The field must be present; if there is no
address, send the empty value ('').
comprador.documento
ID Number. Mandatory field.
1234567
comprador.coordenadas
Coordinates of the buyer's address, if not available, send
with the empty value.
comprador.razon_social
Buyer's business name, if not available, send the field
with the empty value.
comprador.tipo_documento
Buyer's document type, for now, must always be sent
with the value 'CI'.
CI
comprador.direccion_referencia
Buyer's address reference. The field must be present; if
there is no reference, send it empty.
public_key
Public key obtained from Pagopar.com in the 'Integrar
con mi sitio web' section.
63820974a40fe7c5c5c53c429af8b25bed599dbf
monto_total
Total amount to be transacted, in the currency
'Guaraníes (PYG)'.
100000
tipo_pedido
If it's a simple transaction, the value 'VENTA-
COMERCIO' must be sent. If it's split billing,
'COMERCIO-HEREDADO'. 
VENTA-COMERCIO
compras_items.[0].ciudad
The buyer's city, if not available, send the value 1.
1
compras_items.[0].nombre
Name of the product or service being purchased.
Mandatory.
Ticket virtual a evento Ejemplo 2017
compras_items.[0].cantidad
Quantity of the product being purchased, for
informational purposes only.
1
compras_items.[0].categoria
If you are not using courier services offered by Pagopar
(Only for physical products), you must still send the
909
      "categoria": "909",
      "public_key": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
      "url_imagen": "http://www.example.com/d7/wordpress/wp-content/uploads/2017/10/ticket.png",
      "descripcion": "Ticket virtual a evento Ejemplo 2017",
      "id_producto": 895,
      "precio_total": 100000,
      "vendedor_telefono": "",
      "vendedor_direccion": "",
      "vendedor_direccion_referencia": "",
      "vendedor_direccion_coordenadas": ""
    }
  ],
  "fecha_maxima_pago": "2018-01-04 14:14:48",
  "id_pedido_comercio": "1134",
  "descripcion_resumen": "",
  "forma_pago": 9
}
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 3

field with the value 909. Otherwise, refer to the courier
integration documentation to obtain the category ID.
compras_items.[0].public_key
Seller's public key, if it is not a split billing transaction,
it will be the same value as the 'public_key' field.
63820974a40fe7c5c5c53c429af8b25bed599dbf
compras_items.[0].url_imagen
Product image URL. If there is no image, send the field
with the empty value.
http://www.example.com/d7/wordpress/wp-
content/uploads/2017/10/ticket.png
compras_items.[0].descripcion
Description of the product being purchased.
Ticket virtual a evento Ejemplo 2017
compras_items.[0].id_producto
Identifier of the product/service being purchased.
895
compras_items.[0].precio_total
Total price of the product/service being purchased (It is
not the unit price, but the total price grouped by
product).
100000
compras_items.[0].vendedor_telefono
Buyer's phone number. If not available, it must be sent
with the empty value.
compras_items.[0].vendedor_direccion
Seller's address. If not available, it must be sent with the
empty value.
 
compras_items.[0].vendedor_direccion_referencia
Reference of the seller's address. If not available, it must
be sent with the empty value.
compras_items.[0].vendedor_direccion_coordenadas
Coordinates of the seller's address. If not available, it
must be sent with the empty value.
fecha_maxima_pago
It is the maximum date that the buyer has to pay the
order. Once it reaches the specified date, the order is
automatically canceled and can no longer be paid.
2018-01-04 14:14:48
id_pedido_comercio
Alfanumérico.Commerce order/transaction ID. It must
be unique in both Development and Production
environments. Alphanumeric.
1134
descripcion_resumen
Brief description of the order, it can match the value of
purchases_items.[0].name or be sent with the empty
value.
Ticket virtual a evento Ejemplo 2017
forma_pago
Payment method in which the created order will be paid
9
Sample data that Pagopar would return on success (returns the order hash):
{
    "respuesta": true,
    "resultado": [
        {
            "data": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
            "pedido": "1750"
        }
    ]
}
Sample data that Pagopar would return in case of error:
   
{
    "respuesta": false,
The 'data' field is the one you will use in your database to associate the data of each order; this field is mandatory to store. On the other hand, the 'pedido' field is used
purely for informational purposes 
Keep in mind, the value of result.data is the order identifier.
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 4

"resultado": "Token no coincide."
   
}
   
You can see the details of the different types of errors that the execution of the 'iniciar-transacción' endpoint might return.
Step # 2: The commerce redirects to the Pagopar checkout page.
Description 
The commerce redirects to the page Checkout of Pagopar, with the data obtained in the  first step. Before redirecting, the commerce identifier must be associated with the
Order hash.
Example in PHP: 
<?php header('Location: https://www.pagopar.com/pagos/ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn'); exit(); ?>
Pagopar Checkout page:
Do you have automatic redirection permission? 
This feature is only available to some shops upon request and approval. This serves to “skip” Pagopar  screen by implementing payment methods in the shop website, in such a
way that final customer selects  the payment method on the shop website, clicks “Finalize purchase” and won´t see Pagopar screen. You  will only see the vPOS page to pay
with a credit card (in case you have selected that payment method),  and in case you have selected a collection point you will see the redirection screen of the shop site, not  the
Pagopar screen.
To indicate which payment method have been selected, simply add the parameter when redirecting to  the Pagopar platform.
 https://www.pagopar.com/pagos/$hash?forma_pago=' + idPaymentMethod; 
List of payment methods 
Id
Payment Method
Image URL
9
Bancard - Credit/Debit Cards
(Accepts Visa, Mastercard,
https://cdn.pagopar.com/assets/im
credito.png
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 5

American Express, Discover,
Diners Club, and Credifielco.
1
Procard - Credit/Debit Cards
(Accepts Visa, Mastercard,
Credicard, and Unica).
https://cdn.pagopar.com/assets/im
credito.png
2
Aqui Pago
https://cdn.pagopar.com/assets/im
aquipago.png
3
Pago Express
https://cdn.pagopar.com/assets/im
pagoexpress.png
4
Practipago
https://cdn.pagopar.com/assets/im
practipago.png
10
Tigo Money
https://cdn.pagopar.com/assets/im
tigo-money.png
11
Transferencia Bancaria
https://pago.pagopar.com/assets/images/metodos-
pago/pago-manual.png
12
Billetera Personal
https://cdn.pagopar.com/assets/im
billetera-personal.png
13
Pago Móvil
https://cdn.pagopar.com/assets/im
infonet-pago-movil.png
15
Infonet Cobranzas
https://cdn.pagopar.com/assets/im
infonet.png
18
Zimple
https://cdn.pagopar.com/assets/images/pago-
zimple.png
20
Wally
https://cdn.pagopar.com/assets/images/wally.png
 22
 Wepa
https://cdn.pagopar.com/assets/images/wepa.png
23
Giros Claro
https://cdn.pagopar.com/assets/images/logos_Giros_Claro.png
 24
QR payments
https://cdn.pagopar.com/assets/images/pago-
qr-app.png
List of payment methods via WS
Token for this endpoint is generated:
 sha1(Private_key + “FORMA-PAGO”) 
In PHP: sha1($datos['comercio_token_privado'] . “FORMA-PAGO”)
URL: https://api.pagopar.com/api/forma-pago/1.1/traer/
Method: POST
Sample data that the shop will send to Pagopar:
Content:
{
    "token": "56c042541873efa67da5fa085cab8c6b4b41ca66",
    "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf"
}
Sample data that Pagopar will return for the previous request:
Content:
{
    "respuesta": true,
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 6

"resultado": [
        {
            "forma_pago": "25",
            "titulo": "PIX",
            "descripcion": "PIX vía QR",
            "monto_minimo": "1000",
            "porcentaje_comision": "3.00"
        },
        {
            "forma_pago": "24",
            "titulo": "Pago QR",
            "descripcion": "Pagá con la app de tu banco, financiera o cooperativa a través de un QR",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "18",
            "titulo": "Zimple",
            "descripcion": "Utilice sus fondos de Zimple",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "9",
            "titulo": "Tarjetas de crédito",
            "descripcion": "Acepta Visa, Mastercard, American Express, Cabal, Panal, Discover, Diners Club.",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82",
            "pagos_internacionales": false
        },
        {
            "forma_pago": "10",
            "titulo": "Tigo Money",
            "descripcion": "Utilice sus fondos de Tigo Money",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "11",
            "titulo": "Transferencia Bancaria",
            "descripcion": "Pago con transferencias bancarias. Los pagos se procesan de 08:30 a 17:30 hs.",
            "monto_minimo": "1000",
            "porcentaje_comision": "3.30"
        },
        {
            "forma_pago": "12",
            "titulo": "Billetera Personal",
            "descripcion": "Utilice sus fondos de Billetera Personal",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "13",
            "titulo": "Pago Móvil",
            "descripcion": "Usando la App Pago Móvil / www.infonet.com.py",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "20",
            "titulo": "Wally",
            "descripcion": "Utilice sus fondos de Wally",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "23",
            "titulo": "Giros Claro",
            "descripcion": "Utilice sus fondos de Billetera Claro",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 7

"forma_pago": "22",
            "titulo": "Wepa",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "2",
            "titulo": "Aqui Pago",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "3",
            "titulo": "Pago Express",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        },
        {
            "forma_pago": "15",
            "titulo": "Infonet Cobranzas",
            "descripcion": "Acercándose a las bocas de pagos habilitadas luego de confirmar el pedido",
            "monto_minimo": "1000",
            "porcentaje_comision": "6.82"
        }
    ]
}
Step # 3: Pagopar notifies the shop of the payment.
Description
Pagopar makes a request to the response URL specifies in the option “Integrate with my website” of  Pagopar.com. In this endpoint, the shop must put “paid” as the specified
order in thier system,  therefore this point is critical, because if someone knew the response URL, knowing the API and how it  works, they could put as “Paid” some orders in
the shop system. In order to avoid that, it is strictly  necessary to validate the token before updating the order status to Paid. This avoids the  aforementioned, since the private
key is used to generate the token, which should never be shared or  exposed.  
The shop must return Code 200, in case shop does not return that status Code, either due to a  connectivity problem, a fallen server or similar, Pagopar will notify about the
payment every 10 minutes  until you get the correct answer.
Obs
The value of public key and private key is obtained from the option “Integrate with my website” from  Pagopar.com 
At this point Token is generated as follows: sha1(private_key + hash_pedido) 
URL: https://api.misitio.com/pagopar/respuesta/
Method: POST
Sample data that Pagopar would send to the Merchant in case of a paid order:
Content:
{
  "resultado": [
    {
      "pagado": true,
      "numero_comprobante_interno": "8230473",
      "ultimo_mensaje_error": null,
      "forma_pago": "Tarjetas de crédito/débito",
      "fecha_pago": "2023-06-07 09:11:49.52895",
      "monto": "100000.00",
      "fecha_maxima_pago": "2023-06-14 09:11:32",
      "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
      "numero_pedido": "1746",
      "cancelado": false,
      "forma_pago_identificador": "1",
      "token": "9c2ed973536395bf3f91c43ffa925bacadcf58e5"
    }
  ],
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 8

"respuesta": true
}
Sample data that the Merchant must respond to Pagopar in case of a paid order:
Content:
[
    {
      "pagado": true,
      "numero_comprobante_interno": "8230473",
      "ultimo_mensaje_error": null,
      "forma_pago": "Tarjetas de crédito/débito",
      "fecha_pago": "2023-06-07 09:11:49.52895",
      "monto": "100000.00",
      "fecha_maxima_pago": "2023-06-14 09:11:32",
      "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
      "numero_pedido": "1746",
      "cancelado": false,
      "forma_pago_identificador": "1",
      "token": "9c2ed973536395bf3f91c43ffa925bacadcf58e5"
    }
  ]
Sample data that Pagopar would send to the Merchant in case of a reversal:
Content:
{
    "resultado": [
        {
            "pagado": false,
            "numero_comprobante_interno": "8230473",
            "ultimo_mensaje_error": null,
            "forma_pago": "Tarjetas de crédito/débito",
            "fecha_pago": null,
            "monto": "100000.00",
            "fecha_maxima_pago": "2018-01-04 23:40:36",
            "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
            "numero_pedido": "1746",
            "cancelado": false,
            "forma_pago_identificador": "1",
            "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
        }
    ],
    "respuesta": true
}
Sample data that the Merchant must respond to Pagopar in case of a reversed order:
Content:
[
    {
        "pagado": false,
        "numero_comprobante_interno": "8230473",
        "ultimo_mensaje_error": null,
        "forma_pago": "Tarjetas de crédito/débito",
        "fecha_pago": null,
        "monto": "100000.00",
        "fecha_maxima_pago": "2018-01-04 23:40:36",
        "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
        "numero_pedido": "1746",
        "cancelado": false,
        "forma_pago_identificador": "1",
        "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
    }
]
Sample data that Pagopar would send to the Merchant in case of a confirmed (pending payment) order for reversal:
Content:
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 9

{
    "resultado": [
        {
            "pagado": false,
            "numero_comprobante_interno": "8230473",
            "ultimo_mensaje_error": null,
            "forma_pago": "Pagoexpress",
            "fecha_pago": null,
            "monto": "100000.00",
            "fecha_maxima_pago": "2018-01-04 23:40:36",
            "hash_pedido": "ad57c9c94f745fdd9bc9093bb409297607264af1a904e6300e71c24f15d6ggnn",
            "numero_pedido": "1746",
            "cancelado": false,
            "forma_pago_identificador": "3",
            "token": "ef4f7ebd763e205a45a9fae5e5d8d7508235778d"
        }
    ],
    "respuesta": true
}
Example of Token validation in Woocommerce/PHP.:
Content:
<?php $rawInput = file_get_contents('php://input');
 $json_pagopar = json_decode($rawInput, true); 
global $wpdb; 
#We obtain the Order ID 
$order_db = $wpdb->get_results($wpdb->prepare( "SELECT id FROM wp_transactions_pagopar WHERE hash = %s ORDER BY id DESC LIMIT 1", $json_p
#We obtain the Private Key
$db = new DBPagopar(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, "wp_transactions_pagopar"); 
$pedidoPagopar = new Pagopar(null, $db, $origin_pagopar); 
$payments = WC()->payment_gateways->payment_gateways(); 
#If the tokens match, this validation is strictly mandatory to prevent malicious use of this endpoint
if (sha1($payments['pagopar']->settings['private_key'] . $json_pagopar['result'][0]['hash_pedido']) === $json_pagopar['resultado'][0]['to
#We mark it as paid if it has already been paid 
if (isset($order_db[0]->id)) { 
if ($json_pagopar['result'][0]['pagado'] === true) { 
$order_id = $order_db[0]->id; 
global $woocommerce; 
$customer_order = new WC_Order((int) $order_id); 
//We mark the order as Paid 
$customer_order->payment_complete(); 
$customer_order->update_status('completed', 'Order Completed/Paid.'); 
} elseif ($json_pagopar['result'][0]['pagado'] === false) { 
In terms of code : We recommend that the merchant directly returns the content of the JSON result sent by Pagopar, thus avoiding manually constructing the JSON,
optimizing code and functionality (additional adjustments to JSON construction will be avoided in case there are updates in the structure of the JSON sent by
Pagopar).
Obs: These payment notifications are made only when the payment for the order is completed and are done according to the transaction status (paid/reversed).
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 10

//We mark the order as Pending 
            } 
      } 
} else { 
echo 'Token does not match'; 
return ''; 
} 
echo json_encode($json_pagopar['result']); 
?>
Step # 4: Pagopar redirects to the shop´s payment result page.
Description 
Pagopar redirects to the result page specified in the option “Integrate with my website” from  Pagopar.com, with the order hash. In that moment the shop makes a request to
Pagopar to know the  status of that order in real time, and accordingly it shows the message of Paid / Error when paying  /Pending Payment.
Obs
The value of public key and private key is obtained from the option “Integrate with my website” from  Pagopar.com 
At this point the Token is generated as follows: Sha1(Private_key + "CONSULTA") 
Example URL to which Pagopar will redirect: https://www.mywebsite.com/pagopar/result/
Method: GET
The URL to which the Merchant will make the request: https://api.pagopar.com/api/pedidos/1.1/traer
Method: POST
Example data that the merchant will send to Pagopar:
Content
{
  "hash_pedido": "b1d98a906be9d0dc6956ead8642e0d6393abe9a6fd2743663109aa90e4d73e59",
  "token": "56c042541873efa67da5fa085cab8c6b4b41ca66",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf"
}
Example data that Pagopar will return for the previous request:
Content:
{
  "respuesta": true,
  "resultado": [
    {
      "pagado": false,
      "forma_pago": "Pago Express",
      "fecha_pago": null,
      "monto": "100000.00",
      "fecha_maxima_pago": "2018-01-05 02:09:37",
      "hash_pedido": "b1d98a906be9d0dc6956ead8642e0d6393abe9a6fd2743663109aa90e4d73e59",
      "numero_pedido": "1750",
      "cancelado": true,
It is extremely important to verify that the token sent by Pagopar is the same as the token generated by the merchant, to prevent individuals who may know your
response URL from making requests and affecting the status of your orders, for example, marking them as Paid. 
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos


---

## Página 11

"forma_pago_identificador": "3",
      "token": "fa443e1b63c7a51bd14732ed22098c62b7ebb4dd",
      "mensaje_resultado_pago": {
        "titulo": "Pedido pendiente de pago",
        "descripcion": "<ul><li>  Eligió pagar con Pago Express, recuerde que tiene hasta las
             02:09:37 del 05/01/2018 para pagar.</li><li>  Debe ir a boca de cobranza de Pago Express,
             decir que quiere pagar el comercio <strong>Pagopar</strong>, mencionando su cédula <strong>
            0</strong> o número de pedido <strong>1.750</strong>.</li></ul>"
      }
    }
  ]
}
Following the completion of the steps in this documentation, the only remaining task is to transition to production.
https://soporte.pagopar.com/portal/es/kb/articles/version-ingles-api-integración-de-medios-de-pagos



---

# Fuente: listado-de-errores-al-iniciar-transacción.pdf


---

## Página 1

Pagopar
Listado de errores al iniciar transacción
Este es un listado de algunos de los errores que se pudieran presentar al realizar la petición iniciar-transacción
Descripción del error
Explicación
Token no coincide
El token debe ser generado según en el endpoint, en el caso del endpoint "iniciar-
transacción" se genera de la siguiente forma: sha1($datos['comercio_token_privado'] .
$idPedido . strval(floatval($j['monto_total'])));
Tenga en cuenta que como $idPedido es alfanumerico, no es lo mismo "01" que 1, por
lo cual, el valor de $idPedido a utilizarse en la generación de token debe ser
exactamente igual al campo de id_pedido_comercio
El comercio no tiene permiso para crear pedidos
Por motivos de seguridad y prevención, el comercio pudiera no tener permisos para
crear pedidos de forma temporal. Si le aparece este error, debe comunicarse con el
área administrativa vía el e-mail administracion@pagopar.com
Comercio no habilitado para generar pedidos
Debe ponerse en comunicación con el equipo de Desarrollo vía ticket en caso de
visualizar este error, se debe a que se está utilizando un comercio de un entorno no
existente.
Comercio no existe
Debe ponerse en comunicación con el equipo de Desarrollo vía ticket en caso de
visualizar este error, se debe a que se está utilizando un comercio no existente.
Forma de pago seleccionado no corresponde
Si su comercio tiene alguna restricción de algún medio de pago, ya sea por el rubro de
su comercio o por pedido suyo, no pueden crearse un pedido con la forma de pago
que no está asociada al cliente. En caso que crea que deba crearse puede solicitar al
equipo de Desarrollo vía ticket.
El id pedido del comercio debe de estar presente
El campo id_pedido_comercio tiene que estar presente en el JSON enviado
El pedido ya existe para ese comercio
El campo id_pedido_comercio debe ser único tanto en entorno de desarrollo como en
entorno de producción combinados. Ejemplo, el id_pedido_comercio = 1 solo debe
existir una sola vez.
La descripcion debe de estar presente
El campo descripcion debe enviarse, aunque sea con el valor vacío ("").
El documento debe de estar presente
El campo documento debe estar presente y cumplir con el formato: no se aceptan
valores alfabéticos, ni caracteres especiales (exceptuando puntos que serán
eliminados), debe ser de un rango entre 5 y 24.
El tipo documento debe de estar presente
El campo tipo_documento debe estar presente. El valor por el momento siempre debe
ser CI.
Fecha inválida.
La el campo fecha_maxima_pago debe estar presente y no puede ser una fecha (en
día) anterior a la actual.
Datos de productos invalidos
Se debe enviar el campo compras_items.
venta invalido
El campo debe estar definido, los valores posibles son VENTA-COMERCIO y
COMERCIO-HEREDADO.
El email del comprador debe existir
El campo comprador debe existir.
Monto debe ser mínimo Gs. 1.000 o máximo de Gs. 50.000.00
El monto total a pagarse puede ser entre Gs. 1.000 y Gs. 50.000.000
La moneda no existe
Debe existir el campo y por el momento el valor debe ser siempre PYG.
El precio mínimo de cada item debe ser de Gs. 1.000
Cada item dentro de compras_items debe ser de al menos Gs. 1.000.
https://soporte.pagopar.com/portal/es/kb/articles/listado-de-errores-al-iniciar-transacción



---

# Fuente: modificar-un-pedido.pdf


---

## Página 1

Pagopar
Modificar un pedido
Si por motivos propio de su negocio necesite modificar un pedido previamente creado, el siguiente endpoint le permitirá hacerlo:
Método: POST
URL: https://api.pagopar.com/api/pedidos/1.1/cambiar-datos/
Generación de token: 
sha1(token_privado + 'CAMBIAR-PEDIDO'),
Datos a enviar
{  
   "token_publico":"",
   "token": "",
   "fecha_maxima_pago":"2020-01-01",
   "monto":1000,
   "cotizacion":1,
   "descripcion":"Nueva descripcion",
   "hash_pedido":""
}
Observación: todos los cambios que se envién serán reemplazados por el valor enviado
Respuesta en caso de modificación exitosa:
{
   "respuesta": true,
   "resultado": [{"data": "de5ae0dcc9ff2bf933f5d45858edc10f88a36c73ec56b22ff72eaf1792a3d28c"}]
}
Respuesta en caso de error:
{
   "respuesta": false,
   "resultado": "Error en la cotizacion\n"
}
https://soporte.pagopar.com/portal/es/kb/articles/modificar-un-pedido



---

# Fuente: reversar-un-pedido-pagado.pdf


---

## Página 1

Pagopar
Reversar un pedido pagado
La acción de reversar está disponible cuando el cliente pagó utilizando tarjeta a través de la procesadora Bancard, también en los medios de pago Zimple, Tigo Money, Giros
Claro, Wally y Billetera Personal. Esta petición debe hacerse el mismo día del pago para que sea hecha la reversión. En caso que se realice el pedido de reversión al día
siguiente o los siguientes días, el pedido de reversión se agendará. Es importante acotar que incluso si solicita la reversión en las últimas horas del día, este podría agendarse en
lugar de aplicarse inmediatamente la reversión.
URL: https://api.pagopar.com/api/pedidos/1.1/reversar
Método: POST
Generación de token
token: sha1(token_privado + 'PEDIDO-REVERSAR')
Datos a enviar
{
    "hash_pedido": "7c07355e5a54d181cde995a8790ee9c7",
    "token": "df1da6932deb72eca5828ac5641d3bf6",
    "token_publico": "35a10eafefc6e8a22099450918383cd0"
}
Explicación de los campos
Campo
Descripción
Ejemplo
hash_pedido
Hash identificador del pedido
7c07355e5a54d181cde995a8790ee9c7
token
Se genera: sha1(token_privado + 'PEDIDO-
REVERSAR')
df1da6932deb72eca5828ac5641d3bf6
token_publico
Clave publica del comercio 
35a10eafefc6e8a22099450918383cd0
Datos de respuesta en caso de realizarse satisfactoriamente la reversión en tiempo real
{
  "respuesta": true,
  "resultado": [
    {
      "pedido": "2792947",
      "hash": "63b42f5f77dba52d9ad9981a489643ecc46ae29676692277f4c28397c2616197",
      "forma_pago": "14",
      "transaccion": "2434418",
      "estado_transaccion": "2",
      "tiempo_reversion": "Inmediata",
      "otros_datos": {
        "json_respuesta": {
          "status": "success",
          "confirmation": {
            "token": "d2126a0f6abb1a66d0a8f2546d19822d",
            "shop_process_id": 2434418,
            "response": "S",
            "response_details": "Procesado Satisfactoriamente",
            "amount": "38000.00",
            "currency": "PYG",
            "authorization_number": "791317",
            "ticket_number": "2939784103",
            "response_code": "00",
Si desea reversar un pedido pagado con algún medio de pago distinto a los mencionados anteriormente, puede enviar un e-mail a
reversiones@pagopar.com solicitando la reversión del pedido específico.
https://soporte.pagopar.com/portal/es/kb/articles/reversar-un-pedido-pagado


---

## Página 2

"response_description": "Transaccion aprobada",
            "extended_response_description": null,
            "security_information": {
              "card_source": "L",
              "customer_ip": "159.203.178.112",
              "card_country": "PARAGUAY",
              "version": "0.3",
              "risk_index": 0
            }
          }
        },
        "fecha_respuesta": "2022-04-14T12:35:00",
        "json_reversion": {
          "status": "success",
          "messages": [
            {
              "key": "RollbackSuccessful",
              "dsc": "Transacción Aprobada",
              "level": "info"
            }
          ]
        },
        "fecha_reversion": "2022-04-14T12:55:00",
        "estado_transaccion": 3,
        "forma_pago": 14
      },
      "pagado": false
    }
  ]
}
Campos
Descripción
Ejemplo
respuesta
Si es true, es porque se ejecutó el endpoint satisfactoriamente
true
resultado.pedido
Identificador de pedido generado por Pagopar y asociado al
hash de pedido
2792947
resultado.hash
Hash identificador del pedido, generado por Pagopar
63b42f5f77dba52d9ad9981a489643ecc46ae29676692277f4c28397c2616197
resultado.forma_pago
3
14
resultado.transaccion
Identificador de transacción, de uso mayormente interno
2434418
resultado.estado_transaccion
Identificador del estado de pago, de uso interno
2
resultado.tiempo_reversion
"Inmediata" si se aplica la reversión inmediata. "Agendada"
si se programa
Inmediata
resultado.otros_datos
Datos adicionales asociados al pedido, de uso mayormente
interno
(Array variable)
Datos de respuesta en caso de realizarse satisfactoriamente la reversión en tiempo real
{
  "respuesta": true,
  "resultado": [
    {
      "pedido": "2810362",
      "hash": "d3f692c39c80dec9f416ebf2ea4dfc4a84a4cbca9d2e105f9d885397886bf5e5",
      "forma_pago": "10",
      "transaccion": "2451796",
      "estado_transaccion": "2",
      "tiempo_reversion": "Agendada"
    }
  ]
Si respuesta es true y resultado.[0].tiempo_reversion = "Inmediata", significa que la reversión ha sido aplicada satisfactoriamente.
https://soporte.pagopar.com/portal/es/kb/articles/reversar-un-pedido-pagado


---

## Página 3

Como en este caso la reversión es programada, probablemente necesitemos saber cuándo se aplica efectivamente. Para saber si la reversión fue aplicada, puede hacer la
siguiente petición:
URL: https://api.pagopar.com/api/pedidos/1.1/traer
Método: POST
{
  "hash_pedido": "7c07355e5a54d181cde995a8790ee9c7",
  "token": "e7007e9913d378805a6637ac91b4e394afb4fc06",
  "token_publico": "35a10eafefc6e8a22099450918383cd0",
  "datos_adicionales": true
}
Explicación de los campos
Campo
Descripción
Ejemplo
hash_pedido
Hash identificador del pedido
7c07355e5a54d181cde995a8790ee9c7
token
Se genera: sha1(token_privado + 'CONSULTA')
df1da6932deb72eca5828ac5641d3bf6
token_publico
Clave publica del comercio 
35a10eafefc6e8a22099450918383cd0
datos_adicionales
Si se quieren obtener datos secundarios/adicionales
sobre el pedido, para este caso, se debe enviar true
true
Datos de respuesta de Pagopar:
{
  "respuesta": true,
  "resultado": [
    {
      "pagado": false,
      "forma_pago": "Bancard - Catastrar Tarjeta",
      "fecha_pago": null,
      "monto": "38000.00",
      "fecha_maxima_pago": "2022-04-16 12:39:58",
      "hash_pedido": "63b42f5f77dba52d9ad9981a489643ecc46ae29676692277f4c28397c2616197",
      "numero_pedido": "2792947",
      "cancelado": true,
      "forma_pago_identificador": "14",
      "token": "9f7022a58d99a6703ca2ef5e18543e054293c65b",
      "datos_adicionales": [
        {
          "json_respuesta": {
            "status": "success",
            "confirmation": {
              "token": "d2126a0f6abb1a66d0a8f2546d19822d",
              "shop_process_id": 2434418,
              "response": "S",
              "response_details": "Procesado Satisfactoriamente",
              "amount": "38000.00",
              "currency": "PYG",
              "authorization_number": "791317",
              "ticket_number": "2939784103",
              "response_code": "00",
              "response_description": "Transaccion aprobada",
              "extended_response_description": null,
              "security_information": {
                "card_source": "L",
                "customer_ip": "159.203.178.112",
                "card_country": "PARAGUAY",
                "version": "0.3",
                "risk_index": 0
              }
            }
          },
          "fecha_respuesta": "2022-04-14T12:35:00",
          "json_reversion": {
Si respuesta es true y resultado.[0].tiempo_reversion = "Agendada", significa que la reversión ha sido programada para aplicarse de forma manual.
https://soporte.pagopar.com/portal/es/kb/articles/reversar-un-pedido-pagado


---

## Página 4

"status": "success",
            "messages": [
              {
                "key": "RollbackSuccessful",
                "dsc": "Transacción Aprobada",
                "level": "info"
              }
            ]
          },
          "fecha_reversion": "2022-04-14T12:55:00",
          "estado_transaccion": 3,
          "forma_pago": 14
        }
      ]
    }
  ]
}
Explicación de los campos
Campos
Descripción
Ejemplo
respuesta
Si es true, es porque se ejecutó el
endpoint satisfactoriamente 
true
resultado.pagado
Si es false, es porque no está pagado, si
es true, es porque está pagado
false
resultado.forma_pago
Descripción del medio de pago con el
cual fue pagado o elegido para pagar
Bancard - Catastrar Tarjeta
resultado.fecha_pago
Fecha del pago. Si es null es porque no
está pagado o porque se reversó la
transacción
null
resultado.monto
Monto del pedido
38000
resultado.fecha_maxima_pago
Fecha máxima que se tiene para pagar el
pedido
2022-04-16 12:39:58
resultado.hash_pedido
Hash identificador del pedido, generado
por Pagopar
63b42f5f77dba52d9ad9981a489643ecc46ae29676692277f4c28397c2616197
resultado.numero_pedido
Numero de pedido identificador generado
por Pagopar
2792947
resultado.cancelado
Si es true, es porque el pedido fue
cancelado, sucede cuando se cumple la
fecha máxima de pago
(fecha_maxima_pago) 
false
resultado.forma_pago_identificador
Identificador interno de Pagopar para la
forma de pago 
14
resultado.token
0
0
resultado.datos_adicionales
Datos adicionales mayormente de uso
interno relacionado al pedido
0
resultado.datos_adicionales.fecha_reversion
Fecha de reversión, si ya se realizó
2022-04-14T12:55:00
Datos de respuesta en caso de no haberse realizado la reversión ni inmediata ni de pudo agendarse
{
    "respuesta": false,
    "resultado": "Expiró el tiempo máximo para realizar la reversión de este pedido."
}
Para determinar si una reversión ya se realizó, en caso de que haya sido agendada anteriormente, se debe verificar el valor de
resultado.datos_adicionales.fecha_reversión, si esta es de valor null, es porque aún no se ha aplicado dicha reversión, si contiene una fecha, es porque ya se realizó la
reversión.
https://soporte.pagopar.com/portal/es/kb/articles/reversar-un-pedido-pagado


---

## Página 5

https://soporte.pagopar.com/portal/es/kb/articles/reversar-un-pedido-pagado



---

# Fuente: consulta-tracking.pdf


---

## Página 1

Pagopar
Consulta tracking
Descripción
Si utilizó las funcionalidades de couriers ofrecidos por Pagopar (AEX, Mobi), puede que quiera consultar el estado del tracking de un pedido o de un producto específico, este
endpoint le permite realizar dicha operación.
URL: https://api.pagopar.com/api/pedidos/1.1/tracking
Método: POST
Datos a enviar
{
    "token_publico": "12a1a8b7e2de887fcf451cc0a2c73e4f",
    "token": "a2ac64dc286e75c6f2d5c7a5dd3c35266532dfd8",
    "hash_pedido": "906a7c0f81a0c3213594c5208973d6dcfcc56a82ec112804190ca58214bfd8b3",
    "id_producto": "642317"
}
Campo
Descripción
Ejemplo
token_publico
Clave privada obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
12a1a8b7e2de887fcf451cc0a2c73e4f
token
Se genera concatenando el token privado con el string
'CONSULTA' de la siguiente forma
sha1(private_key.CONSULTA)
a2ac64dc286e75c6f2d5c7a5dd3c35266532dfd8
hash_pedido
Hash de pedido obtenido al iniciar transacción
906a7c0f81a0c3213594c5208973d6dcfcc56a82ec112804190c
id_producto
Es un parámetro opcional, en caso que queramos saber
el tracking de un producto específico dentro de nuestro
pedido
642317
Datos a recibir en caso exitoso
{
    "respuesta": true,
    "resultado": [
        {
            "id_tracking": "A000164544",
            "estado_aex": "Entregada",
            "evento_aex": "Entrega realizada",
            "url_tracking": "http://pagopar.local/tracking/8c5c71a0de617d653991061a64c3e4d361a1c473548b87aa7639557c4b33ccc5%22,
            "etapa": "3",
            "fecha_estimada_entrega": "2020-08-03 22:14:29.232815",
            "monto": "22620.00",
            "metodo_envio": "AEX",
            "id_productos": [
                "642317"
            ]
        }
    ]
}
Datos a recibir en caso fallido
{
    "respuesta": false,
    "resultado": "Token no coincide."
}
https://soporte.pagopar.com/portal/es/kb/articles/consulta-tracking


---

## Página 2

https://soporte.pagopar.com/portal/es/kb/articles/consulta-tracking



---

# Fuente: integración-de-servicios-de-pickup-delivery.pdf


---

## Página 1

Pagopar
Integración de Servicios de pickup/delivery
Pasos para Agregar soporte de servicio de pickup/delivery
Flujo normal de 
1. Paso #1: Obtener lista de ciudades
2. Paso #2: Obtener lista de categorías Pagopar (opcional)
3. Paso #3: Calcular flete / costo de envío
4. Paso #4: Seleccionar método de envio
5. Paso #5: Crear el pedido
Paso #1: Obtener lista de ciudades
Descripción
El comercio obtiene las ciudades disponibles a para el pickup y entrega ofrecidos por las emrpesas de delivery asociadas a Pagopar, por el momento AEX y Mobi.
Observación:
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: Sha1(Private_key + "CIUDADES")
URL: https://api.pagopar.com/api/ciudades/1.1/traer
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido
{
  "token": "3821d00d4b9dc48706b145d503f91fd2de2112a5",
  "token_publico": "e65486d288714ab17e64c8c7febe3851"
}
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": [
    {
      "ciudad": "1",
      "descripcion": "Asuncion"
    },
    {
      "ciudad": "7",
      "descripcion": "Ñemby"
    },
    {
      "ciudad": "4",
      "descripcion": "San Lorenzo"
    },
    {
      "ciudad": "202",
      "descripcion": "Villarrica"
    }
  ]
}
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 2

Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Token no corresponde."
}
Paso #2: Obtener lista de categorías Pagopar (opcional)
Descripción
Para determinar el costo que tendrá un envío se necesitan saber la ciudad de origen y destino, peso y dimensiones del producto (alto, largo y ancho). La categoría Pagopar se
creó para los comercios que no cuenten con el peso y dimensiones de sus productos. Ejemplo, consumiendo el siguiente endpoint verá que la categoría "Notebooks 15
pulgadas" corresponde al ID 3820, entonces enviando ese ID usted indica dicha categoría sin necesidad de tener los datos de peso y dimensiones de su producto. En caso de
tener las dimensiones exactas de su productos, recomendamos usar estas, ya que las categorías se basan en tamaños promedios que podrían ser superior al tamaño de su
producto real, lo cual puede hacer que el envío cueste un poco más caro en el caso que se compre más de un artículo.
Observación:
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: Sha1(Private_key + "CATEGORIAS")
URL: https://api.pagopar.com/api/categorias/2.0/traer
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido
{
  "token_publico": "3821d00d4b9dc48706b145d503f91fd2de2112a5",
  "token": "508fc88ca15ff3d8668321d57831bcdc162e7161"
}
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": [
    {
      "categoria": "7587",
      "descripcion": "Pistolas de Silicona",
      "descripcion_completa": "Productos -> Librería y Mercería -> Pistolas de Silicona -> Mercería",
      "medidas": true,
      "producto_fisico": true,
      "envio_aex": true
    },
    {
      "categoria": "3820",
      "descripcion": "15 Pulgadas",
      "descripcion_completa": "Productos -> Electrónica -> Computación -> Notebooks y Accesorios -> 15 Pulgadas -> Notebooks",
      "medidas": false,
      "producto_fisico": true,
      "envio_aex": true
    },
    {
      "categoria": "4008",
      "descripcion": "Auriculares",
      "descripcion_completa": "Productos -> Electrónica -> Telefonía y Radiofrecuencia -> Radiofrecuencia -> Auriculares -> Accesorios",
      "medidas": true,
      "producto_fisico": true,
      "envio_aex": true
    }
  ]
}
Obs: En caso que su comercio requiera listar las ciudades con sus respectivos barrios, puede utilizar el endpoint de Listar Ciudades con Barrios.
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 3

Campo
Descripción
Ejemplo
categoría
ID de la categoría, a utilizarse al momento de calcular
flete.
3820
descripcion
Nombre de la categoría.
descripcion_completa
Descripción que incluye todos los niveles de categorías
superiores a la categoría en cuestion, escrito en forma de
breadcrumb.
Productos -> Electrónica -> Computación -> Notebooks
y Accesorios -> 15 Pulgadas -> Notebooks
medidas
Si se debe, además de especificar el id de categoría al
momento de calcular flete, enviar las medidas del
producto. Si la categoría dice true, significa que con el
ID de la categoría es suficiente.
false
producto_fisico
Si se trata de una categoría física o no, esto debido a que
podría ser una categoría asociada a un producto no
fisico, como los servicios o productos virtuales.
true
envio_aex
Si es que la categoría soporta envío ofrecidos por
Pagopar (AEX, Mobi)
true
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Token no corresponde."
}
Paso #3: Calcular flete / costo de envío
Descripción
El comercio solicita a Pagopar los servicios disponibles por las distintas empresas de delivery, mostrando costos y tiempos de entrega. Envia los datos del pedido que aún no se
generó, seguido de datos adicio
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: Sha1(Private_key + "CALCULAR-FLETE")
URL: https://api.pagopar.com/api/calcular-flete/2.0/traer
Método: POST
Datos de ejemplo que el comercio enviará a Pagopar:
Contenido:
{
 "tipo_pedido": "VENTA-COMERCIO",
 "fecha_maxima_pago": "2020-05-08 14:01:00",
 "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
 "id_pedido_comercio": 1,
 "monto_total": 910000,
 "token": "4a79f883ba4d83759842f9a1432d4602ab1dedf6",
 "descripcion_resumen": "",
 "comprador": {
  "nombre": "Rudolph Goetz",
  "ciudad": "1",
  "email": "fernandogoetz@gmail.com",
  "telefono": "0972200046",
  "tipo_documento": "CI",
  "documento": "4247903",
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 4

"direccion": "Direccion por defecto del comprador para calcular envio",
  "direccion_referencia": "",
  "coordenadas": "-25.26080770331157, -57.51165674656511",
  "ruc": null,
  "razon_social": null
 },
 "compras_items": [
  {
   "nombre": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "cantidad": 1,
   "precio_total": 10000,
   "ciudad": "1",
   "descripcion": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/10/5533fcbba66a44954e091b640296ae9cf147584a-300x300.jpg",
   "peso": "",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
   "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 405,
   "largo": "",
   "ancho": "",
   "alto": "",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local"
    },
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 16,
       "destino": "1",
       "precio": 1500
      }
     ]
    },
    "metodo_mobi": null
   }
  },
  {
   "nombre": "Iphone SE 2.0b",
   "cantidad": 1,
   "precio_total": 900000,
   "ciudad": "1",
   "descripcion": "Iphone SE 2.0b",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/09/8605bf8a5816a70b20181123221233000000-30-225x300.jpeg",
   "peso": "",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
   "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 327,
   "largo": "",
   "ancho": "",
   "alto": "",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local"
    },
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 17,
       "destino": "1",
       "precio": 1500
      }
     ]
    },
    "metodo_mobi": null
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 5

}
  }
 ],
 "token_publico": "ebcad4d95e229113a4e871cb491fbcfb"
}
Contenido del json dato
Nombre del campo
Explicación
Dato ejemplo
tipo_pedido
Tipo de venta:
por defecto:
VENTA-
COMERCIO
VENTA-COMERCIO
fecha_maxima_pago
Fecha máxima
disponible para
el pago de un
pedido
2020-05-08 14:01:00
public_key
Valor obtenido
desde el panel de
“Integrar con mi
sitio web”
98b96ce444802bf2657ab5c4ff2d4q14
id_pedido_comercio
ID del pedido o
transacción que
utiliza en el
sistema del
comercio, en este
endpoint lo más
probable es que
el valor sea vacío
monto_total
Monto final que
el cliente debe
abonar
100000
token
Valor
alfanumérico
generado:
Sha1(Private_key
+ "CALCULAR-
FLETE")
cebe636cA6b55ec95309060941f5a2c03be9b4b6
descripcion_resumen
Resumen de lo
que se está
comprando
Celular Iphone 8 y mouse
comprador.nombre
Nombre del
comprador
Rudolph Goetz
comprador.ciudad
Ciudad del
comprador (Este
id viene del
#Paso 1)
1
comprador.email
Email del
comprador
fernando@pagopar.com
comprador.telefono
Teléfono del
comrpador
0972200046
comprador.tipo_documento
Tipo de
documento del
comprador, por el
momento
siempre CI
CI
comprador.documento
Cédula de
identidad del
1234567
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 6

comprador
comprador.direccion
Dirección del
comprador, a esta
dirección se
enviará el
producto
Mariscal Lopez 12345 casi España
comprador.direccion_referencia
Referencia de la
casa del
comprador
Porton gris, muralla blanca
comprador.coordenadas
Coordenadas del
la casa del
comprador
-25.27595570421349, -57.548081202468374
comprador.ruc
Ruc del
comprador
Razón Social SA
comprador.razon_social
Razón social del
comprador
800123123-0
compras_items (Pueden ser varios elementos)
compras_items.nombre
Nombre del
producto
Celular Iphone 8
compras_items.cantidad
Cantidad del
producto
comprado
1
compras_items.precio_total
monto total del
item/cantidad
comprado
100000
compras_items.ciudad
Ciudad donde se
encuentra el
producto
1
compras_items.descripcion
Descripción más
larga de lo que se
está comprando
Iphone 8 color blanco, 32gb de espacio
compras_items.url_imagen
URL de la
imagen principal
del producto
https://cdn.pagopar.com/assets/images/logo-
pagopar-400px.png
compras_items.vendedor_telefono
Teléfono del
vendedor
0972200046
compras_items.vendedor_direccion
Dirección del
vendedor. A esta
dirección la
empresa de
delivery pasará a
buscar el
producto
España casi Mcal Lopez
compras_items.vendedor_direccion_referencia
Referencia de la
dirección de
donde se
encuentra el
producto
Portón gris
compras_items.vendedor_direccion_coordenadas
Coordenadas de
donde se
encuentra el
producto
compras_items.public_key
Valor obtenido
desde el panel de
“Integrar con mi
sitio web”
compras_items.id_producto
Identificdor
único del
171
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 7

Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "tipo_pedido": "VENTA-COMERCIO",
  "fecha_maxima_pago": "2020-05-08 14:01:00",
  "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
  "id_pedido_comercio": 1,
  "monto_total": 910000,
  "token": "4a79f883ba4d83759842f9a1432d4602ab1dedf6",
  "descripcion_resumen": "",
  "comprador": {
    "nombre": "Rudolph Goetz",
    "ciudad": "1",
    "email": "fernandogoetz@gmail.com",
    "telefono": "0972200046",
    "tipo_documento": "CI",
    "documento": "4247903",
producto del sitio
del cliente
compras_items.categoria
ID de la
categoria
Pagopar obtenido
en el paso
anterior. Si tiene
las medidas del
producto use
979, si no quiere
habilitar AEX,
utilice 980.
979
Datos
necesarios para
habilitar AEX
compras_items.peso
Peso en
kilogramos
1
compras_items.largo
Largo del
producto en
centímetros
10
compras_items.ancho
Ancho del
producto en
centímetros
5
compras_items.alto
Altodel producto
en centímetros
12
compras_items.opciones_envio
compras_items.opciones_envio.metodo_retiro
Datos si
queremos
habilitar
“Retiro de
sucursal”
compras_items.opciones_envio.observacion
Comentario de
dónde puede
pasar a retirar el
producto
Retiro en sucursal Matriz Mcal Lopez de 08:00
a 18:00
compras_items.opciones_envio.metodo_propio
compras_items.opciones_envio.listado
Datos
necesarios para
habilitar
método de envio
propio, se envía
la lista de
ciudades a las
que podemos
hacer delivery,
el tiempo que
nos
comprometemos
a entregar el
producto y el
costo adicional
para el cliente.
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 8

"direccion": "Direccion por defecto del comprador para calcular envio",
    "direccion_referencia": "",
    "coordenadas": "-25.26080770331157, -57.51165674656511",
    "ruc": null,
    "razon_social": null
  },
  "compras_items": [
    {
      "nombre": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
      "cantidad": 1,
      "precio_total": 10000,
      "ciudad": "1",
      "descripcion": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
      "url_imagen": "http://wordpress.local/wp-content/uploads/2020/10/5533fcbba66a44954e091b640296ae9cf147584a-300x300.jpg",
      "peso": "3.00",
      "vendedor_telefono": "12341234123",
      "vendedor_direccion": "Rafael Barret 6581",
      "vendedor_direccion_referencia": "Portón verde, muralla blanca",
      "vendedor_direccion_coordenadas": "",
      "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
      "categoria": "1471",
      "id_producto": 405,
      "largo": "32.00",
      "ancho": "23.00",
      "alto": "16.00",
      "opciones_envio": {
        "metodo_retiro": {
          "observacion": "Recogida local",
          "costo": 0,
          "tiempo_entrega": 0
        },
        "metodo_propio": {
          "listado": [
            {
              "tiempo_entrega": 16,
              "destino": "1",
              "precio": 1500
            }
          ],
          "costo": 1500,
          "tiempo_entrega": 16
        },
        "metodo_mobi": null,
        "metodo_aex": {
          "id": null,
          "opciones": [
            {
              "id": "10-0",
              "descripcion": "BUMER",
              "costo": 26738,
              "tiempo_entrega": "12"
            },
            {
              "id": "3-0",
              "descripcion": "Envio Standard",
              "costo": 22620,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-17",
              "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-13",
              "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-15",
              "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 9

"costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-14",
              "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
              "costo": 16043,
              "tiempo_entrega": "24"
            }
          ],
          "tiempo_entrega": null,
          "costo": null
        }
      }
    },
    {
      "nombre": "Iphone SE 2.0b",
      "cantidad": 1,
      "precio_total": 900000,
      "ciudad": "1",
      "descripcion": "Iphone SE 2.0b",
      "url_imagen": "http://wordpress.local/wp-content/uploads/2020/09/8605bf8a5816a70b20181123221233000000-30-225x300.jpeg",
      "peso": "3.00",
      "vendedor_telefono": "12341234123",
      "vendedor_direccion": "Rafael Barret 6581",
      "vendedor_direccion_referencia": "Portón verde, muralla blanca",
      "vendedor_direccion_coordenadas": "",
      "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
      "categoria": "1471",
      "id_producto": 327,
      "largo": "32.00",
      "ancho": "23.00",
      "alto": "16.00",
      "opciones_envio": {
        "metodo_retiro": {
          "observacion": "Recogida local",
          "costo": 0,
          "tiempo_entrega": 0
        },
        "metodo_propio": {
          "listado": [
            {
              "tiempo_entrega": 17,
              "destino": "1",
              "precio": 1500
            }
          ],
          "costo": 0,
          "tiempo_entrega": 17
        },
        "metodo_mobi": null,
        "metodo_aex": {
          "id": null,
          "opciones": [
            {
              "id": "10-0",
              "descripcion": "BUMER",
              "costo": 26738,
              "tiempo_entrega": "12"
            },
            {
              "id": "3-0",
              "descripcion": "Envio Standard",
              "costo": 22620,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-17",
              "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 10

"id": "5-13",
              "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-15",
              "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-14",
              "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
              "costo": 16043,
              "tiempo_entrega": "24"
            }
          ],
          "tiempo_entrega": null,
          "costo": 0
        }
      }
    }
  ],
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb"
}
Observación:
Como puede observarse, Pagopar retorna lo mismo que se envió, pero además agrega un array, que pertenece a la opciones de couries disponibles (metodo_aex y
metodo_mobi).
metodo_aex.opciones.descripcion
Descripción del servicio. Para tener en cuenta AEX
cuenta con varios tipos de servicios:
Bumer: es un servicio express, se recoge el producto y
se envía al destinatario de forma más rápida
Standar: el servicio de recogida del producto y entrega
del mismo en tiempo convencional.
E-Lockers: es un servicio en el cual se retira el
producto, y se lleva a unos casilleros estratégicamente
ubicados, para que luego el comprador pase a retirar.
Envio Standard
metodo_aex.opciones.costo
Valor en guaraníes del costo que define AEX del
producto con la categoría, peso y dimensiones
especificadas, teniendo en cuenta la ciudad del pickup y
entrega
20756
Nombre del campo
Explicación
Dato ejemplo
metodo_aex
Array con los datos de AEX
metodo_aex.id
En este endpoint siempre retornará el valor null, en
caso de seleccionar alguna opción del método de
envío AEX en el siguiente endpoint, se debe
reemplazar por el id de dicha opción.
null
metodo_aex.opciones
Tiempo (en horas) en que AEX se compromete a
entregar el producto, teniendo en cuenta el pickup y
entrega de las ciudades definidas del comprador y
vendedor.
24
metodo_aex.opciones.id
Identificador de la opción de envío de AEX, con este
valor se define la opción seleccionada
3-0
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 11

metodo_aex.opciones.tiempo_entrega
Tiempo (en horas) en que AEX se compromete a
entregar el producto, teniendo en cuenta el pickup y
entrega de las ciudades definidas del comprador y
vendedor.
24
metodo_mobi.opciones.descripcion
Descripción del servicio.
Envio Standard
metodo_mobi.opciones.costo
Valor en guaraníes del costo que define MOBI del
producto con la categoría, peso y dimensiones
especificadas, teniendo en cuenta la ciudad del pickup y
entrega
15000
metodo_mobi.opciones.tiempo_entrega
Tiempo (en horas) en que MOBI se compromete a
entregar el producto, teniendo en cuenta el pickup y
entrega de las ciudades definidas del comprador y
vendedor.
24
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Token no corresponde."
}
Paso #4  - Elegir medio de envio
Descripción
El comercio elige un medio de envío, para ello, debe tomar la respuesta de Pagopar del paso anterior realizar los siguientes cambios:
Campo
Acción a realizar
Ejemplo
opciones_envio.metodo_aex.id
Se debe reemplazar por el ID de la opción seleccionada.
En caso de ser una opción de MOBI la seleccionada el
campo a definir el valor
es opciones_envio.metodo_mobi.id
3-0
Nombre del campo
Explicación
Dato ejemplo
metodo_mobi
Array con los datos de MOBI
metodo_mobi.id
En este endpoint siempre retornará el valor null, en
caso de seleccionar alguna opción del método de
envío MOBI en el siguiente endpoint, se debe
reemplazar por el id de dicha opción.
null
metodo_mobi.opciones
Tiempo (en horas) en que MOBI se compromete a
entregar el producto, teniendo en cuenta el pickup y
entrega de las ciudades definidas del comprador y
vendedor.
24
metodo_mobi.opciones.id
Identificador de la opción de envío de MOBI, con este
valor se define la opción seleccionada
3-0
Para que retorne la opción de envío de MOBI, al momento de calcular el flete, se debe agregar en raíz del JSON el campo forma_pago y el campo
comprador.coordenadas debe estar definido.
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 12

opciones_envio.costo_envio
Se debe sumar el valor de todas las opciones
seleccionadas (en caso que haya más de un producto
habrán varias opciones por seleccionar) al campo costo.
22620
opciones_envio.envio_seleccionado
Se debe especificar el método de envió seleccionado.
Las opciones son:
aex
mobi
propio
retiro
aex
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
El Token en este punto se genera de la siguiente forma: Sha1(Private_key + "CALCULAR-FLETE")
URL: https://api.pagopar.com/api/calcular-flete/2.0/traer
Método: POST
Datos a enviar
{
 "id_pedido_comercio": "Test-715",
 "comprador": {
  "nombre": "Rudolph Goetz",
  "ciudad": "1",
  "email": "fernandogoetz@gmail.com",
  "telefono": "0972200046",
  "tipo_documento": "CI",
  "documento": "4247903",
  "direccion": "direccion comprador 1234",
  "direccion_referencia": null,
  "coordenadas": null,
  "ruc": "X",
  "razon_social": "SIN NOMBRE"
 },
 "compras_items": [
  {
   "nombre": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "cantidad": 1,
   "precio_total": 10000,
   "ciudad": "1",
   "descripcion": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/10/5533fcbba66a44954e091b640296ae9cf147584a-300x300.jpg",
   "peso": "3.00",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
   "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 405,
   "largo": "32.00",
   "ancho": "23.00",
   "alto": "16.00",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local",
     "costo": 0,
     "tiempo_entrega": 0
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 13

},
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 16,
       "destino": "1",
       "precio": 1500
      }
     ],
     "costo": 1500,
     "tiempo_entrega": 16
    },
    "metodo_mobi": null,
    "metodo_aex": {
     "id": "3-0",
     "opciones": [
      {
       "id": "10-0",
       "descripcion": "BUMER",
       "costo": 26738,
       "tiempo_entrega": "12"
      },
      {
       "id": "3-0",
       "descripcion": "Envio Standard",
       "costo": 22620,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-17",
       "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-13",
       "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-15",
       "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-14",
       "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
       "costo": 16043,
       "tiempo_entrega": "24"
      }
     ],
     "tiempo_entrega": "24",
     "costo": 22620
    }
   },
   "costo_envio": 22620,
   "envio_seleccionado": "aex",
   "comercio_comision": 0
  },
  {
   "nombre": "Iphone SE 2.0b",
   "cantidad": 1,
   "precio_total": 900000,
   "ciudad": "1",
   "descripcion": "Iphone SE 2.0b",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/09/8605bf8a5816a70b20181123221233000000-30-225x300.jpeg",
   "peso": "3.00",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 14

"public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 327,
   "largo": "32.00",
   "ancho": "23.00",
   "alto": "16.00",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local",
     "costo": 0,
     "tiempo_entrega": 0
    },
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 17,
       "destino": "1",
       "precio": 1500
      }
     ],
     "costo": 0,
     "tiempo_entrega": 17
    },
    "metodo_mobi": null,
    "metodo_aex": {
     "id": "3-0",
     "opciones": [
      {
       "id": "10-0",
       "descripcion": "BUMER",
       "costo": 26738,
       "tiempo_entrega": "12"
      },
      {
       "id": "3-0",
       "descripcion": "Envio Standard",
       "costo": 22620,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-17",
       "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-13",
       "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-15",
       "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-14",
       "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
       "costo": 16043,
       "tiempo_entrega": "24"
      }
     ],
     "tiempo_entrega": "24",
     "costo": 22620
    }
   },
   "costo_envio": 22620,
   "envio_seleccionado": "aex",
   "comercio_comision": 0
  }
 ],
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 15

"public_key": "ebcad4d95e229113a4e871cb491fbcfb",
 "tipo_pedido": "VENTA-COMERCIO",
 "fecha_maxima_pago": "2021-06-28 21:25:03",
 "descripcion_resumen": "",
 "monto_total": 932620,
 "token": "4a79f883ba4d83759842f9a1432d4602ab1dedf6"
}
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
 "id_pedido_comercio": "Test-715",
 "comprador": {
  "nombre": "Rudolph Goetz",
  "ciudad": "1",
  "email": "fernandogoetz@gmail.com",
  "telefono": "0972200046",
  "tipo_documento": "CI",
  "documento": "4247903",
  "direccion": "direccion comprador 1234",
  "direccion_referencia": null,
  "coordenadas": null,
  "ruc": "X",
  "razon_social": "SIN NOMBRE"
 },
 "compras_items": [
  {
   "nombre": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "cantidad": 1,
   "precio_total": 10000,
   "ciudad": "1",
   "descripcion": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/10/5533fcbba66a44954e091b640296ae9cf147584a-300x300.jpg",
   "peso": "3.00",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
   "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 405,
   "largo": "32.00",
   "ancho": "23.00",
   "alto": "16.00",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local",
     "costo": 0,
     "tiempo_entrega": 0
    },
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 16,
       "destino": "1",
       "precio": 1500
      }
     ],
     "costo": 1500,
     "tiempo_entrega": 16
    },
    "metodo_mobi": null,
    "metodo_aex": {
     "id": "3-0",
     "opciones": [
      {
       "id": "10-0",
       "descripcion": "BUMER",
       "costo": 26738,
       "tiempo_entrega": "12"
      },
      {
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 16

"id": "3-0",
       "descripcion": "Envio Standard",
       "costo": 22620,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-17",
       "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-13",
       "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-15",
       "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-14",
       "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
       "costo": 16043,
       "tiempo_entrega": "24"
      }
     ],
     "tiempo_entrega": "24",
     "costo": 22620
    }
   },
   "costo_envio": 22620,
   "envio_seleccionado": "aex",
   "comercio_comision": 0
  },
  {
   "nombre": "Iphone SE 2.0b",
   "cantidad": 1,
   "precio_total": 900000,
   "ciudad": "1",
   "descripcion": "Iphone SE 2.0b",
   "url_imagen": "http://wordpress.local/wp-content/uploads/2020/09/8605bf8a5816a70b20181123221233000000-30-225x300.jpeg",
   "peso": "3.00",
   "vendedor_telefono": "12341234123",
   "vendedor_direccion": "Rafael Barret 6581",
   "vendedor_direccion_referencia": "Portón verde, muralla blanca",
   "vendedor_direccion_coordenadas": "",
   "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
   "categoria": "1471",
   "id_producto": 327,
   "largo": "32.00",
   "ancho": "23.00",
   "alto": "16.00",
   "opciones_envio": {
    "metodo_retiro": {
     "observacion": "Recogida local",
     "costo": 0,
     "tiempo_entrega": 0
    },
    "metodo_propio": {
     "listado": [
      {
       "tiempo_entrega": 17,
       "destino": "1",
       "precio": 1500
      }
     ],
     "costo": 0,
     "tiempo_entrega": 17
    },
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 17

"metodo_mobi": null,
    "metodo_aex": {
     "id": "3-0",
     "opciones": [
      {
       "id": "10-0",
       "descripcion": "BUMER",
       "costo": 26738,
       "tiempo_entrega": "12"
      },
      {
       "id": "3-0",
       "descripcion": "Envio Standard",
       "costo": 0,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-17",
       "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-13",
       "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-15",
       "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
       "costo": 16043,
       "tiempo_entrega": "24"
      },
      {
       "id": "5-14",
       "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
       "costo": 16043,
       "tiempo_entrega": "24"
      }
     ],
     "tiempo_entrega": "24",
     "costo": 0
    }
   },
   "costo_envio": 0,
   "envio_seleccionado": "aex",
   "comercio_comision": 0
  }
 ],
 "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
 "tipo_pedido": "VENTA-COMERCIO",
 "fecha_maxima_pago": "2021-06-28 21:25:03",
 "descripcion_resumen": "",
 "monto_total": 932620,
 "token": "4a79f883ba4d83759842f9a1432d4602ab1dedf6"
}
Paso #5 - Crear pedido
Al momento de elegir un medio de envío, tener en cuenta que en caso de tener más de un producto que tiene la misma dirección de pickup y además de elegir la
misma opción de envío, se retornará el total del costo sumado en la primera opción de envío y luego el costo será 0 Gs. ya que agrupado en la primera opción, por
tratarse de solo un servicio de pickup/envío y no dos por serparado.
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 18

Se debe enviar la respuesta del paso anterior al endpoint de Iniciar Transacción, reemplazando el valor de token por el token de generación de pedido, es decir:
sha1($datos['comercio_token_privado'] . $idPedido . strval(floatval($j['monto_total'])));. Ya que el token se estaba generando hasta este punto, para el cálculo del flete y el
token para crear el pedido se genera de forma distinta. Además, la URL a la que debe enviarse es la versión 2.0 del API, como especifica más adelante:
URL: https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion
Método: POST
{
  "id_pedido_comercio": "Test-715",
  "comprador": {
    "nombre": "Rudolph Goetz",
    "ciudad": "1",
    "email": "fernandogoetz@gmail.com",
    "telefono": "0972200046",
    "tipo_documento": "CI",
    "documento": "4247903",
    "direccion": "direccion comprador 1234",
    "direccion_referencia": null,
    "coordenadas": null,
    "ruc": "X",
    "razon_social": "SIN NOMBRE"
  },
  "compras_items": [
    {
      "nombre": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
      "cantidad": 1,
      "precio_total": 10000,
      "ciudad": "1",
      "descripcion": "Accesorios y repuestos para notebook nuevos y sin garantia 2",
      "url_imagen": "http://wordpress.local/wp-content/uploads/2020/10/5533fcbba66a44954e091b640296ae9cf147584a-300x300.jpg",
      "peso": "3.00",
      "vendedor_telefono": "12341234123",
      "vendedor_direccion": "Rafael Barret 6581",
      "vendedor_direccion_referencia": "Portón verde, muralla blanca",
      "vendedor_direccion_coordenadas": "",
      "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
      "categoria": "1471",
      "id_producto": 405,
      "largo": "32.00",
      "ancho": "23.00",
      "alto": "16.00",
      "opciones_envio": {
        "metodo_retiro": {
          "observacion": "Recogida local",
          "costo": 0,
          "tiempo_entrega": 0
        },
        "metodo_propio": {
          "listado": [
            {
              "tiempo_entrega": 16,
              "destino": "1",
              "precio": 1500
            }
          ],
          "costo": 1500,
          "tiempo_entrega": 16
        },
        "metodo_mobi": null,
        "metodo_aex": {
          "id": "3-0",
          "opciones": [
            {
              "id": "10-0",
              "descripcion": "BUMER",
              "costo": 26738,
              "tiempo_entrega": "12"
            },
            {
              "id": "3-0",
              "descripcion": "Envio Standard",
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 19

"costo": 22620,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-17",
              "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-13",
              "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-15",
              "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-14",
              "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
              "costo": 16043,
              "tiempo_entrega": "24"
            }
          ],
          "tiempo_entrega": "24",
          "costo": 22620
        }
      },
      "costo_envio": 22620,
      "envio_seleccionado": "aex",
      "comercio_comision": 0
    },
    {
      "nombre": "Iphone SE 2.0b",
      "cantidad": 1,
      "precio_total": 900000,
      "ciudad": "1",
      "descripcion": "Iphone SE 2.0b",
      "url_imagen": "http://wordpress.local/wp-content/uploads/2020/09/8605bf8a5816a70b20181123221233000000-30-225x300.jpeg",
      "peso": "3.00",
      "vendedor_telefono": "12341234123",
      "vendedor_direccion": "Rafael Barret 6581",
      "vendedor_direccion_referencia": "Portón verde, muralla blanca",
      "vendedor_direccion_coordenadas": "",
      "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
      "categoria": "1471",
      "id_producto": 327,
      "largo": "32.00",
      "ancho": "23.00",
      "alto": "16.00",
      "opciones_envio": {
        "metodo_retiro": {
          "observacion": "Recogida local",
          "costo": 0,
          "tiempo_entrega": 0
        },
        "metodo_propio": {
          "listado": [
            {
              "tiempo_entrega": 17,
              "destino": "1",
              "precio": 1500
            }
          ],
          "costo": 0,
          "tiempo_entrega": 17
        },
        "metodo_mobi": null,
        "metodo_aex": {
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery


---

## Página 20

"id": "3-0",
          "opciones": [
            {
              "id": "10-0",
              "descripcion": "BUMER",
              "costo": 26738,
              "tiempo_entrega": "12"
            },
            {
              "id": "3-0",
              "descripcion": "Envio Standard",
              "costo": 0,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-17",
              "descripcion": "Elocker - Super6 Mburucuyá (Santísima Trinidad y Julio Correa)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-13",
              "descripcion": "Elocker - AEX Casa Central (Avda. España Nro. 436 casi Dr. Bestard)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-15",
              "descripcion": "Elocker - Super6 Total (Colón y Carlos Antonio López)",
              "costo": 16043,
              "tiempo_entrega": "24"
            },
            {
              "id": "5-14",
              "descripcion": "Elocker - Super6 Villa Morra (Avda. Mariscal Lopez esq. Monseñor Bogarin)",
              "costo": 16043,
              "tiempo_entrega": "24"
            }
          ],
          "tiempo_entrega": "24",
          "costo": 0
        }
      },
      "costo_envio": 0,
      "envio_seleccionado": "aex",
      "comercio_comision": 0
    }
  ],
  "public_key": "ebcad4d95e229113a4e871cb491fbcfb",
  "tipo_pedido": "VENTA-COMERCIO",
  "fecha_maxima_pago": "2021-06-28 21:25:03",
  "descripcion_resumen": "",
  "monto_total": 932620,
  "token": "021537ccae41532ecc9aa0d2a058180e283022d0"
}
Se obtendrá el hash de pedido en caso de éxito, el flujo de compra debe integrarse según la documentación de integración de medios de pagos..
https://soporte.pagopar.com/portal/es/kb/articles/integración-de-servicios-de-pickup-delivery



---

# Fuente: sincronización-de-productos.pdf


---

## Página 1

Pagopar
Sincronización de productos
Introducción
En ciertos casos un comercio puede tener un sitio web con sus respectivos productos, y querrá que se sincronicen con los links de pago de Pagopar, de tal forma de evitar la
doble carga de productos y sobre todo la doble administración de productos. Esta API nos permitirá sincronizar los productos, incluyendo el stock. La sincronización se hace
en un sentido bidireccional y puede soportar varios comercios. Por ejemplo:  se publica un producto en el sitio web del comercio, este se creará en Pagopar, y a su vez también
en un marketplace donde el comercio esté registrado. Si se realiza una actualización de dicho producto en el marketplace, esto se reflejará en Pagopar y a su vez en el sitio del
comercio.
Circuito de Sincronización
Funciones a desarrollar
Enviar datos de producto
Se creará un producto nuevo
Se modificará un producto ya existente
Recibir cambio de producto
Se creará un producto nuevo
Se editará un producto existente
Recibir cambio de stock
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 2

Enviar datos de un producto a Pagopar
Descripción: Se crea o edita un producto en Pagopar.
URL para crear un producto: https://api.pagopar.com/api/links-venta/1.1/agregar/
URL para editar un producto: https://api.pagopar.com/api/links-venta/1.1/editar/
Método: POST
Datos a enviar:
{
   "id_producto":"44",
   "envio_aex":{
      "activo":true,
      "direccion_coordenadas":"",
      "peso":1,
      "largo":1,
      "ancho":1,
      "alto":1,
      "comentarioPickUp":"No funciona el timbre, favor llamar al llegar",
      "direccion_retiro":null,
      "direccion":"Rafael Barret 6581",
      "direccion_ciudad":"1",
      "hora_inicio":"09:00:00",
      "hora_fin":"16:00:00",
      "direccion_referencia":"Port\u00f3n verde, muralla blanca"
   },
   "envio_mobi": {
    "horarios": [
      {
        "dias": [
          "1",
          "2",
          "3",
          "4",
          "5"
        ],
        "pickup_fin": "17:00",
        "pickup_inicio": "09:00"
      }
    ],
    "titulo": "Horario ",
    "activo": true,
    "usuario_mobi": 302,
    "direccion_retiro": null
  },
   "categoria":979,
   "token_publico":"cc6f9a547fdc7930731dc475cc7513d9",
   "token":"a24689e31175a5ce14c35438f71ae55b52cb3e69",
   "link_publico":true,
   "activo":true,
   "link_venta":"",
   "monto":"25000",
   "titulo":"Lentes realidad virtual Google Cardboard 3D",
   "descripcion":"Prueba aplicaciones para ver los v\u00eddeos del celular con efecto de pantalla gigante todo con privacidad total y co
   "cantidad":1,
   "imagen":[
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/37a6259cc0c1dae299a7866489dff0bdwkpV9uqHWfRnIMG_20180809_111420-830_A-830_
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/37a6259cc0c1dae299a7866489dff0bdeBTIk71Fq8USIMG_20180809_111550-830_A-830_
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/37a6259cc0c1dae299a7866489dff0bdbk5GzmjYPl78IMG_20180809_111331-830_A-830_
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/37a6259cc0c1dae299a7866489dff0bdi0I8oka1yFgOIMG_20180809_111536-830_A-830_
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/publicacion-cc447af40420440962d42b827650568e8a33c63f8e8fb113f6b56874c979e0
      "http:\/\/128.199.11.19\/wp-content\/uploads\/2020\/09\/37a6259cc0c1dae299a7866489dff0bdQnL6KSvDOsEfgoogle-cardboard-3-830_A-830_A
   ]
}
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 3

Campo
Descripción
Ejemplo
token_publico
Clave pública obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
224a987739b87f03b2d54d2c4bbc7334
token
Se genera de la siguiente forma sha1(private_key +
'LINKS-VENTA')
ed2f6f55cdf0b03824b2de3ec81fdd97
id_producto
Id del producto de nuestro sitio web
5
envio_aex.activo
Si se habilita AEX para el producto
true/false
envio_aex.direccion_coordenadas
Coordenadas de la dirección donde se encuentra el
producto
-25.311976, -57.565545
envio_aex.peso
Peso del producto (kg)
1
envio_aex.largo
Largo del producto (cm)
1
envio_aex.ancho
Ancho del producto (cm)
1
envio_aex.alto
Alto del producto (cm)
1
envio_aex.comentarioPickUp
Algún comentario adicional para el courier
Favor llamar al llegar, timbre no funciona
envio_aex.direccion_retiro
ID de la dirección de Pagopar
null por defecto
envio_aex.direccion
Calle de la dirección
Rafael Barret 6581
envio_aex.direccion_ciudad
ID de la ciudad (Se obtiene el ID de la siguiente
documentación)
1
envio_aex.hora_inicio
Hora en la cual está disponible para retirar el producto
09:00:00
envio_aex.hora_fin
Hora hasta la cual está disponible para retirar el
producto
16:00:00
envio_aex.direccion_referencia
Referencia de la dirección para ayudar al courier
identificar el lugar de retiro
Portón verde, muralla blanca
envio_mobi.horarios.[0].dias
Días de la semana disponible para entregar el courier el
producto
Array("1", "2", "3", "4", "5")
envio_mobi.horarios.[0].pickup_fin
Hasta qué hora está disponible para entregar al courier el
producto
17:00
envio_mobi.horarios.[0].pickup_inicio
Desde qué hora está disponible para entregar al courier
el producto
09:00
envio_mobi.horarios.titulo
Título para identificar el horario
Horario
envio_mobi.horarios.activo
Si el courier Mobi está disponible
true/false
envio_mobi.horarios.usuario_mobi
Debe ser null al crear el producto, al editar el producto
debe ser el valor enviado por Pagopar
null
envio_mobi.horarios.direccion_retiro
ID de dirección, puede estar seteado null si está seteado
aex.direccion_retiro si se se está creando el producto, si
se está editando, pasar el valor que Pagopar le enviará
null
categoria
ID de la categoría Pagopar  (Se obtiene el ID de la
siguiente documentación). Si va a especificar las
medidas, se debe enviar 979.
979
link_publico
Si el producto está disponible para importar
true/false
activo
Si el producto esta habilitado o deshabilitado. Si no está
habilitado no se visualizará ni se podrá comprar
true/false
link_venta
Link de pago generado, al crear el producto se envía
vacío, al editar el link de venta que ha recibido, el cual
es un dato numérico entero.
monto
Precio del producto, numérico. La divisa es Guaraníes
25000
titulo
Título del producto
Lentes realidad virtual Google Cardboard 3D
descripcion
Descripción del producto
Prueba aplicaciones para ver los vídeos del celular con
efecto de pantalla gigante todo con privacidad total y
comodidad Compatible con android e iOS.
Recomendado smartphone de ultima generación
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 4

cantidad
Inventario/stock disponible para la venta
1
imagen
Imágenes del producto, este campo sólo se debe incluir
en caso que haya un cambio de imagen (se agregan o
editan), si no se modifican las imágenes del producto,
este campo no debe ser incluido.
https://mi-sitio-sincronizado.com.py/wp-
content/uploads/2020/09/37a6259cc0c1dae299a7866489dff0b
830_A-830_A-830_A-830_A-830_A-830_A.jpg
Datos retornados por Pagopar
{
   "respuesta":true,
   "resultado":{
      "url":"https:\/\/pago.pagopar.com\/bh1",
      "id":"223",
      "link_venta":"14869",
      "resultado":"OK"
   }
}
Campo
Descripción
Ejemplo
respuesta
Si se exportó correctamente el producto
true
resultado.url
URL de link de pago generado en Pagopar
https://pago.pagopar.com/bh1
resultado.id
ID del producto en el sitio del comercio
223
resultado.link_venta
ID del producto en Pagopar
14869
Datos enviados por Pagopar para crear/editar un producto
Descripción: Pagopar realizará una petición a la siguiente URL para crear o editar producto en el sitio web del comercio.
URL para crear/editar un producto: Se define como la URL de respuesta (definido en Pagopar.com > Integrar con mi sitio web) concatenado por "?sincronización"
Ejemplo de URL: https://www.sitio-web.com/confirm-url/?sincronizacion
Método: POST
Datos a recibir
{
   "token_publico":"7a97ba0babb6c621ddaf17a6a1c80ce3",
   "token":"9096306e7d1168d323b9d688ec68604b68ecbda1",
   "datos":[
      {
         "logs":"44830",
         "datos":{
            "alto":1,
            "peso":1,
            "ancho":1,
            "largo":1,
            "monto":100000,
            "activo":true,
            "imagen":[
               
            ],
            "titulo":"Accesorios para linterna pechera Streamlight",
            "usuario":{
               "nombre":"Rudolph",
               "apellido":"Goetz",
               "email":"fernandogoetz@gmail.com",
               "celular":"0972200046"
            },
            "cantidad":1,
            "categoria":{
En caso que no utilice algunos datos de envío como AEX; Mobi o Envio Propio, debe tener en cuenta que puede recibir estos datos de Pagopar, y por lo tanto, debe
guardar y retornar lo recibido, sino al editar un producto y sincronizar se estaría reemplazando estos valores definidos por null y borrando dichos datos.
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 5

"categoria":979,
               "descripcion":"Producto Gen\u00e9rico con AEX",
               "medidas":false,
               "producto_fisico":true,
               "comercio":125073
            },
            "direccion":{
               "direccion":"Rafael Barret 6581",
               "observacion":"Port\u00f3n verde 4",
               "latitud_longitud":"",
               "ciudad":1,
               "ciudad_descripcion":"Asuncion",
               "direccion_retiro":48777,
               "comentario_pickup":"No funciona el timbre, favor llamar al llegar",
               "hora_inicio":"09:00:00",
               "hora_fin":"16:00:00"
            },
            "envio_aex":true,
            "vinculado":true,
            "envio_mobi":{
               "mobi_usuario":309,
               "horarios":[
                  {
                     "dias":[
                        "1",
                        "2",
                        "3",
                        "4",
                        "5"
                     ],
                     "pickup_fin":"16:00",
                     "pickup_inicio":"09:00"
                  }
               ],
               "titulo":"Horario ",
               "activo":true
            },
            "descripcion":"<p>Accesorios para Linterna \"pechera\" Streamlight Survivor.<\/p>",
            "envio_propio":[
               {
                  "descripcion":"Central",
                  "zona_envio":1258,
                  "ciudad":[
                     {
                        "descripcion":"Capiata",
                        "ciudad":9,
                        "costo":10000,
                        "horas_entrega":24
                     },
                     {
                        "descripcion":"Raul Pe\u00f1a",
                        "ciudad":87,
                        "costo":15000,
                        "horas_entrega":24
                     },
                     {
                        "descripcion":"Jose Fassardi",
                        "ciudad":140,
                        "costo":20000,
                        "horas_entrega":48
                     }
                  ]
               }
            ],
            "retiro_local":true,
            "observacion_retiro":"Sucursal Matriz"
         },
         "tipo_aviso":"3",
         "fecha":"2020-10-27 21:05:49.93093",
         "cantidad_venta":"0",
         "token_publico":"7a97ba0babb6c621ddaf17a6a1c80ce3",
         "link_venta":"14846"
      }
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 6

]
}
Campo
Descripción
Ejemplo
token_publico
Clave privada obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
224a987739b87f03b2d54d2c4bbc7334
token
Se genera de la siguiente forma sha1(private_key +
'LINKS-VENTA')
ed2f6f55cdf0b03824b2de3ec81fdd97
datos
datos.[0].logs
ID de log en Pagopar, se recomienda guardar este valor
para hacer seguimiento de los cambios que pueda recibir
el sitio web generado por Pagopar
44830
datos[0].logs.datos.alto
Alto del producto (cm)
1
datos[0].logs.datos.peso
Peso del producto (kg)
1
datos[0].logs.datos.ancho
Ancho del producto (cm)
1
datos[0].logs.datos.largo
Largo del producto (cm)
1
datos[0].logs.datos.monto
Precio del producto, numérico. La divisa es Guaraníes
25000
datos[0].logs.datos.activo
Disponibilidad del producto, si está disponible para la
venta.
true/false
datos[0].logs.datos.imagen
Array con la URL de las Imágenes del producto, este
campo tendrá items sólo si hay que actualizar la lista de
imágenes en el sitio web, sino se enviará vació. En caso
que retorne el array de las URLs, el sitio debe copiar
estas imágenes a su servidor.
datos[0].logs.datos.titulo
Título del producto
Lentes realidad virtual Google Cardboard 3D
datos[0].logs.datos.usuario
Datos del usuario dueño del comercio. Solo infomativo.
datos[0].logs.datos.cantidad
Inventario/stock disponible para la venta
1
datos[0].logs.datos.categoria.categoria
ID de la categoría Pagopar
979
datos[0].logs.datos.categoria.descripcion
Descripción de la categoría Pagopar
Producto Genérico con AEX
datos[0].logs.datos.categoria.medidas
Si la categoría necesita de todas formas medidas (alto,
largo, ancho) y peso
true/false
datos[0].logs.datos.categoria.producto_fisico
Si la categoría corresponde a un producto físico (que
soporta delivery)
true/false
datos[0].logs.datos.categoria.comercio
ID de Comercio Pagopar. Solo informativo.
125073
datos[0].logs.datos.direccion.direccion
Calle de la dirección
Rafael Barret 6581
datos[0].logs.datos.direccion.observacion
Referencia de la dirección para ayudar al courier
identificar el lugar de retiro o alguna observación
Portón verde 4
datos[0].logs.datos.direccion.latitud_longitud
Coordenadas de la dirección donde se encuentra el
producto
-25.311976, -57.565545
datos[0].logs.datos.direccion.ciudad
ID de la ciudad (De Pagopar)
1
datos[0].logs.datos.direccion.ciudad_descripcion
Descripción de la ciudad
Asunción
datos[0].logs.datos.direccion.direccion_retiro
ID de la dirección de retiro (De Pagopar)
48777
datos[0].logs.datos.direccion.comentario_pickup
Algún comentario adicional para el courier
Favor llamar al llegar, timbre no funciona
datos[0].logs.datos.direccion.hora_inicio
Hora en la cual está disponible para retirar el producto
09:00:00
datos[0].logs.datos.direccion.hora_fin
Hora hasta la cual está disponible para retirar el
producto
16:00:00
datos[0].logs.datos.envio_aex.
Si se habilita AEX para el producto
true/false
datos[0].logs.datos.vinculado
Si el comercio está vinculado. Uso solo informativo.
true/false
datos[0].logs.datos.envio_mobi.mobi_usuario
ID interno de Pagopar
306
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 7

datos[0].logs.datos.envio_mobi.horarios.[0].dias
Días de la semana disponible para entregar el courier el
producto
Array("1", "2", "3", "4", "5")
datos[0].logs.datos.envio_mobi.[0].horarios.pickup_fin
Hasta qué hora está disponible para entregar al courier el
producto
17:00
datos[0].logs.datos.envio_mobi.
[0].horarios.pickup_inicio
Desde qué hora está disponible para entregar al courier
el producto
09:00
datos[0].logs.datos.envio_mobi.titulo
Título para identificar el horario
Horario
datos[0].logs.datos.envio_mobi.activo
Si el courier Mobi está disponible
true/false
datos[0].logs.datos.descripcion
Descripción del producto
Prueba aplicaciones para ver los vídeos del celular con
efecto de pantalla gigante todo con privacidad total y
comodidad Compatible con android e iOS.
Recomendado smartphone de ultima generación
datos[0].logs.datos.envio_propio.[0].descripcion
Nombre de la zona de cobertura de entrega de pedido a
cargo del comercio. 
Central
datos[0].logs.datos.envio_propio.[0].zona_envio
ID de la zona de envío en Pagopar
1258
datos[0].logs.datos.envio_propio.[0].ciudad.ciudad
Ciudad destino
1
datos[0].logs.datos.envio_propio.[0].ciudad.descripcion
Descripción de la ciudad destino
Asunción
datos[0].logs.datos.envio_propio.[0].ciudad.costo
Costo que se le cobrará al cliente por el delivery a la
ciudad destino
10000
datos[0].logs.datos.envio_propio.
[0].ciudad.horas_entrega
Tiempo (en horas) en el cual se compromete el comercio
a entregar el producto en la ciudad especificada
24
datos[0].logs.datos.retiro_local
Si está habilitado retiro del local
true/false
datos[0].logs.datos.observacion_retiro
Alguna observación sobre la opción de "retiro del local",
ejemplo, dirección y horario disponible para el retiro
Sucursal Matriz
datos[0].logs.tipo_aviso
Tipo de notificación que está enviado Pagopar. De
acuerdo a este parámetro debe realizar la distinta tarea
de actualización de datos.
1. Venta pedido 
Debe desencadenar descontar el stock
2. Pedido cancelado
Debe desencadenaraumentar el stock
3. Modificación link de pago
Debe desencadenar actualizar un producto
4. Nuevo link de pago.
Debe desencadenar crear un nuevo producto
2
datos[0].logs.fecha.
Fecha generación de log de actualización
2020-10-27 21:05:49.93093
datos[0].logs.cantidad_venta
Cantidad de ventas totales (sincronizadas)
0
datos[0].logs.token_publico
Token público del comercio
7a97ba0babb6c621ddaf17a6a1c80ce3
datos[0].logs.link_venta
Link de pago generado, el cual es un dato numérico
entero. Este ID es importante ya en otras palabras es el
ID de producto en Pagopar, por tanto nos sirve para
emparejar nuestro ID de producto con dicho ID.
14846
Datos a responder
{
   "resultado":[
      {
         "link_venta":"14846",
         "logs":"44830",
         "tipo_aviso":"3",
         "id_producto":"29",
         "respuesta":true
      }
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 8

],
   "respuesta":true
}
Campos
Descripción
Ejemplo
resultado.[0].link_venta
Se debe retornar el link de pago (link_venta) enviado
por Pagopar
resultado.[0].logs
ID de log enviado por pagopar
44830
resultado.[0].tipo_aviso
Tipo de notificación, se debe retornar el mismo valor
enviado por Pagopar
3
resultado.[0].id_producto
ID de producto del sitio web
20
resultado.[0].respuesta
Resultado de la actualización, si se realizó
satisfactoriamente.
true/false
respuesta
Resultado en general de la petición en bloque, si se
realizó satisfactoriamente.
true/false
Datos enviados por Pagopar cuando se debe actualizar el inventario
Descripción: Pagopar realizará una petición a la siguiente URL para actualizar el inventario del producto en el sitio del comercio, esta actualización se puede dar ya sea porque
hubo un pedido confirmado o porque se liberó un pedido reservado.
URL para crear/editar un producto: Se define como la URL de respuesta (definido en Pagopar.com > Integrar con mi sitio web) concatenado por "?sincronización"
Ejemplo de URL: https://www.sitio-web.com/confirm-url/?sincronizacion
Método: POST
{
   "token_publico":"7a97ba0babb6c621ddaf17a6a1c80ce3",
   "token":"9096306e7d1168d323b9d688ec68604b68ecbda1",
   "datos":[
      {
         "logs":"44840",
         "datos":{
            "cantidad":0
         },
         "tipo_aviso":"1",
         "fecha":"2020-10-27 23:47:22.317092",
         "cantidad_venta":"1",
         "token_publico":"7a97ba0babb6c621ddaf17a6a1c80ce3",
         "link_venta":"14846",
         "imagenes":"[\"archivos\/imagenes\/5bb49b09bc36440043fb4688a5fe9fb9e7b971f7.jpg\",\"archivos\/imagenes\/f4655758adeeb961da336051
         "comercio_padre_heredado":null,
         "comercio":"125072"
      }
   ]
}
Campos
Descripción
Ejemplo
token_publico
Clave privada obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
7a97ba0babb6c621ddaf17a6a1c80ce3
token
Se genera de la siguiente forma sha1(private_key)
9096306e7d1168d323b9d688ec68604b68ecbda1
datos[0].logs
ID de log en Pagopar, se recomienda guardar este valor
para hacer seguimiento de los cambios que pueda recibir
el sitio web generado por Pagopar
44840
datos[0].logs.datos.cantidad
Inventario actual
0
datos[0].logs.datos.tipo_aviso
Se especifica si el disparador es por una venta o una
cancelación de pedido, de acuerdo a esto se puede sumar
o restar el stock (cantidad_venta), o directamente
actualizar el inventario al campo datos.cantidad.
1
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos


---

## Página 9

1. Venta pedido 
Debe desencadenar descontar el stock
2. Pedido cancelado
Debe desencadenaraumentar el stock
datos[0].logs.datos.fecha
Fecha generación de log de actualización
2020-10-27 23:47:22.317092
datos[0].logs.datos.cantidad_venta
Cantidad de la venta o cantidad de reposición segun el
tipo_aviso
1
datos[0].logs.datos.token_publico
Clave privada obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
7a97ba0babb6c621ddaf17a6a1c80ce3
datos[0].logs.datos.link_venta
ID del producto en Pagopar
14846
datos[0].logs.datos.comercio_padre_heredado
null
datos[0].logs.datos.comercio
ID de Comercio Pagopar
Datos a responder
{
   "resultado":[
      {
         "link_venta":"14846",
         "logs":"44840",
         "tipo_aviso":"1",
         "respuesta":true
      }
   ],
   "respuesta":true
}
Campos
Descripción
Ejemplo
resultado.[0].link_venta
Se debe retornar el link de pago (link_venta) enviado
por Pagopar
resultado.[0].logs
ID de log enviado por pagopar
44830
resultado.[0].tipo_aviso
Tipo de notificación, se debe retornar el mismo valor
enviado por Pagopar
1
resultado.[0].respuesta
Resultado de la actualización, si se realizó
satisfactoriamente.
true/false
respuesta
Resultado en general de la petición en bloque, si se
realizó satisfactoriamente.
true/false
https://soporte.pagopar.com/portal/es/kb/articles/sincronización-de-productos



---

# Fuente: link-suscripcion.pdf


---

## Página 1

Pagopar
Link de suscripción
El "Link de Suscripción" es una innovadora herramienta proporcionada por Pagopar, diseñada para simplificar el
proceso de gestión de productos o servicios por parte de nuestros clientes, ya sean comercios o vendedores. Esta
herramienta permite cargar fácilmente los datos relevantes de los productos o servicios directamente desde la
plataforma Pagopar, convirtiéndolos en enlaces de suscripción accesibles para los clientes finales.
Con el "Link de Suscripción", los clientes de nuestros comercios o vendedores pueden suscribirse para realizar
pagos de manera recurrente utilizando todos nuestros medios de pago disponibles. Estas suscripciones pueden
configurarse con diferentes periodos de cobro, que pueden ser mensuales, quincenales o semanales, adaptándose
así a las necesidades específicas de cada negocio.
Además, se ofrece flexibilidad en cuanto a la duración de las suscripciones, que pueden tener una vigencia de 6
meses, 12 meses o incluso ser ilimitadas, brindando así una amplia gama de opciones para adaptarse a diversas
estrategias comerciales.
Configuración avanzada
Para recibir las notificaciones debes definir los siguientes datos en el apatado de 'Configuración avanzada' 
Datos para configuración avanzada:
Campo
Descripción
Url de callback
Dirección web a la que se notifica después de
completar la acción
específica(suscripción/pago/desuscripción) 
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 2

Identificador en tu comercio
Identificador del link de suscripción que utiliza su
comercio, se utiliza para identificar en tu
sitio/aplicación el link de suscripción por el cual se
está notificando 
Datos de ejemplo que Pagopar enviará en caso de nueva suscripción:
Especificación de datos:
Es de suma importancia que el sitio que usted especifique como 'Url de callback'  retorne exactamente el m
Pagopar que recibió exitosamente la notificación, de lo contrario, si no notifica que la recibió exitosamente, P
{
  "tipo_accion": "suscripcion",
  "token": "e13bc8411fa2adc4d8cf6c14c2fdb66c718c6599",
  "usuario": {
    "token_identificador": "45e47cb0c497039fe80260eca471dc74b557e2d9",
    "documento": "2209099",
    "nombre": "Juan",
    "apellido": "González",
    "email": "mailcliente9@gmail.com",
    "celular": "0985886259",
    "razon_social": "Juan M. González",
    "ruc": "2209099-9"
  },
  "suscripcion": {
    "id": "5",
    "identificador_comercio": "AAA001",
    "fecha_suscripcion": "2023-09-19 16:40:42.142421",
    "link_suscripcion": "2",
    "titulo": "Servicio Suscripción Indefinida",
    "monto": "55000",
    "titulo_suscripcion": "Suscripción Indefinida",
    "estado": "Pendiente de Pago",
    "cantidad_debito": null,
    "vigencia": "Ilimitado",
    "periodicidad": "Mensual",
    "identificador_forma_pago": "14",
    "titulo_forma_pago": "Bancard - Catastrar Tarjeta",
    "visitas": "10"
  }
}
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 3

Campo
Descripción
tipo_accion
Indica la acción que se está notificando, puede ser pagado, suscripc
desuscripcion
token
Se genera con el token privado del comercio concatenado al tipo d
notificación de la siguiente
forma: sha1(token_privado_comercio.suscripcion)
usuario.token_identificador
Token identificador del usuario
usuario.documento
Documento de identidad del usuario
usuario.nombre
Nombre del usuario
usuario.apellido
Apellido del usuario
usuario.email
Dirección de mail del usuario
usuario.celular
Número de celular del usuario
usuario.razon_social
Razón social del usuario
usuario.ruc
RUC del usuario
suscripcion.id
Identificador del link de suscripción
suscripcion.identificador_comercio
Identificador del link de suscripción definida en el comercio 
suscripcion.fecha_suscripcion
Fecha en la que el usuario se suscribió
suscripcion.link_suscripcion
Link de suscripción
suscripcion.titulo
Titulo vigente de la suscripción
suscripcion.monto
Monto del link de suscripción
suscripcion.titulo_suscripcion
Titulo histórico de la suscripción
suscripcion.estado
Estado actual de la suscripción
suscripcion.cantidad_debito
Cantidad de débitos realizados de la sucripción realizadas al usuari
suscripcion.vigencia
Vigencia de la suscripción
suscripcion.periodicidad
Periocidad de cobro de la suscripción
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 4

suscripcion.identificador_forma_pago
Identificador de la forma de pago seleccionada por el usuario al mo
de suscribirse
suscripcion.titulo_forma_pago
Descripción de la forma de pago seleccionada por el usuario al mo
de suscribirse
suscripcion.visitas
Cantidad de visitas de la suscripción
Datos de ejemplo que Pagopar enviará en caso de nuevo pago:
{
  "tipo_accion": "pagado",
  "token": "192ce72393abc6e6a5eca96859bff3019a6e6009",
  "usuario": {
    "token_identificador": "45e47cb0c497039fe80260eca471dc74b557e2d9",
    "documento": "2209099",
    "nombre": "Juan",
    "apellido": "González",
    "email": "mailcliente9@gmail.com",
    "celular": "0985886259",
    "razon_social": "Juan M. González",
    "ruc": "2209099-9"
  },
  "pago": {
    "hash_pedido": "d585079c0cd77b885e115bf67d7d618fcdc66bab5fd815a0d03c063d784dacc9",
    "comprobante_interno": "497294",
    "fecha_pago": "2024-01-25 11:10:44.30565",
    "identificador_forma_pago_transaccion": "14",
    "titulo_forma_pago_transaccion": "Bancard - Catastrar Tarjeta"
  },
  "suscripcion": {
    "id": "72",
    "identificador_comercio": "OL1902",
    "fecha_suscripcion": "2024-01-25 11:10:36.159187",
    "link_suscripcion": "6",
    "titulo": "Suscripcion Plan 2",
    "monto": "1000",
    "titulo_suscripcion": "Suscripcion Plan 2",
    "estado": "Pagada",
    "cantidad_debito": "6",
    "vigencia": "6 Meses",
    "periodicidad": "Mensual",
    "identificador_forma_pago": "14",
    "titulo_forma_pago": "Bancard - Catastrar Tarjeta",
    "visitas": "6"
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 5

Especificación de datos:
Campo
Descripción
tipo_accion
Indica la acción que se está notificando, puede ser pagado, suscripcion
desuscripcion
token
Se genera con el token privado del comercio concatenado al tipo de
notificación de la siguiente
forma: sha1(token_privado_comercio.tipo_accion)
usuario.token_identificador
Token identificador del usuario
usuario.documento
Documento de identidad del usuario
usuario.nombre
Nombre del usuario
usuario.apellido
Apellido del usuario
usuario.email
Dirección de mail del usuario
usuario.celular
Número de celular del usuario
usuario.razon_social
Razón social del usuario
usuario.ruc
RUC del usuario
pago.hash_pedido
Hash identificador del pedido. Sólo aplica para la notificacion de
pago(pagado)
pago.comprobante_interno
Número de comprobante del pago. Sólo aplica para la notificacion de
pago(pagado)
pago.fecha_pago
Fecha en la que se realizó el pago al link de suscripción. Sólo aplica p
notificacion de pago(pagado)
pago.identificador_forma_pago_transacci
on
Identificador de la forma de pago utilizada para pagar el link de suscri
Sólo aplica para la notificacion de pago(pagado)
pago.titulo_forma_pago_transaccion
Descripción de la forma de pago utilizada para pagar el link de suscrip
Sólo aplica para la notificacion de pago(pagado)
suscripcion.id
Identificador del link de suscripción
suscripcion.identificador_comercio
Identificador del link de suscripción definida en el comercio 
suscripcion.fecha_suscripcion
Fecha en la que el usuario se suscribió
  }
}
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 6

suscripcion.fecha_desuscripcion
Fecha en la que el usuario se desuscribió Sólo aplica para la notificaci
desuscripción(desuscripcion) 
suscripcion.link_suscripcion
Link de suscripción
suscripcion.titulo
Titulo vigente de la suscripción
suscripcion.monto
Monto del link de suscripción
suscripcion.titulo_suscripcion
Titulo histórico de la suscripción
suscripcion.estado
Estado actual de la suscripción
suscripcion.cantidad_debito
Cantidad de débitos realizados de la sucripción realizadas al usuario
suscripcion.vigencia
Vigencia de la suscripción
suscripcion.periodicidad
Periocidad de cobro de la suscripción
suscripcion.identificador_forma_pago
Identificador de la forma de pago seleccionada por el usuario al mome
suscribirse
suscripcion.titulo_forma_pago
Descripción de la forma de pago seleccionada por el usuario al momen
suscribirse
suscripcion.visitas
Cantidad de visitas de la suscripción
Datos de ejemplo que Pagopar enviará en caso de nueva desuscripción:
{
  "tipo_accion": "desuscripcion",
  "token": "4aba0b7bb3da17797b15faea586c17e98c1a12a9",
  "usuario": {
    "token_identificador": "45e47cb0c497039fe80260eca471dc74b557e2d9",
    "documento": "2209099",
    "nombre": "Juan",
    "apellido": "González",
    "email": "mailcliente9@gmail.com",
    "celular": "0985886259",
    "razon_social": "Juan M. González",
    "ruc": "2209099-9"
  },
  "suscripcion": {
    "id": "56",
    "identificador_comercio": "17",
    "fecha_suscripcion": "2023-12-07 09:47:11.612073",
    "fecha_desuscripcion": "2024-03-05 11:49:52.242181",
    "link_suscripcion": "5",
    "titulo": "Suscripcion Plan 1",
    "monto": "1000",
    "titulo_suscripcion": "Suscripcion Plan 1",
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 7

Especificación de datos:
Campo
Descripción
tipo_accion
Indica la acción que se está notificando, puede ser pagado, suscripcion
desuscripcion
token
Se genera con el token privado del comercio concatenado al tipo de
notificación de la siguiente forma: sha1(token_privado_comercio.suscr
usuario.token_identificador
Token identificador del usuario
usuario.documento
Documento de identidad del usuario
usuario.nombre
Nombre del usuario
usuario.apellido
Apellido del usuario
usuario.email
Dirección de mail del usuario
usuario.celular
Número de celular del usuario
usuario.razon_social
Razón social del usuario
usuario.ruc
RUC del usuario
suscripcion.id
Identificador del link de suscripción
suscripcion.identificador_comercio
Identificador del link de suscripción definida en el comercio 
suscripcion.fecha_suscripcion
Fecha en la que el usuario se suscribió
suscripcion.fecha_desuscripcion
Fecha en la que el usuario se suscribió
suscripcion.link_suscripcion
Link de suscripción
suscripcion.titulo
Titulo vigente de la suscripción
    "estado": "Cancelada",
    "cantidad_debito": "12",
    "vigencia": "12 Meses",
    "periodicidad": "Mensual",
    "identificador_forma_pago": "14",
    "titulo_forma_pago": "Bancard - Catastrar Tarjeta",
    "visitas": "115"
  }
}
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion


---

## Página 8

suscripcion.monto
Monto del link de suscripción
suscripcion.titulo_suscripcion
Titulo histórico de la suscripción
suscripcion.estado
Estado actual de la suscripción
suscripcion.cantidad_debito
Cantidad de débitos realizados de la sucripción realizadas al usuario
suscripcion.vigencia
Vigencia de la suscripción
suscripcion.periodicidad
Periocidad de cobro de la suscripción
suscripcion.identificador_forma_pago
Identificador de la forma de pago seleccionada por el usuario al mome
suscribirse
suscripcion.titulo_forma_pago
Descripción de la forma de pago seleccionada por el usuario al momen
suscribirse
suscripcion.visitas
Cantidad de visitas de la suscripción
https://soporte.pagopar.com/portal/es/kb/articles/link-suscripcion



---

# Fuente: pagopar-login-29-8-2020.pdf


---

## Página 1

Pagopar
Pagopar Login
 Table of contents
¿Qué es Pagopar Login?
Requisitos
Conceptos básicos
Pasos para integrar Pagopar Login
Pantalla inicial
Link de vinculación
Página de Pagopar Login
Redireccionamiento de vinculación
Confirmación de vinculación
Obtener datos del comercio hijo
¿Qué es Pagopar Login?
Pagopar Login es una herramienta que te permite conectar una cuenta de usuario de tu sitio web con una cuenta específica (comercio) de Pagopar. Esto puede ser muy útil
cuando se utiliza Split Billing, ya que Pagopar retorna los datos necesarios para identificar a dicho usuario Pagopar, para luego poder acreditarle ventas hechas en tu sitio web.
Si tenés un sitio web tipo marketplace esta herramienta puede ser muy útil.
Requisitos
Para utilizar esta funcionalidad primero debe contactarse con el equipo comercial a comercial@pagopar.com
Conceptos básicos
Comercio Padre: Es el comercio que posee el plan empresarial y quien desarrolla la integración con Pagopar Login. El comercio padre puede ganar una comisión, definida
por el mismo de forma dinámica, de acuerdo a sus reglas de negocios (planes propios en su sitio web) por cada venta que se tenga. Un ejemplo a nivel mundial de marketplace
podría ser Amazon.com 
Comercio Hijo: Es el comercio dueño del producto o servicio que se está vendiendo, vinculará su cuenta del sitio web del comercio padre con un comercio de su cuenta de
Pagopar. Siguiendo el ejemplo anterior, si Amazon.com es el comercio padre, los comercios hijos serían todos los comercios dentro de Amazon.com que venden.
Pasos para integrar Pagopar Login
Pantalla inicial
El primer paso es tener una página donde expliques al usuario sobre la vinculación, en caso de que cobres un adicional por venta, deberías explicar en esta pantalla también.
Además, se debe tener un botón con un link de vinculación ,dicho link sería el siguiente:
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 2

Ejemplo de página inicial. En este caso, el link de vinculación se encuentra en el botón "Empezar"
Link de vinculación
El link de vinculación sería el siguiente: 
https://www.pagopar.com/v1.0/pagopar-login/login/?hash_comercio=A8aEa8X9e3te9w7fcf451cx0a2cz3xYf&usuario_id=4161&url_redirect=https%3A%2F
Campo
Explicación
Ejemplo
hash_comercio
Clave pública del comercio padre.
A8aEa8X9e3te9w7fcf451cx0a2cz3xYf
usuario_id
El id de usuario/cuenta del usuario en el sitio web del
comercio padre
4161
url_redirect
URL donde se realizará un redireccionamiento al
finalizar la vinculación
https://www.comerciopadre.com/callback-pagopar-
login&pro=0
plan
(opcional) Plan de Pagopar al que se va a suscribir el
usuario. Para ver los planes disponibles puede visitar
https://www.pagopar.com/planes
1
Página de Pagopar Login
Una vez que el cliente haga clic en la url de vinculación, verá la página de Pagopar Login, en la cual se puede loguear a su cuenta Pagopar o registrar en caso que no posea una
cuenta.
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 3

Resultado de hacer clic en el link de vinculación
Una vez en esta página, pueden suceder varias opciones:
1. Si el usuario se loguea:
1. Vincula automáticamente su cuenta y se redirecciona al parámetro url_redirect previamente definido
2. Dependiendo del estado del comercio del usuario en Pagopar, se le puede pedir al usuario que suba algunos documentos de ser necesario
3. Dependiendo de la cantidad de comercios que tenga en Pagopar, se le puede pedir elegir con cuál comercio desea vincular
2. Si el usuario decide registrarse
1. Completa sus datos, ingresa a su cuenta, y luego se le pedirá cargar algunos documentos. Luego se redireccionará al parámetro url_redirect previamente definido.
Redireccionamiento de vinculación
Una vez vinculada la cuenta, se redireccionará a la url de redireccionamiento previamente definida (url_redirect) pero con un parámetro agregado, explicado a continuación.
Campo
Explicación
Ejemplo
hash_comercio
Clave pública del comercio hijo.
H8aEa8X9e3te9w7fcf451cx0a2cz3xYf
Confirmación de vinculación
Una vez aterrizada en la página del cliente, se debe confirmar la vinculación, esto finaliza el proceso de vinculación:
URL: https://api.pagopar.com/api/pagopar-login/2.0/confirmar-vinculacion/
Método: POST
Generación del token
 sha1(token_privado + 'PAGOPAR-LOGIN'),
Datos a enviar
El hash_comercio debe ser guardado en el sitio de cliente, con este dato serán invocadas los endpoint correspondientes al comercio hijo. 
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 4

{  
   "token":"d17c2ccd82bf1929bf734b046e3a611e",
   "token_publico":"3301513c6ce2e98985b231c5801de515",
   "token_comercio_hijo":"e433de7422c08f1e15a6d9929d1e3f59",
   "usuario_id":4161,
}
Datos retornados en caso de error
{
    "respuesta": false,
    "resultado": "Token no corresponde."
}
Datos retornados en caso de éxito
{
    "respuesta": true,
    "resultado": {
        "descripcion": "Ushop",
        "porcentaje_comision": 6.05,
        "razon_social": "Ushop de Enrique González",
        "ruc": "1234567-8",
        "modo_pago_denominacion": "Pagopar-Card",
        "servicios": true,
        "retiro_local": true,
        "envio_propio": true,
        "comercio": 12,
        "ranking": 5,
        "modo_pago": 1,
        "contrato_firmado": false,
        "permisos_link_venta": false,
        "forma_pago": [
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Express",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Tigo Money",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 50000,
                "forma_pago": "Practipago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Billetera Personal",
                "tipo": "Diferenciado",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Móvil",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 5

{
                "monto_minimo": 1000,
                "forma_pago": "Infonet Cobranzas",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Procard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 7.7
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Catastrar Tarjeta",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Aqui Pago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Contra Entrega",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Zimple",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - V2.0",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            }
        ],
        "plan": {
            "plan": 3,
            "descripcion": "Avanzado",
            "costo": 199000,
            "fecha_siguiente_factura": "2020-08-01T12:36:56.685076"
        },
        "entorno": "Staging",
        "tipo_venta": "Venta Comercio",
        "usuario": {
            "email": "emailcliente@gmail.com",
            "nombre": "Enrique",
            "apellido": "González",
            "celular": "0972123456",
            "saldo": 26661,
            "documento": "1234567",
            "fecha_saldo_actualizacion": "2020-07-17T13:10:35.428805",
            "monto_pendiente_cobro": -33002,
            "hash": null,
            "estado_pago": "N",
            "pago_plan": true,
            "pago_tarjeta": true
        },
        "pedidos_pendientes": [
        {
            "url": "https://pagopar.com/pagos/0b7a21a9e019a98568b857d868e4bbd8c66df72372697033d7d2e6670cd3326b%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Junio"
        },
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 6

{
            "url": "https://pagopar.com/pagos/2b5e93ca665affefb34476b7d7bc29af609e162cbf0e7c91795a0b11ac00e30e%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Mayo"
        }
    ]
    }
}
Obtener datos del comercio hijo
Este endpoint no está dentro del circuito de Pagopar Login, pero puede ser útil cuando se necesite obtener datos de la cuenta vinculada en tiempo real, por ejemplo, para
mostrar las deudas que tiene en Pagopar en el sitio web del comercio padre.
URL: https://api.pagopar.com/api/pagopar-login/2.0/datos-comercio/
Método: POST
Generación del token
 sha1(token_privado + 'PAGOPAR-LOGIN'),
Datos a enviar
{  
   "token":"d17c2ccd82bf1929bf734b046e3a611e",
   "token_publico":"3301513c6ce2e98985b231c5801de515",
   "token_comercio_hijo":"e433de7422c08f1e15a6d9929d1e3f59",
   "usuario_id":4161,
}
Datos retornados en caso de error
{
    "respuesta": false,
    "resultado": "Token no corresponde."
}
Datos retornados en caso de éxito
{
    "respuesta": true,
    "resultado": {
        "descripcion": "Ushop",
        "porcentaje_comision": 6.05,
        "razon_social": "Ushop de Enrique González",
        "ruc": "1234567-8",
        "modo_pago_denominacion": "Pagopar-Card",
        "servicios": true,
        "retiro_local": true,
        "envio_propio": true,
        "comercio": 12,
        "ranking": 5,
        "modo_pago": 1,
        "contrato_firmado": false,
        "permisos_link_venta": false,
        "forma_pago": [
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Express",
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 7

"tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Tigo Money",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 50000,
                "forma_pago": "Practipago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Billetera Personal",
                "tipo": "Diferenciado",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Móvil",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Infonet Cobranzas",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Procard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 7.7
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Catastrar Tarjeta",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Aqui Pago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Contra Entrega",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Zimple",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - V2.0",
                "tipo": "Defecto",
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020


---

## Página 8

"porcentaje_comision": 6.05
            }
        ],
        "plan": {
            "plan": 3,
            "descripcion": "Avanzado",
            "costo": 199000,
            "fecha_siguiente_factura": "2020-08-01T12:36:56.685076"
        },
        "entorno": "Staging",
        "tipo_venta": "Venta Comercio",
        "usuario": {
            "email": "emailcliente@gmail.com",
            "nombre": "Enrique",
            "apellido": "González",
            "celular": "0972123456",
            "saldo": 26661,
            "documento": "1234567",
            "fecha_saldo_actualizacion": "2020-07-17T13:10:35.428805",
            "monto_pendiente_cobro": -33002,
            "hash": null,
            "estado_pago": "N",
            "pago_plan": true,
            "pago_tarjeta": true
        },
        "pedidos_pendientes": [
        {
            "url": "https://pagopar.com/pagos/0b7a21a9e019a98568b857d868e4bbd8c66df72372697033d7d2e6670cd3326b%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Junio"
        },
        {
            "url": "https://pagopar.com/pagos/2b5e93ca665affefb34476b7d7bc29af609e162cbf0e7c91795a0b11ac00e30e%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Mayo"
        }
    ]
    }
}
https://soporte.pagopar.com/portal/es/kb/articles/pagopar-login-29-8-2020



---

# Fuente: datos-del-comercio.pdf


---

## Página 1

Pagopar
Obtener datos del comercio
Este endpoint retorna los datos de un comercio, puede ser útil para saber la comisión que posee el comercio, las deudas pendientes con Pagopar y los permisos habilitados,
entre otros datos que se retornan.
URL: https://api.pagopar.com/api/comercios/2.0/datos-comercio/
Método: POST
Generación del token
 sha1(token_privado + 'DATOS-COMERCIO'),
Datos a enviar
{  
   "token":"5f37540d5e9ac4c2797ec67ba9395872fde9becc",
   "public_key":"3ceefa55009e99ea761493d8a4104740"
}
Datos retornados en caso de error
{
    "respuesta": false,
    "resultado": "Token no corresponde."
}
Datos retornados en caso de éxito
{
    "descripcion": "Ushop",
    "porcentaje_comision": 9.35,
    "razon_social": "Ushop de Rudolph Goetz",
    "ruc": "4247903-7",
    "modo_pago_denominacion": "Pagopar-Card",
    "servicios": true,
    "retiro_local": true,
    "envio_propio": true,
    "comercio": 12,
    "ranking": 5,
    "modo_pago": 1,
    "permisos_link_venta": false,
    "forma_pago": [
        {
            "monto_minimo": 1000,
            "forma_pago": "Pago Express",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Bancard - Tarjetas de crédito",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Tigo Money",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
https://soporte.pagopar.com/portal/es/kb/articles/datos-del-comercio


---

## Página 2

{
            "monto_minimo": 50000,
            "forma_pago": "Practipago",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Billetera Personal",
            "tipo": "Diferenciado",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Pago Móvil",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Infonet Cobranzas",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Procard - Tarjetas de crédito",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Bancard - Catastrar Tarjeta",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Aqui Pago",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Contra Entrega",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Zimple",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        },
        {
            "monto_minimo": 1000,
            "forma_pago": "Bancard - V2.0",
            "tipo": "Defecto",
            "porcentaje_comision": 9.35
        }
    ],
    "plan": {
        "plan": 3,
        "descripcion": "Avanzado",
        "costo": 199000,
        "fecha_siguiente_factura": "2020-07-24T06:05:27.31065"
    },
    "entorno": "Staging",
    "tipo_venta": "Venta Comercio",
    "usuario": {
        "email": "fernandogoetz@gmail.com",
        "nombre": "Rudolph",
        "apellido": "Goetz",
https://soporte.pagopar.com/portal/es/kb/articles/datos-del-comercio


---

## Página 3

"celular": "0972200046",
        "saldo": 65661,
        "documento": "4247903",
        "fecha_saldo_actualizacion": "2020-07-17T09:33:56.79868",
        "monto_pendiente_cobro": -33002,
        "hash": null,
        "estado_pago": "B",
        "pago_plan": true,
        "pago_tarjeta": true
    },
    "pedidos_pendientes": [
        {
            "url": "https://pagopar.com/pagos/0b7a21a9e019a98568b857d868e4bbd8c66df72372697033d7d2e6670cd3326b%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Junio"
        },
        {
            "url": "https://pagopar.com/pagos/2b5e93ca665affefb34476b7d7bc29af609e162cbf0e7c91795a0b11ac00e30e%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Mayo"
        }
    ]
}
{
    "respuesta": true,
    "resultado": {
        "descripcion": "Ushop",
        "porcentaje_comision": 6.05,
        "razon_social": "Ushop de Rudolph Goetz",
        "ruc": "4247903-7",
        "modo_pago_denominacion": "Pagopar-Card",
        "servicios": true,
        "retiro_local": true,
        "envio_propio": true,
        "comercio": 12,
        "ranking": 5,
        "modo_pago": 1,
        "contrato_firmado": false,
        "permisos_link_venta": false,
        "forma_pago": [
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Express",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Tigo Money",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 50000,
                "forma_pago": "Practipago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
https://soporte.pagopar.com/portal/es/kb/articles/datos-del-comercio


---

## Página 4

"forma_pago": "Billetera Personal",
                "tipo": "Diferenciado",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Pago Móvil",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Infonet Cobranzas",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Procard - Tarjetas de crédito",
                "tipo": "Defecto",
                "porcentaje_comision": 7.7
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - Catastrar Tarjeta",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Aqui Pago",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Contra Entrega",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Zimple",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            },
            {
                "monto_minimo": 1000,
                "forma_pago": "Bancard - V2.0",
                "tipo": "Defecto",
                "porcentaje_comision": 6.05
            }
        ],
        "plan": {
            "plan": 3,
            "descripcion": "Avanzado",
            "costo": 199000,
            "fecha_siguiente_factura": "2020-08-01T12:36:56.685076"
        },
        "entorno": "Staging",
        "tipo_venta": "Venta Comercio",
        "usuario": {
            "email": "fernandogoetz@gmail.com",
            "nombre": "Rudolph",
            "apellido": "Goetz",
            "celular": "0972200046",
            "saldo": 26661,
            "documento": "4247903",
            "fecha_saldo_actualizacion": "2020-07-17T13:10:35.428805",
            "monto_pendiente_cobro": -33002,
            "hash": null,
            "estado_pago": "N",
            "pago_plan": true,
https://soporte.pagopar.com/portal/es/kb/articles/datos-del-comercio


---

## Página 5

"pago_tarjeta": true
        },
        "pedidos_pendientes": [
        {
            "url": "https://pagopar.com/pagos/0b7a21a9e019a98568b857d868e4bbd8c66df72372697033d7d2e6670cd3326b%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Junio"
        },
        {
            "url": "https://pagopar.com/pagos/2b5e93ca665affefb34476b7d7bc29af609e162cbf0e7c91795a0b11ac00e30e%22,
            "fecha_maxima_pago": "2020-09-01T00:00:00",
            "estado": "Pendiente",
            "monto": 199000,
            "descripcion": "Pago mensual plan: Avanzado Mayo"
        }
    ]
    }
}
https://soporte.pagopar.com/portal/es/kb/articles/datos-del-comercio



---

# Fuente: pagos-recurrentes-vía-bancard-pagopar.pdf


---

## Página 1

Pagopar
Pagos Recurrentes vía Bancard/Pagopar
 Table of contents
Pagos recurrentes con Tarjeta de credito/débito vía Bancard en Pagopar
Primeros pasos
Descripción
Requisitos
Agregar Cliente
Endpoint “Agregar Cliente”
Descripción
Agregar Tarjeta
Endpoint “Agregar Tarjeta”
Descripción
Agregar Tarjeta
HTML Agregar Tarjeta
Descripción
Confirmar Tarjeta
Endpoint Confirmar Tarjeta
Descripción
Listar Tarjetas
Endpoint Listar tarjetas
Descripción
Eliminar Tarjeta
Endpoint Eliminar tarjeta
Descripción
Pagar
Endpoint pagar
Pagos recurrentes con Tarjeta de credito/débito vía Bancard en Pagopar
Primeros pasos
Importante: A modo de ofrecerle mejoras y actualizaciones, le recomendamos utilizar la documentación actualizada  Catastro de tarjetas - Pagos recurrentes -
Preautorización, que asegurará una mejor experiencia y compatibilidad con futuros desarrollos.
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 2

Descripción
La funcionalidad de pagos recurrentes vía Bancard a traves de Pagopar permite realizar un pago en cualquier momento, de una tarjeta de crédito/débito previamente catastrada/guardada por el
usuario.
El usuario guarda/catrastra la tarjeta, se le hará preguntas de seguridad, en caso que conteste todas las preguntas correctamente, se permitirá agregar la tarjeta asociandola al usuario, caso
contrario, bloqueará la tarjeta y deberá comunicarse vía telefónica con Bancard para desbloquearla.
Para poder pagar o eliminar una tarjeta, por seguridad Bancard utiliza tokens temporales, por tanto, primero se debe listar las tarjeta de un usuario, seleccionar utilizando ese token temporal y
luego decidir si se va a abonar utlizando dicha tarjeta, u otra acción, como eliminar la tarjeta, siempre utilizando ese token temporal.
Requisitos
1. 
Poseer un contrato firmado con Pagopar, para dicha gestión debe de contactar al Departamento de Administración de Pagopar (administracion@pagopar.com) y solicitar dicha
funcionalidad
2. 
Haber implementado todos los pasos del circuito de Pagopar en su sitio.
3. 
Bajar el script que genera el código embedbido en el sitio web: Bancard Checkout JS
Agregar Cliente
Endpoint “Agregar Cliente”
Descripción
El comercio envia a Pagopar los datos del cliente, creando un cliente con un identificador, al cual serán asignadas tarjetas posteriormente.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/1.1/agregar-cliente/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
   "token": "a3955831ca0315797a4fd2c01d4338a76672acdd",
   "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
   "identificador": 1,
   "nombre_apellido": "Enrique González",
   "email": "mailcliente@gmail.com",
   "celular": "0981111222"
}
Observación: El campo “identificador” corresponde al ID del usuario del sistema del comercio, no debe repetirse
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": {
    "id_comprador_comercio": "1",
    "nombres_apellidos": "Enrique González",
    "email": "mailcliente@gmail.com",
    "celular": "0981111222"
  }
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Token no corresponde."
}
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 3

Agregar Tarjeta
Endpoint “Agregar Tarjeta”
Descripción
El comercio solicita a Pagopar la creación de una nueva tarjeta asociada a un Usuario.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/1.1/agregar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "a3955831ca0315797a4fd2c01d4338a76672acdd",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "url": "https://www.misitioejemplo.com.py/checkout",
  "identificador": 1
}
Observación:
El campo “identificador” corresponde al ID del usuario del sistema al cual va a asociarse la tarjeta
El campo “url” es a donde se va a redireccionar luego del que el cliente agregue su tarjeta a través del iframe de Bancard
Datos de ejemplo que Pagopar retornaría en caso de éxito:
Datos de ejemplo que Pagopar retornaría en caso de error:
Agregar Tarjeta
HTML Agregar Tarjeta
Descripción
El comercio muestra el HTML utilizando la librería de Bancard, con el dato obtenido en el paso anterior “Endpoints - Agregar Tarjeta”
Contenido del HTML:
<html>
 <head>
   <script src="bancard-checkout-2.1.0.js"></script>
 </head>
 <script type="text/javascript">
   window.onload = function () {
     var styles = {
       'input-background-color' : '#ffffff',
       'input-text-color': '#333333',
       'input-border-color' : '#ffffff',
       'input-placeholder-color' : '#333333',
{
   "respuesta": true,
   "resultado": "JIugXOLYIvpjMpN2n9GN"
}
{
   "respuesta": false,
   "resultado": "Error al cargar"
}
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 4

'button-background-color' : '#5CB85C',
       'button-text-color' : '#ffffff',
       'button-border-color' : '#4CAE4C',
       'form-background-color' : '#ffffff',
       'form-border-color' : '#dddddd',
       'header-background-color' : '#dddddd',
       'header-text-color' : '#333333',
       'hr-border-color' : '#dddddd'
     };
     options = {
       styles: styles
     }
     Bancard.Cards.createForm('iframe-container', 'json.resultado', options);
   };
 </script>
 <body>
   <h1>iFrame vPos</h1>
   <div style="height: 130px; width: 100%; margin: auto" id="iframe-container"/>
 </body>
</html>
Vista Previa:
Observación: Se le pedirá ingresar su CI más algunas preguntas de seguridad
Al completar los datos en caso que se complete todo de forma correcta:
Se direccionará a:
Al completar los datos en caso que se complete de forma incorrecta:
Se direccionará a:
Importante
Al retornar a la Url especificada, ya sea que se haya realizado el catastro de forma correcta o no, se debe llamar al endpoint “Confirmar tarjeta”. Es de caracter obligatorio y necesario para el
funcionamiento de todo el circuito.
https://www.misitio-ejemplo.com/?status=add_new_card_success
https://www.misitio-ejemplo.com/?
status=add_new_card_fail&description=Favor%20reintente%20nuevamente.%20Aseg%FArese%20de%20contar%20con%20los%20datos%20de%20sus%20tarjetas%20para%20responder%20las%20preguntas%20de%20seguridad.%20%20Favor%20comun%EDquese%20al%20CA
2493000.%20Presione%20opci%F3n%201,%20luego%20la%20opci%F3n%204
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 5

Confirmar Tarjeta
Endpoint Confirmar Tarjeta
Descripción
El comercio solicita a Pagopar la confirmación de la tarjeta (o las tarjetas) previamente catastradas/agregadas. Este paso es obligatorio tanto se haya agregado satifactoriamente la tarjeta o no.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/1.1/confirmar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "a3955831ca0315797a4fd2c01d4338a76672acdd",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "url": "https://www.misitioejemplo.com.py/checkout",
  "identificador": 1
}
Observación:
El campo “identificador” corresponde al ID del usuario del sistema al cual va a asociarse la tarjeta
Pagopar retornará:
null
Listar Tarjetas
Endpoint Listar tarjetas
Descripción
El comercio solicita a Pagopar las tarjetas previamente catastradas de un específico. Eso puede ser simplemente para mostrarle al cliente sus tarjetas catastradas, o si se quiere pagar/eliminar
con una tarjeta específica, se debe necesariamente ejecutar este endpoint, puesto que en el se retorna el token temporal de cada tarjeta para realizar dicha acción.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/2.0/listar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "a3955831ca0315797a4fd2c01d4338a76672acdd",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "identificador": 1
}
Observación: El campo “identificador” corresponde al ID del usuario retornado por Pagopar en el endpoint “Agregar cliente”.
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": [
    {
      "tarjeta": "3",
      "url_logo": "https://cdn.pagopar.com/assets/images/card-payment/mastercard.png?0.20180928224330",
      "tarjeta_numero": "541863******1234",
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 6

"alias_token": "faf3e3b0def97b0bace298faef9c0b330e060230e2651eab6d2250cc8220d685"
    }
  ]
}
Observación: El campo “alias_token” corresponde a un hash temporal de la tarjeta, este será utilizado para eliminar una tarjeta o para pagar con dicha tarjeta, tener en cuenta siempre que es
un hash temporal..
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "No existe comprador"
}
Eliminar Tarjeta
Endpoint Eliminar tarjeta
Descripción
Para eliminar una tarjeta previamente agregada/catastrada, el comercio debe primero listar las tarjetas del comercio (Endpoint - Listar Tarjetas), luego, con el campo alias_token, hacer
referencia a dicha tarjeta para eliminarla. Tener en cuenta que el alias_token es un hash temporal, por lo tanto cada vez que se desee borrar una tarjeta, debe ejecutarse el endpoint Listar
Tarjetas para obtener el alias_token identificador.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/2.0/eliminar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "4172b540dd2084363aec9673a7754987b17769ac",
  "token_publico": "0eef1badfcea4f88f9ea346bd263497d",
  "tarjeta": "fac17d188d61d1171d28083aabd577fdd40f7f0e19a653f116668b6ebdbce0ef",
  "identificador": 24
}
Observación:
El campo “identificador” corresponde al ID del usuario retornado por Pagopar en el endpoint “Listar tarjeta”.
El campo “tarjeta” corresponde al hash temporal de la tarjeta retornado por Pagopar en el endpoint “Listar tarjeta”.
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": "Borrado"
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Selecciona una tarjeta valida."
}
Pagar
Endpoint pagar
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar


---

## Página 7

Descripción
Para pagar con una tarjeta previamente agregada/catastrada, el comercio debe primero listar las tarjetas del comercio (Endpoint - Listar Tarjetas), luego, con el campo alias_token, hacer
referencia a dicha tarjeta para pagar con dicha tarjeta, además, el hash de pedido debe estar ya generado para saber cuál pedido es el que va a ser pagado. Tener en cuenta que el alias_token es
un hash temporal, por lo tanto cada vez que se desee pagar con una tarjeta específica, debe ejecutarse el endpoint Listar Tarjetas para obtener el alias_token identificador.
Observación
El valor de public key y private key se obtiene desde la opción “Integrar con mi sitio web” de Pagopar.com
Token para este endpoint se genera:
sha1(Private_key + “PAGO-RECURRENTE”)
En PHP: sha1($datos['comercio_token_privado'] . “PAGO-RECURRENTE”)
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/2.0/pagar/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "a3955831ca0315797a4fd2c01d4338a76672acdd",
  "token_publico": "63820974a40fe7c5c5c53c429af8b25bed599dbf",
  "hash_pedido": "438af751ff62c43d62773aa0a3d1eb8fdc7b57b46488a978cbdaf8091c03c994",
  "tarjeta": "ed7c095d38df1bb7a588344a32216e9724ff0dc0c0c70e1a8093fff4e1bdb996",
  "identificador": 1
}
Observación:
El campo “identificador” corresponde al ID del usuario retornado por Pagopar en el endpoint “Listar tarjeta”.
El campo “tarjeta” corresponde al hash temporal de la tarjeta retornado por Pagopar en el endpoint “Listar tarjeta”.
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": ""
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "No existe comprador"
}
https://soporte.pagopar.com/portal/es/kb/articles/pagos-recurrentes-vía-bancard-pagopar



---

# Fuente: catastro-tarjetas-pagos-recurrentes-preautorizacion.pdf


---

## Página 1

Pagopar
Catastro de tarjetas - Pagos recurrentes - Preautorización
 Table of contents
Catastro de tarjetas para pagos recurrentes o sin acción del usuario
Primeros pasos
Descripción
Requisitos
Agregar Cliente
Endpoint “Agregar Cliente”
Descripción
Agregar Tarjeta
Endpoint “Agregar Tarjeta”
Descripción
Agregar Tarjeta
HTML Agregar Tarjeta
Descripción
Mostrar HTML en caso de que el proveedor sea Bancard
Mostrar HTML en caso de que el proveedor sea uPay
Agregar Tarjeta
HTML Agregar Tarjeta con el proveedor uPay
Descripción
Confirmar Tarjeta
Endpoint Confirmar Tarjeta
Descripción
Listar Tarjetas
Endpoint Listar tarjetas
Descripción
Eliminar Tarjeta
Endpoint Eliminar tarjeta
Descripción
Debitar
Pagar - Débito sin Pre autorización
Endpoint pagar
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 2

Pre autorizar - Débito con Pre autorización
Endpoint preautorizar
Descripción
Confirmar Pre autorización 
Endpoint preautorizar
Descripción
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/confirmar-preautorizacion/
Explicación de datos a enviar
Cancelar Pre autorización 
Endpoint 
Descripción
En caso que queramos cancelar una pre autorización podemos hacerlo en cualquier momento, esto devolverá el saldo congelado al usuario. Una vez cancelada la pre
autorización, ya no se puede confirmar.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/cancelar-preautorizacion/
Explicación de datos a enviar
Catastro de tarjetas para pagos recurrentes o sin acción del usuario
Primeros pasos
Descripción
La funcionalidad de pagos recurrentes a través de Pagopar permite realizar un pago en cualquier momento, de una tarjeta de crédito/débito previamente catastrada/guardada por el usuario.
Para poder pagar o eliminar una tarjeta, por seguridad se utiliza tokens temporales, por tanto, primero se debe listar las tarjeta de un usuario, seleccionar utilizando ese token temporal y luego
decidir si se va a abonar utlizando dicha tarjeta, u otra acción, como eliminar la tarjeta, siempre utilizando ese token temporal.
Esta funcionalidad permite el catastro y posterior pago de una transacción con una tarjeta previamente catastrada utilizando dos proveedores: Bancard y uPay. 
Requisitos
1. 
Poseer un contrato firmado con Pagopar, para dicha gestión debe de contactar al Departamento de Administración de Pagopar (administracion@pagopar.com) y solicitar dicha
funcionalidad
2. 
Haber implementado todos los pasos del circuito de Pagopar en su sitio.
Agregar Cliente
Endpoint “Agregar Cliente”
Para facilidad de integración, contamos con un proyecto en POSTMAN con los endpoints utilizados en esta documentación.
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 3

Descripción
El comercio envia a Pagopar los datos del cliente, creando un cliente con un identificador, al cual serán asignadas tarjetas posteriormente. Esto se debe hacer antes de agregar una tarjeta solo
la primera vez para registrar al cliente en Pagopar, no obstante, si se ejecuta cada vez antes de agregar una tarjeta tampoco dará algún error, simplemente no es necesario.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/agregar-cliente/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
   "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
   "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
   "identificador": 1,
   "nombre_apellido": "Mikhail Szwako",
   "email": "mihares@gmail.com",
   "celular": "0981252238"
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma:
sha1(Private_key + "PAGO-
RECURRENTE")
La clave privada se obtiene desde
Pagopar.com en el apartado "Integrar con
mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace
65a05
token_publico
Clave publica obtenida desde
Pagopar.com en el apartado "Integrar con
mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
identificador
Corresponde al ID del usuario del sistema
del comercio, no debe repetirse.
1
nombre_apellido
El nombre y apellido del usuario que va a
catastrar su tarjeta
Mikhail Szwako
email
Correo electrónico del usuario que va a
catastrar su tarjeta
1
celular
Número de celular del usuario que va a
catastrar su tarjeta
0981252238
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": {
    "id_comprador_comercio": "1",
    "nombres_apellidos": "Mikhail Szwako",
    "email": "mihares@gmail.com",
    "celular": "0981252238"
  }
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Token no corresponde."
}
Agregar Tarjeta
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 4

Endpoint “Agregar Tarjeta”
Descripción
El comercio solicita a Pagopar la creación de una nueva tarjeta asociada a un Usuario.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/agregar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
  "url": "https://www.misitioejemplo.com.py/checkout",
  "proveedor": "Bancard",
  "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
url
Es la URL a donde se va a redireccionar luego del que el
cliente agregue su tarjeta a través del iframe de Pagopar
https://www.misitioejemplo.com.py/checkout
proveedor
El proveedor que se desea utilizar para catastrar la
tarjeta. Puede ser "uPay" o "Bancard". La opción "uPay"
estará disponible próximamente.
Tarjetas que pueden ser catastradas con uPay:
VISA
Mastercard
Tarjetas que pueden ser catastradas con Bancard:
VISA
Mastercard
American Express
Otras tarjetas
Bancard
identificador
Corresponde al ID del usuario del sistema del comercio
al cual va a asociarse la tarjeta. Por ejemplo, si en el
sistema del comercio el ID de la tabla usuarios es 1,
entonces el identificador es 1.
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": "JIugXOLYIvpjMpN2n9GN"
}
Datos de ejemplo que Pagopar retornaría en caso de error:
Recomendamos la utilización del proveedor uPay para las tarjetas VISA y Mastercard
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 5

{
  "respuesta": false,
  "resultado": "Error al cargar"
}
Agregar Tarjeta
HTML Agregar Tarjeta
Descripción
El comercio muestra el HTML que contiene la funcionalidad que crea el formulario para que el usuario agregue el número de tarjeta y otros datos para catrastrar la tarjeta. Dependiendo de si
el proveedor es uPay o Bancard la forma de mostrar el HTML para agregar la tarjeta es distinta. En ambos casos se utiliza el campo resultado obtenido en el paso anterior “Endpoints -
Agregar Tarjeta” y en ambos casos el flujo de la respuesta es el mismo.
Mostrar HTML en caso de que el proveedor sea Bancard
Contenido del HTML:
<html>
 <head>
   <script src="bancard-checkout-2.1.0.js"></script>
 </head>
 <script type="text/javascript">
   window.onload = function () {
     var styles = {
       'input-background-color' : '#ffffff',
       'input-text-color': '#333333',
       'input-border-color' : '#ffffff',
       'input-placeholder-color' : '#333333',
       'button-background-color' : '#5CB85C',
       'button-text-color' : '#ffffff',
       'button-border-color' : '#4CAE4C',
       'form-background-color' : '#ffffff',
       'form-border-color' : '#dddddd',
       'header-background-color' : '#dddddd',
       'header-text-color' : '#333333',
       'hr-border-color' : '#dddddd'
     };
     options = {
       styles: styles
     }
     Bancard.Cards.createForm('iframe-container', 'json.resultado', options);
   };
 </script>
 <body>
   <div style="height: 130px; width: 100%; margin: auto" id="iframe-container"/>
 </body>
</html>
Vista Previa:
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 6

Mostrar HTML en caso de que el proveedor sea uPay
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mi Checkout</title>
</head>
<body>
    <h1>Bienvenido a la Página Principal</h1>
    <iframe src="https://www.pagopar.com/upay-iframe/?id-form={json.resuldado}" width="100%" height="300px" frameborder="0"></iframe
</body>
</html>
Vista previa:
Observación: El archivo bancard-checkout-2.1.0.js lo encuentran descomprimiendo la librería oficial de Bancard. 
Observación: En el caso de uPay, el iframe se puede incrustar en el dominio que corresponda al campo url enviado en 'agregar-tarjeta', según nuestro ejemplo, el
valor de url es https://www.misitioejemplo.com.py/checkout, por ende, el iframe se podrá incluir en https://www.misitioejemplo.com.py. El protocolo utilizado debe
ser https.
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 7

Al completar los datos en caso que se complete todo de forma correcta:
Se direccionará a:
https://www.misitio-ejemplo.com/?status=add_new_card_success
Al completar los datos en caso que se complete de forma incorrecta:
Se direccionará a:
https://www.misitio-ejemplo.com/?status=add_new_card_fail&description=Favor%20reintente%20nuevamente.%20Aseg%FArese%20de%20contar%20con%20los%20dat
Agregar Tarjeta
HTML Agregar Tarjeta con el proveedor uPay
Descripción
El comercio muestra el HTML utilizando agregando un iframe, con el dato obtenido en el paso anterior “Endpoints - Agregar Tarjeta”
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mi Checkout</title>
</head>
<body>
    <h1>Bienvenido a la Página Principal</h1>
    <iframe src="http://pagopar.local/pagopar-iframe/?id-form={json.resuldado}" width="100%" height="300px" frameborder="0"></iframe>
</body>
</html>
Confirmar Tarjeta
Endpoint Confirmar Tarjeta
Descripción
El comercio solicita a Pagopar la confirmación de la tarjeta (o las tarjetas) previamente catastradas/agregadas. Este paso es obligatorio tanto se haya agregado satisfactoriamente la tarjeta o
no.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/confirmar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
Como se puede observar, en caso de éxito al catastrar la tarjeta se redireccionará a la URL enviada en el endpoint "agregar-tarjeta" y se agregará el parámetro GET
"status" con el estado "add_new_card_success"
Como se puede observar, en caso de error al catastrar la tarjeta se redireccionará a la URL enviada en el endpoint "agregar-tarjeta" y se agregará el parámetro GET
"status" con el estado "add_new_card_fail"
Importante. Al retornar a la URL especificada, ya sea que se haya realizado el catastro de forma correcta o no, se debe llamar al endpoint “Confirmar tarjeta”. Es de carácter
obligatorio y necesario para el funcionamiento de todo el circuito.
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 8

{
  "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
  "url": "https://www.misitioejemplo.com.py/checkout",
  "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
url
URL a la que se va a redireccionar luego de que se
catastre la tarjeta
https://www.misitioejemplo.com.py/checkout
identificador
Corresponde al ID del usuario del sistema al cual va a
asociarse la tarjeta
1
Pagopar retornará:
{
    "respuesta": true,
    "resultado": "Ok"
}
Listar Tarjetas
Endpoint Listar tarjetas
Descripción
El comercio solicita a Pagopar las tarjetas previamente catastradas de un específico. Eso puede ser simplemente para mostrarle al cliente sus tarjetas catastradas, o si se quiere pagar/eliminar
con una tarjeta específica, se debe necesariamente ejecutar este endpoint, puesto que en el se retorna el token temporal de cada tarjeta para realizar dicha acción.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/listar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
  "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
identificador
Corresponde al ID del usuario retornado por Pagopar en
el endpoint “Agregar cliente”
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 9

{
  "respuesta": true,
  "resultado": [
    {
      "tarjeta": "3",
      "url_logo": "https://cdn.pagopar.com/assets/images/card-payment/mastercard.png?0.20180928224330",
      "tarjeta_numero": "541863******4424",
      "marca": "Mastercard",
      "emisor": "UENO HOLDING S.A.E.C.A.",
      "alias_token": "faf3e3b0def97b0bace298faef9c0b330e060230e2651eab6d2250cc8220d685",
      "proveedor": "uPay",
      "tipo_tarjeta": "Débito"
    }
  ]
}
Explicación de datos recibidos en caso de éxito
Campo
Descripción
Ejemplo
respuesta
Se determina si se ejecutó correctamente el endpoint, si
es true, entonces lo hizo satisfactoriamente, si es false,
no.
true
resultado.tarjeta
Identificador numérico de la tarjeta
3
resultado.url_logo
URL del logo de la marca de la tarjeta
https://cdn.pagopar.com/assets/images/card-
payment/mastercard.png?0.20180928224330
resultado.tarjeta_numero
Número de tarjeta enmascarada para que el usuario
pueda identificar su tarjeta
541863******4424
resultado.marca
La marca de la tarjeta. Ejemplos: Visa, Mastercard
Mastercard
resultado.emisor
El emisor de la tarjeta.
UENO HOLDING S.A.E.C.A.
resultado.alias_token
Hash temporal con duración de 15 minutos de validez
para identificar las tarjetas catastradas
faf3e3b0def97b0bace298faef9c0b330e060230e2651eab
6d2250cc8220d685
resultado.proveedor
Proveedor en donde se catastró la tarjeta. Puede ser uPay
o Bancard.
Bancard
resultado.tipo_tarjeta
Tipo de tarjeta catastrada. Pueden ser las opciones:
"Crédito": Tarjetas de crédito
"Débito": Tarjetas de débito
"Prepaga": Tarjetas prepagas
Débito
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "No existe comprador"
}
Eliminar Tarjeta
Endpoint Eliminar tarjeta
Descripción
Para eliminar una tarjeta previamente agregada/catastrada, el comercio debe primero listar las tarjetas del comercio (Endpoint - Listar Tarjetas), luego, con el campo alias_token, hacer
referencia a dicha tarjeta para eliminarla. Tener en cuenta que el alias_token es un hash temporal, por lo tanto cada vez que se desee borrar una tarjeta, debe ejecutarse el endpoint Listar
Tarjetas para obtener el alias_token identificador.
Observación: El campo “alias_token” corresponde a un hash temporal de la tarjeta, este será utilizado para eliminar una tarjeta o para pagar con dicha tarjeta, tener en cuenta
siempre que es un hash temporal de duración de 15 minutos, no obstante, recomendamos la llamada a este endpoint (listar) inmediatamente antes de la llamada a la acción de
pagar/eliminar/preautorizar.
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 10

URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/eliminar-tarjeta/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "4172b540dd2084363aec9673a7754987b17769ac",
  "token_publico": "0eef1badfcea4f88f9ea346bd263497d",
  "tarjeta": "fac17d188d61d1171d28083aabd577fdd40f7f0e19a653f116668b6ebdbce0ef",
  "identificador": 24
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
4172b540dd2084363aec9673a7754987b17769ac
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
0eef1badfcea4f88f9ea346bd263497d
tarjeta
Corresponde al hash temporal de la tarjeta retornado por
Pagopar en el endpoint “Listar tarjeta”.
fac17d188d61d1171d28083aabd577fdd40f7f0e19a653f1
16668b6ebdbce0ef
identificador
Corresponde al ID del usuario retornado por Pagopar en
el endpoint “Listar tarjeta”.
24
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": "Borrado"
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "Selecciona una tarjeta valida."
}
Debitar
La acción de debitar se pueden dar de dos formas, una es con pre autorización y la otra es sin pre autorización, la diferencia es que la pre autorización si bien descuenta el
saldo de la tarjeta de crédito, se debe confirmar posteriormente o sino la transacción se cancela automáticamente a los 30 días.
Pagar - Débito sin Pre autorización
Endpoint pagar
Descripción
Para pagar con una tarjeta previamente agregada/catastrada, el comercio debe primero listar las tarjetas del comercio (Endpoint - Listar Tarjetas), luego, con el campo alias_token, hacer
referencia a dicha tarjeta para pagar con dicha tarjeta, además, el hash de pedido debe estar ya generado para saber cuál pedido es el que va a ser pagado. Tener en cuenta que el alias_token es
un hash temporal, por lo tanto cada vez que se desee pagar con una tarjeta específica, debe ejecutarse el endpoint Listar Tarjetas para obtener el alias_token identificador.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/pagar/
Método: POST
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 11

Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
  "hash_pedido": "438af751ff62c43d62773aa0a3d1eb8fdc7b57b46488a978cbdaf8091c03c994",
  "tarjeta": "ed7c095d38df1bb7a588344a32216e9724ff0dc0c0c70e1a8093fff4e1bdb996",
  "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
hash_pedido
Es la URL a donde se va a redireccionar luego del que el
cliente agregue su tarjeta a través del iframe de Pagopar
https://www.misitioejemplo.com.py/checkout
tarjeta
Corresponde al hash temporal de la tarjeta retornado por
Pagopar en el endpoint “Listar tarjeta”
ed7c095d38df1bb7a588344a32216e9724ff0dc0c0c70e1
a8093fff4e1bdb996
identificador
Corresponde al ID del usuario retornado por Pagopar en
el endpoint “Listar tarjeta”.
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true,
  "resultado": ""
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "No existe comprador"
}
Pre autorizar - Débito con Pre autorización
Endpoint preautorizar
Descripción
En caso que queramos pre autorizar una transacción, es decir, congelar el saldo de la tarjeta para luego poder confirmarlo o cancelarlo, podemos utilizar el endpoint de pre
autorizar. Es importante tener en cuenta que en caso que no se confirme la preautorización en 30 días se cancelará automáticamente..
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/preautorizar/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
  "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
  "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
  "tarjeta": 24,
  "monto": 1000,
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 12

"descripcion": "Monto ejemplo",
  "id_transaccion": 1,
  "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma: sha1(Private_key +
"PAGO-RECURRENTE")
La clave privada se obtiene desde Pagopar.com en el
apartado "Integrar con mi sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en el
apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
tarjeta
Corresponde al ID numérico que identifica la tarjeta
catastrada retornado por Pagopar en el endpoint "Listar
tarjetas"
24
monto
Monto que será congelado para luego confirmar o
cancelar la pre autorización
1000
id_transaccion
Identificador de la transacción que está asociada a la pre
autorización en el sistema del Comercio. Por ejemplo: Si
el ID de la tabla transacciones del sistema del comercio
es 1, entonces el id_transaccion es 1
1
identificador
Corresponde al ID de usuario, al campo "identificador"
enviado en el endpoint "Listar tarjetas"
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
    "respuesta": true,
    "resultado": {
        "transaccion": "8302771",
        "comprobante_interno": "3926505331"
    }
}
Explicación de datos recibidos
Campo
Descripción
Ejemplo
respuesta
Si se ejecutó correctamente la acción de pre autorizar o
no
true
resultado.transaccion
ID de transacción interno en Pagopar que hace
referencia a la preautorizar. Se utilizará para confirmar o
para cancelar la pre autorización por lo tanto debe ser
guardado por el co.
8302771
resultado.comprobante_interno
Código alfanumérico que comprueba la pre autorización
en el proveedor
3926505331
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "id_transaccion debe estar presente"
}
Confirmar Pre autorización 
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 13

Endpoint preautorizar
Descripción
En caso que queramos pre autorizar una transacción, es decir, congelar el saldo de la tarjeta para luego poder confirmarlo o cancelarlo, podemos utilizar el endpoint de pre
autorizar. Es importante tener en cuenta que en caso que no se confirme la preautorización en 30 días se cancelará automáticamente..
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/confirmar-preautorizacion/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
    "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
    "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
    "hash_pedido": "3de3621705020abc7a91e5cd0f5fba90ad73ee7a24612c74abb3a744e4b4ab59",
    "transaccion": 8299761,
    "id_transaccion": 1,
    "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma:
sha1(Private_key + "PAGO-
RECURRENTE")
La clave privada se obtiene desde
Pagopar.com en el apartado "Integrar con mi
sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en
el apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
hash_pedido
Corresponde al hash de un pedido creado en
Pagopar en el endpoint "iniciar-transaccion"
ed7c095d38df1bb7a588344a32216e9724ff0dc
0c0c70e1a8093fff4e1bdb996
transaccion
Identificador de transacción retornado por
pagopar en el endpoint "preautorizar"
1
id_transaccion
Identificador de la transacción que está
asociada a la pre autorización en el sistema
del Comercio. Es el valor del campo
id_transaccion enviado en el endpoint
"preautorizar"
1
identificador
Corresponde al ID de usuario, al campo
"identificador" enviado en el endpoint
"Listar tarjetas"
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
{
  "respuesta": true
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "id_transaccion debe estar presente"
}
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 14

Cancelar Pre autorización 
Endpoint cancelar-preautorizacion
Descripción
En caso que queramos cancelar una pre autorización podemos hacerlo en cualquier momento, esto devolverá el saldo congelado al usuario. Una vez cancelada la pre autorización,
ya no se puede confirmar.
URL de ejemplo: https://api.pagopar.com/api/pago-recurrente/3.0/cancelar-preautorizacion/
Método: POST
Datos de ejemplo que el Comercio enviaría a Pagopar:
Contenido:
{
    "token": "2e2dc08bf16e4cc8334bfb9815043a7dace65a05",
    "token_publico": "ebcad4d95e229113a4e871cb491fbcfb",
    "transaccion": 8299761,
    "id_transaccion": 1,
    "identificador": 1
}
Explicación de datos a enviar
Campo
Descripción
Ejemplo
token
Se genera de la siguiente forma:
sha1(Private_key + "PAGO-
RECURRENTE")
La clave privada se obtiene desde
Pagopar.com en el apartado "Integrar con mi
sitio web"
2e2dc08bf16e4cc8334bfb9815043a7dace65a05
token_publico
Clave publica obtenida desde Pagopar.com en
el apartado "Integrar con mi sitio web"
ebcad4d95e229113a4e871cb491fbcfb
hash_pedido
Corresponde al hash de un pedido creado en
Pagopar en el endpoint "iniciar-transaccion".
El monto del pedido que se debe crear puede
ser igual o menor al monto pre autorizado en
el endpoint "preautorizar", pero no mayor.
ed7c095d38df1bb7a588344a32216e9724ff0dc
0c0c70e1a8093fff4e1bdb996
transaccion
Identificador de transacción retornado por
pagopar en el endpoint "preautorizar"
1
id_transaccion
Identificador de la transacción que está
asociada a la pre autorización en el sistema
del Comercio. Es el valor del campo
id_transaccion enviado en el endpoint
"preautorizar"
1
identificador
Corresponde al ID de usuario, al campo
"identificador" enviado en el endpoint
"Listar tarjetas"
1
Datos de ejemplo que Pagopar retornaría en caso de éxito:
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion


---

## Página 15

{
    "respuesta": true,
    "resultado": "OK"
}
Datos de ejemplo que Pagopar retornaría en caso de error:
{
  "respuesta": false,
  "resultado": "id_transaccion debe estar presente"
}
https://soporte.pagopar.com/portal/es/kb/articles/catastro-tarjetas-pagos-recurrentes-preautorizacion



---

# Fuente: entornos-pase-a-producción.pdf


---

## Página 1

Pagopar
Entornos y pase a Producción
Entornos de desarrollo y producción
En Pagopar existen dos entornos, por defecto, cuando uno empieza la integración se están utilizando las claves
públicas y privadas de desarrollo/staging, una vez terminado la integración, debe pasar a producción y usar las
nuevas claves. ¿Cuáles son las diferencias entre estos entornos? Si bien en ambas se pueden hacer pagos reales, la
integración no estará completa hasta que se haga el pase a producción, es muy importante este último paso ya que
utilizar las claves de producción habilita a todas las funciones de Pagopar y por ende, el correcto funcionamiento.
Algunas de esas funciones son: control de IP para mayor seguridad en la integración, notificaciones de pagos
recurrentes en caso de que el servidor del comercio esté inaccesible o la comunicación falle, entre otras funciones
como sincronización.
El pase a producción lo puede hacer usted mismo y el proceso es bastante rápido si ya tiene realizada la
integración, y dicho proceso se resume en comprobar que cada función/endpoint fue implementada correctamente.
Todas las pruebas se hacen sobre un pedido creado satisfactoriamente. Los pasos son los siguientes.
Desde tu cuenta de Pagopar en tu apartado de "Integrar con mi sitio web" contás con tres pasos que consisten
básicamente en realizar el proceso de generación de pedidos y simular el pago del mismo por sistema. 
Paso 1:  Generar el pedido en Pagopar. (Endpoint: iniciar-transaccion)
El comercio debe demostrar que puede crear un pedido satisfactoriamente en Pagopar siguiendo las directrices de
la documentación técnica. Más información sobre este paso.
Paso 2:  Simular el pago del pedido generado. (Pagopar notifica a comercio sobre el pago)
Pagopar hará una petición a la URL de respuesta definida por el comercio, el comercio debe responder
correctamente el JSON según la documentación técnica. Más información sobre este paso.
Tener en cuenta que el paso 2 en el simulador Pagopar envía el paramtro pagado:false, si se tratase de un
pago real, este valor sería pagado:true. Si se quiere probar cómo sería el JSON cuando se paga, se puede
copiar el JSON que Pagopar envía, y cambiar el valor de pagado: false a pagado: true, y enviar este
JSON modificado con alguna herramienta como POSTMAN.  Si se quiere probar todo el flujo de pago
completo, puede pagar un pedido y luego hacer la reversión, recomendamos hacer las pruebas con monto
de 1.000 Gs y la reversión en el día.
https://soporte.pagopar.com/portal/es/kb/articles/entornos-pase-a-producción


---

## Página 2

Paso 3:  Obtiene el estado actual de un pedido. (Comercio consulta el estado actual de un pedido específico)
Se debe haber implementado correctamente el endpoint   https://api.pagopar.com/api/pedidos/1.1/traer, si bien
gracias al paso 2 uno ya puede saber si se realizó el pago o no, es obligatorio haberlo implementado, ya que puede
ser útil para saber el estado real (pagado/no pagado) de un pedido por si el aviso del paso 2 falla. Más información
sobre este paso.
Una vez que se encuentren chequeados los tres pasos, deberás colocar la IP saliente de tu sitio en el campo de "IPs
habilitadas" y pasar el entorno a producción. 
Una vez que cambia el entorno al recargar la página los token también son actualizados por lo que deberás
copiarlos nuevamente dentro de los ajustes del plugin de Pagopar dentro de tu sitio web. 
https://soporte.pagopar.com/portal/es/kb/articles/entornos-pase-a-producción



---

# Fuente: vulnerability-a4f0eeec-682a-41c1-b91f-5fa19e31cb66.pdf


---

## Página 1

1
keyboard_arrow_down LOW
Pending Fix
Target
https://auth.api.qa.py-tigomoney.io
Basic Information
folder Source: : Tigo Money - Cambios Login
radio_button_checked Type: : insecure_design
format_list_bulleted CWE: : Cleartext Transmission of Sensitive Information
today Report date: : 07 January 2026
CVSS Score
keyboard_arrow_down 3.1 - LOW
Vector: CVSS:3.0/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N
Exploitability Metrics
Attack vector
NETWORK
Attack complexity
HIGH
Privileges required
NONE
User interaction
REQUIRED
Scope
UNCHANGED
Impact Metrics
Confidentiality
LOW
Integrity
NONE
Availability
NONE
Description
The API endpoint at https://auth.api.qa.py-tigomoney.io/* is served over HTTPS but does not include
the Strict-Transport-Security (HSTS) HTTP response header.
Missing HSTS header


---

## Página 2

2
Steps to reproduce
1.- Perform the following HTTP request:
POST /access/task HTTP/2
Host: auth.api.qa.py-tigomoney.io
X-Api-Key: a4745e7c07c1
Content-Type: application/json
User-Agent: PostmanRuntime/7.29.2
Accept: */*
Postman-Token: 9fb32061-c34d-4e17-be68-9db23703492d
Accept-Encoding: gzip, deflate, br
Content-Length: 85
{
   "username": "0981253265",
   "fingerprint": "AAA",
   "model": "Samsung S3"
}
2.- Inspect the HTTP response:
 You will see that there is no HSTS
Impact
The absence of the Strict-Transport-Security (HSTS) header on a publicly accessible API endpoint
exposes clients to protocol downgrade attacks such as SSL stripping. An attacker positioned in a
man-in-the-middle (MITM) scenario can force the client to communicate over an insecure HTTP
connection instead of HTTPS, allowing interception and potential modification of sensitive data in
transit.
Suggested fix


---

## Página 3

3
Enable HTTP Strict-Transport-Security (HSTS) on all HTTPS responses from the API server
HTTP Request
POST /access/task HTTP/2 Host: auth.api.qa.py-tigomoney.io X-Api-Key: a4745e7c07c1 Content-
Type: application/json User-Agent: PostmanRuntime/7.29.2 Accept: / Postman-Token: 9fb32061-
c34d-4e17-be68-9db23703492d Accept-Encoding: gzip, deflate, br Content-Length: 85
{ "username": "0981253265", "fingerprint": "AAA", "model": "Samsung S3" }
HTTP Response
HTTP/2 200 OK Date: Tue, 06 Jan 2026 21:28:14 GMT Content-Type: application/json Content-Length:
54 Cache-Control: no-cache, no-store, max-age=0, must-revalidate Pragma: no-cache Expires: 0 X-
Content-Type-Options: nosniff X-Frame-Options: DENY X-Xss-Protection: 0 Referrer-Policy: no-
referrer
{"otp":true,"uuid":"ea219b5c42464e9d92849df808feba45"}
