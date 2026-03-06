"""
Endpoints de administracion de system export templates.
Solo accesibles por administradores.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from app.api.deps import _get_current_admin_user
from app.models.export_template import ExportField, FieldType, FieldAlignment

router = APIRouter()
logger = logging.getLogger(__name__)


class SystemTemplateCreateRequest(BaseModel):
    name: str = Field(..., description="Nombre del template")
    system_code: str = Field(..., description="Codigo unico del system template (e.g. 'rg90_compras')")
    description: Optional[str] = Field(None, description="Descripcion del template")
    sheet_name: Optional[str] = Field("Facturas", description="Nombre de la hoja Excel")
    include_header: bool = Field(True, description="Incluir fila de encabezados")
    include_totals: bool = Field(False, description="Incluir fila de totales")
    fields: List[Dict[str, Any]] = Field(default_factory=list, description="Campos del template")


class SystemTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sheet_name: Optional[str] = None
    include_header: Optional[bool] = None
    include_totals: Optional[bool] = None
    fields: Optional[List[Dict[str, Any]]] = None


@router.get("")
async def list_system_templates(
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Lista todos los system templates"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()
        templates = repo.get_system_templates()

        return {
            "success": True,
            "data": [t.model_dump() for t in templates],
            "count": len(templates)
        }
    except Exception as e:
        logger.error(f"Error listando system templates: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo system templates")


@router.post("")
async def create_system_template(
    request: SystemTemplateCreateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Crear un nuevo system template"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()

        # Check for duplicate system_code
        existing = repo.get_system_template_by_code(request.system_code)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un system template con el codigo '{request.system_code}'"
            )

        template_data = {
            "name": request.name,
            "system_code": request.system_code,
            "description": request.description,
            "sheet_name": request.sheet_name,
            "include_header": request.include_header,
            "include_totals": request.include_totals,
            "fields": request.fields,
            "is_system": True,
            "owner_email": None,
        }

        template_id = repo.create_system_template(template_data)

        logger.info(f"Admin {admin.get('email')} creo system template '{request.name}' (code={request.system_code})")

        return {
            "success": True,
            "template_id": template_id,
            "message": f"System template '{request.name}' creado exitosamente"
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando system template: {e}")
        raise HTTPException(status_code=500, detail="Error creando system template")


@router.get("/{template_id}")
async def get_system_template(
    template_id: str,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Obtener un system template por ID"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()
        template = repo.get_template_by_id_any(template_id)

        if not template or not template.is_system:
            raise HTTPException(status_code=404, detail="System template no encontrado")

        return {
            "success": True,
            "data": template.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo system template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo system template")


@router.put("/{template_id}")
async def update_system_template(
    template_id: str,
    request: SystemTemplateUpdateRequest,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Actualizar un system template existente"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.models.export_template import ExportTemplate

        repo = ExportTemplateRepository()
        existing = repo.get_template_by_id_any(template_id)

        if not existing or not existing.is_system:
            raise HTTPException(status_code=404, detail="System template no encontrado")

        # Build updated template preserving existing values
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.sheet_name is not None:
            update_data["sheet_name"] = request.sheet_name
        if request.include_header is not None:
            update_data["include_header"] = request.include_header
        if request.include_totals is not None:
            update_data["include_totals"] = request.include_totals
        if request.fields is not None:
            update_data["fields"] = request.fields

        # Create updated template from existing + changes
        existing_dict = existing.model_dump()
        existing_dict.update(update_data)
        updated_template = ExportTemplate(**existing_dict)

        if repo.update_template(template_id, updated_template):
            logger.info(f"Admin {admin.get('email')} actualizo system template {template_id}")
            return {
                "success": True,
                "message": f"System template actualizado exitosamente"
            }
        else:
            raise HTTPException(status_code=500, detail="Error actualizando system template")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando system template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando system template")


@router.delete("/{template_id}")
async def delete_system_template(
    template_id: str,
    admin: Dict[str, Any] = Depends(_get_current_admin_user)
):
    """Eliminar un system template"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from bson import ObjectId

        repo = ExportTemplateRepository()
        existing = repo.get_template_by_id_any(template_id)

        if not existing or not existing.is_system:
            raise HTTPException(status_code=404, detail="System template no encontrado")

        # Direct delete since system templates have no owner_email
        result = repo.collection.delete_one({"_id": ObjectId(template_id), "is_system": True})

        if result.deleted_count > 0:
            logger.info(f"Admin {admin.get('email')} elimino system template {template_id}")
            return {
                "success": True,
                "message": "System template eliminado exitosamente"
            }
        else:
            raise HTTPException(status_code=404, detail="System template no encontrado")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando system template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando system template")
