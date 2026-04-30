"""
Endpoints de templates de exportación y exportación personalizada a Excel.
Movido desde api.py — no se modificó la lógica.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.api.deps import _get_current_user
from app.repositories.user_repository import UserRepository

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/export-templates")
async def get_export_templates(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtener todos los templates de exportación del usuario, incluyendo system templates de su plan"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.repositories.subscription_repository import SubscriptionRepository

        owner_email = user["email"]

        # Determine which system template codes are included in the user's plan
        plan_template_codes = []
        try:
            sub_repo = SubscriptionRepository()
            subscription = await sub_repo.get_user_active_subscription(owner_email)
            if subscription:
                plan_code = subscription.get("plan_code")
                if plan_code:
                    plan = await sub_repo.get_plan_by_code(plan_code)
                    if plan and plan.get("features"):
                        features = plan["features"]
                        plan_template_codes = features.get("included_system_templates", [])
                        # If plan has custom_templates enabled, include ALL system templates
                        if features.get("custom_templates") and not plan_template_codes:
                            plan_template_codes = "__all__"
        except Exception as e:
            logger.warning(f"Error obteniendo plan para system templates de {owner_email}: {e}")

        repo = ExportTemplateRepository()
        templates = repo.get_templates_for_user(owner_email, plan_template_codes)

        result = []
        for template in templates:
            t_dict = template.model_dump()
            t_dict["is_system"] = template.is_system
            result.append(t_dict)

        return {
            "templates": result,
            "count": len(result)
        }

    except Exception as e:
        logger.error(f"Error obteniendo templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export-templates/available-fields")
async def get_available_fields(user: Dict[str, Any] = Depends(_get_current_user)):
    """Obtener lista de campos disponibles para templates - SOLO CAMPOS REALES"""
    try:
        from app.models.export_template import AVAILABLE_FIELDS, get_available_field_categories
        
        return {
            "fields": AVAILABLE_FIELDS,
            "categories": get_available_field_categories(),
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo campos disponibles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-templates")
async def create_export_template(
    template_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Crear un nuevo template de exportación"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.models.export_template import ExportTemplate, get_invalid_template_field_keys
        
        # Agregar owner_email
        template_data["owner_email"] = user["email"]
        
        # Crear template
        template = ExportTemplate(**template_data)
        invalid_fields = get_invalid_template_field_keys(template.fields)
        if invalid_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Template contiene campos no soportados",
                    "invalid_fields": invalid_fields,
                },
            )

        repo = ExportTemplateRepository()
        template_id = repo.create_template(template)
        
        return {
            "success": True,
            "template_id": template_id,
            "message": f"Template '{template.name}' creado exitosamente"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export-templates/{template_id}")
async def get_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Obtener un template específico (user-owned o system template)"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()
        template = repo.get_template_by_id(template_id, user["email"])

        # If not found as user template, try system template
        if not template:
            template = repo.get_template_by_id_any(template_id)
            if not template or not template.is_system:
                raise HTTPException(status_code=404, detail="Template no encontrado")

        return template.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/export-templates/{template_id}")
async def update_export_template(
    template_id: str,
    template_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Actualizar un template existente"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.models.export_template import ExportTemplate, get_invalid_template_field_keys

        repo = ExportTemplateRepository()

        # Block modification of system templates
        existing = repo.get_template_by_id_any(template_id)
        if existing and existing.is_system:
            raise HTTPException(
                status_code=403,
                detail="No se puede modificar un template del sistema. Puede duplicarlo para crear su propia versión."
            )

        # Agregar owner_email
        template_data["owner_email"] = user["email"]

        # Actualizar template
        template = ExportTemplate(**template_data)
        invalid_fields = get_invalid_template_field_keys(template.fields)
        if invalid_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Template contiene campos no soportados",
                    "invalid_fields": invalid_fields,
                },
            )

        if repo.update_template(template_id, template):
            return {
                "success": True,
                "message": f"Template '{template.name}' actualizado exitosamente"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/export-templates/{template_id}")
async def delete_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Eliminar un template"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository

        repo = ExportTemplateRepository()

        # Block deletion of system templates
        existing = repo.get_template_by_id_any(template_id)
        if existing and existing.is_system:
            raise HTTPException(
                status_code=403,
                detail="No se puede eliminar un template del sistema."
            )

        if repo.delete_template(template_id, user["email"]):
            return {
                "success": True,
                "message": "Template eliminado exitosamente"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-templates/{template_id}/duplicate")
async def duplicate_export_template(
    template_id: str,
    request_data: Dict[str, str],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Duplicar un template existente"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        new_name = request_data.get("name")
        if not new_name:
            raise HTTPException(status_code=400, detail="Nombre requerido para el template duplicado")
        
        repo = ExportTemplateRepository()
        new_template_id = repo.duplicate_template(template_id, new_name, user["email"])
        
        if new_template_id:
            return {
                "success": True,
                "template_id": new_template_id,
                "message": f"Template duplicado como '{new_name}'"
            }
        else:
            raise HTTPException(status_code=404, detail="Template original no encontrado")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicando template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-templates/{template_id}/set-default")
async def set_default_export_template(
    template_id: str,
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Establecer un template como por defecto"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        
        repo = ExportTemplateRepository()
        
        if repo.set_default_template(template_id, user["email"]):
            return {
                "success": True,
                "message": "Template establecido como por defecto"
            }
        else:
            raise HTTPException(status_code=404, detail="Template no encontrado")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estableciendo template por defecto {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export/custom")
async def export_invoices_with_template(
    export_request: Dict[str, Any],
    user: Dict[str, Any] = Depends(_get_current_user)
):
    """Exportar facturas usando un template personalizado"""
    try:
        from app.repositories.export_template_repository import ExportTemplateRepository
        from app.modules.excel_exporter.template_exporter import ExcelExporter
        from app.repositories.mongo_invoice_repository import MongoInvoiceRepository
        
        template_id = export_request.get("template_id")
        filters = export_request.get("filters", {})
        filename = export_request.get("filename", f"facturas_custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        # Verificar si el plan del usuario permite exportación
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.repositories.user_repository import UserRepository
        
        owner = user.get("email", "").lower()
        user_repo = UserRepository()
        is_admin = user_repo.is_admin(owner)
        
        if not is_admin:
            sub_repo = SubscriptionRepository()
            subscription = await sub_repo.get_user_active_subscription(owner)
            
            # Formatos permitidos (por ahora solo excel)
            requested_format = "excel" if filename.endswith((".xlsx", ".xls")) else "unknown"
            
            if not subscription:
                # Usuario FREE: Permitir solo excel
                if requested_format != "excel":
                     raise HTTPException(status_code=403, detail="Tu plan no permite este formato de exportación.")
            else:
                plan_code = subscription.get("plan_code")
                plan = await sub_repo.get_plan_by_code(plan_code)
                if plan and plan.get("features"):
                    allowed = plan["features"].get("allowed_export_formats", ["excel"])
                    if requested_format not in allowed:
                        raise HTTPException(status_code=403, detail=f"El formato {requested_format} no está permitido en tu plan actual.")
        
        if not template_id:
            raise HTTPException(status_code=400, detail="template_id requerido")
        
        # Obtener template (user-owned o system template)
        template_repo = ExportTemplateRepository()
        template = template_repo.get_template_by_id(template_id, user["email"])

        if not template:
            # Try system template
            template = template_repo.get_template_by_id_any(template_id)
            if not template or not template.is_system:
                raise HTTPException(status_code=404, detail="Template no encontrado")

        # Obtener facturas
        invoice_repo = MongoInvoiceRepository()
        invoices_raw = invoice_repo.get_invoices_by_user(user["email"], filters)
        
        if not invoices_raw:
            raise HTTPException(status_code=404, detail="No se encontraron facturas con los filtros especificados")
        
        # Convertir diccionarios a InvoiceData
        invoices = [_mongo_doc_to_invoice_data(invoice) for invoice in invoices_raw]
        
        # Generar Excel
        exporter = ExcelExporter()
        excel_data = exporter.export_invoices(invoices, template)
        
        # Retornar archivo
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        return Response(
            content=excel_data,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exportando con template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# OBSERVABILIDAD - LOGS FRONTEND
# ================================

class FrontendLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    component: Optional[str] = None
    user_email: Optional[str] = None
    request_id: Optional[str] = None
    event_type: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None

class FrontendLogsPayload(BaseModel):
    logs: List[FrontendLogEntry]

