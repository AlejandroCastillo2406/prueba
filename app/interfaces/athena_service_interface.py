"""
Interface para servicio de Athena
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class IAthenaService(ABC):
    """Interface para servicio de Athena"""
    
    @abstractmethod
    def get_historial_rfc(self, rfc: str) -> List[Dict[str, Any]]:
        """Obtiene el historial de un RFC"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Ejecuta una query en Athena"""
        pass
    
    @abstractmethod
    def repair_partitions(self) -> bool:
        """Repara las particiones de la tabla"""
        pass
