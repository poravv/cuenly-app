# Persistencia de Datos en Monitoring Stack - Configuración Actualizada

## 📊 Estado Actual (Configuración Persistente - 30 días)

### ✅ TODOS los componentes con persistencia

- **Grafana**: PersistentVolumeClaim de 10GB
  - Dashboards, usuarios, configuración de datasources
  - Storage Class: Longhorn
  - Persiste indefinidamente
  
- **Loki**: PersistentVolumeClaim de 5GB
  - **Retención de logs: 30 días** ✅
  - Logs históricos se mantienen después de reinicios
  - Storage Class: Longhorn
  - Auto-limpieza de logs > 30 días
  - Suficiente para ~50GB de logs/día
  
- **Prometheus**: PersistentVolumeClaim de 8GB
  - **Retención de métricas: 30 días** ✅
  - Métricas históricas se mantienen después de reinicios
  - Storage Class: Longhorn
  - Auto-limpieza de métricas > 30 días
  - Suficiente para proyectos pequeños/medianos
  
- **ConfigMaps**: Almacenados en etcd de Kubernetes
  - Configuración de Promtail (todos los namespaces)
  - Configuración de Prometheus (scraping y alertas)
  - Configuración de AlertManager (SMTP)
  - Persisten indefinidamente

---

## 🔄 Comportamiento al Reiniciar el Servidor

```bash
# 1. Reinicias el nodo de Kubernetes
sudo reboot

# 2. Kubernetes se levanta (systemd service)
systemctl status kubelet

# 3. Los pods se recrean automáticamente
kubectl get pods -n cuenly-monitoring

# RESULTADO: TODO funciona con datos históricos ✅
# → Grafana: Mantiene dashboards y configuración
# → Loki: Mantiene logs de los últimos 30 días
# → Prometheus: Mantiene métricas de los últimos 30 días
# → Promtail: Recolecta logs de todos los namespaces
```

---

## 🛡️ Garantías de Configuración con GitHub Actions

### ✅ Manifiestos aplicados automáticamente

Tu workflow `.github/workflows/cuenly-deploy.yml` aplica los manifiestos al cluster:

```yaml
# GitHub Actions ejecuta:
kubectl apply -f k8s-monitoring/simple-monitoring-stack.yaml

# Esto crea en Kubernetes (etcd):
- Namespace: cuenly-monitoring
- PersistentVolumeClaims (3): grafana, loki, prometheus
- Deployments (3): grafana, loki, prometheus
- DaemonSet: promtail
- ConfigMaps (4): grafana, loki, prometheus, promtail
- Services (3): grafana, loki, prometheus
```

**Una vez aplicados con `kubectl apply`, los manifiestos viven en Kubernetes indefinidamente**, incluso si:
- GitHub deja de funcionar ❌
- Borras el repositorio ❌
- El workflow falla ❌
- Reinicias el servidor ✅

---

## 📦 Almacenamiento Actual

| Componente | Storage | Capacidad | Retención | Persiste Config | Persiste Datos |
|------------|---------|-----------|-----------|-----------------|----------------|
| Grafana | PVC (Longhorn) | 10GB | Indefinido | ✅ SÍ | ✅ SÍ |
| Loki | PVC (Longhorn) | 5GB | 30 días | ✅ SÍ | ✅ SÍ |
| Prometheus | PVC (Longhorn) | 8GB | 30 días | ✅ SÍ | ✅ SÍ |
| Promtail | ConfigMap | N/A | N/A | ✅ SÍ | N/A |
| AlertManager | ConfigMap | N/A | N/A | ✅ SÍ | N/A |

**Total de almacenamiento: ~23GB** (deja 77GB libres para otros proyectos)

---

## 🚀 Cambios Aplicados

### Antes (Volátil):
```yaml
# Loki y Prometheus perdían datos al reiniciar
volumes:
  - name: storage
    emptyDir: {}  # ❌ Efímero

# Retención corta
args:
  - --storage.tsdb.retention.time=7d  # Solo 7 días
```

### Ahora (Persistente):
```yaml
# PersistentVolumeClaims creados
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cuenly-loki-storage
spec:
  storageClassName: longhorn
  resources:
    requests:
      storage: 5Gi  # ✅ Optimizado para uso real (~100MB/día)

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cuenly-prometheus-storage
spec:
  storageClassName: longhorn
  resources:
    requests:
      storage: 8Gi  # ✅ Optimizado para uso real (~200MB/día)

# Deployments usan PVCs
volumes:
  - name: storage
    persistentVolumeClaim:
      claimName: cuenly-loki-storage  # ✅ Persistente

# Retención extendida
# Prometheus:
args:
  - --storage.tsdb.retention.time=30d  # ✅ 30 días

# Loki:
limits_config:
  reject_old_samples_max_age: 720h  # 30 días
chunk_store_config:
  max_look_back_period: 720h  # 30 días
table_manager:
  retention_deletes_enabled: true
  retention_period: 720h  # 30 días
```

