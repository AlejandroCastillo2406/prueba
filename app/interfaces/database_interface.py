"""
Interfaces para gestión de base de datos
"""
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class IDatabaseManager(ABC):
    """Interface para gestión de base de datos"""
    
    @abstractmethod
    def create_session(self) -> Session:
        """Crea una nueva sesión de base de datos"""
        pass
    
    @abstractmethod
    def close_session(self, session: Session) -> None:
        """Cierra una sesión de base de datos"""
        pass
    
    @abstractmethod
    def get_session(self) -> Session:
        """Obtiene la sesión actual (para dependency injection)"""
        pass
