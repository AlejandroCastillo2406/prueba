"""
DTOs para planes de suscripción
"""
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal


class PlanResponseDTO(BaseModel):
    """DTO para respuesta de un plan individual"""
    id: int
    nombre: str
    descripcion: Optional[str]
    limite_proveedores: Optional[int]
    limite_usuarios: Optional[int]
    conciliacion_automatica: bool
    precio: float
    activo: bool
    
    class Config:
        from_attributes = True


class PlanesListResponseDTO(BaseModel):
    """DTO para lista de planes"""
    planes: List[PlanResponseDTO]
    total: int

