"""
Plan mixin: CRUD de planes de suscripción.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class _PlanMixin:

    async def get_all_plans(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        try:
            query: Dict[str, Any] = {} if include_inactive else {"status": "active"}
            plans = list(self.plans_collection.find(query, {"_id": 0}).sort("sort_order", 1))
            logger.info(f"Obtenidos {len(plans)} planes")
            return plans
        except Exception as e:
            logger.error(f"Error obteniendo planes: {e}")
            return []

    async def get_plan_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            return self.plans_collection.find_one({"code": code}, {"_id": 0})
        except Exception as e:
            logger.error(f"Error obteniendo plan {code}: {e}")
            return None

    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.plans_collection.find_one({"_id": ObjectId(plan_id)}, {"_id": 0})
        except Exception as e:
            logger.error(f"Error obteniendo plan {plan_id}: {e}")
            return None

    async def create_plan(self, plan_data: Dict[str, Any]) -> bool:
        try:
            plan_data["created_at"] = datetime.utcnow()
            plan_data["updated_at"] = datetime.utcnow()
            result = self.plans_collection.insert_one(plan_data)
            logger.info(f"Plan creado: {plan_data['code']}")
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creando plan: {e}")
            return False

    async def update_plan(self, code: str, plan_data: Dict[str, Any]) -> bool:
        try:
            plan_data["updated_at"] = datetime.utcnow()
            result = self.plans_collection.update_one({"code": code}, {"$set": plan_data})
            logger.info(f"Plan actualizado: {code}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error actualizando plan {code}: {e}")
            return False

    async def delete_plan(self, code: str) -> bool:
        """Soft delete — marca el plan como deprecated."""
        try:
            result = self.plans_collection.update_one(
                {"code": code},
                {"$set": {"status": "deprecated", "updated_at": datetime.utcnow()}},
            )
            logger.info(f"Plan eliminado: {code}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error eliminando plan {code}: {e}")
            return False
