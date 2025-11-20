"""
DTOs para operaciones con el DOF (Diario Oficial de la Federación)
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class ProcesarDOFRequestDTO(BaseModel):
    """DTO para solicitar procesamiento de DOF. Si no se proporciona fecha, se usa la fecha actual de CDMX"""
    fecha: Optional[str] = Field(None, description="Fecha opcional en formato YYYY-MM-DD. Si no se proporciona, se usa la fecha actual de CDMX")


class ErrorDOFDTO(BaseModel):
    """DTO para error en procesamiento"""
    oficio: str
    error: str


class ProcesarDOFResponseDTO(BaseModel):
    """DTO de respuesta para procesamiento de DOF"""
    fecha: str
    articulos_encontrados: int
    articulos_nuevos: int
    articulos_existentes: int
    articulos_procesados: int
    errores: List[ErrorDOFDTO] = []



