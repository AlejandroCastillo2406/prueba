"""
Factory para crear instancias de repositorios
"""
from app.repositories.tenant_repository import TenantRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.repositories.tenant_proveedor_repository import TenantProveedorRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.conciliacion_historial_repository import ConciliacionHistorialRepository
from app.repositories.conciliacion_detalle_repository import ConciliacionDetalleRepository
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.proveedor_repository_interface import IProveedorRepository
from app.interfaces.tenant_proveedor_repository_interface import ITenantProveedorRepository
from app.interfaces.plan_repository_interface import IPlanRepository
from app.interfaces.conciliacion_historial_repository_interface import IConciliacionHistorialRepository
from app.interfaces.conciliacion_detalle_repository_interface import IConciliacionDetalleRepository


class RepositoryFactory:
    """Factory para crear instancias de repositorios"""
    
    @staticmethod
    def create_tenant_repository() -> ITenantRepository:
        """Crea una instancia de TenantRepository"""
        return TenantRepository()
    
    @staticmethod
    def create_proveedor_repository() -> IProveedorRepository:
        """Crea una instancia de ProveedorRepository"""
        return ProveedorRepository()
    
    @staticmethod
    def create_tenant_proveedor_repository() -> ITenantProveedorRepository:
        """Crea una instancia de TenantProveedorRepository"""
        return TenantProveedorRepository()
    
    @staticmethod
    def create_plan_repository() -> IPlanRepository:
        """Crea una instancia de PlanRepository"""
        return PlanRepository()
    
    @staticmethod
    def create_conciliacion_historial_repository() -> IConciliacionHistorialRepository:
        """Crea una instancia de ConciliacionHistorialRepository"""
        return ConciliacionHistorialRepository()
    
    @staticmethod
    def create_conciliacion_detalle_repository() -> IConciliacionDetalleRepository:
        """Crea una instancia de ConciliacionDetalleRepository"""
        return ConciliacionDetalleRepository()
    
    @staticmethod
    def create_all_repositories() -> dict:
        """Crea todas las instancias de repositorios"""
        return {
            "tenant_repository": RepositoryFactory.create_tenant_repository(),
            "proveedor_repository": RepositoryFactory.create_proveedor_repository(),
            "tenant_proveedor_repository": RepositoryFactory.create_tenant_proveedor_repository(),
            "plan_repository": RepositoryFactory.create_plan_repository(),
            "conciliacion_historial_repository": RepositoryFactory.create_conciliacion_historial_repository(),
            "conciliacion_detalle_repository": RepositoryFactory.create_conciliacion_detalle_repository()
        }
