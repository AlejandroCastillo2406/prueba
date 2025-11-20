"""
DTOs para órdenes de pago de RFCs excedentes
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class RFCExcedenteDisponibleDTO(BaseModel):
    """DTO para RFC excedente disponible para pago"""
    rfc: str
    orden: int  # Posición en la cola de excedentes
    pagado: bool


class ExcedentesDisponiblesResponseDTO(BaseModel):
    """DTO para respuesta de excedentes disponibles"""
    excedentes: List[RFCExcedenteDisponibleDTO]


class CrearOrdenExcedenteRequestDTO(BaseModel):
    """DTO para crear orden de pago de excedentes"""
    rfcs: List[str] = Field(..., min_items=1, description="Lista de RFCs a pagar")


class CrearOrdenExcedenteResponseDTO(BaseModel):
    """DTO para respuesta de creación de orden"""
    orden_id: str
    cantidad_rfcs: int
    monto_total: float
    precio_unitario: float
    stripe_checkout_url: str
    expira_at: str


class OrdenPagoExcedenteResponseDTO(BaseModel):
    """DTO para respuesta de consulta de orden"""
    orden_id: str
    estado: str  # 'pendiente', 'pagado', 'cancelado', 'expirado', 'fallido'
    rfcs: List[str]
    cantidad_rfcs: int
    monto_total: float
    precio_unitario: float
    conciliado: bool
    conciliacion_id: Optional[str]
    created_at: str
    pagado_at: Optional[str]
    expira_at: str

