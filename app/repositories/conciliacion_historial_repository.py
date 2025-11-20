from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.conciliacion_historial import ConciliacionHistorial
from app.repositories.base_repository import BaseRepository
from app.interfaces.conciliacion_historial_repository_interface import IConciliacionHistorialRepository
from app.core.timezone import get_mexico_time_naive


class ConciliacionHistorialRepository(BaseRepository, IConciliacionHistorialRepository):
    """
    Repositorio para gestión del historial de conciliaciones
    """
    
    def __init__(self):
        super().__init__(ConciliacionHistorial)
    
    def create_historial(self, session: Session, tenant_id: UUID, tipo_conciliacion: str, 
                        version_sat: Optional[str], rfcs_procesados: int, coincidencias: int,
                        fecha_conciliacion: Optional[datetime] = None) -> ConciliacionHistorial:
        """
        Crea un nuevo registro en el historial de conciliaciones
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            tipo_conciliacion: Tipo de conciliación ("Automatica" o "Manual")
            version_sat: Versión del SAT utilizada
            rfcs_procesados: Cantidad de RFCs procesados
            coincidencias: Cantidad de coincidencias encontradas
            fecha_conciliacion: Fecha de conciliación (si no se proporciona, usa la hora actual de México)
            
        Returns:
            Registro creado en el historial
        """
        try:
            # Si no se proporciona fecha, usar hora de México
            if fecha_conciliacion is None:
                fecha_conciliacion = get_mexico_time_naive()
            
            historial = ConciliacionHistorial(
                tenant_id=tenant_id,
                tipo_conciliacion=tipo_conciliacion,
                version_sat=version_sat,
                rfcs_procesados=rfcs_procesados,
                coincidencias=coincidencias,
                estado="completado",
                fecha_conciliacion=fecha_conciliacion
            )
            
            session.add(historial)
            # No hacer flush aquí, se hará cuando sea necesario (al crear detalles)
            # El ID se generará automáticamente al hacer flush posteriormente
            
            return historial
            
        except Exception as e:
            session.rollback()
            raise e
    
    def get_historial_by_tenant(self, session: Session, tenant_id: UUID, 
                               limit: int = 10) -> List[ConciliacionHistorial]:
        """
        Obtiene el historial de conciliaciones de un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            limit: Límite de registros a obtener
            
        Returns:
            Lista de registros del historial
        """
        try:
            return session.query(ConciliacionHistorial)\
                .filter(ConciliacionHistorial.tenant_id == tenant_id)\
                .order_by(desc(ConciliacionHistorial.fecha_conciliacion))\
                .limit(limit)\
                .all()
                
        except Exception as e:
            raise e
    
    def get_ultima_conciliacion(self, session: Session, tenant_id: UUID) -> Optional[ConciliacionHistorial]:
        """
        Obtiene la última conciliación realizada por un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Último registro de conciliación o None
        """
        try:
            return session.query(ConciliacionHistorial)\
                .filter(ConciliacionHistorial.tenant_id == tenant_id)\
                .order_by(desc(ConciliacionHistorial.fecha_conciliacion))\
                .first()
                
        except Exception as e:
            raise e

