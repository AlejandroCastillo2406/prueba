"""
Repositorio base con gestión correcta de sesiones
"""
from typing import List, Optional, Dict, Any, Type, TypeVar
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

T = TypeVar('T')


class BaseRepository:
    """Repositorio base con operaciones CRUD genéricas"""
    
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
    
    def get_by_id(self, session: Session, entity_id: UUID) -> Optional[T]:
        """
        Obtiene una entidad por ID
        
        Args:
            session: Sesión de base de datos
            entity_id: ID de la entidad
            
        Returns:
            Entidad si existe, None si no
        """
        try:
            return session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo entidad por ID {entity_id}: {e}")
            return None
    
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Obtiene todas las entidades
        
        Args:
            session: Sesión de base de datos
            skip: Número de registros a saltar
            limit: Límite de registros
            
        Returns:
            Lista de entidades
        """
        try:
            return session.query(self.model_class).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo todas las entidades: {e}")
            return []
    
    def create(self, session: Session, entity_data: Dict[str, Any]) -> Optional[T]:
        """
        Crea una nueva entidad
        
        Args:
            session: Sesión de base de datos
            entity_data: Datos de la entidad
            
        Returns:
            Entidad creada si exitoso, None si error
        """
        try:
            entity = self.model_class(**entity_data)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error creando entidad: {e}")
            session.rollback()
            return None
    
    def update(self, session: Session, entity_id: UUID, entity_data: Dict[str, Any]) -> Optional[T]:
        """
        Actualiza una entidad
        
        Args:
            session: Sesión de base de datos
            entity_id: ID de la entidad
            entity_data: Datos a actualizar
            
        Returns:
            Entidad actualizada si exitoso, None si error
        """
        try:
            entity = session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
            
            if not entity:
                return None
            
            for key, value in entity_data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            session.commit()
            session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando entidad {entity_id}: {e}")
            session.rollback()
            return None
    
    def delete(self, session: Session, entity_id: UUID) -> bool:
        """
        Elimina una entidad
        
        Args:
            session: Sesión de base de datos
            entity_id: ID de la entidad
            
        Returns:
            True si exitoso, False si error
        """
        try:
            entity = session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
            
            if not entity:
                return False
            
            session.delete(entity)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error eliminando entidad {entity_id}: {e}")
            session.rollback()
            return False
