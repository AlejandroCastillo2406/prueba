"""
Rutas para gestión de roles
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.usuario import Usuario
from app.models.rol import Rol
from pydantic import BaseModel

router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
)


class RolResponse(BaseModel):
    """Response con datos del rol"""
    id: UUID
    nombre: str
    descripcion: str
    nivel: int
    permisos: dict
    es_sistema: bool
    activo: bool
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[RolResponse])
async def list_roles(
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos los roles disponibles
    
    Requiere autenticación JWT.
    """
    try:
        roles = db.query(Rol).filter(Rol.activo == True).order_by(Rol.nivel).all()
        return [RolResponse.model_validate(rol) for rol in roles]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar roles: {str(e)}"
        )


@router.get("/{rol_id}", response_model=RolResponse)
async def get_role(
    rol_id: UUID,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene información detallada de un rol
    
    Requiere autenticación JWT.
    """
    try:
        rol = db.query(Rol).filter(Rol.id == rol_id).first()
        if not rol:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado"
            )
        return RolResponse.model_validate(rol)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener rol: {str(e)}"
        )

