"""
Interface para servicio de cifrado
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
from sqlalchemy.orm import Session


class IEncryptionService(ABC):
    """Interface para servicio de cifrado"""
    
    @abstractmethod
    def create_tenant(self, session: Session, rfc: str, nombre_comercial: str, razon_social: str) -> Any:
        """Crea un nuevo tenant"""
        pass
    
    
    @abstractmethod
    def get_tenant_by_api_key(self, session: Session, api_key: str) -> Optional[Any]:
        """Obtiene tenant por API key"""
        pass
    
    
    @abstractmethod
    def authenticate_user(self, session: Session, email: str, password: str, tenant_id: str) -> Optional[Any]:
        """Autentica un usuario"""
        pass
