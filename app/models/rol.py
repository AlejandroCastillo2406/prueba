"""
Modelo de Rol
Define los roles disponibles en el sistema
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import uuid


class Rol(Base):
    """
    Modelo de Rol para gestión de permisos
    """
    __tablename__ = "roles"
    __table_args__ = {"schema": "test"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Información del rol
    nombre = Column(String(50), unique=True, nullable=False, index=True, comment="Nombre del rol (ej: owner, admin, editor)")
    descripcion = Column(String(255), comment="Descripción del rol")
    nivel = Column(Integer, nullable=False, default=0, comment="Nivel de jerarquía (0=owner, 1=admin, 2=editor, 3=viewer)")
    
    # Permisos
    permisos = Column(JSON, nullable=False, default=dict, comment="Permisos del rol en formato JSON")
    
    # Estado
    es_sistema = Column(Boolean, default=True, comment="Si es un rol del sistema (no se puede eliminar)")
    activo = Column(Boolean, default=True, nullable=False)
    
    # Auditoría
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    usuarios = relationship("Usuario", back_populates="rol")
    
    def __repr__(self):
        return f"<Rol(nombre='{self.nombre}', nivel={self.nivel})>"
    
    def tiene_permiso(self, permiso: str) -> bool:
        """
        Verifica si el rol tiene un permiso específico
        
        Args:
            permiso: Nombre del permiso a verificar
            
        Returns:
            True si tiene el permiso
        """
        if not self.permisos:
            return False
        return self.permisos.get(permiso, False)
    
    def es_owner(self) -> bool:
        """Verifica si es el rol de owner"""
        return self.nivel == 0 or self.nombre == "owner"
    
    def es_admin(self) -> bool:
        """Verifica si es admin o superior"""
        return self.nivel <= 1
    
    def puede_invitar_usuarios(self) -> bool:
        """Verifica si puede invitar usuarios"""
        return self.tiene_permiso("invitar_usuarios") or self.es_admin()

