"""
Modelo para órdenes de pago de RFCs excedentes
"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Numeric, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.core.database import Base


class OrdenPagoExcedente(Base):
    """
    Tabla para gestionar órdenes de pago de RFCs excedentes
    Cada orden representa un pago a Stripe por N RFCs específicos
    """
    __tablename__ = "ordenes_pago_excedentes"
    __table_args__ = {"schema": "test"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("test.tenants.id"), nullable=False, index=True)
    
    # RFCs seleccionados
    rfcs = Column(ARRAY(String), nullable=False)
    cantidad_rfcs = Column(Integer, nullable=False)
    monto_total = Column(Numeric(10, 2), nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False, default=10.00)
    
    # Stripe
    stripe_payment_intent_id = Column(String(255), unique=True, index=True)
    stripe_checkout_session_id = Column(String(255), unique=True, index=True)
    stripe_customer_id = Column(String(255))
    
    # Estado
    estado = Column(String(50), nullable=False, default="pendiente", index=True)
    # Estados: 'pendiente', 'pagado', 'cancelado', 'expirado', 'fallido'
    
    # Conciliación
    conciliacion_id = Column(UUID(as_uuid=True), ForeignKey("test.conciliacion_historial.id"))
    conciliado = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    pagado_at = Column(DateTime)
    expira_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    tenant = relationship("Tenant", back_populates="ordenes_pago")
    conciliacion = relationship("ConciliacionHistorial")
    
    def __repr__(self):
        return f"<OrdenPagoExcedente(id={self.id}, tenant_id={self.tenant_id}, estado={self.estado}, rfcs={len(self.rfcs)})>"
    
    @property
    def esta_expirada(self) -> bool:
        """Verifica si la orden ha expirado"""
        return datetime.utcnow() > self.expira_at and self.estado == "pendiente"
    
    @property
    def puede_conciliar(self) -> bool:
        """Verifica si la orden puede ser conciliada"""
        return self.estado == "pagado" and not self.conciliado

