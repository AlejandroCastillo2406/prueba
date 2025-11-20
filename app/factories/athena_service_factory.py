"""
Factory para crear instancias de AthenaService
"""
from app.services.athena_service import AthenaService
from app.interfaces.athena_service_interface import IAthenaService


class AthenaServiceFactory:
    """Factory para crear instancias de AthenaService"""
    
    @staticmethod
    def create_athena_service() -> IAthenaService:
        """Crea una instancia de AthenaService"""
        return AthenaService()
