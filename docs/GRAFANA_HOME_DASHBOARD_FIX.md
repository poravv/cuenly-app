# 🔧 Solución: "Failed to load home dashboard" en Grafana

## 🐛 **PROBLEMA**

Al abrir Grafana sale el error:
```
Failed to load home dashboard
```

Los botones de "Add visualization", "Add library panel" e "Import dashboard" no funcionan.

---

## 🔍 **CAUSA**

Grafana está configurado para cargar un dashboard de inicio que **NO EXISTE**:

```yaml
[dashboards]
default_home_dashboard_path = /etc/grafana/dashboards/cuenly-overview.json
```

El archivo `cuenly-overview.json` no fue creado, causando el error.

---

## ✅ **SOLUCIÓN APLICADA**

He comentado la configuración del dashboard por defecto en `k8s-monitoring/grafana.yaml`:

```yaml
[session]
provider = file

# [dashboards]
# Comentado - No forzar dashboard por defecto al inicio
# Grafana mostrará la página de bienvenida
# default_home_dashboard_path = /etc/grafana/dashboards/cuenly-overview.json
```

---

## 🚀 **CÓMO APLICAR LA SOLUCIÓN**

### **Opción 1: Deploy completo (Recomendado)**

```bash
git add k8s-monitoring/grafana.yaml
git commit -m "fix: Remove non-existent default home dashboard from Grafana config"
git push origin main
```

Espera a que el workflow complete (~5-10 minutos).

### **Opción 2: Aplicar manualmente (Más rápido)**

```bash
# 1. Aplicar el ConfigMap actualizado
kubectl apply -f k8s-monitoring/grafana.yaml

# 2. Reiniciar Grafana para que recargue la configuración
kubectl rollout restart deployment/cuenly-grafana -n cuenly-monitoring

# 3. Esperar que el pod esté listo
kubectl rollout status deployment/cuenly-grafana -n cuenly-monitoring

# 4. Verificar logs
kubectl logs -n cuenly-monitoring -l app=cuenly-grafana --tail=50
```

### **Opción 3: Editar directamente el ConfigMap (Temporal)**

```bash
# Editar el ConfigMap
kubectl edit configmap cuenly-grafana-config -n cuenly-monitoring

# Buscar la sección [dashboards] y comentarla o eliminarla:
# [dashboards]
# default_home_dashboard_path = /etc/grafana/dashboards/cuenly-overview.json

# Guardar y salir (:wq en vim)

# Reiniciar Grafana
kubectl rollout restart deployment/cuenly-grafana -n cuenly-monitoring
```

---

## 🧪 **VERIFICACIÓN**

Después de aplicar la solución:

### 1. **Esperar que el pod reinicie:**
```bash
kubectl get pods -n cuenly-monitoring -l app=cuenly-grafana -w
```

Espera a que el status sea `Running` y `READY 1/1`.

### 2. **Verificar logs (no debe haber errores de dashboard):**
```bash
kubectl logs -n cuenly-monitoring -l app=cuenly-grafana --tail=100 | grep -i dashboard
```

No debería mostrar errores como:
```
❌ Failed to load dashboard from file
❌ Dashboard not found
```

### 3. **Acceder a Grafana:**
```
https://metrics.mindtechpy.net/
```

**Credenciales:**
- Usuario: `admin`
- Password: `cuenly2025!` (⚠️ Cámbiala después)

### 4. **Página de inicio esperada:**

Ahora deberías ver la **página de bienvenida de Grafana** con:
- ✅ Botones funcionales
- ✅ "Welcome to Grafana"
- ✅ Opciones para crear dashboards
- ✅ Sección de "Getting Started"

---

## 📊 **PRÓXIMOS PASOS - Crear Dashboard Inicial**

### **Opción A: Dashboard Básico (Rápido)**

Desde Grafana UI:

1. Click en "**+ New**" → "**New Dashboard**"
2. Click "**+ Add visualization**"
3. Selecciona datasource "**Prometheus**"
4. Query ejemplo:
   ```promql
   up{job=~"kubernetes-pods"}
   ```
5. Click "**Apply**"
6. Click "**Save dashboard**" (icono de disco)
7. Nombre: `Cuenly Overview`
8. Click "**Save**"
9. Click "⭐" (Star) para marcarlo como favorito
10. Settings → General → Set as home dashboard

### **Opción B: Importar Dashboard Pre-configurado (Recomendado)**

Importar dashboards de la comunidad:

#### 1. **Kubernetes Cluster Monitoring:**
```
Dashboard ID: 12740
URL: https://grafana.com/grafana/dashboards/12740
```

1. Grafana → Dashboards → Import
2. Enter dashboard ID: `12740`
3. Click "Load"
4. Select Prometheus datasource
5. Click "Import"

