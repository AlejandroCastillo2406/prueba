"""
Repositorios para acceso a datos
"""
from app.repositories.base_repository import BaseRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.repositories.tenant_proveedor_repository import TenantProveedorRepository
from app.repositories.plan_repository import PlanRepository

__all__ = [
    "BaseRepository",
    "TenantRepository",
    "ProveedorRepository",
    "TenantProveedorRepository",
    "PlanRepository"
]