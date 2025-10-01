#!/bin/bash

echo "🔍 Diagnóstico de diferencias Local vs Producción - CuenlyApp"
echo "============================================================="

# Verificar pods del frontend
echo "📱 Frontend Pods:"
kubectl get pods -n cuenly-frontend -o wide
echo ""

# Verificar pods del backend
echo "🚀 Backend Pods:"
kubectl get pods -n cuenly-backend -o wide
echo ""

# Verificar configuración del frontend
echo "⚙️ ConfigMap Frontend:"
kubectl get configmap frontend-config -n cuenly-frontend -o yaml
echo ""

# Verificar logs recientes del frontend
echo "📋 Logs Frontend (últimas 20 líneas):"
kubectl logs -n cuenly-frontend deployment/cuenly-frontend --tail=20
echo ""

# Verificar logs recientes del backend
echo "📋 Logs Backend (últimas 20 líneas):"
kubectl logs -n cuenly-backend deployment/cuenly-backend --tail=20
echo ""

# Verificar el estado del deployment
echo "🔄 Estado del Deployment Frontend:"
kubectl describe deployment cuenly-frontend -n cuenly-frontend | grep -A 10 "RollingUpdateStrategy\|Recreate"
echo ""

# Verificar versión de las imágenes
echo "🏷️ Versiones de Imágenes:"
echo "Frontend:"
kubectl get deployment cuenly-frontend -n cuenly-frontend -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""
echo "Backend:"
kubectl get deployment cuenly-backend -n cuenly-backend -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""

# Verificar servicios
echo "🌐 Servicios:"
kubectl get svc -n cuenly-frontend
kubectl get svc -n cuenly-backend
echo ""

# Verificar si hay múltiples pods de frontend ejecutándose
echo "🔢 Número de replicas activas:"
echo "Frontend: $(kubectl get pods -n cuenly-frontend -l app=cuenly-frontend --field-selector=status.phase=Running --no-headers | wc -l)"
echo "Backend: $(kubectl get pods -n cuenly-backend -l app=cuenly-backend --field-selector=status.phase=Running --no-headers | wc -l)"
echo ""

# Comando para verificar diferencias en la base de datos
echo "💾 Para verificar el estado del usuario en MongoDB:"
echo "kubectl exec -it deployment/mongodb-deployment -n mongodb-namespace -- mongosh --eval \"db.auth_users.findOne({email: 'tu-email@ejemplo.com'}, {is_trial_user: 1, ai_invoices_limit: 1, trial_expires_at: 1})\""
echo ""

echo "📝 Para forzar un redespliegue completo:"
echo "kubectl rollout restart deployment/cuenly-frontend -n cuenly-frontend"
echo "kubectl rollout restart deployment/cuenly-backend -n cuenly-backend"
echo ""

echo "✅ Diagnóstico completado. Compara estos resultados con tu entorno local usando docker-compose."