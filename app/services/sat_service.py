"""
Servicio  para manejo de listas del SAT con inyección de dependencias
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.interfaces.sat_service_interface import ISATService
from app.interfaces.proveedor_repository_interface import IProveedorRepository
from app.services.sat_processor import sat_processor


class SATService(ISATService):
    """Servicio para gestionar el listado del SAT"""
    
    def __init__(self, proveedor_repository: IProveedorRepository):
        self.proveedor_repository = proveedor_repository
    
    def update_database(self, session: Session, force: bool = False) -> Dict[str, Any]:
        """
        Actualiza la base de datos con la lista del SAT
        
        Args:
            session: Sesión de base de datos
            force: Forzar actualización aunque no sea necesario (no se usa actualmente)
            
        Returns:
            Diccionario con:
            - success: True si la actualización fue exitosa, False en caso contrario
            - nueva_version: True si se detectó una nueva versión, False si ya estaba procesada
            - fecha_version: Fecha de la versión procesada (str en formato YYYY-MM-DD) o None
            - total_registros: Total de registros procesados (opcional)
        """
        try:
            logger.info("🔄 Usando procesador inteligente del SAT")
            resultado = sat_processor.process_sat_update(session)
            return resultado
        except Exception as e:
            logger.error(f"Error actualizando base de datos del SAT: {e}")
            return {
                "success": False,
                "nueva_version": False,
                "fecha_version": None,
                "total_registros": None
            }
    
    def get_proveedor_by_rfc(self, session: Session, rfc: str) -> Optional[Any]:
        """
        Busca un proveedor por RFC en la base de datos
        
        Args:
            session: Sesión de base de datos
            rfc: RFC del proveedor
            
        Returns:
            Proveedor si existe, None en caso contrario
        """
        try:
            return self.proveedor_repository.get_by_rfc(session, rfc)
        except Exception as e:
            logger.error(f"Error obteniendo proveedor por RFC {rfc}: {e}")
            return None
    
    def get_stats(self, session: Session) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la lista del SAT
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Diccionario con estadísticas
        """
        try:
            return self.proveedor_repository.get_stats(session)
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del SAT: {e}")
            return {}
    
    def search_proveedores(self, session: Session, razon_social: str, limit: int = 100) -> list:
        """
        Busca proveedores por razón social
        
        Args:
            session: Sesión de base de datos
            razon_social: Razón social a buscar
            limit: Límite de resultados
            
        Returns:
            Lista de proveedores encontrados
        """
        try:
            return self.proveedor_repository.search_by_razon_social(session, razon_social, limit)
        except Exception as e:
            logger.error(f"Error buscando proveedores por razón social: {e}")
            return []
    
    def get_proveedores_by_situacion(self, session: Session, situacion: str) -> list:
        """
        Obtiene proveedores por situación
        
        Args:
            session: Sesión de base de datos
            situacion: Situación del contribuyente
            
        Returns:
            Lista de proveedores
        """
        try:
            return self.proveedor_repository.get_by_situacion(session, situacion)
        except Exception as e:
            logger.error(f"Error obteniendo proveedores por situación {situacion}: {e}")
            return []
