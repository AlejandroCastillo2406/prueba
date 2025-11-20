"""
Modelo para relación entre tenants y proveedores
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class TenantProveedor(Base):
    """
    Tabla de relación entre tenants y proveedores.
    Solo almacena la relación sin duplicar datos del SAT.
    """
    __tablename__ = "tenant_proveedores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("test.tenants.id"), nullable=False, index=True)
    rfc = Column(String(13), nullable=False, index=True)  # RFC del proveedor (12 o 13 caracteres)
    razon_social = Column(String(500), nullable=True, comment="Razón social del proveedor (del archivo)")
    activo = Column(Boolean, default=True, nullable=False, index=True, comment="Indica si el RFC está activo")
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("test.grupos.id"), nullable=True, index=True, comment="ID del grupo al que pertenece el RFC")
    fecha_inicio = Column(DateTime, nullable=True, comment="Fecha de inicio del proveedor")
    fecha_baja = Column(DateTime, nullable=True, comment="Fecha de baja del proveedor")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    tenant = relationship("Tenant", back_populates="proveedores")
    grupo_rel = relationship("Grupo", back_populates="proveedores")
    
    # Índices y restricciones
    __table_args__ = (
        Index('ix_tenant_proveedores_tenant_rfc', 'tenant_id', 'rfc'),
        Index('ix_tenant_proveedores_tenant_activo', 'tenant_id', 'activo'),
        Index('ix_tenant_proveedores_tenant_grupo', 'tenant_id', 'grupo_id'),
        Index('ix_tenant_proveedores_activo_created', 'tenant_id', 'activo', 'created_at'),  # Para excedentes
        UniqueConstraint('tenant_id', 'rfc', name='uq_tenant_proveedor'),
        {"schema": "test"}
    )
    
    def __repr__(self):
        return f"<TenantProveedor(tenant_id={self.tenant_id}, rfc={self.rfc}, activo={self.activo})>"
