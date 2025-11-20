from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.conciliacion_historial import ConciliacionHistorial

if TYPE_CHECKING:
    from datetime import datetime


class IConciliacionHistorialRepository(ABC):
    """
    Interfaz para el repositorio de historial de conciliaciones
    """
    
    @abstractmethod
    def create_historial(self, session: Session, tenant_id: UUID, tipo_conciliacion: str, 
                        version_sat: Optional[str], rfcs_procesados: int, coincidencias: int,
                        fecha_conciliacion: Optional['datetime'] = None) -> ConciliacionHistorial:
        pass
    
    @abstractmethod
    def get_historial_by_tenant(self, session: Session, tenant_id: UUID, 
                               limit: int = 10) -> List[ConciliacionHistorial]:
        pass
    
    @abstractmethod
    def get_ultima_conciliacion(self, session: Session, tenant_id: UUID) -> Optional[ConciliacionHistorial]:
        pass