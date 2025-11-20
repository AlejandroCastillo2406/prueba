"""
Repositorio para TenantProveedor con gestión correcta de sesiones
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger
from sqlalchemy import func, case, cast, Date, nullslast

from app.models.proveedor import Proveedor
from app.models.grupo import Grupo
from app.models.tenant_proveedor import TenantProveedor
from app.repositories.base_repository import BaseRepository
from app.interfaces.tenant_proveedor_repository_interface import ITenantProveedorRepository


class TenantProveedorRepository(BaseRepository, ITenantProveedorRepository):
    """Repositorio para operaciones de TenantProveedor"""
    
    def __init__(self):
        super().__init__(TenantProveedor)
    
    def get_by_tenant_within_limit(self, session: Session, tenant_id: UUID, limite: int) -> List[TenantProveedor]:
        """
        Obtiene proveedores de un tenant dentro del límite del plan (ordenados por fecha de agregado)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            limite: Límite de RFCs del plan
            
        Returns:
            Lista de relaciones tenant-proveedor (solo las primeras N, ordenadas por created_at)
        """
        try:
            return session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id
            ).order_by(
                TenantProveedor.created_at.asc()  # Del más viejo al más nuevo
            ).limit(limite).all()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedores del tenant {tenant_id} dentro del límite {limite}: {e}")
            return []
    
    def get_by_tenant_excedentes(self, session: Session, tenant_id: UUID, limite: int) -> List[TenantProveedor]:
        """
        Obtiene proveedores EXCEDENTES ACTIVOS de un tenant (fuera del límite del plan)
        
        El límite se aplica sobre los RFCs ACTIVOS ordenados por fecha.
        Los primeros N RFCs activos están dentro del plan.
        Los RFCs activos restantes son los excedentes.
        
        Ejemplo: Si límite=3 y hay RFC1(activo), RFC2(inactivo), RFC3(activo), RFC4(activo), RFC5(activo)
        - RFCs dentro del plan: RFC1, RFC3, RFC4 (primeros 3 activos)
        - Excedentes: RFC5 (siguiente activo después de los primeros 3)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            limite: Límite de RFCs ACTIVOS del plan
            
        Returns:
            Lista de relaciones tenant-proveedor ACTIVAS que exceden el límite
        """
        try:
            from sqlalchemy.orm import load_only
            
            return session.query(TenantProveedor).options(
                load_only(TenantProveedor.rfc)
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True  # Solo RFCs activos
            ).order_by(
                TenantProveedor.created_at.asc()  # Del más viejo al más nuevo
            ).offset(limite).all()  # Los primeros N activos están dentro del plan, los demás son excedentes
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedores excedentes del tenant {tenant_id}: {e}")
            return []
    
    def get_by_tenant_and_rfc(self, session: Session, tenant_id: UUID, rfc: str) -> Optional[TenantProveedor]:
        """
        Obtiene relación por tenant y RFC
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor
            
        Returns:
            Relación si existe, None si no
        """
        try:
            rfc_norm = rfc.upper().strip()
            return session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.rfc == rfc_norm
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo relación tenant-proveedor: {e}")
            return None
    
    def delete_by_tenant_and_rfc(self, session: Session, tenant_id: UUID, rfc: str) -> bool:
        """
        Elimina relación por tenant y RFC
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor
            
        Returns:
            True si exitoso, False si error
        """
        try:
            rfc_norm = rfc.upper().strip()
            relation = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.rfc == rfc_norm
            ).first()
            
            if not relation:
                return False
            
            session.delete(relation)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error eliminando relación tenant-proveedor: {e}")
            session.rollback()
            return False
    
    def get_tenant_proveedores_count(self, session: Session, tenant_id: UUID) -> int:
        """
        Obtiene cantidad de proveedores de un tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Cantidad de proveedores
        """
        try:
            return session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id
            ).count()
        except SQLAlchemyError as e:
            logger.error(f"Error contando proveedores del tenant {tenant_id}: {e}")
            return 0
    
    def create_relation(self, session: Session, tenant_id: UUID, rfc: str) -> Optional[TenantProveedor]:
        """
        Crea una nueva relación tenant-proveedor
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor
            
        Returns:
            Relación creada si exitoso, None si error
        """
        try:
            rfc_norm = rfc.upper().strip()
            logger.info(f"Creando relación: tenant_id={tenant_id}, rfc={rfc_norm}")
            
            relation = TenantProveedor(
                tenant_id=tenant_id,
                rfc=rfc_norm,
                activo=True,  # Por defecto activo
                grupo_id=None    # Sin grupo por defecto
            )
            session.add(relation)
            session.commit()
            session.refresh(relation)
            
            logger.info(f"Relación creada exitosamente: {relation.id}")
            return relation
        except SQLAlchemyError as e:
            logger.error(f"Error creando relación tenant-proveedor: {e}")
            logger.error(f"Tipo de error SQLAlchemy: {type(e).__name__}")
            session.rollback()
            return None
    
    def get_by_tenant_and_rfcs_batch(self, session: Session, tenant_id: UUID, rfcs: List[str]) -> Dict[str, TenantProveedor]:
        """
        Obtiene múltiples relaciones por tenant y RFCs 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfcs: Lista de RFCs a consultar
            
        Returns:
            Diccionario con RFC como clave y TenantProveedor como valor
        """
        try:
            if not rfcs:
                return {}
            
            rfcs_norm = [rfc.upper().strip() for rfc in rfcs]
            relaciones = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.rfc.in_(rfcs_norm)
            ).all()
            
            # Construir diccionario de forma eficiente
            return {rel.rfc: rel for rel in relaciones}
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo relaciones batch: {e}")
            return {}
    
    def create_relations_batch(self, session: Session, tenant_id: UUID, proveedores: List[Dict[str, Any]]) -> List[TenantProveedor]:
        """
        Crea múltiples relaciones tenant-proveedor de una vez (bulk insert)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            proveedores: Lista de diccionarios con 'rfc' y opcionalmente 'razon_social'
            
        Returns:
            Lista de relaciones creadas
        """
        try:
            relaciones = []
            for proveedor in proveedores:
                rfc = proveedor.get("rfc", "").upper().strip()
                razon_social = proveedor.get("razon_social")
                
                relacion = TenantProveedor(
                    tenant_id=tenant_id,
                    rfc=rfc,
                    razon_social=razon_social if razon_social else None,
                    activo=True,
                    grupo_id=None
                )
                relaciones.append(relacion)
            
            session.add_all(relaciones)
            session.flush()
            
            return relaciones
        except SQLAlchemyError as e:
            logger.error(f"Error creando relaciones batch: {e}")
            session.rollback()
            return []
    
    def create_relations_batch_with_status(self, session: Session, tenant_id: UUID, proveedores: List[Dict[str, Any]]) -> List[TenantProveedor]:
        """
        Crea múltiples relaciones tenant-proveedor con estado (activo/inactivo) especificado
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            proveedores: Lista de diccionarios con 'rfc', 'razon_social' (opcional) y 'activo' (opcional)
            
        Returns:
            Lista de relaciones creadas
        """
        try:
            relaciones = []
            for proveedor in proveedores:
                rfc = proveedor.get("rfc", "").upper().strip()
                razon_social = proveedor.get("razon_social")
                activo = proveedor.get("activo", True)  # Por defecto activo
                
                relacion = TenantProveedor(
                    tenant_id=tenant_id,
                    rfc=rfc,
                    razon_social=razon_social if razon_social else None,
                    activo=activo,
                    grupo_id=None
                )
                relaciones.append(relacion)
            
            session.add_all(relaciones)
            session.flush()
            
            return relaciones
        except SQLAlchemyError as e:
            logger.error(f"Error creando relaciones batch con status: {e}")
            session.rollback()
            return []
    
    def get_tenant_proveedores_with_sat_info(self, session: Session, tenant_id: UUID) -> List[Dict[str, Any]]:
        """
        Obtiene proveedores del tenant con información del SAT
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Lista de proveedores con información del SAT
        """
        try:
            from app.models.proveedor import Proveedor
            
            # Join con la tabla de proveedores para obtener información del SAT
            results = session.query(
                TenantProveedor,
                Proveedor
            ).outerjoin(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id
            ).all()
            
            proveedores = []
            for tenant_prov, sat_prov in results:
                proveedor_info = {
                    "id": str(tenant_prov.id),
                    "rfc": tenant_prov.rfc,
                    "en_sat": sat_prov is not None,
                    "estatus_sat": sat_prov.situacion_contribuyente if sat_prov else None,
                    "razon_social_sat": sat_prov.razon_social if sat_prov else None,
                    "fecha_lista_sat": sat_prov.fecha_lista if sat_prov else None,
                    "created_at": tenant_prov.created_at
                }
                proveedores.append(proveedor_info)
            
            return proveedores
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo proveedores con info SAT del tenant {tenant_id}: {e}")
            return []
    
    def update_estado_operativo(self, session: Session, tenant_id: UUID, rfc: str, activo: bool, commit: bool = False) -> Optional[TenantProveedor]:
        """
        Actualiza el estado operativo (activo/inactivo) de un RFC 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor
            activo: True para activar, False para desactivar
            commit: Si True, hace commit. Si False, solo actualiza (más rápido)
            
        Returns:
            TenantProveedor actualizado o None si no existe
        """
        try:
            rfc_norm = rfc.upper().strip()
            relation = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.rfc == rfc_norm
            ).first()
            
            if not relation:
                return None
            
            relation.activo = activo
            
            if commit:
                session.commit()
                session.refresh(relation)
            else:
                session.flush()  # Flush para que los cambios se reflejen sin commit
            
            return relation
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando estado operativo del RFC {rfc}: {e}")
            if commit:
                session.rollback()
            return None
    
    def update_grupo(self, session: Session, tenant_id: UUID, rfc: str, grupo_id: Optional[UUID], commit: bool = False) -> Optional[TenantProveedor]:
        """
        Actualiza el grupo de un RFC usando grupo_id 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor
            grupo_id: ID del grupo (None para eliminar grupo)
            commit: Si True, hace commit. Si False, solo actualiza (más rápido)
            
        Returns:
            TenantProveedor actualizado o None si no existe
        """
        try:
            rfc_norm = rfc.upper().strip()
            relation = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.rfc == rfc_norm
            ).first()
            
            if not relation:
                return None
            
            relation.grupo_id = grupo_id
            
            if commit:
                session.commit()
                session.refresh(relation)
            else:
                session.flush()  # Flush para que los cambios se reflejen sin commit
            
            return relation
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando grupo del RFC {rfc}: {e}")
            if commit:
                session.rollback()
            return None
    
    def get_count_by_estado(self, session: Session, tenant_id: UUID, activo: Optional[bool] = None) -> int:
        """
        Obtiene la cantidad de RFCs por estado operativo
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            activo: True para activos, False para inactivos, None para todos
            
        Returns:
            Cantidad de RFCs
        """
        try:
            query = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id
            )
            
            if activo is not None:
                query = query.filter(TenantProveedor.activo == activo)
            
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Error contando RFCs por estado del tenant {tenant_id}: {e}")
            return 0
    
    def get_count_con_alerta(self, session: Session, tenant_id: UUID) -> int:
        """
        Obtiene la cantidad de RFCs con alerta (estado SAT = "Definitivo")
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Cantidad de RFCs con alerta
        """
        try:
            from app.models.proveedor import Proveedor
            
            return session.query(TenantProveedor).join(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                Proveedor.situacion_contribuyente == "Definitivo"
            ).count()
        except SQLAlchemyError as e:
            logger.error(f"Error contando RFCs con alerta del tenant {tenant_id}: {e}")
            return 0
    
    def get_all_rfcs_with_details_paginado(self, session: Session, tenant_id: UUID, pagina: int = 1, por_pagina: int = 20) -> Dict[str, Any]:
        """
        Obtiene RFCs del tenant con información completa paginado
        PRIORIZA razón social de SAT sobre razón social de tenant_proveedores
        Ordenado por fecha de actualización descendente (updated_at DESC, más recientes primero)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            pagina: Número de página (empezando en 1)
            por_pagina: Registros por página
            
        Returns:
            Diccionario con lista paginada de RFCs y metadatos de paginación
        """
        try:
            # Calcular offset
            offset = (pagina - 1) * por_pagina
            
            #  Obtener total con count directo 
            total_registros = session.query(func.count(TenantProveedor.rfc)).filter(
                TenantProveedor.tenant_id == tenant_id
            ).scalar() or 0
            
            # Obtener datos paginados
            fecha_ultima_actualizacion_expr = func.coalesce(
                cast(Proveedor.fecha_actualizacion, Date),
                cast(TenantProveedor.updated_at, Date)
            )
            
            base_query = session.query(
                TenantProveedor.rfc,
                TenantProveedor.updated_at,  # Necesario para ordenar por fecha de actualización
                case(
                    (TenantProveedor.activo == True, 'activo'),
                    else_='inactivo'
                ).label('estado_operativo'),
                func.coalesce(Proveedor.razon_social, TenantProveedor.razon_social).label('razon_social'),
                Proveedor.situacion_contribuyente.label('estado_sat'),
                Grupo.nombre.label('grupo'),
                fecha_ultima_actualizacion_expr.label('fecha_ultima_actualizacion')
            ).outerjoin(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).outerjoin(
                Grupo, TenantProveedor.grupo_id == Grupo.id
            ).filter(
                TenantProveedor.tenant_id == tenant_id
            )
            
            results = base_query.order_by(
                nullslast(fecha_ultima_actualizacion_expr.desc()),
                TenantProveedor.rfc.asc()
            ).offset(offset).limit(por_pagina).all()
            
            # Construir lista de diccionarios
            rfcs_list = [
                {
                    "rfc": row.rfc,
                    "estado_operativo": row.estado_operativo,
                    "razon_social": row.razon_social,
                    "estado_sat": row.estado_sat,
                    "grupo": row.grupo,
                    "fecha_ultima_actualizacion": row.fecha_ultima_actualizacion
                }
                for row in results
            ]
            
            # Calcular total de páginas
            total_paginas = (total_registros + por_pagina - 1) // por_pagina if total_registros > 0 else 0
            
            return {
                "rfcs": rfcs_list,
                "total": total_registros,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": total_paginas
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo RFCs paginados del tenant {tenant_id}: {e}")
            return {
                "rfcs": [],
                "total": 0,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": 0
            }