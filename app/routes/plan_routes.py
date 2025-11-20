"""
Rutas para planes de suscripción
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

from app.core.database import get_db
from app.dto.plan_dto import PlanResponseDTO, PlanesListResponseDTO
from app.models.plan import Plan


router = APIRouter()


@router.get(
    "/planes",
    response_model=PlanesListResponseDTO,
    summary="Listar planes activos disponibles",
    description="Obtiene la lista de planes activos de suscripción con sus características y precios"
)
async def listar_planes(
    db: Session = Depends(get_db)
):
    """
    Lista todos los planes activos disponibles.
    
    **Retorna:**
    - Lista de planes activos con todas sus características
    - Total de planes encontrados
    
    **No requiere autenticación** (endpoint público para mostrar en landing/registro)
    """
    try:
        # Query solo planes activos
        query = db.query(Plan).filter(Plan.activo == True)
        
        # Ordenar por precio (ascendente)
        query = query.order_by(Plan.precio.asc())
        
        # Ejecutar query
        planes = query.all()
        
        # Convertir a DTOs
        planes_dto = [
            PlanResponseDTO(
                id=plan.id,
                nombre=plan.nombre,
                descripcion=plan.descripcion,
                limite_proveedores=plan.limite_proveedores,
                limite_usuarios=plan.limite_usuarios,
                conciliacion_automatica=plan.conciliacion_automatica,
                precio=float(plan.precio),
                activo=plan.activo
            )
            for plan in planes
        ]
        
        return PlanesListResponseDTO(
            planes=planes_dto,
            total=len(planes_dto)
        )
        
    except Exception as e:
        logger.error(f"Error listando planes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo planes: {str(e)}"
        )


@router.get(
    "/planes/{plan_id}",
    response_model=PlanResponseDTO,
    summary="Obtener detalles de un plan específico",
    description="Obtiene la información completa de un plan por su ID"
)
async def obtener_plan(
    plan_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un plan específico por ID.
    
    **Path Parameters:**
    - `plan_id` (int): ID del plan
    
    **Retorna:**
    - Información completa del plan
    
    **No requiere autenticación**
    """
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan con ID {plan_id} no encontrado"
            )
        
        return PlanResponseDTO(
            id=plan.id,
            nombre=plan.nombre,
            descripcion=plan.descripcion,
            limite_proveedores=plan.limite_proveedores,
            limite_usuarios=plan.limite_usuarios,
            conciliacion_automatica=plan.conciliacion_automatica,
            precio=float(plan.precio),
            activo=plan.activo
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo plan {plan_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo plan: {str(e)}"
        )

