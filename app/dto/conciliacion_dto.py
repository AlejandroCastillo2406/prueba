"""
DTOs para Conciliación
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from .proveedor_list_dto import ProveedorListResponseDTO


class ConsultarRFCRequestDTO(BaseModel):
    """DTO para consultar un RFC en el SAT"""
    rfc: str = Field(..., description="RFC del proveedor", min_length=12, max_length=13)


class ProveedorItemDTO(BaseModel):
    """DTO para un proveedor individual"""
    rfc: str = Field(..., description="RFC del proveedor (12 o 13 caracteres)", min_length=12, max_length=13)
    razon_social: Optional[str] = Field(None, description="Razón social del proveedor (opcional)", max_length=500)


class AgregarProveedorRequestDTO(BaseModel):
    """DTO para agregar uno o varios proveedores"""
    proveedores: List[ProveedorItemDTO] = Field(..., description="Lista de proveedores a agregar", min_items=1)


class AgregarProveedorItemResponseDTO(BaseModel):
    """DTO de respuesta para un proveedor agregado"""
    rfc: str
    proveedor_id: str
    error: Optional[str] = None


class AgregarProveedorResponseDTO(BaseModel):
    """DTO de respuesta para agregar proveedores"""
    resultados: List[AgregarProveedorItemResponseDTO]


