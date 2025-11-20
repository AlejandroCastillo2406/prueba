"""
DTOs para gestión de RFCs
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from uuid import UUID


class RFCItemDTO(BaseModel):
    """DTO para información de un RFC individual"""
    rfc: str = Field(..., description="RFC del proveedor")
    razon_social: Optional[str] = Field(None, description="Razón social/Nombre del contribuyente")
    estado_sat: Optional[str] = Field(None, description="Estado SAT (Definitivo, Desvirtuado, Sentencia Favorable, etc.)")
    estado_operativo: str = Field(..., description="Estado operativo (activo/inactivo)")
    grupo: Optional[str] = Field(None, description="Grupo al que pertenece el RFC")
    fecha_ultima_actualizacion: Optional[date] = Field(None, description="Fecha de última actualización del RFC (solo fecha)")
    
    class Config:
        from_attributes = True


class RFCDashboardResponseDTO(BaseModel):
    """DTO para respuesta del dashboard de RFCs"""
    total_rfcs: int = Field(..., description="Número total de RFCs del tenant")
    rfcs_activos: int = Field(..., description="Número de RFCs activos")
    rfcs_inactivos: int = Field(..., description="Número de RFCs inactivos")
    rfcs_con_alerta: int = Field(..., description="Número de RFCs con alerta (Definitivo)")
    fecha_ultima_conciliacion: Optional[date] = Field(None, description="Fecha de última conciliación (solo fecha)")
    rfcs: List[RFCItemDTO] = Field(..., description="Lista de RFCs con su información")
    total: int = Field(..., description="Total de RFCs")
    pagina: int = Field(..., description="Página actual")
    por_pagina: int = Field(..., description="Elementos por página")
    total_paginas: int = Field(..., description="Total de páginas")
    
    class Config:
        from_attributes = True


class ActivarRFCRequestDTO(BaseModel):
    """DTO para activar un RFC"""
    activo: bool = Field(True, description="True para activar, False para desactivar")


class AsignarGrupoRequestDTO(BaseModel):
    """DTO para asignar un RFC a un grupo"""
    grupo: Optional[str] = Field(None, description="Nombre del grupo (None para eliminar grupo)", max_length=100)


class RFCUpdateResponseDTO(BaseModel):
    """DTO para respuesta de actualización de RFC"""
    rfc: str = Field(..., description="RFC actualizado")
    activo: Optional[bool] = Field(None, description="Estado operativo actualizado")
    grupo: Optional[str] = Field(None, description="Grupo asignado")
    mensaje: str = Field(..., description="Mensaje de confirmación")


class GruposListResponseDTO(BaseModel):
    """DTO para respuesta de lista de grupos"""
    grupos: List[str] = Field(..., description="Lista de nombres de grupos del tenant")
    total: int = Field(..., description="Total de grupos")
