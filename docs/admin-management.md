# Gestión de Administradores — CuenlyApp

> Última revisión: 2026-04-29
> Estado: Plan aprobado, pendiente implementación

---

## Estado actual

Los admins se definen en la variable de entorno `ADMIN_EMAILS` en `backend/app/config/settings.py`, con `andyvercha@gmail.com` hardcodeado como fallback. Agregar un admin nuevo requiere redeploy.

**Archivos relevantes hoy:**
- `backend/app/config/settings.py:56-69` — definición de `ADMIN_EMAILS`
- `backend/app/api/deps.py:100-114` — `_get_current_admin()`
- `backend/app/repositories/user_repository.py:445-448` — `is_admin()`

---

## Arquitectura objetivo: Firestore `admins`

La lista canónica de admins vive en **Firestore** (proyecto `cuenly-app`), colección `admins`. El backend la lee via **Firebase Admin SDK** con cache Redis de 60 segundos. El frontend nunca escribe Firestore directamente.

```
Firebase Console / Frontend Admin UI
          ↓ POST /api/admin/admins
     FastAPI Backend
          ↓ Firebase Admin SDK
     Firestore: admins/{email}
          ↓ cache 60s
     Redis: admin:lookup:{email}
```

### Estructura de documento Firestore

```json
// admins/{email}
{
  "email": "admin@ejemplo.com",
  "granted_by": "andyvercha@gmail.com",
  "granted_at": "2026-04-29T00:00:00Z",
  "revoked": false,
  "revoked_by": null,
  "revoked_at": null,
  "notes": "Admin principal",
  "uid": "firebase-uid-opcional"
}
```

### Firestore Security Rules

```javascript
// Solo el Firebase Admin SDK (backend) puede leer/escribir admins
match /admins/{email} {
  allow read, write: if false;
}
```

---

## Protocolo de seguridad

### Bootstrap del primer admin

1. Configurar `BOOTSTRAP_ADMIN_EMAIL=andyvercha@gmail.com` en los secrets de Kubernetes
2. Al arrancar el backend por primera vez, si Firestore no tiene ningún admin activo, crea el documento de bootstrap automáticamente
3. Una vez que existe al menos un admin activo, `BOOTSTRAP_ADMIN_EMAIL` se ignora
4. La variable puede removerse del secret después del primer deploy exitoso

### Agregar un admin (desde frontend o Firebase Console)

**Vía API (frontend):**
```
POST /api/admin/admins
Authorization: Bearer <JWT del admin actual>
{ "target_email": "nuevo@ejemplo.com" }
```

**Validaciones del backend:**
- El solicitante debe ser admin activo en Firestore
- `target_email` no puede ser el propio solicitante (no auto-promoción)
- `target_email` debe existir en `auth_users` MongoDB (usuario registrado)
- `target_email` no debe tener ya un documento activo en Firestore

**Vía Firebase Console:**  
Crear documento manualmente en `admins/{email}` con `revoked: false`. El backend lo detecta en el próximo request (cache TTL: 60s).

### Revocar un admin

```
DELETE /api/admin/admins/{target_email}
Authorization: Bearer <JWT del admin actual>
```

**Validaciones:**
- No auto-revocación
- No se puede revocar al último admin activo (protección anti-lockout)
- La revocación es soft-delete: `revoked: true`, el documento histórico se preserva

### Audit log

Todas las operaciones se registran en `admin_audit_log` (MongoDB):

| Acción | Cuándo |
|--------|--------|
| `admin_bootstrap` | Creación del primer admin |
| `admin_granted` | Nuevo admin promovido |
| `admin_revoked` | Admin revocado |

---

## Plan de implementación — 5 fases (~12-14h)

| Fase | Qué hace | Esfuerzo | Riesgo | Archivos nuevos |
|------|----------|----------|--------|-----------------|
| **1** | Instalar `firebase-admin>=6.2.0` + singleton `FirebaseAdminClient` | 2-3h | Bajo | `backend/app/core/firebase_admin_client.py` |
| **2** | `FirestoreAdminRepository` + cache Redis 60s + lógica bootstrap | 3-4h | Bajo | `backend/app/repositories/firestore_admin_repository.py`, `backend/app/core/startup.py` |
| **3** | Migrar `_get_current_admin` y `is_admin()` para leer Firestore | 2-3h | Medio | modifica `deps.py`, `user_repository.py` |
| **4** | Endpoints `GET/POST/DELETE /api/admin/admins` + UI Angular | 3-4h | Bajo | `backend/app/api/endpoints/admin_manage.py` |
| **5** | Eliminar `settings.ADMIN_EMAILS` del codebase | 2h | Bajo | modifica `settings.py`, `admin_users.py`, `api.py` |

**Orden crítico para Fase 3:** Crear el documento de bootstrap en Firestore ANTES de desplegar la Fase 3. Si se despliega sin el documento, `andyvercha@gmail.com` pierde acceso admin hasta que se ejecute el bootstrap.

---

## Secrets de GitHub y Kubernetes a configurar

| Secret | Destino | Descripción |
|--------|---------|-------------|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | GitHub Secrets + `backend-env-secrets` K8s | JSON de service account con rol `Cloud Datastore User` en proyecto `cuenly-app`. Codificar en base64. |
| `BOOTSTRAP_ADMIN_EMAIL` | `backend-env-secrets` K8s | `andyvercha@gmail.com`. Temporal — remover después del primer deploy. |
| `FIREBASE_API_KEY` | GitHub Secrets (ya existe) | Actualizar si se rota la Web API Key. |

### Crear service account en GCP

1. Ir a [GCP Console → IAM → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts?project=cuenly-app)
2. Crear cuenta: `cuenly-backend@cuenly-app.iam.gserviceaccount.com`
3. Asignar rol: `Cloud Datastore User` (Firestore read/write)
4. Generar clave JSON → descargar
5. Codificar: `base64 -i clave.json | tr -d '\n'`
6. Agregar como secret `FIREBASE_SERVICE_ACCOUNT_JSON` en GitHub y en K8s

---

## Rotación de Firebase Web API Key

La `FIREBASE_API_KEY` actual (`AIzaSyA...`) estuvo hardcodeada en el historial git.

**Recomendación:** Antes de rotar, agregar restricción de referer HTTP en GCP Console → APIs & Services → Credentials → editar la API Key → agregar `app.cuenly.com/*` como referer autorizado. Esto mitiga el abuso sin riesgo de romper el login.

**Si se decide rotar:**
1. GCP Console → APIs & Services → Credentials → Regenerar la clave
2. Actualizar `FIREBASE_API_KEY` en GitHub Actions Secrets
3. El CI/CD inyecta el nuevo valor automáticamente en el próximo build
4. Verificar en producción que el login con Google sigue funcionando

---

## Lo que NO cambia

- El flujo de verificación JWT Firebase (`verify_firebase_token()`) — no se toca
- Los 55 endpoints que usan `Depends(_get_current_admin_user)` — firma idéntica
- El `AdminGuard` del frontend — sigue llamando `GET /api/admin/check`
- El `admin_audit_log` en MongoDB — se extiende, no se reemplaza
- El campo `role` en `auth_users` MongoDB — se sincroniza desde Firestore en cada login
