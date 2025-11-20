"""
Interface para repositorio de tenants
"""
from abc import abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from .base_repository_interface import IBaseRepository


class ITenantRepository(IBaseRepository):
    """Interface para repositorio de tenants"""
    
    
    @abstractmethod
    def get_by_api_key(self, session: Session, api_key: str) -> Optional[Any]:
        """Obtiene tenant por API key"""
        pass
    
    @abstractmethod
    def get_usage_stats(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Obtiene estadísticas de uso del tenant"""
        pass
