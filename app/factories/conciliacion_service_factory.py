"""
Factory para crear instancias de ConciliacionService
"""
from app.services.conciliacion_service import ConciliacionService
from app.interfaces.conciliacion_service_interface import IConciliacionService
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.proveedor_repository_interface import IProveedorRepository
from app.interfaces.tenant_proveedor_repository_interface import ITenantProveedorRepository
from app.interfaces.conciliacion_historial_repository_interface import IConciliacionHistorialRepository
from app.interfaces.conciliacion_detalle_repository_interface import IConciliacionDetalleRepository


class ConciliacionServiceFactory:
    """Factory para crear instancias de ConciliacionService"""
    
    @staticmethod
    def create_conciliacion_service(
        tenant_repository: ITenantRepository,
        proveedor_repository: IProveedorRepository,
        tenant_proveedor_repository: ITenantProveedorRepository,
        conciliacion_historial_repository: IConciliacionHistorialRepository,
        conciliacion_detalle_repository: IConciliacionDetalleRepository
    ) -> IConciliacionService:
        """Crea una instancia de ConciliacionService con inyección de dependencias"""
        return ConciliacionService(
            tenant_repository=tenant_repository,
            proveedor_repository=proveedor_repository,
            tenant_proveedor_repository=tenant_proveedor_repository,
            conciliacion_historial_repository=conciliacion_historial_repository,
            conciliacion_detalle_repository=conciliacion_detalle_repository
        )
