"""
Modelo para artículos del DOF relacionados con el artículo 69-B
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class DOFArticulo(Base):
    """
    Tabla para almacenar artículos del Diario Oficial de la Federación
    relacionados con el artículo 69-B del Código Fiscal de la Federación
    """
    __tablename__ = "dof_articulos"
    __table_args__ = (
        UniqueConstraint('numero_oficio', 'fecha_publicacion', name='uix_oficio_fecha'),
        Index('idx_dof_fecha_publicacion', 'fecha_publicacion'),
        Index('idx_dof_numero_oficio', 'numero_oficio'),
        Index('idx_dof_tipo_lista', 'tipo_lista'),
        {"schema": "test"}
    )
    
    # Clave primaria
    id = Column(Integer, primary_key=True, index=True)
    
    # Información del artículo
    numero_oficio = Column(String(100), nullable=False, index=True, comment="Número de oficio (ej: 500-05-2025-20369)")
    fecha_publicacion = Column(DateTime, nullable=False, index=True, comment="Fecha de publicación en el DOF")
    titulo = Column(Text, nullable=False, comment="Título completo del artículo")
    tipo_lista = Column(String(50), nullable=False, index=True, comment="Tipo: presuncion, desvirtuados, definitivo, sentencia_favorable")
    url_pdf = Column(String(500), nullable=True, comment="URL del PDF del artículo")
    
    # Estadísticas del archivo
    total_rfcs = Column(Integer, default=0, comment="Total de RFCs en el artículo")
    procesado = Column(Integer, default=0, comment="0=pendiente, 1=procesado exitosamente, 2=error")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    error_mensaje = Column(Text, nullable=True, comment="Mensaje de error si falló el procesamiento")

