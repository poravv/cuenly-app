# Resumen de Cambios - Fix de Campo IVA y Deployment Forzado

## 📅 Fecha: 21 de septiembre de 2025

## 🎯 Objetivo Principal
Corregir el procesamiento de facturas para que el campo `iva` contenga el **TIPO de IVA** (0, 5, 10) en lugar del **monto del IVA** (cantidad monetaria).

## ✅ Cambios Implementados

### 1. **Fix del Procesamiento XML Nativo**
**Archivo:** `backend/app/modules/openai_processor/xml_parser.py`
- **Función modificada:** `_extract_iva_info()`
- **Cambio:** Agregado mapeo correcto de `tasa_iva` al campo `iva`
- **Resultado:** Garantiza que el campo `iva` contenga el tipo (5, 10) no el monto

### 2. **Clarificación de Prompts de OpenAI**
**Archivo:** `backend/app/modules/openai_processor/prompts.py`
- **Funciones modificadas:** `base_text_schema()`, `v2_header_detail_schema()`, `build_image_prompt_v2()`, `build_text_prompt()`, `build_xml_prompt()`
- **Cambios realizados:**
  - Agregado: `"iva": 0 # TIPO de IVA: 0, 5 o 10 (NO el monto, sino el porcentaje aplicado)`
  - Agregado: `# CRÍTICO: En productos, el campo iva debe ser el TIPO de IVA (0, 5 o 10), NO el monto del IVA`
  - Agregado: `# IMPORTANTE: En items, el campo iva debe ser el TIPO de IVA (0, 5 o 10), NO el monto del IVA`

### 3. **Mejoras en Deployment de Kubernetes**
**Archivos:**
- `frontend/k8s/deployment.yaml`
- `backend/k8s/deployment.yaml`

**Cambios:**
- Agregadas anotaciones de revisión para tracking
- Confirmado `imagePullPolicy: Always` para forzar descarga de imágenes
- Estrategias de rollout optimizadas

### 4. **Script de Deployment Forzado**
**Archivo:** `force-deploy.sh` (nuevo)
- Script completo para forzar actualizaciones de deployment
- Opciones: `frontend`, `backend`, `all`, `restart-frontend`, `restart-backend`
- Verificación automática de conectividad a Kubernetes
- Logging con colores y manejo de errores

### 5. **Documentación Actualizada**
**Archivos:**
- `DEPLOYMENT_GUIDE.md` (nuevo) - Guía completa de deployment
- `README.md` - Actualizado con información de deployment

## 🧪 Verificación Realizada

### Pruebas del Parser XML
- ✅ Parser XML nativo extrae correctamente tipos de IVA (5, 10)
- ✅ Función `normalize_data()` maneja ambos campos (`iva` y `tasa_iva`)
- ✅ Productos muestran `iva: 5` e `iva: 10` (correcto)

### Pruebas de Prompts
- ✅ Todos los prompts contienen clarificaciones sobre tipo vs monto
- ✅ Advertencias críticas agregadas en esquemas
- ✅ Consistencia entre prompts de imagen, texto y XML

## 🎯 Resultado Esperado

### Antes del Fix:
```json
{
  "articulo": "Producto con IVA 10%",
  "iva": 50000  // ❌ INCORRECTO: monto del IVA
}
```

### Después del Fix:
```json
{
  "articulo": "Producto con IVA 10%", 
  "iva": 10     // ✅ CORRECTO: tipo de IVA
}
```

## 🚀 Comandos para Usar

### Deployment Forzado:
```bash
# Deployment completo de todo
./force-deploy.sh all

# Solo frontend
./force-deploy.sh frontend

# Restart rápido
./force-deploy.sh restart-frontend
```

### Verificación de Estado:
```bash
kubectl get pods -n cuenly-frontend
kubectl get pods -n cuenly-backend
```

## 📝 Archivos Modificados

1. ✅ `backend/app/modules/openai_processor/xml_parser.py`
2. ✅ `backend/app/modules/openai_processor/prompts.py`
3. ✅ `frontend/k8s/deployment.yaml`
4. ✅ `backend/k8s/deployment.yaml`
5. ✅ `README.md`
6. 🆕 `force-deploy.sh`
7. 🆕 `DEPLOYMENT_GUIDE.md`

## 🎉 Estado Final
- ✅ Problema de campo IVA **RESUELTO**
- ✅ Deployment forzado **IMPLEMENTADO**
- ✅ Documentación **COMPLETA**
- ✅ Scripts de automatización **LISTOS**

El sistema ahora maneja correctamente el campo IVA como tipo (0, 5, 10) en lugar de montos monetarios, tanto en procesamiento XML nativo como en procesamiento de PDFs con OpenAI.