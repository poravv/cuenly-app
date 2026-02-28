"""
Endpoint para consultar el log de auditoría administrativa.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
import logging

from app.api.deps import _get_current_admin_user
from app.repositories.audit_repository import get_audit_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    action: Optional[str] = Query(default=None),
    admin_email: Optional[str] = Query(default=None),
    admin: Dict[str, Any] = Depends(_get_current_admin_user),
):
    """Consulta paginada del log de auditoría."""
    try:
        result = get_audit_repo().get_logs(
            page=page,
            page_size=page_size,
            action=action or None,
            admin_email=admin_email or None,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error consultando audit log: {e}")
        raise HTTPException(status_code=500, detail="Error consultando log de auditoría")
