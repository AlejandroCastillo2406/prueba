"""
Interface para repositorio de planes
"""
from abc import abstractmethod
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from .base_repository_interface import IBaseRepository


class IPlanRepository(IBaseRepository):
    """Interface para repositorio de planes"""
    
    @abstractmethod
    def get_active_plans(self, session: Session) -> List[Any]:
        """Obtiene planes activos"""
        pass
    
