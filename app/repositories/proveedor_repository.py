"""
Repositorio para Proveedor con gestión correcta de sesiones
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.orm import load_only
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.proveedor import Proveedor
from app.repositories.base_repository import BaseRepository
from app.interfaces.proveedor_repository_interface import IProveedorRepository


class ProveedorRepository(BaseRepository, IProveedorRepository):
    """Repositorio para operaciones de Proveedor"""
    
    def __init__(self):
        super().__init__(Proveedor)
    
    def get_by_rfc(self, session: Session, rfc: str) -> Optional[Proveedor]:
        """
        Obtiene proveedor por RFC
        
        Args:
            session: Sesión de base de datos
            rfc: RFC del proveedor
            
        Returns:
            Proveedor si existe, None si no
        """
        try:
            rfc_norm = rfc.upper().strip()
            return session.query(Proveedor).filter(Proveedor.rfc == rfc_norm).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedor por RFC {rfc}: {e}")
            return None
    
    def get_by_rfcs_batch(self, session: Session, rfcs: List[str]) -> List[Proveedor]:
        """
        Obtiene múltiples proveedores por RFCs (consulta masiva)
        
        Args:
            session: Sesión de base de datos
            rfcs: Lista de RFCs a consultar
            
        Returns:
            Lista de proveedores encontrados
        """
        try:
            # Normalizar y deduplicar RFCs
            rfcs_norm = sorted(set(rfc.upper().strip() for rfc in rfcs))

            # Cargar solo columnas necesarias para conciliación
            return session.query(Proveedor).options(
                load_only(Proveedor.rfc, Proveedor.situacion_contribuyente)
            ).filter(
                Proveedor.rfc.in_(rfcs_norm)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedores por RFCs batch: {e}")
            return []
    
    def get_stats(self, session: Session) -> Dict[str, Any]:
        """
        Obtiene estadísticas de proveedores
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Diccionario con estadísticas
        """
        try:
            total = session.query(Proveedor).count()
            
            # Contar por situación
            definitivos = session.query(Proveedor).filter(
                Proveedor.situacion_contribuyente == 'Definitivo'
            ).count()
            
            desvirtuados = session.query(Proveedor).filter(
                Proveedor.situacion_contribuyente == 'Desvirtuado'
            ).count()
            
            presuntos = session.query(Proveedor).filter(
                Proveedor.situacion_contribuyente == 'Presunto'
            ).count()
            
            sentencias = session.query(Proveedor).filter(
                Proveedor.situacion_contribuyente == 'Sentencia Favorable'
            ).count()
            
            # Obtener fecha de última actualización
            ultimo = session.query(Proveedor).order_by(
                Proveedor.fecha_actualizacion.desc()
            ).first()
            
            return {
                'total': total,
                'definitivos': definitivos,
                'desvirtuados': desvirtuados,
                'presuntos': presuntos,
                'sentencias_favorables': sentencias,
                'ultima_actualizacion': ultimo.fecha_actualizacion if ultimo else None
            }
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo estadísticas de proveedores: {e}")
            return {}
    
    def bulk_insert(self, session: Session, proveedores_data: List[Dict[str, Any]]) -> bool:
        """
        Inserción masiva de proveedores
        
        Args:
            session: Sesión de base de datos
            proveedores_data: Lista de datos de proveedores
            
        Returns:
            True si exitoso, False si error
        """
        try:
            session.bulk_insert_mappings(Proveedor, proveedores_data)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error en inserción masiva de proveedores: {e}")
            session.rollback()
            return False
    
    def clear_all(self, session: Session) -> bool:
        """
        Limpia todos los proveedores
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            True si exitoso, False si error
        """
        try:
            session.query(Proveedor).delete()
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error limpiando proveedores: {e}")
            session.rollback()
            return False
    
    def get_by_situacion(self, session: Session, situacion: str) -> List[Proveedor]:
        """
        Obtiene proveedores por situación
        
        Args:
            session: Sesión de base de datos
            situacion: Situación del contribuyente
            
        Returns:
            Lista de proveedores
        """
        try:
            return session.query(Proveedor).filter(
                Proveedor.situacion_contribuyente == situacion
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedores por situación {situacion}: {e}")
            return []
    
    def search_by_razon_social(self, session: Session, razon_social: str, limit: int = 100) -> List[Proveedor]:
        """
        Busca proveedores por razón social
        
        Args:
            session: Sesión de base de datos
            razon_social: Razón social a buscar
            limit: Límite de resultados
            
        Returns:
            Lista de proveedores
        """
        try:
            return session.query(Proveedor).filter(
                Proveedor.razon_social.ilike(f"%{razon_social}%")
            ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error buscando proveedores por razón social: {e}")
            return []
