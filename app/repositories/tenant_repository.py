"""
Repositorio para Tenant con gestión correcta de sesiones
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.tenant import Tenant
from app.models.plan import Plan
from app.repositories.base_repository import BaseRepository
from app.interfaces.tenant_repository_interface import ITenantRepository


class TenantRepository(BaseRepository, ITenantRepository):
    """Repositorio para operaciones de Tenant"""
    
    def __init__(self):
        super().__init__(Tenant)
    
    
    def get_by_api_key(self, session: Session, api_key: str) -> Optional[Tenant]:
        """
        Obtiene tenant por API key
        
        Args:
            session: Sesión de base de datos
            api_key: API key del tenant
            
        Returns:
            Tenant si existe, None si no
        """
        try:
            return session.query(Tenant).filter(
                Tenant.api_key == api_key,
                Tenant.activo == True
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo tenant por API key: {e}")
            return None
    
    def get_usage_stats(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """
        Obtiene estadísticas de uso del tenant 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Diccionario con estadísticas de uso
        """
        try:
            from sqlalchemy.orm import joinedload
            from app.models.tenant_proveedor import TenantProveedor
            
            #  Cargar plan y proveedores 
            tenant = session.query(Tenant).options(
                joinedload(Tenant.plan)
            ).filter(Tenant.id == tenant_id).first()
            
            if not tenant:
                return {}
            
            #  Contar proveedores 
            from sqlalchemy import func
            proveedores_count = session.query(func.count(TenantProveedor.id)).filter(
                TenantProveedor.tenant_id == tenant_id
            ).scalar() or 0
            
            return {
                "tenant_id": str(tenant.id),
                "plan": tenant.plan.nombre if tenant.plan else "N/A",
                "limite_proveedores": tenant.plan.limite_proveedores if tenant.plan else 0,
                "proveedores_usados": proveedores_count,
                "porcentaje_uso": tenant.get_usage_percentage(),
                "cerca_del_limite": tenant.is_near_limit(),
                "puede_agregar_proveedores": tenant.can_add_proveedor()
            }
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo estadísticas de uso para tenant {tenant_id}: {e}")
            return {}
    
    def get_active_tenants(self, session: Session) -> List[Tenant]:
        """
        Obtiene todos los tenants activos
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Lista de tenants activos
        """
        try:
            return session.query(Tenant).filter(Tenant.activo == True).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo tenants activos: {e}")
            return []
    
    def update_api_key(self, session: Session, tenant_id: UUID, new_api_key: str) -> bool:
        """
        Actualiza la API key de un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            new_api_key: Nueva API key
            
        Returns:
            True si exitoso, False si error
        """
        try:
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return False
            
            tenant.api_key = new_api_key
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando API key para tenant {tenant_id}: {e}")
            session.rollback()
            return False
    
    def get_usage_stats(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """
        Obtiene estadísticas de uso del tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Diccionario con estadísticas de uso
        """
        try:
            # Cargar tenant con plan 
            from sqlalchemy.orm import joinedload
            tenant = session.query(Tenant).options(
                joinedload(Tenant.plan)
            ).filter(Tenant.id == tenant_id).first()
            
            if not tenant:
                return {"limite_rfcs": 0}
            
            # Obtener el límite del plan (ya cargado)
            limite_rfcs = 0
            if tenant.plan:
                limite_rfcs = tenant.plan.limite_proveedores or 0
            
            return {
                "limite_rfcs": limite_rfcs,
                "plan_id": tenant.plan_id,
                "plan_nombre": tenant.plan.nombre if tenant.plan else None
            }
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo estadísticas de uso del tenant {tenant_id}: {e}")
            return {"limite_rfcs": 0}
