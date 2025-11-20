"""
Servicio para gestión de tenants con inyección de dependencias
"""
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from loguru import logger
import secrets

from app.interfaces.tenant_service_interface import ITenantService
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.plan_repository_interface import IPlanRepository
from app.dto.tenant_dto import TenantCreateDTO, TenantUpdateDTO, TenantResponseDTO, TenantUsageDTO
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.rol import Rol


class TenantService(ITenantService):
    """Servicio para gestión de tenants"""
    
    def __init__(self, tenant_repository: ITenantRepository, plan_repository: IPlanRepository):
        self.tenant_repository = tenant_repository
        self.plan_repository = plan_repository
        self._role_cache = {} 
    
    def _get_role_by_name(self, session: Session, role_name: str) -> Optional[Rol]:
        """
        Obtiene un rol por nombre con cache
        
        Args:
            session: Sesión de base de datos
            role_name: Nombre del rol
            
        Returns:
            Rol si existe, None si no
        """
        # Verificar cache
        if role_name in self._role_cache:
            return self._role_cache[role_name]
        
        # Buscar en BD
        rol = session.query(Rol).filter(Rol.nombre == role_name).first()
        if rol:
            self._role_cache[role_name] = rol
        
        return rol
    
    def create_tenant(self, session: Session, tenant_data: Dict[str, Any]) -> Optional[Any]:
        """
        Crea un nuevo tenant
        
        Args:
            session: Sesión de base de datos
            tenant_data: Datos del tenant
            
        Returns:
            Tenant creado si exitoso, None si error
        """
        try:
            # Verificar que el plan existe
            plan = self.plan_repository.get_by_id(session, tenant_data['plan_id'])
            if not plan:
                logger.error(f"Plan {tenant_data['plan_id']} no encontrado")
                return None
            
            # Generar API key única
            api_key = secrets.token_hex(32)
            
            # Preparar datos del tenant
            tenant_create_data = {
                "rfc": tenant_data['rfc'].upper().strip(),
                "nombre_comercial": tenant_data['nombre_comercial'],
                "razon_social": tenant_data['razon_social'],
                "plan_id": tenant_data['plan_id'],
                "api_key": api_key,
                "estado": "active",
                "activo": True
            }
            
            tenant = self.tenant_repository.create(session, tenant_create_data)
            if tenant:
                logger.info(f"Tenant creado exitosamente: {tenant.id}")
            
            return tenant
            
        except Exception as e:
            logger.error(f"Error creando tenant: {e}")
            return None
    
    def create_tenant_for_user(self, session: Session, user_id: UUID, tenant_data: Dict[str, Any]) -> Optional[Any]:
        """
        Crea un nuevo tenant y asigna al usuario como OWNER
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario que será owner
            tenant_data: Datos del tenant
            
        Returns:
            Tenant creado si exitoso, None si error
        """
        try:
            # Verificar que el plan existe
            plan = self.plan_repository.get_by_id(session, tenant_data['plan_id'])
            if not plan:
                logger.error(f"Plan {tenant_data['plan_id']} no encontrado")
                return None
            
            # Verificar que el usuario existe y no tiene tenant
            usuario = session.query(Usuario).filter(Usuario.id == user_id).first()
            if not usuario:
                logger.error(f"Usuario {user_id} no encontrado")
                return None
            
            if usuario.tenant_id is not None:
                logger.error(f"Usuario {user_id} ya tiene un tenant asignado")
                return None
            
            # Obtener rol de Owner 
            rol_owner = self._get_role_by_name(session, "owner")
            if not rol_owner:
                logger.error("Rol 'owner' no encontrado. Ejecuta: python crear_roles.py")
                return None
            
            # Generar API key única
            api_key = secrets.token_hex(32)
            
            # Crear tenant 
            tenant = Tenant(
                rfc=tenant_data['rfc'].upper().strip(),
                nombre_comercial=tenant_data['nombre_comercial'],
                razon_social=tenant_data['razon_social'],
                plan_id=tenant_data['plan_id'],
                api_key=api_key,
                estado="active",
                activo=True,
                created_by=user_id
            )
            session.add(tenant)
            session.flush()  
            
            # Asignar usuario como owner del tenant
            usuario.tenant_id = tenant.id
            usuario.rol_id = rol_owner.id
            
            session.commit()
            
            logger.info(f"Tenant {tenant.id} creado exitosamente con usuario {usuario.email} como owner")
            
            return tenant
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creando tenant para usuario: {e}")
            return None
    
    def get_tenant(self, session: Session, tenant_id: UUID) -> Optional[Any]:
        """
        Obtiene un tenant por ID
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Tenant si existe, None si no
        """
        try:
            return self.tenant_repository.get_by_id(session, tenant_id)
        except Exception as e:
            logger.error(f"Error obteniendo tenant {tenant_id}: {e}")
            return None
    
    def update_tenant(self, session: Session, tenant_id: UUID, tenant_data: Dict[str, Any]) -> Optional[Any]:
        """
        Actualiza un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            tenant_data: Datos a actualizar
            
        Returns:
            Tenant actualizado si exitoso, None si error
        """
        try:
            # Si se está cambiando el plan, verificar que existe
            if 'plan_id' in tenant_data:
                plan = self.plan_repository.get_by_id(session, tenant_data['plan_id'])
                if not plan:
                    logger.error(f"Plan {tenant_data['plan_id']} no encontrado")
                    return None
            
            return self.tenant_repository.update(session, tenant_id, tenant_data)
            
        except Exception as e:
            logger.error(f"Error actualizando tenant {tenant_id}: {e}")
            return None
    
    def get_tenant_usage(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """
        Obtiene estadísticas de uso del tenant 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Diccionario con estadísticas de uso
        """
        try:
            from app.models.plan import Plan
            from app.models.tenant import Tenant
            
            # Consulta con JOIN para obtener el límite
            resultado = session.query(Plan.limite_proveedores).join(
                Tenant, Tenant.plan_id == Plan.id
            ).filter(
                Tenant.id == tenant_id
            ).first()
            
            if not resultado:
                return {"limite_rfcs": 0}
            
            return {
                "limite_rfcs": resultado[0]
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de uso del tenant {tenant_id}: {e}")
            return {"limite_rfcs": 0}
    
    
    def regenerate_api_key(self, session: Session, tenant_id: UUID) -> str:
        """
        Regenera la API key del tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Nueva API key si exitoso, cadena vacía si error
        """
        try:
            # Generar nueva API key
            new_api_key = secrets.token_hex(32)
            
            # Actualizar en la base de datos
            success = self.tenant_repository.update_api_key(session, tenant_id, new_api_key)
            if success:
                logger.info(f"API key regenerada para tenant {tenant_id}")
                return new_api_key
            else:
                logger.error(f"Error regenerando API key para tenant {tenant_id}")
                return ""
                
        except Exception as e:
            logger.error(f"Error regenerando API key para tenant {tenant_id}: {e}")
            return ""
    
    def get_tenant_by_api_key(self, session: Session, api_key: str) -> Optional[Any]:
        """
        Obtiene tenant por API key
        
        Args:
            session: Sesión de base de datos
            api_key: API key del tenant
            
        Returns:
            Tenant si existe, None si no
        """
        try:
            return self.tenant_repository.get_by_api_key(session, api_key)
        except Exception as e:
            logger.error(f"Error obteniendo tenant por API key: {e}")
            return None
    
