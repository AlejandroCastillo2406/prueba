"""
Rutas para gestión de tenants
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from loguru import logger

from app.core.database import get_db
from app.core.auth import get_current_tenant, get_current_active_user
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.dto.tenant_dto import (
    TenantCreateDTO,
    TenantUpdateDTO,
    TenantResponseDTO,
    TenantUsageDTO,
    ApiKeyRegenerateDTO
)
from app.dto.tenant_stats_dto import TenantStatsResponseDTO
from app.dto.proveedor_list_dto import ProveedorListResponseDTO
from app.factories.service_factory import service_factory


router = APIRouter()


@router.post("/", response_model=TenantResponseDTO)
async def create_tenant(
    tenant_data: TenantCreateDTO,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo tenant y asigna al usuario como OWNER
    
    Requiere autenticación JWT (Bearer token).
    El usuario que crea el tenant se convierte automáticamente en owner.
    """
    try:
        # Verificar que el usuario no tenga ya un tenant
        if current_user.tenant_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya tienes un tenant asignado. Solo puedes tener un tenant."
            )
        
        service = service_factory.create_tenant_service()
        tenant = service.create_tenant_for_user(db, current_user.id, tenant_data.dict())
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creando tenant"
            )
        
        logger.info(f"Tenant creado: {tenant.id} por usuario {current_user.email}")
        
        return TenantResponseDTO.from_orm(tenant)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando tenant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando tenant: {str(e)}"
        )


@router.get("/me", response_model=TenantResponseDTO)
async def get_my_tenant(
    current_tenant: Tenant = Depends(get_current_tenant)
):
    """
    Obtiene información del tenant actual
    """
    return TenantResponseDTO.from_orm(current_tenant)


@router.put("/me", response_model=TenantResponseDTO)
async def update_my_tenant(
    tenant_update: TenantUpdateDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Actualiza información del tenant actual
    """
    try:
        service = service_factory.create_tenant_service()
        updated_tenant = service.update_tenant(
            db, 
            current_tenant.id, 
            tenant_update.dict(exclude_unset=True)
        )
        
        if not updated_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error actualizando tenant"
            )
        
        return TenantResponseDTO.from_orm(updated_tenant)
        
    except Exception as e:
        logger.error(f"Error actualizando tenant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando tenant: {str(e)}"
        )


@router.post("/regenerate-api-key", response_model=ApiKeyRegenerateDTO)
async def regenerate_api_key(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Regenera la API key del tenant
    """
    try:
        service = service_factory.create_tenant_service()
        new_api_key = service.regenerate_api_key(db, current_tenant.id)
        
        if not new_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error regenerando API key"
            )
        
        return ApiKeyRegenerateDTO(
            api_key=new_api_key,
            message="API key regenerada exitosamente"
        )
        
    except Exception as e:
        logger.error(f"Error regenerando API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerando API key: {str(e)}"
        )


@router.get("/stats", response_model=TenantStatsResponseDTO)
async def get_tenant_stats(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas del tenant basado en su API key
    
    Retorna:
    - total_rfcs: Cantidad de RFCs activos agregados como proveedores
    - limite_rfcs: Límite de RFCs según su plan
    - alertas: Cantidad de RFCs activos con status definitivo
    - porcentaje_uso: Porcentaje de uso del límite
    - ultima_conciliacion_fecha: Fecha de la última conciliación realizada
    """
    try:
        service = service_factory.create_tenant_service()
        usage_stats = service.get_tenant_usage(db, current_tenant.id)
        
        # Obtener estadísticas solo dentro del límite del plan
        conciliacion_service = service_factory.create_conciliacion_service()
        limite_rfcs = usage_stats.get('limite_rfcs', 0)
        
        # Obtener estadísticas contando solo RFCs dentro del límite (ordenados por fecha de agregado)
        stats_dentro_limite = conciliacion_service.get_tenant_stats_within_limit(
            db, 
            current_tenant.id, 
            limite_rfcs
        )
        
        total_rfcs = stats_dentro_limite.get('total_rfcs', 0)
        alertas = stats_dentro_limite.get('alertas', 0)
        porcentaje_uso = (total_rfcs / limite_rfcs * 100) if limite_rfcs > 0 else 0
        
        # Obtener fecha de la última conciliación
        ultima_conciliacion = conciliacion_service.conciliacion_historial_repository.get_ultima_conciliacion(
            db, 
            current_tenant.id
        )
        ultima_conciliacion_fecha = None
        if ultima_conciliacion and ultima_conciliacion.fecha_conciliacion:
            fecha = ultima_conciliacion.fecha_conciliacion

            ultima_conciliacion_fecha = fecha.strftime("%Y-%m-%d %H:%M:%S")
        
        return TenantStatsResponseDTO(
            total_rfcs=total_rfcs,
            limite_rfcs=limite_rfcs,
            alertas=alertas,
            porcentaje_uso=round(porcentaje_uso, 2),
            ultima_conciliacion_fecha=ultima_conciliacion_fecha
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del tenant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.get("/proveedores", response_model=ProveedorListResponseDTO)
async def listar_proveedores_paginado(
    pagina: int = Query(1, ge=1, description="Número de página"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Lista los proveedores del tenant con paginación (20 por página)
    
    Requiere autenticación con API Key en el header X-API-Key.
    
    Parámetros:
    - pagina: Número de página (empezando en 1)
    
    Retorna:
    - proveedores: Lista de proveedores con RFC, estatus y fecha de agregado
    - total: Total de proveedores
    - pagina: Página actual
    - por_pagina: Elementos por página (fijo en 20)
    - total_paginas: Total de páginas
    """
    try:
        service = service_factory.create_conciliacion_service()
        resultado = service.listar_proveedores_paginado(
            db, 
            current_tenant.id, 
            pagina, 
            20  # Fijo en 20 elementos por página
        )
        
        return ProveedorListResponseDTO(**resultado)
        
    except Exception as e:
        logger.error(f"Error listando proveedores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando proveedores: {str(e)}"
        )
