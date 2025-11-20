"""
DTOs (Data Transfer Objects) para transferencia de datos
"""
from app.dto.tenant_dto import (
    TenantCreateDTO,
    TenantUpdateDTO,
    TenantResponseDTO,
    TenantUsageDTO,
    ApiKeyRegenerateDTO
)
from app.dto.conciliacion_dto import (
    ConsultarRFCRequestDTO,
    AgregarProveedorRequestDTO,
    AgregarProveedorResponseDTO
)
from app.dto.sat_dto import (
    ConsultaSATResponseDTO,
    HistoricoRFCRequestDTO,
    HistoricoRFCItemDTO,
    HistoricoRFCResponseDTO,
    SATStatsDTO,
    HealthResponseDTO
)
from app.dto.tenant_stats_dto import TenantStatsResponseDTO
from app.dto.conciliacion_response_dto import ConciliacionResponseDTO

__all__ = [
    # Tenant DTOs
    "TenantCreateDTO",
    "TenantUpdateDTO", 
    "TenantResponseDTO",
    "TenantUsageDTO",
    "ApiKeyRegenerateDTO",
    
    # Conciliación DTOs
    "ConsultarRFCRequestDTO",
    "AgregarProveedorRequestDTO",
    "AgregarProveedorResponseDTO",
    
    # SAT DTOs
    "ConsultaSATResponseDTO",
    "HistoricoRFCRequestDTO",
    "HistoricoRFCItemDTO",
    "HistoricoRFCResponseDTO",
    "SATStatsDTO",
    "HealthResponseDTO",
    
    # Tenant Stats DTOs
    "TenantStatsResponseDTO",
    
    # Conciliación Response DTOs
    "ConciliacionResponseDTO"
]