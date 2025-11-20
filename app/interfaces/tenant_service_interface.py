"""
Interface para servicio de tenants
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session


class ITenantService(ABC):
    """Interface para servicio de tenants"""
    
    @abstractmethod
    def create_tenant(self, session: Session, tenant_data: Dict[str, Any]) -> Any:
        """Crea un nuevo tenant"""
        pass
    
    @abstractmethod
    def get_tenant(self, session: Session, tenant_id: UUID) -> Optional[Any]:
        """Obtiene un tenant por ID"""
        pass
    
    @abstractmethod
    def update_tenant(self, session: Session, tenant_id: UUID, tenant_data: Dict[str, Any]) -> Optional[Any]:
        """Actualiza un tenant"""
        pass
    
    @abstractmethod
    def get_tenant_usage(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Obtiene estadísticas de uso del tenant"""
        pass
    
    @abstractmethod
    def regenerate_api_key(self, session: Session, tenant_id: UUID) -> str:
        """Regenera la API key del tenant"""
        pass
