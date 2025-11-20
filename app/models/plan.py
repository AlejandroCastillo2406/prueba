"""
Modelo para planes de suscripción
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Plan(Base):
    """
    Modelo para planes de suscripción de los tenants
    """
    __tablename__ = "planes"
    
    # Clave primaria
    id = Column(Integer, primary_key=True, index=True)

    # Información del plan
    nombre = Column(String(100), nullable=False, index=True)
    descripcion = Column(Text)
    
    # Límites del plan
    limite_proveedores = Column(Integer, nullable=True, comment="Límite de proveedores (NULL = ilimitado)")
    limite_usuarios = Column(Integer, nullable=True, default=5, comment="Límite de usuarios (NULL = ilimitado)")
    
    # Características del plan
    conciliacion_automatica = Column(Boolean, default=True, nullable=False, comment="Si tiene conciliación automática")
    
    # Precio
    precio = Column(Numeric(10, 2), default=0.00, nullable=False)
    activo = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    tenants = relationship("Tenant", back_populates="plan")

    # Índices y esquema
    __table_args__ = (
        Index('idx_plan_activo_precio', 'activo', 'precio'),
        {"schema": "test"}
    )

    def __repr__(self):
        return f"<Plan(id={self.id}, nombre='{self.nombre}', precio={self.precio})>"

    @property
    def es_ilimitado_proveedores(self) -> bool:
        """Verifica si el plan tiene límite ilimitado de proveedores"""
        return self.limite_proveedores is None
    
    @property
    def es_ilimitado_usuarios(self) -> bool:
        """Verifica si el plan tiene límite ilimitado de usuarios"""
        return self.limite_usuarios is None
    
    @property
    def es_ilimitado(self) -> bool:
        """DEPRECATED: Usar es_ilimitado_proveedores"""
        return self.es_ilimitado_proveedores

    def puede_agregar_proveedor(self, cantidad_actual: int) -> bool:
        """
        Verifica si el tenant puede agregar más proveedores según su plan
        
        Args:
            cantidad_actual: Cantidad actual de proveedores del tenant
            
        Returns:
            True si puede agregar más proveedores
        """
        if not self.activo:
            return False
        
        if self.es_ilimitado_proveedores:
            return True
        
        return cantidad_actual < self.limite_proveedores
    
    def puede_agregar_usuario(self, cantidad_actual: int) -> bool:
        """
        Verifica si el tenant puede agregar más usuarios según su plan
        
        Args:
            cantidad_actual: Cantidad actual de usuarios del tenant
            
        Returns:
            True si puede agregar más usuarios
        """
        if not self.activo:
            return False
        
        if self.es_ilimitado_usuarios:
            return True
        
        return cantidad_actual < self.limite_usuarios
