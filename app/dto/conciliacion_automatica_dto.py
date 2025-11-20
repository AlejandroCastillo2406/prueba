"""
DTOs para conciliación automática de todos los tenants
"""
from pydantic import BaseModel
from typing import List, Optional


class ConciliacionAutomaticaItemDTO(BaseModel):
    """
    DTO para un resultado de conciliación automática
    """
    tenant_id: str
    fecha_conciliacion: str
    tipo_conciliacion: str
    version_sat: Optional[str]
    rfcs_procesados: int
    coincidencias: int
    estado: str
    historial_id: Optional[str]


class ConciliacionAutomaticaResponseDTO(BaseModel):
    """
    DTO para la respuesta de conciliación automática de todos los tenants
    """
    total_tenants: int
    total_procesados: int
    total_exitosos: int
    total_fallidos: int
    resultados: List[ConciliacionAutomaticaItemDTO]