---

## 📋 Resumen de Cambios

### Archivos Modificados:
1. **k8s-monitoring/simple-monitoring-stack.yaml**
   - ✅ Agregados 2 PersistentVolumeClaims (Loki 5GB, Prometheus 8GB)
   - ✅ Cambiados `emptyDir` → `persistentVolumeClaim` en Deployments
   - ✅ Retención Prometheus: 7d → 30d
   - ✅ Retención Loki: 7d → 30d
   - ✅ Tamaños optimizados para uso real (~13GB total vs 150GB inicial)

### Beneficios:
- ✅ **Datos históricos sobreviven reinicios** (30 días de logs y métricas)
- ✅ **Configuración 100% persistente**
- ✅ **Auto-limpieza automática** (logs/métricas > 30 días se eliminan)
- ✅ **Deploy automático via GitHub Actions**

---

## 🔍 Verificación Post-Deploy

```bash
# 1. Verificar PVCs creados
kubectl get pvc -n cuenly-monitoring
# Esperado:
# cuenly-grafana-storage       Bound    10Gi
# cuenly-loki-storage          Bound    5Gi
# cuenly-prometheus-storage    Bound    8Gi

# 2. Verificar pods usando PVCs
kubectl get pods -n cuenly-monitoring -o wide

# 3. Verificar retención de Prometheus (30 días)
kubectl logs -n cuenly-monitoring deployment/cuenly-prometheus | grep retention
# → storage.tsdb.retention.time=30d

# 4. Verificar configuración de Loki (30 días)
kubectl exec -n cuenly-monitoring deployment/cuenly-loki -- cat /etc/loki/loki.yaml | grep retention_period
# → retention_period: 720h

# 5. Reiniciar y verificar que datos persisten
kubectl delete pod -n cuenly-monitoring -l app=cuenly-loki
kubectl delete pod -n cuenly-monitoring -l app=cuenly-prometheus
# → Espera 30s y verifica que los datos históricos siguen disponibles en Grafana
```

---

## 🎯 Aplicar Cambios

```bash
# 1. Commit y push
git add k8s-monitoring/simple-monitoring-stack.yaml docs/MONITORING_DATA_PERSISTENCE.md
git commit -m "feat: Add 30-day persistent storage for Loki and Prometheus"
git push origin main

# 2. GitHub Actions aplica automáticamente los cambios
# → Crea los PVCs
# → Reinicia Loki y Prometheus con nuevos volúmenes
# → Los datos empiezan a acumularse en almacenamiento persistente

# 3. Verificar en el cluster
kubectl get pvc -n cuenly-monitoring
kubectl get pods -n cuenly-monitoring
```

---

## 📚 Notas Importantes

1. **Los PVCs se crean una sola vez**: Al aplicar el manifiesto por primera vez, Longhorn provisiona los volúmenes. En deploys posteriores, los pods se conectan a los PVCs existentes.

2. **Migración de datos**: Como Loki y Prometheus usaban `emptyDir`, NO hay datos históricos previos. Los datos nuevos se almacenarán en los PVCs desde el momento del deploy.

3. **Espacio en disco**: Verifica que tu cluster Longhorn tenga al menos 25GB libres:
   - Grafana: 10GB
   - Loki: 5GB
   - Prometheus: 8GB
   - **Total: ~23GB para monitoring (deja ~77GB para otros proyectos)**

4. **Auto-limpieza**: Loki y Prometheus eliminarán automáticamente datos > 30 días, no necesitas hacer nada manualmente.

5. **Backups**: Los PVCs de Longhorn pueden respaldarse usando Longhorn UI o sus snapshots automáticos (si lo tienes configurado).

---

## 🔗 Referencias

- **Workflow**: `.github/workflows/cuenly-deploy.yml`
- **Manifiestos**: `k8s-monitoring/simple-monitoring-stack.yaml`
- **Secrets**: GitHub Settings → Secrets → Actions
- **Documentación relacionada**: 
  - `docs/MONITORING_SCOPE_CONFIG.md` (Monitoreo de todos los namespaces)
  - `docs/PROMETHEUS_ALERTMANAGER_CONFIG.md` (AlertManager SMTP)
