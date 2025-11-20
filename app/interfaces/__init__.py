"""
Interfaces del sistema
"""
from .conciliacion_service_interface import IConciliacionService
from .sat_service_interface import ISATService
from .encryption_service_interface import IEncryptionService
from .tenant_service_interface import ITenantService
from .athena_service_interface import IAthenaService
from .base_repository_interface import IBaseRepository
from .tenant_repository_interface import ITenantRepository
from .proveedor_repository_interface import IProveedorRepository
from .tenant_proveedor_repository_interface import ITenantProveedorRepository
from .plan_repository_interface import IPlanRepository
from .database_interface import IDatabaseManager

__all__ = [
    # Service Interfaces
    "IConciliacionService",
    "ISATService", 
    "IEncryptionService",
    "ITenantService",
    "IAthenaService",
    
    # Repository Interfaces
    "IBaseRepository",
    "ITenantRepository",
    "IProveedorRepository", 
    "ITenantProveedorRepository",
    "IPlanRepository",
    
    # Database Interfaces
    "IDatabaseManager"
]