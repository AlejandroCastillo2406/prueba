"""
DTOs para SAT
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ConsultaSATResponseDTO(BaseModel):
    """DTO de respuesta para consulta SAT"""
    rfc: str
    existe: bool
    estatus: Optional[str] = None
    fecha_lista: Optional[datetime] = None
    razon_social: Optional[str] = None


class HistoricoRFCRequestDTO(BaseModel):
    """DTO para consultar historial de RFC"""
    rfc: str = Field(..., description="RFC del proveedor", min_length=12, max_length=13)


class HistoricoRFCItemDTO(BaseModel):
    """DTO para item del historial de RFC"""
    rfc: str
    nombre_contribuyente: str
    situacion_contribuyente: str
    version: str


class HistoricoRFCResponseDTO(BaseModel):
    """DTO de respuesta para historial de RFC"""
    historial: List[HistoricoRFCItemDTO]


class SATStatsDTO(BaseModel):
    """DTO para estadísticas del SAT"""
    total: int
    definitivos: int
    desvirtuados: int
    presuntos: int
    sentencias_favorables: int
    ultima_actualizacion: Optional[datetime]


class HealthResponseDTO(BaseModel):
    """DTO de respuesta para health check"""
    status: str
    timestamp: datetime
    version: str
    database: str
    sat_list_status: str
    sat_list_last_update: Optional[datetime]
    sat_list_total_proveedores: int
