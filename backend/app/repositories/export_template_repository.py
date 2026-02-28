from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
import logging

from app.config.export_config import get_mongodb_config
from app.models.export_template import ExportTemplate, ExportField, AVAILABLE_FIELDS

logger = logging.getLogger(__name__)

class ExportTemplateRepository:
    """Repository para gestionar templates de exportación"""
    _indexes_ensured: bool = False

    def __init__(self):
        self.db_config = get_mongodb_config()
        self.db = self.db_config["client"][self.db_config["database"]]
        self.collection: Collection = self.db["export_templates"]

        self._create_indexes()

    def _create_indexes(self):
        """Crear índices una sola vez por proceso."""
        if ExportTemplateRepository._indexes_ensured:
            return
        try:
            self.collection.create_index([("owner_email", 1), ("name", 1)], unique=True)
            self.collection.create_index([("owner_email", 1), ("created_at", -1)])
            self.collection.create_index([("owner_email", 1), ("is_default", 1)])
            ExportTemplateRepository._indexes_ensured = True
            logger.debug("Índices de export_templates creados correctamente")
        except Exception as e:
            logger.warning(f"Error creando índices de export_templates: {e}")
    
    def create_template(self, template: ExportTemplate) -> str:
        """
        Crear un nuevo template de exportación
        
        Args:
            template: Template a crear
            
        Returns:
            str: ID del template creado
            
        Raises:
            ValueError: Si ya existe un template con el mismo nombre para el usuario
        """
        try:
            # Si es el primer template del usuario o se marca como default, hacerlo default
            if template.is_default or not self.get_templates_by_user(template.owner_email):
                # Quitar default de otros templates del mismo usuario
                self.collection.update_many(
                    {"owner_email": template.owner_email, "is_default": True},
                    {"$set": {"is_default": False}}
                )
                template.is_default = True
            
            template_dict = template.model_dump(exclude={"id"})
            template_dict["created_at"] = datetime.utcnow()
            template_dict["updated_at"] = datetime.utcnow()
            
            result = self.collection.insert_one(template_dict)
            template_id = str(result.inserted_id)
            
            logger.info(f"Template '{template.name}' creado para usuario {template.owner_email}")
            return template_id
            
        except DuplicateKeyError:
            raise ValueError(f"Ya existe un template con el nombre '{template.name}' para este usuario")
        except Exception as e:
            logger.error(f"Error creando template: {e}")
            raise
    
    def get_template_by_id(self, template_id: str, owner_email: str) -> Optional[ExportTemplate]:
        """
        Obtener template por ID (solo si pertenece al usuario)
        
        Args:
            template_id: ID del template
            owner_email: Email del propietario
            
        Returns:
            Template encontrado o None
        """
        try:
            doc = self.collection.find_one({
                "_id": ObjectId(template_id),
                "owner_email": owner_email
            })
            
            if doc:
                doc["id"] = str(doc["_id"])
                if "_id" in doc:
                    del doc["_id"]
                # Migrar datos para compatibilidad
                doc = self._migrate_template_data(doc)
                return ExportTemplate(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo template {template_id}: {e}")
            return None
    
    def _migrate_template_data(self, template_dict: dict) -> dict:
        """
        Migra datos de template para compatibilidad con versiones anteriores
        """
        # Migrar valores de alignment de mayúsculas a minúsculas
        alignment_mapping = {
            'LEFT': 'left',
            'CENTER': 'center', 
            'RIGHT': 'right'
        }
        
        if 'fields' in template_dict:
            # 1) Normalizar alignment
            for field in template_dict['fields']:
                if 'alignment' in field and field['alignment'] in alignment_mapping:
                    field['alignment'] = alignment_mapping[field['alignment']]
            # 2) Filtrar campos no soportados (por ejemplo: descripcion_factura eliminada)
            allowed = set(AVAILABLE_FIELDS.keys())
            filtered_fields = [f for f in template_dict['fields'] if f.get('field_key') in allowed]
            # 3) Reordenar por 'order' si existe, preservando estabilidad; luego reasignar orden secuencial
            sorted_fields = sorted(filtered_fields, key=lambda x: x.get('order', 10**9))
            for i, f in enumerate(sorted_fields, start=1):
                f['order'] = i
            template_dict['fields'] = sorted_fields
        
        return template_dict

    def get_templates_by_user(self, owner_email: str) -> List[ExportTemplate]:
        """
        Obtener todos los templates de un usuario
        
        Args:
            owner_email: Email del usuario
            
        Returns:
            Lista de templates del usuario
        """
        try:
            docs = list(self.collection.find(
                {"owner_email": owner_email}
            ).sort("created_at", -1))
            
            templates = []
            for doc in docs:
                # Convertir ObjectId a string y agregarlo como id
                template_dict = dict(doc)
                template_dict["id"] = str(doc["_id"])
                # Eliminar el _id original para evitar conflictos
                if "_id" in template_dict:
                    del template_dict["_id"]
                
                # Migrar datos para compatibilidad
                template_dict = self._migrate_template_data(template_dict)
                
                templates.append(ExportTemplate(**template_dict))
            
            return templates
            
        except Exception as e:
            logger.error(f"Error obteniendo templates para {owner_email}: {e}")
            return []
    
    def get_default_template(self, owner_email: str) -> Optional[ExportTemplate]:
        """
        Obtener el template por defecto del usuario
        
        Args:
            owner_email: Email del usuario
            
        Returns:
            Template por defecto o None
        """
        try:
            doc = self.collection.find_one({
                "owner_email": owner_email,
                "is_default": True
            })
            
            if doc:
                doc["id"] = str(doc["_id"])
                if "_id" in doc:
                    del doc["_id"]
                # Migrar datos para compatibilidad
                doc = self._migrate_template_data(doc)
                return ExportTemplate(**doc)
            
            # Si no hay default, tomar el más reciente
            docs = list(self.collection.find(
                {"owner_email": owner_email}
            ).sort("created_at", -1).limit(1))
            
            if docs:
                doc = docs[0]
                template_dict = dict(doc)
                template_dict["id"] = str(doc["_id"])
                if "_id" in template_dict:
                    del template_dict["_id"]
                # Migrar datos para compatibilidad
                template_dict = self._migrate_template_data(template_dict)
                return ExportTemplate(**template_dict)
                
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo template por defecto para {owner_email}: {e}")
            return None
    
    def update_template(self, template_id: str, template: ExportTemplate) -> bool:
        """
        Actualizar un template existente
        
        Args:
            template_id: ID del template a actualizar
            template: Datos actualizados
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Si se marca como default, quitar default de otros
            if template.is_default:
                self.collection.update_many(
                    {"owner_email": template.owner_email, "_id": {"$ne": ObjectId(template_id)}},
                    {"$set": {"is_default": False}}
                )
            
            template_dict = template.model_dump(exclude={"id", "created_at"})
            template_dict["updated_at"] = datetime.utcnow()
            
            result = self.collection.update_one(
                {"_id": ObjectId(template_id), "owner_email": template.owner_email},
                {"$set": template_dict}
            )
            
            if result.modified_count > 0:
                logger.info(f"Template {template_id} actualizado")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error actualizando template {template_id}: {e}")
            return False
    
    def delete_template(self, template_id: str, owner_email: str) -> bool:
        """
        Eliminar un template
        
        Args:
            template_id: ID del template
            owner_email: Email del propietario
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            # Verificar si es el template por defecto
            template = self.get_template_by_id(template_id, owner_email)
            if not template:
                return False
            
            result = self.collection.delete_one({
                "_id": ObjectId(template_id),
                "owner_email": owner_email
            })
            
            if result.deleted_count > 0:
                # Si se eliminó el template por defecto, hacer default al más reciente
                if template.is_default:
                    remaining_templates = self.get_templates_by_user(owner_email)
                    if remaining_templates:
                        self.set_default_template(remaining_templates[0].id, owner_email)
                
                logger.info(f"Template {template_id} eliminado")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error eliminando template {template_id}: {e}")
            return False
    
    def set_default_template(self, template_id: str, owner_email: str) -> bool:
        """
        Establecer un template como por defecto
        
        Args:
            template_id: ID del template
            owner_email: Email del propietario
            
        Returns:
            True si se estableció correctamente
        """
        try:
            # Quitar default de todos los templates del usuario
            self.collection.update_many(
                {"owner_email": owner_email},
                {"$set": {"is_default": False}}
            )
            
            # Establecer el nuevo default
            result = self.collection.update_one(
                {"_id": ObjectId(template_id), "owner_email": owner_email},
                {"$set": {"is_default": True, "updated_at": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error estableciendo template por defecto {template_id}: {e}")
            return False
    
    def duplicate_template(self, template_id: str, new_name: str, owner_email: str) -> Optional[str]:
        """
        Duplicar un template existente
        
        Args:
            template_id: ID del template a duplicar
            new_name: Nuevo nombre para el template duplicado
            owner_email: Email del propietario
            
        Returns:
            ID del nuevo template o None si falla
        """
        try:
            original = self.get_template_by_id(template_id, owner_email)
            if not original:
                return None
            
            # Crear copia con nuevo nombre
            new_template = original.model_copy()
            new_template.id = None
            new_template.name = new_name
            new_template.is_default = False
            new_template.created_at = datetime.utcnow()
            new_template.updated_at = datetime.utcnow()
            
            return self.create_template(new_template)
            
        except Exception as e:
            logger.error(f"Error duplicando template {template_id}: {e}")
            return None
