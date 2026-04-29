"""
Endpoints para gestión de administradores en Firestore.

Permite a un admin activo listar, promover y revocar otros admins.
Protecciones:
  - No auto-promoción ni auto-revocación.
  - El target debe existir como usuario registrado en MongoDB.
  - No se puede revocar si es el único admin activo (anti-lockout).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import _get_current_admin
from app.repositories.firestore_admin_repository import FirestoreAdminRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin-management"])


class GrantAdminRequest(BaseModel):
    target_email: str


@router.get("")
async def list_admins(current_admin: dict = Depends(_get_current_admin)):
    """
    Lista todos los admins activos en Firestore.

    Returns:
        Lista de admins con email, otorgante, fecha y notas.
    """
    repo = FirestoreAdminRepository()
    admins = repo.list_admins()
    safe_admins = [
        {
            "email": a.get("email"),
            "granted_by": a.get("granted_by"),
            "granted_at": str(a.get("granted_at", "")),
            "notes": a.get("notes", ""),
        }
        for a in admins
    ]
    return {"admins": safe_admins}


@router.post("", status_code=201)
async def grant_admin(
    payload: GrantAdminRequest,
    current_admin: dict = Depends(_get_current_admin),
):
    """
    Promueve un usuario registrado a administrador.

    Args:
        payload.target_email: Email del usuario a promover.

    Raises:
        400: Auto-promoción o usuario ya es admin.
        404: Usuario no registrado en CuenlyApp.
        409: Usuario ya es administrador activo.
        500: Error en Firestore.
    """
    target_email = payload.target_email.strip().lower()
    granter_email = current_admin.get("email", "").lower()

    if target_email == granter_email:
        raise HTTPException(status_code=400, detail="No puedes promoverte a ti mismo")

    user_repo = UserRepository()
    existing_user = user_repo.get_by_email(target_email)
    if not existing_user:
        raise HTTPException(status_code=404, detail="El usuario no existe en CuenlyApp")

    admin_repo = FirestoreAdminRepository()
    if admin_repo.is_admin(target_email):
        raise HTTPException(status_code=409, detail="El usuario ya es administrador")

    uid = str(existing_user.get("_id", ""))
    success = admin_repo.grant_admin(
        email=target_email,
        granted_by=granter_email,
        uid=uid,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Error al otorgar permisos de admin")

    try:
        AuditRepository().log(
            action="admin_granted",
            admin_email=granter_email,
            target_user=target_email,
            details={"uid": uid},
        )
    except Exception as exc:
        logger.warning("No se pudo registrar audit log para grant_admin: %s", exc)

    logger.info("Admin otorgado: %s por %s", target_email, granter_email)
    return {"message": f"Admin otorgado a {target_email}"}


@router.delete("/{target_email}")
async def revoke_admin(
    target_email: str,
    current_admin: dict = Depends(_get_current_admin),
):
    """
    Revoca los permisos de admin de un usuario (soft-delete en Firestore).

    Args:
        target_email: Email del admin a revocar.

    Raises:
        400: Auto-revocación o último admin activo.
        404: Usuario no es admin activo.
        500: Error en Firestore.
    """
    target_email = target_email.strip().lower()
    revoker_email = current_admin.get("email", "").lower()

    if target_email == revoker_email:
        raise HTTPException(status_code=400, detail="No puedes revocar tus propios permisos de admin")

    admin_repo = FirestoreAdminRepository()

    if not admin_repo.is_admin(target_email):
        raise HTTPException(status_code=404, detail="El usuario no es administrador activo")

    if admin_repo.get_active_admin_count() <= 1:
        raise HTTPException(
            status_code=400,
            detail="No se puede revocar: es el único administrador activo",
        )

    success = admin_repo.revoke_admin(email=target_email, revoked_by=revoker_email)
    if not success:
        raise HTTPException(status_code=500, detail="Error al revocar permisos de admin")

    try:
        AuditRepository().log(
            action="admin_revoked",
            admin_email=revoker_email,
            target_user=target_email,
        )
    except Exception as exc:
        logger.warning("No se pudo registrar audit log para revoke_admin: %s", exc)

    logger.info("Admin revocado: %s por %s", target_email, revoker_email)
    return {"message": f"Permisos de admin revocados para {target_email}"}
