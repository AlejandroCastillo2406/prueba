"""
Repositorio para gestión de usuarios
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
import uuid

from app.models.usuario import Usuario
from app.core.config import settings
from app.core.timezone import get_mexico_time_naive


class UsuarioRepository:
    """Repositorio para operaciones CRUD de usuarios"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get(self, user_id: uuid.UUID) -> Optional[Usuario]:
        """
        Obtiene un usuario por ID
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Usuario o None
        """
        return self.db.query(Usuario).filter(Usuario.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[Usuario]:
        """
        Obtiene un usuario por email
        
        Args:
            email: Email del usuario
            
        Returns:
            Usuario o None
        """
        return self.db.query(Usuario).filter(
            Usuario.email == email.lower()
        ).first()
    
    def get_by_email_and_tenant(self, email: str, tenant_id: uuid.UUID) -> Optional[Usuario]:
        """
        Obtiene un usuario por email y tenant
        
        Args:
            email: Email del usuario
            tenant_id: ID del tenant
            
        Returns:
            Usuario o None
        """
        return self.db.query(Usuario).filter(
            and_(
                Usuario.email == email.lower(),
                Usuario.tenant_id == tenant_id
            )
        ).first()
    
    def get_by_tenant(self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Usuario]:
        """
        Obtiene todos los usuarios de un tenant
        
        Args:
            tenant_id: ID del tenant
            skip: Registros a saltar
            limit: Máximo de registros
            
        Returns:
            Lista de usuarios
        """
        return self.db.query(Usuario).filter(
            Usuario.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()
    
    def get_active_users(self, tenant_id: uuid.UUID) -> List[Usuario]:
        """
        Obtiene usuarios activos de un tenant
        
        Args:
            tenant_id: ID del tenant
            
        Returns:
            Lista de usuarios activos
        """
        return self.db.query(Usuario).filter(
            and_(
                Usuario.tenant_id == tenant_id,
                Usuario.activo == True,
                Usuario.estado == "active"
            )
        ).all()
    
    def update_last_access(self, user_id: uuid.UUID) -> Usuario:
        """
        Actualiza la fecha del último acceso
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Usuario actualizado
        """
        usuario = self.get(user_id)
        if usuario:
            usuario.ultimo_acceso = get_mexico_time_naive()
            self.db.commit()
            self.db.refresh(usuario)
        
        return usuario
    
    def update_password(self, user_id: uuid.UUID, new_password_hash: str) -> Usuario:
        """
        Actualiza el password del usuario (para bcrypt)
        
        Args:
            user_id: ID del usuario
            new_password_hash: Nuevo hash bcrypt
            
        Returns:
            Usuario actualizado
        """
        usuario = self.get(user_id)
        if usuario:
            usuario.password_hash = new_password_hash
            usuario.fecha_ultimo_cambio_password = get_mexico_time_naive()
            usuario.updated_at = get_mexico_time_naive()
            self.db.commit()
            self.db.refresh(usuario)
        
        return usuario
    
    def verify_email(self, user_id: uuid.UUID) -> Usuario:
        """
        Marca el email como verificado
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Usuario actualizado
        """
        usuario = self.get(user_id)
        if usuario:
            usuario.email_verificado = True
            usuario.fecha_verificacion_email = get_mexico_time_naive()
            usuario.updated_at = get_mexico_time_naive()
            self.db.commit()
            self.db.refresh(usuario)
        
        return usuario
    
    def email_exists(self, email: str) -> bool:
        """
        Verifica si un email ya existe
        
        Args:
            email: Email a verificar
            
        Returns:
            True si existe
        """
        return self.db.query(Usuario).filter(
            Usuario.email == email.lower()
        ).first() is not None
    
    def email_exists_in_tenant(self, email: str, tenant_id: uuid.UUID) -> bool:
        """
        Verifica si un email existe en un tenant específico
        
        Args:
            email: Email a verificar
            tenant_id: ID del tenant
            
        Returns:
            True si existe
        """
        return self.db.query(Usuario).filter(
            and_(
                Usuario.email == email.lower(),
                Usuario.tenant_id == tenant_id
            )
        ).first() is not None

