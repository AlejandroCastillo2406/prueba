"""
DTOs para listado de proveedores
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ProveedorItemDTO(BaseModel):
    """DTO para un item de proveedor en el listado"""
    rfc: str = Field(..., description="RFC del proveedor")
    estatus: str = Field(..., description="Estatus del proveedor en el SAT")
    fecha_agregado: str = Field(..., description="Fecha cuando se agregó el proveedor")


class ProveedorListResponseDTO(BaseModel):
    """DTO de respuesta para listado de proveedores"""
    proveedores: List[ProveedorItemDTO] = Field(..., description="Lista de proveedores")
    total: int = Field(..., description="Total de proveedores")
    pagina: int = Field(..., description="Página actual")
    por_pagina: int = Field(..., description="Elementos por página")
    total_paginas: int = Field(..., description="Total de páginas")
