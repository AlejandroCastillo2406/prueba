"""
Repositorio para Grupos
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.grupo import Grupo
from app.repositories.base_repository import BaseRepository


class GrupoRepository(BaseRepository):
    """Repositorio para operaciones de Grupo"""
    
    def __init__(self):
        super().__init__(Grupo)
    
    def get_by_tenant(self, session: Session, tenant_id: UUID) -> List[Grupo]:
        """
        Obtiene todos los grupos de un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Lista de grupos del tenant
        """
        try:
            return session.query(Grupo).filter(
                Grupo.tenant_id == tenant_id,
                Grupo.activo == True
            ).order_by(Grupo.nombre).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo grupos del tenant {tenant_id}: {e}")
            return []
    
    def get_by_tenant_and_nombre(self, session: Session, tenant_id: UUID, nombre: str) -> Optional[Grupo]:
        """
        Obtiene un grupo por tenant y nombre (case-insensitive)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            nombre: Nombre del grupo
            
        Returns:
            Grupo si existe, None si no
        """
        try:
            nombre_norm = nombre.strip().lower()  # Normalizar a minúsculas
            return session.query(Grupo).filter(
                Grupo.tenant_id == tenant_id,
                Grupo.nombre == nombre_norm
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo grupo por nombre: {e}")
            return None
    
    def get_by_id_and_tenant(self, session: Session, grupo_id: UUID, tenant_id: UUID) -> Optional[Grupo]:
        """
        Obtiene un grupo por ID verificando que pertenezca al tenant
        
        Args:
            session: Sesión de base de datos
            grupo_id: ID del grupo
            tenant_id: ID del tenant
            
        Returns:
            Grupo si existe y pertenece al tenant, None si no
        """
        try:
            return session.query(Grupo).filter(
                Grupo.id == grupo_id,
                Grupo.tenant_id == tenant_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo grupo por ID: {e}")
            return None
    
    def create_or_get(self, session: Session, tenant_id: UUID, nombre: str, commit: bool = False) -> Optional[Grupo]:
        """
        Crea un grupo si no existe, o retorna el existente.
        Normaliza el nombre a minúsculas para evitar duplicados (ej: "General" y "general" son el mismo).
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            nombre: Nombre del grupo (se normaliza a minúsculas)
            commit: Si True, hace commit. Si False, solo hace flush (más rápido)
            
        Returns:
            Grupo creado o existente
        """
        try:
            nombre_norm = nombre.strip().lower()  # Normalizar a minúsculas para evitar duplicados
            
            # Buscar si ya existe 
            grupo_existente = session.query(Grupo).filter(
                Grupo.tenant_id == tenant_id,
                Grupo.nombre == nombre_norm
            ).first()
            
            if grupo_existente:
                return grupo_existente
            
            # Crear nuevo grupo (siempre en minúsculas)
            nuevo_grupo = Grupo(
                tenant_id=tenant_id,
                nombre=nombre_norm,
                activo=True
            )
            session.add(nuevo_grupo)
            session.flush()  # Flush para obtener el ID sin commit
            session.refresh(nuevo_grupo)
            
            if commit:
                session.commit()
            
            logger.debug(f"Grupo creado: {nuevo_grupo.id} - {nuevo_grupo.nombre}")
            return nuevo_grupo
            
        except SQLAlchemyError as e:
            logger.error(f"Error creando/obteniendo grupo: {e}")
            if commit:
                session.rollback()
            return None

