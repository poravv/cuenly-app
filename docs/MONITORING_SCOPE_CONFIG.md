# 🔍 Configuración de Alcance de Monitoreo

Guía para configurar qué namespaces monitorear con Prometheus y Loki.

---

## 📊 **CONFIGURACIÓN ACTUAL - TODO EL CLUSTER** ✅

Después de los cambios realizados, **ahora monitoreamos TODOS los namespaces del cluster**.

### **¿Qué significa esto?**

- ✅ **Prometheus** recolectará métricas de **todos los pods** que tengan `prometheus.io/scrape: "true"`
- ✅ **Loki** recolectará logs de **todos los namespaces** (no solo Cuenly)
- ✅ En Grafana verás pods de cualquier proyecto en tu cluster

---

## 🎯 **OPCIONES DE CONFIGURACIÓN**

### **Opción 1: Monitorear TODO el Cluster (ACTUAL)** ⭐ Recomendado

**Ventajas:**
- 🌐 Visibilidad completa del cluster
- 📊 Monitoreas todos tus proyectos desde un solo Grafana
- 🔍 Útil para troubleshooting cross-namespace
- 💰 Máximo aprovechamiento de recursos de monitoring

**Desventajas:**
- 📈 Más datos almacenados (más uso de disco)
- 🔐 Necesitas controlar acceso a Grafana (todos pueden ver todo)

**Configuración actual en `k8s-monitoring/simple-monitoring-stack.yaml`:**

#### Prometheus (líneas ~265-295):
```yaml
- job_name: 'kubernetes-pods'
  kubernetes_sd_configs:
    - role: pod
      # SIN filtro de namespaces = TODOS los namespaces
```

#### Promtail (líneas ~395-400):
```yaml
relabel_configs:
  # Filtro comentado = TODOS los namespaces
  # - source_labels: [__meta_kubernetes_namespace]
  #   action: keep
  #   regex: (cuenly-backend|cuenly-frontend|cuenly-monitoring)
```

---

### **Opción 2: Solo Namespaces de Cuenly (ANTERIOR)**

Si prefieres limitar **solo a tus aplicaciones Cuenly**:

**Ventajas:**
- 🎯 Datos enfocados solo en tu app
- 💾 Menos uso de almacenamiento
- 🔒 Aislamiento de datos

**Desventajas:**
- ❌ No verás otros proyectos en el cluster
- ❌ Si tienes múltiples apps, necesitas múltiples stacks de monitoring

**Para volver a esta configuración:**

#### Prometheus:
```yaml
- job_name: 'cuenly-backend'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - cuenly-backend

- job_name: 'cuenly-frontend'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - cuenly-frontend
```

#### Promtail:
```yaml
relabel_configs:
  - source_labels: [__meta_kubernetes_namespace]
    action: keep
    regex: (cuenly-backend|cuenly-frontend|cuenly-monitoring)
```

---

### **Opción 3: Namespaces Selectivos (Personalizado)**

Monitorear **algunos** namespaces específicos:

**Ejemplo: Cuenly + Production + Staging**

#### Prometheus:
```yaml
- job_name: 'monitored-namespaces'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - cuenly-backend
          - cuenly-frontend
          - production
          - staging
          - my-other-app
```

#### Promtail:
```yaml
relabel_configs:
  - source_labels: [__meta_kubernetes_namespace]
    action: keep
    regex: (cuenly-backend|cuenly-frontend|production|staging|my-other-app)
```

---

## 🔐 **CONTROL DE ACCESO CON GRAFANA**

Si monitoreás todo el cluster, considera configurar **roles en Grafana**:

### **Opción A: Dashboard por Namespace**

Crear dashboards separados por proyecto:
- `Cuenly Dashboard` → Filtra `namespace=~"cuenly-.*"`
- `Production Dashboard` → Filtra `namespace="production"`
- `Staging Dashboard` → Filtra `namespace="staging"`

### **Opción B: Folders y Permisos**

Grafana Enterprise permite folders con permisos:
```
📁 Cuenly (solo equipo Cuenly)
   └─ Backend Dashboard
   └─ Frontend Dashboard
📁 Production (solo DevOps)
   └─ Production Overview
```

### **Opción C: Multi-tenancy con Grafana**

Usar organizaciones separadas en Grafana:
- Org 1: Cuenly Team
- Org 2: Production Team
- Org 3: DevOps Team

---

## 📈 **IMPACTO EN RECURSOS**

### **Monitoreo TODO el cluster:**

| Recurso | Cuenly Solo | Todo el Cluster (10 namespaces) |
|---------|-------------|----------------------------------|
| Prometheus storage | ~500MB/día | ~2GB/día |
| Loki storage | ~1GB/día | ~5GB/día |
| Memoria Prometheus | ~512MB | ~1-2GB |
| Memoria Loki | ~256MB | ~512MB-1GB |

