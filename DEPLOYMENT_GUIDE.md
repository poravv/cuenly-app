# Guía de Deployment Forzado

## Problema Resuelto

Cuando las imágenes Docker se actualizan con la misma etiqueta `latest`, Kubernetes no siempre detecta que hay una nueva versión disponible, especialmente si el deployment ya existe.

## Soluciones Implementadas

### 1. Configuración de Deployments
- ✅ `imagePullPolicy: Always` - Siempre intenta descargar la imagen más reciente
- ✅ Anotaciones de revisión para tracking de cambios
- ✅ Estrategias de rollout optimizadas

### 2. Script de Deployment Forzado (`force-deploy.sh`)

#### Uso Básico:
```bash
# Forzar deployment completo del frontend
./force-deploy.sh frontend

# Forzar deployment completo del backend  
./force-deploy.sh backend

# Forzar deployment de ambos componentes
./force-deploy.sh all

# Solo reiniciar (más rápido) sin recrear
./force-deploy.sh restart-frontend
./force-deploy.sh restart-backend
```

#### ¿Cuándo usar cada opción?

**Deployment Completo (`frontend`/`backend`/`all`):**
- Cuando hay cambios significativos en la configuración
- Cuando quieres garantizar que se descargue la imagen más reciente
- Primera vez desplegando o después de cambios en los YAML

**Restart (`restart-frontend`/`restart-backend`):**
- Cuando solo quieres reiniciar los pods existentes
- Más rápido, no elimina el deployment
- Útil para actualizaciones menores

### 3. Namespaces Utilizados
- Frontend: `cuenly-frontend`
- Backend: `cuenly-backend`

### 4. Verificación de Estado
```bash
# Verificar pods del frontend
kubectl get pods -n cuenly-frontend

# Verificar pods del backend  
kubectl get pods -n cuenly-backend

# Ver logs del frontend
kubectl logs -f deployment/cuenly-frontend -n cuenly-frontend

# Ver logs del backend
kubectl logs -f deployment/cuenly-backend -n cuenly-backend
```

## Cambios Técnicos Realizados

### Frontend (`frontend/k8s/deployment.yaml`)
- Agregada anotación `deployment.kubernetes.io/revision: "1"`
- Confirmado `imagePullPolicy: Always`
- Estrategia `RollingUpdate` con `maxUnavailable: 0`

### Backend (`backend/k8s/deployment.yaml`)  
- Agregada anotación `deployment.kubernetes.io/revision: "1"`
- Confirmado `imagePullPolicy: Always`
- Estrategia `Recreate` para evitar conflictos de base de datos

### Script de Deployment (`force-deploy.sh`)
- Verificación automática de conectividad a Kubernetes
- Eliminación segura de deployments existentes
- Espera inteligente para rollouts
- Logging con colores para mejor visibilidad
- Manejo de errores robusto

## Flujo Recomendado

1. **Desarrollo Local:** Hacer cambios en código
2. **Build y Push:** CI/CD construye y empuja imágenes con tag `latest`
3. **Deployment:** Usar el script para forzar actualización
4. **Verificación:** Comprobar que los pods están ejecutándose correctamente

## Troubleshooting

### Si los pods no se actualizan:
```bash
# Forzar deployment completo
./force-deploy.sh all

# Verificar que las imágenes se descargaron
kubectl describe pod <pod-name> -n <namespace>
```

### Si hay problemas de conectividad:
```bash
# Verificar conexión a cluster
kubectl cluster-info

# Verificar contexto actual
kubectl config current-context
```

### Si los pods fallan al iniciar:
```bash
# Ver logs detallados
kubectl logs <pod-name> -n <namespace> --previous

# Ver eventos del namespace
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```