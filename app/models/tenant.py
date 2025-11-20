"""
Modelo de Tenant (Empresa)
Representa a las empresas/contribuyentes que usan la API
"""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import uuid


class Tenant(Base):
    """
    Modelo de Tenant para gestión de clientes de la API
    """
    __tablename__ = "tenants"
    __table_args__ = {"schema": "test"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Información de la empresa
    nombre_comercial = Column(String(255), nullable=False, comment="Nombre comercial de la empresa")
    razon_social = Column(String(500), nullable=False, comment="Razón social completa")
    rfc = Column(String(13), unique=True, nullable=False, index=True, comment="RFC de la empresa en texto plano")
    
    # Plan de suscripción
    plan_id = Column(Integer, ForeignKey("test.planes.id"), nullable=False, comment="ID del plan de suscripción")
    
    # Seguridad y autenticación
    api_key = Column(String(64), unique=True, index=True, nullable=False, comment="API Key única para autenticación")
    
    # Estado
    estado = Column(String(20), nullable=False, default="active", comment="Estado del tenant: active, suspended, trial, cancelled")
    fecha_inicio_plan = Column(DateTime, default=datetime.utcnow, comment="Fecha de inicio del plan actual")
    fecha_fin_plan = Column(DateTime, comment="Fecha de fin del plan actual")
    
    # Auditoría
    activo = Column(Boolean, default=True, nullable=False, comment="Indica si el tenant está activo")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), comment="Usuario que creó el tenant")
    updated_by = Column(UUID(as_uuid=True), comment="Usuario que actualizó el tenant")
    
    # Relaciones
    plan = relationship("Plan", back_populates="tenants")
    usuarios = relationship("Usuario", back_populates="tenant")
    proveedores = relationship("TenantProveedor", back_populates="tenant")
    grupos = relationship("Grupo", back_populates="tenant")
    conciliaciones_historial = relationship("ConciliacionHistorial", back_populates="tenant")
    ordenes_pago = relationship("OrdenPagoExcedente", back_populates="tenant")
    
    def __repr__(self):
        return f"<Tenant(id='{self.id}', nombre='{self.nombre_comercial}', plan_id={self.plan_id})>"
    
    def can_add_proveedor(self) -> bool:
        """
        Verifica si el tenant puede agregar más proveedores según su plan
        
        Returns:
            True si puede agregar proveedores, False si ha alcanzado el límite
        """
        if not self.plan:
            return False
        return self.plan.puede_agregar_proveedor(self.get_proveedores_count())
    
    def get_proveedores_count(self) -> int:
        """
        Obtiene la cantidad actual de proveedores del tenant
        
        Returns:
            Cantidad de proveedores
        """
        return len(self.proveedores) if self.proveedores else 0
    
    def get_usage_percentage(self) -> float:
        """
        Obtiene el porcentaje de uso de proveedores
        
        Returns:
            Porcentaje de uso (0.0 a 100.0)
        """
        if not self.plan or self.plan.es_ilimitado:
            return 0.0
        
        if self.plan.limite_proveedores == 0:
            return 0.0
            
        return (self.get_proveedores_count() / self.plan.limite_proveedores) * 100.0
    
    def is_near_limit(self, threshold: float = 90.0) -> bool:
        """
        Verifica si está cerca del límite de proveedores
        
        Args:
            threshold: Umbral de porcentaje (default: 90%)
            
        Returns:
            True si está cerca del límite
        """
        return self.get_usage_percentage() >= threshold
