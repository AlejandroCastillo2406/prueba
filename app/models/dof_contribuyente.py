"""
Modelo para contribuyentes extraídos de artículos del DOF 69-B
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class DOFContribuyente(Base):
    """
    Tabla para almacenar contribuyentes extraídos de artículos del DOF
    relacionados con el artículo 69-B
    """
    __tablename__ = "dof_contribuyentes"
    __table_args__ = (
        UniqueConstraint('rfc', 'dof_articulo_id', name='uix_rfc_articulo'),
        Index('idx_dof_contrib_rfc', 'rfc'),
        Index('idx_dof_contrib_situacion', 'situacion_contribuyente'),
        Index('idx_dof_contrib_articulo', 'dof_articulo_id'),
        {"schema": "test"}
    )
    
    # Clave primaria
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con el artículo
    dof_articulo_id = Column(Integer, ForeignKey("test.dof_articulos.id"), nullable=False, index=True)
    
    # Datos del contribuyente
    rfc = Column(String(13), nullable=False, index=True, comment="RFC del contribuyente")
    razon_social = Column(String(500), nullable=False, comment="Razón social del contribuyente")
    situacion_contribuyente = Column(String(100), nullable=False, index=True, comment="Situación: Presunto, Desvirtuado, Definitivo, Sentencia favorable")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

