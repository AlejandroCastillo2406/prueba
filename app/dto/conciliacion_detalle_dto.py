"""
DTOs para endpoint de detalles de conciliación
"""
from pydantic import BaseModel
from typing import List


class RFCDetalleDTO(BaseModel):
    """DTO para detalle de un RFC individual"""
    rfc: str
    estado: str  # "Definitivo", "Desvirtuado", "Sentencia Favorable", "No encontrado"
    resultado: str  # "Coincidencia", "Sin coincidencia", "Regularizado"


class ResumenTecnicoDTO(BaseModel):
    """DTO para resumen técnico de la conciliación"""
    execution_id: str
    status: str  # "completed", "error", "en_proceso"
    processed: int
    matched: int


class DatosTecnicosDTO(BaseModel):
    """DTO para datos técnicos de la conciliación"""
    execution_id: str
    tenant_id: str
    start_time: str  # ISO 8601 format
    end_time: str  # ISO 8601 format
    trigger_source: str  # "automatic" o "manual"
    sat_version: str
    rfc_processed: int
    matched: int
    status: str  # "completed", "error", "en_proceso"


class ConciliacionDetalleResponseDTO(BaseModel):
    """DTO completo para respuesta de detalles de conciliación"""
    rfcs_procesados: int
    coincidencias: int
    sin_coincidencias: int
    duracion_ms: int
    rfcs: List[RFCDetalleDTO]
    resumen_tecnico: ResumenTecnicoDTO
    datos_tecnicos: DatosTecnicosDTO

