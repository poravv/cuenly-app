# 📦 Archivos Archivados - Backend K8s

Estos archivos fueron movidos aquí porque **NO se están usando** en el workflow de deployment actual (`cuenly-deploy.yml`).

---

## 📋 Lista de Archivos a Archivar

### 1. **mongodb-replicaset.yaml** ❌
- **Razón**: Se usa `mongodb-simple.yaml` en su lugar
- **Última referencia**: Nunca usado en el workflow actual
- **Seguro eliminar**: ✅ Sí

### 2. **mongodb-appuser-job.yaml** ❌
- **Razón**: Job de creación de usuario no se ejecuta
- **Última referencia**: Nunca usado en el workflow actual
- **Seguro eliminar**: ✅ Sí

### 3. **bastion-ssh.yaml** ❌
- **Razón**: No se despliega bastion SSH
- **Última referencia**: Nunca usado en el workflow actual
- **Seguro eliminar**: ✅ Sí

### 4. **secrets-and-config.yaml** ❌
- **Razón**: Secrets se crean dinámicamente en el workflow con `kubectl create secret`
- **Última referencia**: Nunca usado en el workflow actual
- **Seguro eliminar**: ✅ Sí

### 5. **configmap.yaml** ❌
- **Razón**: No se referencia en el workflow
- **Última referencia**: Nunca usado en el workflow actual
- **Seguro eliminar**: ✅ Sí

### 6. **ingress.yaml** (backend) ❌
- **Razón**: Backend no tiene ingress propio, se accede a través del frontend
- **Línea de eliminación en workflow**: 701 - `kubectl delete ingress cuenly-backend-ingress`
- **Seguro eliminar**: ✅ Sí

### 7. **deployment-observability.yaml** ❌
- **Razón**: DUPLICADO - Las anotaciones de observabilidad ya están en `deployment.yaml`
- **Problema**: Se aplicaba y luego `deployment.yaml` lo sobrescribía
- **Solución**: Consolidadas las anotaciones en `deployment.yaml`
- **Seguro eliminar**: ✅ Sí

### 8. **service-observability.yaml** ❌
- **Razón**: DUPLICADO - Las anotaciones de Prometheus ya están en el Service de `deployment.yaml`
- **Problema**: Se aplicaba y luego el service en `deployment.yaml` podía sobrescribirlo
- **Solución**: Consolidadas las anotaciones en el Service de `deployment.yaml`
- **Seguro eliminar**: ✅ Sí

---

## ✅ Archivos que SÍ se Usan (NO mover)

- ✅ `deployment.yaml` - Deployment principal con anotaciones de observabilidad
- ✅ `mongodb-simple.yaml` - MongoDB standalone
- ✅ `networkpolicy-mongodb.yaml` - NetworkPolicy para MongoDB
- ✅ `networkpolicy-backend.yaml` - NetworkPolicy para Backend
- ✅ `alertmanager-deployment.yaml` - AlertManager
- ✅ `observability-configmap.yaml` - ConfigMap con configuración de métricas/logs/alertas

---

## 🔄 Cómo Restaurar un Archivo

Si necesitas restaurar algún archivo archivado:

```bash
# Copiar de vuelta
cp backend/k8s/archive/NOMBRE_ARCHIVO.yaml backend/k8s/

# Actualizar el workflow para usarlo
# Editar .github/workflows/cuenly-deploy.yml
```

---

## 🗑️ Eliminación Permanente

Estos archivos se pueden **eliminar permanentemente** después de verificar que el deployment funciona correctamente por al menos 1 semana.

```bash
# Después de 1 semana sin problemas:
rm -rf backend/k8s/archive
```

---

**Fecha de archivo**: 13 de octubre de 2025  
**Razón**: Limpieza de manifiestos no utilizados después del análisis del workflow
