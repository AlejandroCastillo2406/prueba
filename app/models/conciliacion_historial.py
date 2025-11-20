from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ConciliacionHistorial(Base):
    __tablename__ = "conciliacion_historial"
    __table_args__ = (
        Index('idx_conciliacion_historial_tenant_fecha', 'tenant_id', 'fecha_conciliacion'),
        Index('idx_conciliacion_historial_tenant_fecha_duracion', 'tenant_id', 'fecha_conciliacion', 'duracion_ms'),
        {"schema": "test"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("test.tenants.id"), nullable=False)
    fecha_conciliacion = Column(DateTime, nullable=False, default=datetime.utcnow)
    tipo_conciliacion = Column(String(20), nullable=False)  # "Manual" o "Excedentes - Pago"
    version_sat = Column(String(50), nullable=True)  # Versión del SAT utilizada
    rfcs_procesados = Column(Integer, nullable=False, default=0)
    coincidencias = Column(Integer, nullable=False, default=0)
    estado = Column(String(20), nullable=False, default="completado")  # "completado", "error", "en_proceso"
    duracion_ms = Column(Integer, nullable=False, default=0)
    
    # Relación con tenant
    tenant = relationship("Tenant", back_populates="conciliaciones_historial")
    
    def __repr__(self):
        return f"<ConciliacionHistorial(id={self.id}, tenant_id={self.tenant_id}, fecha={self.fecha_conciliacion}, tipo={self.tipo_conciliacion})>"
