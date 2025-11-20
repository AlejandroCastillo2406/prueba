from pydantic import BaseModel
from typing import Optional

class ConciliacionResponseDTO(BaseModel):
    """
    DTO para la respuesta de realizar conciliación
    """
    fecha_conciliacion: str
    tipo_conciliacion: str  # "Automatica" o "Manual"
    version_sat: Optional[str]
    rfcs_procesados: int
    coincidencias: int
    estado: str
    historial_id: str
