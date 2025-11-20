"""
Factory para crear instancias de EncryptionService
"""
from app.services.encryption_service import EncryptionService
from app.interfaces.encryption_service_interface import IEncryptionService


class EncryptionServiceFactory:
    """Factory para crear instancias de EncryptionService"""
    
    @staticmethod
    def create_encryption_service() -> IEncryptionService:
        """Crea una instancia de EncryptionService"""
        return EncryptionService()