**Recomendación:**
- Para clusters pequeños (<20 namespaces): Monitorear TODO
- Para clusters grandes (>50 namespaces): Selectivo o multi-instancia

---

## 🛠️ **CÓMO CAMBIAR LA CONFIGURACIÓN**

### **Para volver a monitorear SOLO Cuenly:**

1. Edita `k8s-monitoring/simple-monitoring-stack.yaml`

2. Prometheus - Reemplaza el job `kubernetes-pods` con:
```yaml
- job_name: 'cuenly-backend'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - cuenly-backend
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true

- job_name: 'cuenly-frontend'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - cuenly-frontend
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
```

3. Promtail - Descomenta el filtro:
```yaml
relabel_configs:
  - source_labels: [__meta_kubernetes_namespace]
    action: keep
    regex: (cuenly-backend|cuenly-frontend|cuenly-monitoring)
```

4. Aplica los cambios:
```bash
kubectl apply -f k8s-monitoring/simple-monitoring-stack.yaml
kubectl rollout restart deployment/cuenly-prometheus -n cuenly-monitoring
kubectl rollout restart daemonset/cuenly-promtail -n cuenly-monitoring
```

---

### **Para agregar más namespaces específicos:**

Modifica el regex de Promtail:
```yaml
regex: (cuenly-backend|cuenly-frontend|cuenly-monitoring|production|staging|otro-namespace)
```

Y agrega más jobs en Prometheus:
```yaml
- job_name: 'production-apps'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - production
          - staging
```

---

## 🔍 **VERIFICACIÓN EN GRAFANA**

### **Ver qué namespaces se están monitoreando:**

1. **Prometheus Targets:**
   ```
   Port-forward: kubectl port-forward -n cuenly-monitoring svc/cuenly-prometheus 9090:9090
   Visita: http://localhost:9090/targets
   ```
   Verás todos los targets descubiertos con sus namespaces.

2. **Loki Labels:**
   ```
   Grafana → Explore → Loki → Label filters
   ```
   En el dropdown de `namespace` verás todos los namespaces disponibles.

3. **Query de prueba (Prometheus):**
   ```promql
   count by (kubernetes_namespace) (up)
   ```
   Muestra todos los namespaces con pods monitoreados.

4. **Query de prueba (Loki):**
   ```logql
   {namespace!=""}
   ```
   Muestra logs de todos los namespaces.

---

## ⚠️ **IMPORTANTE - PERMISOS RBAC**

El ServiceAccount `cuenly-monitoring` tiene permisos para leer **todos los namespaces**:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cuenly-monitoring
rules:
- apiGroups: [""]
  resources:
    - nodes
    - nodes/proxy
    - services
    - endpoints
    - pods
  verbs: ["get", "list", "watch"]  # ← Cluster-wide
```

Si cambias a monitoreo limitado, considera usar **RoleBinding** en lugar de **ClusterRoleBinding** para seguridad adicional.

---

## 📊 **EJEMPLO DE QUERIES MULTI-NAMESPACE**

### **Prometheus:**

**Top 5 pods por uso de CPU (todos los namespaces):**
```promql
topk(5, 
  rate(container_cpu_usage_seconds_total[5m]) 
  * on (namespace,pod) group_left(kubernetes_namespace) 
  kube_pod_info
)
```

**Pods por namespace:**
```promql
count by (kubernetes_namespace) (kube_pod_info)
```

### **Loki:**

**Logs de error de todos los namespaces:**
```logql
{namespace!=""} |~ "(?i)error|exception|fatal"
```

**Logs de un namespace específico:**
```logql
{namespace="cuenly-backend"} | json
```

**Logs de múltiples apps:**
```logql
{app=~"cuenly-backend|cuenly-frontend"}
```

---

## 🎯 **RECOMENDACIÓN FINAL**

**Para tu caso (Cuenly):**

✅ **Usa configuración actual (TODO el cluster)** si:
- Tienes pocos proyectos en el cluster (<10 namespaces)
- Quieres visibilidad completa
- El cluster es tuyo/privado
- Tienes suficiente almacenamiento

❌ **Vuelve a solo Cuenly** si:
- Cluster compartido con muchos equipos
- Preocupaciones de seguridad/privacidad
- Limitaciones de almacenamiento
- Solo te interesa Cuenly

---

## 📚 **REFERENCIAS**

- Prometheus Kubernetes SD: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#kubernetes_sd_config
- Loki relabel_configs: https://grafana.com/docs/loki/latest/clients/promtail/configuration/#relabel_configs
- Grafana Multi-tenancy: https://grafana.com/docs/grafana/latest/administration/organizations/

---

**Configuración actual:** Monitoreo de TODO el cluster ✅  
**Última actualización:** 13 de octubre de 2025
