"""
Repositorio para gestión de detalles de conciliación
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.conciliacion_detalle import ConciliacionDetalle
from app.repositories.base_repository import BaseRepository
from app.interfaces.conciliacion_detalle_repository_interface import IConciliacionDetalleRepository
from app.core.logging import logger


class ConciliacionDetalleRepository(BaseRepository, IConciliacionDetalleRepository):
    """Repositorio para operaciones CRUD de detalles de conciliación"""
    
    def __init__(self):
        super().__init__(ConciliacionDetalle)
    
    def create(self, session: Session, conciliacion_detalle: ConciliacionDetalle) -> ConciliacionDetalle:
        """Crea un nuevo detalle de conciliación"""
        try:
            session.add(conciliacion_detalle)
            session.commit()
            session.refresh(conciliacion_detalle)
            logger.info(f"Detalle de conciliación creado: {conciliacion_detalle.id}")
            return conciliacion_detalle
        except Exception as e:
            session.rollback()
            logger.error(f"Error al crear detalle de conciliación: {e}")
            raise
    
    def create_bulk(self, session: Session, detalles: List[ConciliacionDetalle]) -> List[ConciliacionDetalle]:
        """Crea múltiples detalles de conciliación en una sola operación (sin commit)."""
        try:
            # Convertir a diccionarios para bulk_insert_mappings (más rápido)
            detalles_dict = [
                {
                    "conciliacion_id": detalle.conciliacion_id,
                    "rfc": detalle.rfc,
                    "estado": detalle.estado
                }
                for detalle in detalles
            ]
            
            # Usa bulk_insert_mappings para máxima velocidad (bypass ORM)
            session.bulk_insert_mappings(ConciliacionDetalle, detalles_dict)
            session.flush()
            
            return detalles
        except Exception as e:
            session.rollback()
            logger.error(f"Error al crear detalles de conciliación en bulk: {e}")
            raise
    
    def get_by_conciliacion_id(self, session: Session, conciliacion_id: UUID) -> List[ConciliacionDetalle]:
        """Obtiene todos los detalles de una conciliación específica"""
        return session.query(ConciliacionDetalle).filter(
            ConciliacionDetalle.conciliacion_id == conciliacion_id
        ).all()
    
    def get_by_rfc(self, session: Session, rfc: str) -> List[ConciliacionDetalle]:
        """Obtiene todos los detalles de un RFC específico"""
        return session.query(ConciliacionDetalle).filter(
            ConciliacionDetalle.rfc == rfc.upper()
        ).order_by(ConciliacionDetalle.created_at.desc()).all()
    
    def get_by_id(self, session: Session, detalle_id: UUID) -> Optional[ConciliacionDetalle]:
        """Obtiene un detalle por su ID"""
        return session.query(ConciliacionDetalle).filter(
            ConciliacionDetalle.id == detalle_id
        ).first()
    
    def delete_by_conciliacion_id(self, session: Session, conciliacion_id: UUID) -> int:
        """Elimina todos los detalles de una conciliación"""
        try:
            deleted_count = session.query(ConciliacionDetalle).filter(
                ConciliacionDetalle.conciliacion_id == conciliacion_id
            ).delete()
            session.commit()
            logger.info(f"Eliminados {deleted_count} detalles de conciliación {conciliacion_id}")
            return deleted_count
        except Exception as e:
            session.rollback()
            logger.error(f"Error al eliminar detalles de conciliación: {e}")
            raise