#### 2. **Loki Logs Dashboard:**
```
Dashboard ID: 13639
URL: https://grafana.com/grafana/dashboards/13639
```

Mismo proceso.

#### 3. **Node Exporter (si tienes):**
```
Dashboard ID: 1860
URL: https://grafana.com/grafana/dashboards/1860
```

### **Opción C: Crear Dashboard Custom para Cuenly**

Voy a crear un dashboard JSON básico para Cuenly:

```bash
# Ver archivo: config/grafana-dashboard-cuenly.json
```

Luego importarlo en Grafana.

---

## 🔒 **IMPORTANTE - Cambiar Password**

### **Método 1: Desde Grafana UI**
```
1. Login con admin/cuenly2025!
2. Click en tu avatar → Profile
3. Click "Change password"
4. Ingresar password actual y nueva password
```

### **Método 2: Desde Kubernetes Secret**

```bash
# Generar nueva password
NEW_PASSWORD="tu-password-super-segura"

# Actualizar el secret
kubectl create secret generic cuenly-grafana-credentials \
  --from-literal=admin-user=admin \
  --from-literal=admin-password="$NEW_PASSWORD" \
  --namespace=cuenly-monitoring \
  --dry-run=client -o yaml | kubectl apply -f -

# Reiniciar Grafana
kubectl rollout restart deployment/cuenly-grafana -n cuenly-monitoring
```

---

## 🎯 **SOLUCIÓN ALTERNATIVA - Crear Dashboard de Inicio**

Si prefieres tener un dashboard de inicio automático:

### 1. **Crear el dashboard en Grafana UI**
- Crea tu dashboard perfecto
- Guárdalo como "Cuenly Overview"
- Settings → General → Set as home dashboard

### 2. **Exportar el dashboard**
```
Settings → JSON Model → Copy to clipboard
```

### 3. **Guardarlo como archivo**
```bash
# Guardar en config/grafana-dashboard-cuenly-overview.json
```

### 4. **Crear ConfigMap con el dashboard**

Agregar al workflow o aplicar manualmente:

```bash
kubectl create configmap cuenly-dashboards \
  --from-file=cuenly-overview.json=config/grafana-dashboard-cuenly-overview.json \
  --namespace=cuenly-monitoring \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 5. **Descomentar la configuración**

En `grafana.yaml`, descomentar:
```yaml
[dashboards]
default_home_dashboard_path = /etc/grafana/dashboards/cuenly-overview.json
```

---

## 📋 **CHECKLIST DE VERIFICACIÓN**

Después de aplicar la solución:

- [ ] Grafana pod está `Running`
- [ ] No hay errores en logs
- [ ] Puedes acceder a `https://metrics.mindtechpy.net/`
- [ ] Login funciona con admin/cuenly2025!
- [ ] Página de inicio se carga sin errores
- [ ] Botones son clickeables
- [ ] Datasources funcionan (Prometheus + Loki)
- [ ] Puedes crear un nuevo dashboard
- [ ] Puedes ejecutar queries
- [ ] **Cambiaste la password** 🔒

---

## 🛠️ **TROUBLESHOOTING**

### **Error persiste después de reiniciar:**

1. **Verificar que el ConfigMap se actualizó:**
```bash
kubectl get configmap cuenly-grafana-config -n cuenly-monitoring -o yaml | grep -A5 dashboards
```

Debería estar comentado o no aparecer.

2. **Verificar que Grafana recargó la config:**
```bash
kubectl exec -n cuenly-monitoring deployment/cuenly-grafana -- cat /etc/grafana/grafana.ini | grep -A5 dashboards
```

3. **Forzar recreación del pod:**
```bash
kubectl delete pod -n cuenly-monitoring -l app=cuenly-grafana
```

### **Botones siguen sin funcionar:**

1. **Verificar permisos:**
```bash
kubectl logs -n cuenly-monitoring -l app=cuenly-grafana --tail=100 | grep -i permission
```

2. **Verificar storage:**
```bash
kubectl get pvc -n cuenly-monitoring
```

El PVC `cuenly-grafana-storage` debe estar `Bound`.

3. **Verificar usuario admin:**
```bash
kubectl get secret cuenly-grafana-credentials -n cuenly-monitoring -o yaml
```

### **Error de datasources:**

```bash
# Verificar que los servicios existen
kubectl get svc -n cuenly-monitoring cuenly-prometheus
kubectl get svc -n cuenly-monitoring cuenly-loki
```

---

## 📚 **REFERENCIAS**

- Grafana Configuration: https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/
- Grafana Provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
- Dashboard JSON: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/export-import/

---

**Estado:** Solución aplicada en `k8s-monitoring/grafana.yaml` ✅  
**Próximo paso:** Hacer push y esperar deploy o aplicar manualmente  
**Última actualización:** 13 de octubre de 2025
