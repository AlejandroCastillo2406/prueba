"""
Modelo para almacenar los detalles/resultados de cada conciliación
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ConciliacionDetalle(Base):
    """
    Tabla para almacenar los resultados individuales de cada conciliación
    Guarda cada RFC conciliado con su estado definitivo
    """
    __tablename__ = "resultado_conciliaciones"
    __table_args__ = {"schema": "test"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conciliacion_id = Column(UUID(as_uuid=True), ForeignKey("test.conciliacion_historial.id"), nullable=False, index=True)
    rfc = Column(String(13), nullable=False, index=True)
    estado = Column(String(50), nullable=False)  # Definitivo, Desvirtuado, Sentencia Favorable, No encontrado
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relación con conciliacion_historial
    conciliacion = relationship("ConciliacionHistorial", backref="detalles")
    
    def __repr__(self):
        return f"<ConciliacionDetalle(id={self.id}, rfc={self.rfc}, estado={self.estado})>"

