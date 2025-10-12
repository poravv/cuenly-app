# 🔍 Firebase Analytics - Guía de Debugging

## **❓ ¿Por qué no veo eventos en Firebase?**

### **Posibles causas:**

1. **⏱️ Latencia normal** - Los eventos pueden tardar 30 minutos - 24 horas en aparecer
2. **🧪 Modo debug no activado** - Firebase necesita debug mode para eventos inmediatos
3. **🔧 Analytics no inicializado** - Error en la configuración

## **🛠️ Cómo debuggear:**

### **1. Abrir herramientas de desarrollador**
- Ve a tu sitio: `https://tu-dominio.com`
- Presiona F12 → Console

### **2. Verificar estado de Analytics**
```javascript
// En la consola del navegador:
analyticsDebug.info()
```

**Resultado esperado:**
```
📊 Firebase Analytics Debug Info:
- Production mode: true
- Measurement ID: G-JCQ8120888
- Current URL: https://tu-dominio.com
✅ gtag found - Analytics should be working
```

### **3. Enviar eventos de prueba**
```javascript
// Enviar eventos de prueba:
analyticsDebug.test()

// O enviar múltiples eventos:
analyticsDebug.forceEvents()
```

### **4. Activar Debug Mode en Firebase**

#### **Opción A: Via URL (temporal)**
Agrega `?debug_mode=1` a tu URL:
```
https://tu-dominio.com?debug_mode=1
```

#### **Opción B: Via consola del navegador**
```javascript
gtag('config', 'G-JCQ8120888', {
  debug_mode: true
});
```

#### **Opción C: Activar DebugView en Firebase Console**
1. Ve a Firebase Console → Analytics → DebugView  
2. Los eventos aparecerán inmediatamente cuando debug_mode esté activo

## **🔍 Verificar en Firebase Console:**

### **Para eventos normales:**
- Firebase Console → Analytics → Events (puede tardar 30 min - 24h)

### **Para eventos inmediatos:**
- Firebase Console → Analytics → DebugView (tiempo real cuando debug_mode=true)

## **📊 Eventos que deberías ver:**

- `page_view` - Automático al navegar
- `login_attempted` - Al intentar login
- `login` - Login exitoso
- `logout` - Al cerrar sesión  
- `debug_test` - Eventos de prueba manuales

## **⚠️ Troubleshooting:**

### **Si no aparece `gtag found`:**
- Analytics no se inicializó correctamente
- Verificar `environment.production = true`
- Verificar `measurementId` en environment

### **Si aparece `gtag found` pero no hay eventos:**
- Activar debug_mode
- Esperar 30 minutos para eventos normales
- Verificar en DebugView para eventos inmediatos

### **Si debug_mode no funciona:**
```javascript
// Forzar activación:
window.gtag = window.gtag || function(){dataLayer.push(arguments);};
gtag('config', 'G-JCQ8120888', { debug_mode: true });

// Enviar evento de prueba:
gtag('event', 'test_manual', { manual: true });
```

---

**Estado esperado**: Los eventos deberían aparecer en DebugView inmediatamente con debug_mode activo, y en Events normales dentro de 30 minutos.