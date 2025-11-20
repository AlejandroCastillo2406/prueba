"""
Interfaz para el repositorio de detalles de conciliación
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.conciliacion_detalle import ConciliacionDetalle


class IConciliacionDetalleRepository(ABC):
    """Interfaz para operaciones CRUD de detalles de conciliación"""
    
    @abstractmethod
    def create(self, session: Session, conciliacion_detalle: ConciliacionDetalle) -> ConciliacionDetalle:
        """
        Crea un nuevo detalle de conciliación
        
        Args:
            session: Sesión de base de datos
            conciliacion_detalle: Objeto ConciliacionDetalle a crear
            
        Returns:
            ConciliacionDetalle creado
        """
        pass
    
    @abstractmethod
    def create_bulk(self, session: Session, detalles: List[ConciliacionDetalle]) -> List[ConciliacionDetalle]:
        """
        Crea múltiples detalles de conciliación en una sola operación
        
        Args:
            session: Sesión de base de datos
            detalles: Lista de objetos ConciliacionDetalle a crear
            
        Returns:
            Lista de ConciliacionDetalle creados
        """
        pass
    
    @abstractmethod
    def get_by_conciliacion_id(self, session: Session, conciliacion_id: UUID) -> List[ConciliacionDetalle]:
        """
        Obtiene todos los detalles de una conciliación específica
        
        Args:
            session: Sesión de base de datos
            conciliacion_id: ID de la conciliación
            
        Returns:
            Lista de detalles de conciliación
        """
        pass
    
    @abstractmethod
    def get_by_rfc(self, session: Session, rfc: str) -> List[ConciliacionDetalle]:
        """
        Obtiene todos los detalles de un RFC específico
        
        Args:
            session: Sesión de base de datos
            rfc: RFC del proveedor
            
        Returns:
            Lista de detalles de conciliación para ese RFC
        """
        pass
    
    @abstractmethod
    def get_by_id(self, session: Session, detalle_id: UUID) -> Optional[ConciliacionDetalle]:
        """
        Obtiene un detalle por su ID
        
        Args:
            session: Sesión de base de datos
            detalle_id: ID del detalle
            
        Returns:
            ConciliacionDetalle o None si no existe
        """
        pass
    
    @abstractmethod
    def delete_by_conciliacion_id(self, session: Session, conciliacion_id: UUID) -> int:
        """
        Elimina todos los detalles de una conciliación
        
        Args:
            session: Sesión de base de datos
            conciliacion_id: ID de la conciliación
            
        Returns:
            Número de registros eliminados
        """
        pass

