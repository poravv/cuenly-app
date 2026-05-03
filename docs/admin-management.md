# Gestión de Administradores

## Fuente de Verdad

Los permisos admin se validan contra Firestore en la colección `admins`. MongoDB puede guardar rol para UI, pero el backend usa Firestore como control principal.

## Bootstrap

Variable opcional:

```env
BOOTSTRAP_ADMIN_EMAIL=admin@dominio.com
```

Al arrancar, si no existe ningún admin en Firestore, el backend crea ese correo como admin inicial.

## Endpoints

- `GET /admin/check`
- `GET /admin/admins`
- `POST /admin/admins`
- `DELETE /admin/admins/{email}`

Todos requieren Firebase Bearer token de un admin existente, excepto el bootstrap automático.

## Operación Segura

- Mantener al menos un admin activo.
- Auditar cambios en `/admin/audit`.
- No depender de Firebase Web API Key como secreto; la autorización real es por token + Firestore admins.
- Revocar admins desde la UI o endpoint, no editando roles MongoDB manualmente.
