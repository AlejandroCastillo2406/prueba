"""
Interface base para repositorios
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session


class IBaseRepository(ABC):
    """Interface base para repositorios"""
    
    @abstractmethod
    def get_by_id(self, session: Session, entity_id: UUID) -> Optional[Any]:
        """Obtiene una entidad por ID"""
        pass
    
    @abstractmethod
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[Any]:
        """Obtiene todas las entidades"""
        pass
    
    @abstractmethod
    def create(self, session: Session, entity_data: Dict[str, Any]) -> Any:
        """Crea una nueva entidad"""
        pass
    
    @abstractmethod
    def update(self, session: Session, entity_id: UUID, entity_data: Dict[str, Any]) -> Optional[Any]:
        """Actualiza una entidad"""
        pass
    
    @abstractmethod
    def delete(self, session: Session, entity_id: UUID) -> bool:
        """Elimina una entidad"""
        pass
