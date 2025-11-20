"""
Interface para repositorio de proveedores
"""
from abc import abstractmethod
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from .base_repository_interface import IBaseRepository


class IProveedorRepository(IBaseRepository):
    """Interface para repositorio de proveedores"""
    
    @abstractmethod
    def get_by_rfc(self, session: Session, rfc: str) -> Optional[Any]:
        """Obtiene proveedor por RFC"""
        pass
    
    @abstractmethod
    def get_by_rfcs_batch(self, session: Session, rfcs: List[str]) -> List[Any]:
        """Obtiene múltiples proveedores por RFCs (consulta masiva)"""
        pass
    
    @abstractmethod
    def get_stats(self, session: Session) -> Dict[str, Any]:
        """Obtiene estadísticas de proveedores"""
        pass
    
    @abstractmethod
    def bulk_insert(self, session: Session, proveedores_data: List[Dict[str, Any]]) -> bool:
        """Inserción masiva de proveedores"""
        pass
    
    @abstractmethod
    def clear_all(self, session: Session) -> bool:
        """Limpia todos los proveedores"""
        pass
