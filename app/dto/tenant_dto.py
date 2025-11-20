"""
DTOs para Tenant
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class TenantCreateDTO(BaseModel):
    """DTO para crear un tenant"""
    rfc: str = Field(..., description="RFC de la empresa", min_length=12, max_length=13)
    nombre_comercial: str = Field(..., description="Nombre comercial", max_length=255)
    razon_social: str = Field(..., description="Razón social", max_length=500)
    plan_id: int = Field(..., description="ID del plan de suscripción")


class TenantUpdateDTO(BaseModel):
    """DTO para actualizar un tenant"""
    nombre_comercial: Optional[str] = Field(None, description="Nombre comercial", max_length=255)
    razon_social: Optional[str] = Field(None, description="Razón social", max_length=500)
    plan_id: Optional[int] = Field(None, description="ID del plan de suscripción")


class TenantResponseDTO(BaseModel):
    """DTO de respuesta para tenant"""
    id: UUID
    nombre_comercial: str
    razon_social: str
    rfc: str
    plan_id: int
    api_key: str
    estado: str
    fecha_inicio_plan: datetime
    fecha_fin_plan: Optional[datetime]
    activo: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantUsageDTO(BaseModel):
    """DTO para estadísticas de uso del tenant"""
    tenant_id: UUID
    plan: str
    limite_proveedores: Optional[int]
    proveedores_usados: int
    porcentaje_uso: float
    cerca_del_limite: bool
    puede_agregar_proveedores: bool


class ApiKeyRegenerateDTO(BaseModel):
    """DTO para regenerar API key"""
    api_key: str
    message: str
