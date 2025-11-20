"""
Factory para crear instancias de servicios con inyección de dependencias
"""
from app.services.tenant_service import TenantService
from app.services.sat_service import SATService
from app.services.conciliacion_service import ConciliacionService
from app.services.encryption_service import EncryptionService
from app.interfaces.conciliacion_service_interface import IConciliacionService
from app.interfaces.sat_service_interface import ISATService
from app.interfaces.encryption_service_interface import IEncryptionService
from app.interfaces.tenant_service_interface import ITenantService
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.proveedor_repository_interface import IProveedorRepository
from app.interfaces.tenant_proveedor_repository_interface import ITenantProveedorRepository
from app.interfaces.plan_repository_interface import IPlanRepository
from app.factories.repository_factory import RepositoryFactory


class ServiceFactory:
    """Factory para crear instancias de servicios con inyección de dependencias"""
    
    def __init__(self):
        self._repositories = RepositoryFactory.create_all_repositories()
    
    def create_tenant_service(self) -> ITenantService:
        """Crea una instancia de TenantService"""
        return TenantService(
            tenant_repository=self._repositories["tenant_repository"],
            plan_repository=self._repositories["plan_repository"]
        )
    
    def create_sat_service(self) -> ISATService:
        """Crea una instancia de SATService"""
        return SATService(
            proveedor_repository=self._repositories["proveedor_repository"]
        )
    
    def create_conciliacion_service(self) -> IConciliacionService:
        """Crea una instancia de ConciliacionService"""
        return ConciliacionService(
            tenant_repository=self._repositories["tenant_repository"],
            proveedor_repository=self._repositories["proveedor_repository"],
            tenant_proveedor_repository=self._repositories["tenant_proveedor_repository"],
            conciliacion_historial_repository=self._repositories["conciliacion_historial_repository"],
            conciliacion_detalle_repository=self._repositories["conciliacion_detalle_repository"]
        )
    
    def create_encryption_service(self) -> IEncryptionService:
        """Crea una instancia de EncryptionService"""
        return EncryptionService()
    


# Instancia global del factory
service_factory = ServiceFactory()
