"""
Interface para repositorio de relación tenant-proveedor
"""
from abc import abstractmethod
from typing import Optional, List, Any
from uuid import UUID
from sqlalchemy.orm import Session
from .base_repository_interface import IBaseRepository


class ITenantProveedorRepository(IBaseRepository):
    """Interface para repositorio de relación tenant-proveedor"""
    
    @abstractmethod
    def get_by_tenant_within_limit(self, session: Session, tenant_id: UUID, limite: int) -> List[Any]:
        """Obtiene proveedores de un tenant dentro del límite del plan"""
        pass
    
    @abstractmethod
    def get_by_tenant_and_rfc(self, session: Session, tenant_id: UUID, rfc: str) -> Optional[Any]:
        """Obtiene relación por tenant y RFC"""
        pass
    
    @abstractmethod
    def delete_by_tenant_and_rfc(self, session: Session, tenant_id: UUID, rfc: str) -> bool:
        """Elimina relación por tenant y RFC"""
        pass
    
    @abstractmethod
    def get_tenant_proveedores_count(self, session: Session, tenant_id: UUID) -> int:
        """Obtiene cantidad de proveedores de un tenant"""
        pass
