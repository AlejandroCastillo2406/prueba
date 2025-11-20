"""
Factory para crear instancias de TenantService
"""
from app.services.tenant_service import TenantService
from app.interfaces.tenant_service_interface import ITenantService
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.plan_repository_interface import IPlanRepository


class TenantServiceFactory:
    """Factory para crear instancias de TenantService"""
    
    @staticmethod
    def create_tenant_service(
        tenant_repository: ITenantRepository,
        plan_repository: IPlanRepository
    ) -> ITenantService:
        """Crea una instancia de TenantService con inyección de dependencias"""
        return TenantService(
            tenant_repository=tenant_repository,
            plan_repository=plan_repository
        )
