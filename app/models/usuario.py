"""
Modelo de Usuario
Representa a los usuarios del sistema con sistema de cifrado
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ARRAY, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import uuid
from typing import Optional


class Usuario(Base):
    """
    Modelo de Usuario del sistema
    
    Sistema de cifrado: SHA256(password + password_salt)
    """
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "test"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("test.tenants.id"), nullable=True, index=True, comment="ID del tenant (opcional, para multi-tenancy)")
    
    # Información personal
    email = Column(String(255), nullable=False, comment="Email del usuario")
    nombre = Column(String(255), nullable=False, comment="Nombre del usuario")
    apellidos = Column(String(255), comment="Apellidos del usuario")
    telefono = Column(String(20), comment="Teléfono del usuario")
    
    # Autenticación con bcrypt
    password_hash = Column(String(255), nullable=False, comment="Hash del password con bcrypt")
    email_verificado = Column(Boolean, default=False, comment="Si el email está verificado")
    fecha_verificacion_email = Column(DateTime, comment="Fecha de verificación del email")
    
    # Rol y permisos
    rol_id = Column(UUID(as_uuid=True), ForeignKey("test.roles.id"), nullable=True, comment="ID del rol del usuario (opcional)")
    permisos_personalizados = Column(JSON, default=dict, comment="Permisos personalizados del usuario")
    
    # Estado y acceso
    estado = Column(String(20), nullable=False, default="active", comment="Estado: active, inactive, pending, blocked")
    ultimo_acceso = Column(DateTime, comment="Fecha del último acceso")
    fecha_ultimo_cambio_password = Column(DateTime, comment="Fecha del último cambio de password")
    
    # Auditoría
    activo = Column(Boolean, default=True, nullable=False, comment="Si el usuario está activo")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), comment="Usuario que creó este usuario")
    
    # Relaciones
    tenant = relationship("Tenant", back_populates="usuarios")
    rol = relationship("Rol", back_populates="usuarios")
    
    def __repr__(self):
        return f"<Usuario(email='{self.email}', nombre='{self.nombre}', estado='{self.estado}')>"
    
    def is_active(self) -> bool:
        """
        Verifica si el usuario está activo
        
        Returns:
            True si está activo y no bloqueado
        """
        return self.activo and self.estado == "active"
    
    def get_full_name(self) -> str:
        """
        Obtiene el nombre completo del usuario
        
        Returns:
            Nombre completo
        """
        if self.apellidos:
            return f"{self.nombre} {self.apellidos}"
        return self.nombre
    
    def es_owner_del_tenant(self) -> bool:
        """
        Verifica si es owner del tenant
        
        Returns:
            True si es owner
        """
        if not self.rol:
            return False
        return self.rol.es_owner()
    
    def puede_invitar_usuarios(self) -> bool:
        """
        Verifica si puede invitar usuarios
        
        Returns:
            True si tiene permiso
        """
        if not self.rol:
            return False
        return self.rol.puede_invitar_usuarios()
    
    def tiene_permiso(self, permiso: str) -> bool:
        """
        Verifica si tiene un permiso específico
        
        Args:
            permiso: Nombre del permiso
            
        Returns:
            True si tiene el permiso
        """
        # Permisos personalizados tienen prioridad
        if permiso in self.permisos_personalizados:
            return self.permisos_personalizados[permiso]
        
        # Si no, verificar permisos del rol
        if self.rol:
            return self.rol.tiene_permiso(permiso)
        
        return False
