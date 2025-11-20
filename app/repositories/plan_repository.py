"""
Repositorio para Plan con gestión correcta de sesiones
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.models.plan import Plan
from app.repositories.base_repository import BaseRepository
from app.interfaces.plan_repository_interface import IPlanRepository


class PlanRepository(BaseRepository, IPlanRepository):
    """Repositorio para operaciones de Plan"""
    
    def __init__(self):
        super().__init__(Plan)
    
    def get_active_plans(self, session: Session) -> List[Plan]:
        """
        Obtiene planes activos
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Lista de planes activos
        """
        try:
            return session.query(Plan).filter(Plan.activo == True).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo planes activos: {e}")
            return []
    
