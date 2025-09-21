#!/bin/bash

# Script para forzar deployment y actualización de imágenes en Kubernetes
# Uso: ./force-deploy.sh [frontend|backend|all]

set -e

NAMESPACE_FRONTEND="cuenly-frontend"
NAMESPACE_BACKEND="cuenly-backend"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

force_deploy_frontend() {
    log_info "Forzando deployment del frontend..."
    
    # Verificar si el namespace existe
    if ! kubectl get namespace $NAMESPACE_FRONTEND >/dev/null 2>&1; then
        log_warning "Namespace $NAMESPACE_FRONTEND no existe, creándolo..."
        kubectl create namespace $NAMESPACE_FRONTEND
    fi
    
    # Eliminar deployment existente si existe
    if kubectl get deployment cuenly-frontend -n $NAMESPACE_FRONTEND >/dev/null 2>&1; then
        log_info "Eliminando deployment existente del frontend..."
        kubectl delete deployment cuenly-frontend -n $NAMESPACE_FRONTEND --ignore-not-found=true
        
        # Esperar a que se eliminen los pods
        log_info "Esperando a que se eliminen los pods del frontend..."
        kubectl wait --for=delete pods -l app=cuenly-frontend -n $NAMESPACE_FRONTEND --timeout=60s || true
    fi
    
    # Aplicar nueva configuración
    log_info "Aplicando nueva configuración del frontend..."
    kubectl apply -f frontend/k8s/
    
    # Esperar a que esté listo
    log_info "Esperando a que el deployment esté listo..."
    kubectl rollout status deployment/cuenly-frontend -n $NAMESPACE_FRONTEND --timeout=300s
    
    log_success "Frontend desplegado exitosamente"
}

force_deploy_backend() {
    log_info "Forzando deployment del backend..."
    
    # Verificar si el namespace existe
    if ! kubectl get namespace $NAMESPACE_BACKEND >/dev/null 2>&1; then
        log_warning "Namespace $NAMESPACE_BACKEND no existe, creándolo..."
        kubectl create namespace $NAMESPACE_BACKEND
    fi
    
    # Eliminar deployment existente si existe
    if kubectl get deployment cuenly-backend -n $NAMESPACE_BACKEND >/dev/null 2>&1; then
        log_info "Eliminando deployment existente del backend..."
        kubectl delete deployment cuenly-backend -n $NAMESPACE_BACKEND --ignore-not-found=true
        
        # Esperar a que se eliminen los pods
        log_info "Esperando a que se eliminen los pods del backend..."
        kubectl wait --for=delete pods -l app=cuenly-backend -n $NAMESPACE_BACKEND --timeout=60s || true
    fi
    
    # Aplicar nueva configuración
    log_info "Aplicando nueva configuración del backend..."
    kubectl apply -f backend/k8s/
    
    # Esperar a que esté listo
    log_info "Esperando a que el deployment esté listo..."
    kubectl rollout status deployment/cuenly-backend -n $NAMESPACE_BACKEND --timeout=300s
    
    log_success "Backend desplegado exitosamente"
}

restart_deployment() {
    local component=$1
    local namespace=$2
    
    log_info "Reiniciando deployment de $component..."
    
    # Agregar anotación para forzar restart
    kubectl patch deployment $component -n $namespace -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}}}}"
    
    # Esperar a que se complete el rollout
    kubectl rollout status deployment/$component -n $namespace --timeout=300s
    
    log_success "$component reiniciado exitosamente"
}

show_usage() {
    echo "Uso: $0 [frontend|backend|all|restart-frontend|restart-backend]"
    echo ""
    echo "Opciones:"
    echo "  frontend         - Fuerza deployment completo del frontend"
    echo "  backend          - Fuerza deployment completo del backend"
    echo "  all              - Fuerza deployment completo de ambos componentes"
    echo "  restart-frontend - Solo reinicia el deployment del frontend (más rápido)"
    echo "  restart-backend  - Solo reinicia el deployment del backend (más rápido)"
    echo ""
    echo "Ejemplos:"
    echo "  $0 frontend        # Fuerza deployment completo del frontend"
    echo "  $0 restart-frontend # Solo reinicia el frontend existente"
    echo "  $0 all            # Fuerza deployment completo de todo"
}

check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl no está instalado o no está en el PATH"
        exit 1
    fi
    
    # Verificar conexión al cluster
    if ! kubectl cluster-info >/dev/null 2>&1; then
        log_error "No se puede conectar al cluster de Kubernetes"
        exit 1
    fi
    
    log_success "Conexión a Kubernetes establecida"
}

main() {
    check_kubectl
    
    case "${1:-}" in
        "frontend")
            force_deploy_frontend
            ;;
        "backend")
            force_deploy_backend
            ;;
        "all")
            force_deploy_backend
            force_deploy_frontend
            ;;
        "restart-frontend")
            restart_deployment "cuenly-frontend" "$NAMESPACE_FRONTEND"
            ;;
        "restart-backend")
            restart_deployment "cuenly-backend" "$NAMESPACE_BACKEND"
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

main "$@"