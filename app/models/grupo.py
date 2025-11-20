"""
Modelo para Grupos de RFCs
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class Grupo(Base):
    """
    Tabla para grupos de RFCs por tenant.
    Permite organizar RFCs en grupos personalizados.
    """
    __tablename__ = "grupos"
    __table_args__ = (
        Index('ix_grupos_tenant_nombre', 'tenant_id', 'nombre'),
        UniqueConstraint('tenant_id', 'nombre', name='uq_grupo_tenant_nombre'),
        {"schema": "test"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("test.tenants.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False, comment="Nombre del grupo")
    descripcion = Column(String(500), nullable=True, comment="Descripción del grupo")
    color = Column(String(7), nullable=True, comment="Color del grupo en formato HEX (#RRGGBB)")
    activo = Column(Boolean, default=True, nullable=False, comment="Si el grupo está activo")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    tenant = relationship("Tenant", back_populates="grupos")
    proveedores = relationship("TenantProveedor", back_populates="grupo_rel")
    
    def __repr__(self):
        return f"<Grupo(id={self.id}, tenant_id={self.tenant_id}, nombre='{self.nombre}')>"

