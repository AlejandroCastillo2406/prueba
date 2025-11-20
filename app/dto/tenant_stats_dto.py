"""
DTOs para estadísticas del tenant
"""
from typing import Optional
from pydantic import BaseModel


class TenantStatsResponseDTO(BaseModel):
    """DTO de respuesta para estadísticas del tenant"""
    total_rfcs: int
    limite_rfcs: int
    alertas: int  # RFCs con status definitivo
    porcentaje_uso: float
    ultima_conciliacion_fecha: Optional[str] = None  # Fecha de la última conciliación en formato ISO
