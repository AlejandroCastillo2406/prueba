"""
Modelo de base de datos para proveedores del SAT
"""
from sqlalchemy import Column, Integer, String, DateTime, Index
from datetime import datetime
from app.core.database import Base


class Proveedor(Base):
    """
    Tabla para almacenar proveedores de la lista del SAT (Art. 69-B)
    Contiene información actualizada del CSV del SAT
    """
    __tablename__ = "proveedores"
    
    # Clave primaria
    id = Column(Integer, primary_key=True, index=True)
    
    # RFC en texto plano (normalizado)
    rfc = Column(String(13), unique=True, index=True, nullable=False)
    
    # Datos del proveedor del SAT
    razon_social = Column(String(500), nullable=False)  # Nombre del Contribuyente
    situacion_contribuyente = Column(String(50), index=True, nullable=False)  # Definitivo, Desvirtuado, Sentencia Favorable
    fecha_lista = Column(DateTime, nullable=False)  # Fecha de la lista del SAT
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Índices compuestos para búsquedas frecuentes
    __table_args__ = (
        Index('idx_situacion_fecha', 'situacion_contribuyente', 'fecha_actualizacion'),
        {"schema": "test"}
    )

