"""
Interface para servicio de conciliación
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session


class IConciliacionService(ABC):
    """Interface para servicio de conciliación"""
    
    @abstractmethod
    def agregar_proveedores_batch(self, session: Session, tenant_id: UUID, proveedores: List[Dict[str, Any]], limite_rfcs: int) -> List[Dict[str, Any]]:
        """Agrega múltiples proveedores al tenant. Cada proveedor debe tener 'rfc' y opcionalmente 'razon_social'"""
        pass
    
    @abstractmethod
    def realizar_conciliacion(self, session: Session, tenant_id: UUID, tipo_conciliacion: str = "Manual") -> Dict[str, Any]:
        """Realiza conciliación de proveedores del tenant"""
        pass
    
    @abstractmethod
    def eliminar_proveedor(self, session: Session, tenant_id: UUID, rfc: str) -> bool:
        """Elimina un proveedor del tenant"""
        pass
    
    @abstractmethod
    def obtener_ultima_conciliacion_power_query(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Obtiene la última conciliación en formato para Power Query con resultado general y subrama de RFCs"""
        pass
    
    @abstractmethod
    def obtener_detalles_conciliacion(self, session: Session, tenant_id: UUID, historial_id: UUID) -> Dict[str, Any]:
        """Obtiene detalles completos de una conciliación específica"""
        pass
    
    @abstractmethod
    def conciliar_rfcs_especificos(self, session: Session, tenant_id: UUID, rfcs: List[str], tipo_conciliacion: str = "Excedentes - Pago") -> UUID:
        """Crea una conciliación para una lista específica de RFCs (usado para excedentes pagados)"""
        pass
    
    @abstractmethod
    def realizar_conciliacion_todos_tenants(self, session: Session) -> Dict[str, Any]:
        """Ejecuta conciliación automática para todos los tenants activos"""
        pass