"""
Factory para crear instancias de SATService
"""
from app.services.sat_service import SATService
from app.interfaces.sat_service_interface import ISATService
from app.interfaces.proveedor_repository_interface import IProveedorRepository


class SATServiceFactory:
    """Factory para crear instancias de SATService"""
    
    @staticmethod
    def create_sat_service(proveedor_repository: IProveedorRepository) -> ISATService:
        """Crea una instancia de SATService con inyección de dependencias"""
        return SATService(proveedor_repository=proveedor_repository)
