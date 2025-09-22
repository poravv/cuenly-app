# 🚀 Comandos de Deployment - Transparentes y Directos

## 📋 Filosofía: Comandos claros en lugar de scripts ocultos

En lugar de usar scripts que ocultan la lógica, aquí tienes los comandos exactos que puedes ejecutar directamente.

## 🔧 Comandos de Deployment Manual

### **1. Forzar actualización del Frontend:**

```bash
# Variables
NAMESPACE="cuenly-frontend"
IMAGE_TAG="latest"  # o sha-abc1234 para una versión específica

# Actualizar imagen
kubectl set image deployment/cuenly-frontend \
  cuenly-frontend=ghcr.io/poravv/cuenly-app-frontend:${IMAGE_TAG} \
  -n ${NAMESPACE}

# Forzar restart para garantizar pull de imagen
kubectl patch deployment cuenly-frontend -n ${NAMESPACE} -p \
  "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"forceUpdate\":\"$(date +%s)\"}}}}}"

# Verificar rollout
kubectl rollout status deployment/cuenly-frontend -n ${NAMESPACE} --timeout=600s

# Verificar imagen en pods
kubectl get pods -n ${NAMESPACE} -l app=cuenly-frontend -o jsonpath='{.items[*].spec.containers[*].image}'
```

### **2. Forzar actualización del Backend:**

```bash
# Variables
NAMESPACE="cuenly-backend"
IMAGE_TAG="latest"  # o sha-abc1234 para una versión específica

# Actualizar imagen
kubectl set image deployment/cuenly-backend \
  cuenly-backend=ghcr.io/poravv/cuenly-app-backend:${IMAGE_TAG} \
  -n ${NAMESPACE}

# Forzar restart para garantizar pull de imagen
kubectl patch deployment cuenly-backend -n ${NAMESPACE} -p \
  "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"forceUpdate\":\"$(date +%s)\"}}}}}"

# Verificar rollout
kubectl rollout status deployment/cuenly-backend -n ${NAMESPACE} --timeout=300s

# Verificar imagen en pods
kubectl get pods -n ${NAMESPACE} -l app=cuenly-backend -o jsonpath='{.items[*].spec.containers[*].image}'
```

### **3. Deployment completo (ambos servicios):**

```bash
# Frontend
NAMESPACE="cuenly-frontend"
kubectl set image deployment/cuenly-frontend cuenly-frontend=ghcr.io/poravv/cuenly-app-frontend:latest -n ${NAMESPACE}
kubectl patch deployment cuenly-frontend -n ${NAMESPACE} -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}}}}"
kubectl rollout status deployment/cuenly-frontend -n ${NAMESPACE} --timeout=600s

# Backend
NAMESPACE="cuenly-backend"
kubectl set image deployment/cuenly-backend cuenly-backend=ghcr.io/poravv/cuenly-app-backend:latest -n ${NAMESPACE}
kubectl patch deployment cuenly-backend -n ${NAMESPACE} -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}}}}"
kubectl rollout status deployment/cuenly-backend -n ${NAMESPACE} --timeout=300s
```

## 🔍 Comandos de Verificación

### **Ver estado actual:**
```bash
# Estado de deployments
kubectl get deployments -n cuenly-frontend
kubectl get deployments -n cuenly-backend

# Estado de pods
kubectl get pods -n cuenly-frontend -o wide
kubectl get pods -n cuenly-backend -o wide

# Imágenes actuales en uso
kubectl get deployments -n cuenly-frontend -o jsonpath='{.items[*].spec.template.spec.containers[*].image}'
kubectl get deployments -n cuenly-backend -o jsonpath='{.items[*].spec.template.spec.containers[*].image}'
```

### **Ver logs en tiempo real:**
```bash
# Frontend logs
kubectl logs -f deployment/cuenly-frontend -n cuenly-frontend

# Backend logs
kubectl logs -f deployment/cuenly-backend -n cuenly-backend
```

### **Ver eventos recientes:**
```bash
# Eventos del frontend
kubectl get events -n cuenly-frontend --sort-by='.lastTimestamp' | head -20

# Eventos del backend
kubectl get events -n cuenly-backend --sort-by='.lastTimestamp' | head -20
```

## 🧹 Comandos de Limpieza (Si hay problemas)

### **Reinicio completo del Frontend:**
```bash
# Eliminar pods para forzar recreación
kubectl delete pods -l app=cuenly-frontend -n cuenly-frontend

# O escalar a 0 y luego a 2
kubectl scale deployment cuenly-frontend --replicas=0 -n cuenly-frontend
kubectl scale deployment cuenly-frontend --replicas=2 -n cuenly-frontend
```

### **Reinicio completo del Backend:**
```bash
# Eliminar pods para forzar recreación  
kubectl delete pods -l app=cuenly-backend -n cuenly-backend

# O reiniciar deployment
kubectl rollout restart deployment/cuenly-backend -n cuenly-backend
```

## 🎯 Ventajas de este enfoque:

1. **Transparencia total**: Ves exactamente qué comando se ejecuta
2. **Sin dependencias**: No necesitas scripts adicionales
3. **Fácil debugging**: Puedes ejecutar cada paso por separado
4. **Flexibilidad**: Puedes modificar cualquier parámetro fácilmente
5. **Aprendizaje**: Entiendes mejor cómo funciona Kubernetes

## 📝 Notas importantes:

- Reemplaza `IMAGE_TAG` con la versión específica que quieras desplegar
- Los comandos `kubectl patch` fuerzan que Kubernetes descargue la imagen aunque ya exista
- Siempre verifica el estado con `kubectl rollout status` antes de continuar
- Los timeouts están configurados apropiadamente para cada servicio