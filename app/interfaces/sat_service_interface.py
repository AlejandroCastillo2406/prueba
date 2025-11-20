"""
Interface para servicio del SAT
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session


class ISATService(ABC):
    """Interface para servicio del SAT"""
    
    @abstractmethod
    def update_database(self, session: Session, force: bool = False) -> Dict[str, Any]:
        """
        Actualiza la base de datos con la lista del SAT
        
        Returns:
            Diccionario con:
            - success: True si la actualización fue exitosa, False en caso contrario
            - nueva_version: True si se detectó una nueva versión, False si ya estaba procesada
            - fecha_version: Fecha de la versión procesada (str en formato YYYY-MM-DD) o None
            - total_registros: Total de registros procesados (opcional)
        """
        pass
    
    @abstractmethod
    def get_proveedor_by_rfc(self, session: Session, rfc: str) -> Optional[Any]:
        """Busca un proveedor por RFC"""
        pass
    
    @abstractmethod
    def get_stats(self, session: Session) -> Dict[str, Any]:
        """Obtiene estadísticas de la lista del SAT"""
        pass
