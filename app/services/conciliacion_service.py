"""
Servicio de conciliación con inyección de dependencias
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
import time
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, load_only
from loguru import logger

from app.interfaces.conciliacion_service_interface import IConciliacionService
from app.interfaces.tenant_repository_interface import ITenantRepository
from app.interfaces.proveedor_repository_interface import IProveedorRepository
from app.interfaces.tenant_proveedor_repository_interface import ITenantProveedorRepository
from app.interfaces.conciliacion_historial_repository_interface import IConciliacionHistorialRepository
from app.interfaces.conciliacion_detalle_repository_interface import IConciliacionDetalleRepository
from app.models.tenant_proveedor import TenantProveedor
from app.models.proveedor import Proveedor
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.conciliacion_historial import ConciliacionHistorial
from app.models.conciliacion_detalle import ConciliacionDetalle
from app.models.dof_contribuyente import DOFContribuyente
from sqlalchemy import desc
from app.core.timezone import get_mexico_time_naive, formatear_fecha_es, MEXICO_TZ
from app.services.email_service import email_service
from app.services.reporte_service import ReporteService
from app.repositories.usuario_repository import UsuarioRepository
from app.models.usuario import Usuario


class ConciliacionService(IConciliacionService):
    """Servicio de conciliación con inyección de dependencias"""
    
    def __init__(
        self,
        tenant_repository: ITenantRepository,
        proveedor_repository: IProveedorRepository,
        tenant_proveedor_repository: ITenantProveedorRepository,
        conciliacion_historial_repository: IConciliacionHistorialRepository,
        conciliacion_detalle_repository: IConciliacionDetalleRepository
    ):
        self.tenant_repository = tenant_repository
        self.proveedor_repository = proveedor_repository
        self.tenant_proveedor_repository = tenant_proveedor_repository
        self.conciliacion_historial_repository = conciliacion_historial_repository
        self.conciliacion_detalle_repository = conciliacion_detalle_repository
    
    def agregar_proveedores_batch(self, session: Session, tenant_id: UUID, proveedores: List[Dict[str, Any]], limite_rfcs: int) -> List[Dict[str, Any]]:
        """
        Agrega múltiples proveedores al tenant de una vez 
        Si sobrepasa el límite de burst, agrega como INACTIVO
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            proveedores: Lista de diccionarios con 'rfc' y opcionalmente 'razon_social'
            limite_rfcs: Límite de RFCs del plan
            
        Returns:
            Lista de diccionarios con resultado de cada RFC
        """
        try:
            # Extraer RFCs normalizados y mapear razón social
            rfcs_norm = []
            razon_social_map = {}
            for proveedor in proveedores:
                rfc = proveedor.get("rfc", "").upper().strip()
                if len(rfc) in [12, 13]:
                    rfcs_norm.append(rfc)
                    if proveedor.get("razon_social"):
                        razon_social_map[rfc] = proveedor["razon_social"]
            
            if not rfcs_norm:
                return []
            
            # Verificar que el tenant existe
            tenant = self.tenant_repository.get_by_id(session, tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} no encontrado")
            
            #  Contar solo RFCs ACTIVOS (los inactivos no cuentan para el límite)
            total_activos = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True
            ).count()
            
            # Calcular límite de burst (15% extra)
            limite_burst = limite_rfcs + int(limite_rfcs * 0.15)
            
            # Obtener todas las relaciones existentes de una vez
            relaciones_existentes = self.tenant_proveedor_repository.get_by_tenant_and_rfcs_batch(
                session, tenant_id, rfcs_norm
            )
            
            # Separar RFCs existentes y nuevos
            proveedores_nuevos_activos = []
            proveedores_nuevos_inactivos = []
            resultados = []
            
            for rfc in rfcs_norm:
                # Si ya existe, retornar resultado inmediato
                if rfc in relaciones_existentes:
                    resultados.append({
                        "rfc": rfc,
                        "proveedor_id": str(relaciones_existentes[rfc].id),
                        "error": f"El RFC {rfc} ya existe"
                    })
                else:
                    # Si está dentro del límite de burst, agregar como ACTIVO
                    if total_activos < limite_burst:
                        proveedores_nuevos_activos.append({
                            "rfc": rfc,
                            "razon_social": razon_social_map.get(rfc),
                            "activo": True
                        })
                        total_activos += 1
                    else:
                        # Si sobrepasa el burst, agregar como INACTIVO
                        proveedores_nuevos_inactivos.append({
                            "rfc": rfc,
                            "razon_social": razon_social_map.get(rfc),
                            "activo": False
                        })
            
            # Crear todas las relaciones nuevas de una vez 
            proveedores_nuevos = proveedores_nuevos_activos + proveedores_nuevos_inactivos
            
            if proveedores_nuevos:
                relaciones_creadas = self.tenant_proveedor_repository.create_relations_batch_with_status(
                    session, tenant_id, proveedores_nuevos
                )
                
                # Mapear relaciones creadas por RFC
                relaciones_dict = {rel.rfc: rel for rel in relaciones_creadas}
                
                # Agregar resultados de RFCs nuevos
                for proveedor in proveedores_nuevos:
                    rfc = proveedor["rfc"]
                    if rfc in relaciones_dict:
                        error_msg = None
                        if not proveedor.get("activo", True):
                            error_msg = "RFC agregado como INACTIVO (límite de burst alcanzado)"
                        
                        resultados.append({
                            "rfc": rfc,
                            "proveedor_id": str(relaciones_dict[rfc].id),
                            "error": error_msg
                        })
                    else:
                        resultados.append({
                            "rfc": rfc,
                            "proveedor_id": "",
                            "error": "Error creando relación"
                        })
            
            # Ordenar resultados según el orden original de los RFCs
            resultados_dict = {r["rfc"]: r for r in resultados}
            resultados_ordenados = [resultados_dict.get(rfc, {
                "rfc": rfc,
                "proveedor_id": "",
                "error": "RFC no procesado"
            }) for rfc in rfcs_norm]
            
            return resultados_ordenados
            
        except Exception as e:
            logger.error(f"Error agregando proveedores batch para tenant {tenant_id}: {e}")
            raise
    
    def agregar_proveedores_batch_con_datos(self, session: Session, tenant_id: UUID, datos: List[Dict[str, Any]], limite_rfcs: int) -> List[Dict[str, Any]]:
        """
        Agrega múltiples proveedores con datos completos desde archivo
        Si sobrepasa el límite de burst, agrega como INACTIVO
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            datos: Lista de diccionarios con {rfc, razon_social, fecha_inicio, fecha_baja}
            limite_rfcs: Límite de RFCs del plan
            
        Returns:
            Lista de diccionarios con resultado de cada RFC
        """
        try:
            # Verificar que el tenant existe
            tenant = self.tenant_repository.get_by_id(session, tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} no encontrado")
            
            #  Contar solo RFCs ACTIVOS (los inactivos no cuentan para el límite)
            total_activos = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True
            ).count()
            
            # Calcular límite de burst (15% extra)
            limite_burst = limite_rfcs + int(limite_rfcs * 0.15)
            
            # Extraer RFCs para verificar existentes
            rfcs = [dato['rfc'] for dato in datos]
            relaciones_existentes = self.tenant_proveedor_repository.get_by_tenant_and_rfcs_batch(
                session, tenant_id, rfcs
            )
            
            # Procesar cada RFC con sus datos
            resultados = []
            rfcs_a_crear = []
            
            for dato in datos:
                rfc = dato['rfc']
                
                # Si ya existe, actualizar datos
                if rfc in relaciones_existentes:
                    relacion = relaciones_existentes[rfc]
                    # Actualizar datos si vienen del archivo
                    if dato.get('razon_social'):
                        relacion.razon_social = dato['razon_social']
                    if dato.get('fecha_inicio'):
                        relacion.fecha_inicio = dato['fecha_inicio']
                    if dato.get('fecha_baja'):
                        relacion.fecha_baja = dato['fecha_baja']
                    
                    resultados.append({
                        "rfc": rfc,
                        "proveedor_id": str(relacion.id),
                        "error": f"El RFC {rfc} ya existe"
                    })
                else:
                    # Determinar si agregar como activo o inactivo
                    if total_activos < limite_burst:
                        dato['activo'] = True
                        total_activos += 1
                    else:
                        dato['activo'] = False
                    
                    rfcs_a_crear.append(dato)
            
            # Crear nuevas relaciones con todos los datos
            if rfcs_a_crear:
                for dato in rfcs_a_crear:
                    try:
                        nueva_relacion = TenantProveedor(
                            tenant_id=tenant_id,
                            rfc=dato['rfc'],
                            razon_social=dato.get('razon_social'),
                            fecha_inicio=dato.get('fecha_inicio'),
                            fecha_baja=dato.get('fecha_baja'),
                            activo=dato.get('activo', True),
                            grupo_id=None
                        )
                        session.add(nueva_relacion)
                        session.flush()  # Para obtener el ID
                        
                        error_msg = None
                        if not dato.get('activo', True):
                            error_msg = "RFC agregado como INACTIVO (límite de burst alcanzado)"
                        
                        resultados.append({
                            "rfc": dato['rfc'],
                            "proveedor_id": str(nueva_relacion.id),
                            "error": error_msg
                        })
                    except Exception as e:
                        logger.error(f"Error creando relación para RFC {dato['rfc']}: {e}")
                        resultados.append({
                            "rfc": dato['rfc'],
                            "proveedor_id": "",
                            "error": f"Error creando relación: {str(e)}"
                        })
            
            # Commit de los cambios
            session.commit()
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error agregando proveedores con datos para tenant {tenant_id}: {e}")
            session.rollback()
            raise
    
    def realizar_conciliacion(self, session: Session, tenant_id: UUID, tipo_conciliacion: str = "Manual") -> Dict[str, Any]:
        """
        Realiza la conciliación de todos los proveedores del tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            tipo_conciliacion: Tipo de conciliación ("Automatica" o "Manual")
            
        Returns:
            Diccionario con estadísticas de la conciliación
        """
        try:
            
            
            start_time = time.time()
            timings = {}
            
            # Obtener solo limite_proveedores del plan 
            step_start = time.time()
            
            
            # Solo cargar el campo necesario del plan
            tenant = session.query(Tenant).options(
                joinedload(Tenant.plan).load_only(Plan.limite_proveedores)
            ).filter(Tenant.id == tenant_id).first()
            
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} no encontrado")
            
            limite_rfcs = tenant.plan.limite_proveedores if tenant.plan else 0
            timings['get_tenant_and_plan'] = round((time.time() - step_start) * 1000, 2)
            
            # Obtener RFCs tenant + proveedores SAT 
            step_start = time.time()
            
            # Query: JOIN entre tenant_proveedor y proveedor
            # Solo incluir proveedores activos, ordenados por fecha (más viejos primero)
            resultados = session.query(
                TenantProveedor.rfc,
                Proveedor.situacion_contribuyente
            ).outerjoin(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True
            ).order_by(
                TenantProveedor.created_at.asc()
            ).limit(limite_rfcs).all()
            
            total_proveedores = len(resultados)
            
            # Crear diccionario de los resultados del JOIN
            # Si no hay proveedor en SAT, situacion_contribuyente será None
            sat_dict = {}
            rfcs_tenant = []
            for rfc, situacion in resultados:
                rfcs_tenant.append(rfc)
                sat_dict[rfc] = situacion if situacion else "No encontrado"
            
            timings['query_rfcs_and_sat'] = round((time.time() - step_start) * 1000, 2)
            
            # Obtener versión SAT 
            step_start = time.time()
            version_sat = self._obtener_version_sat(session)
            timings['get_version_sat'] = round((time.time() - step_start) * 1000, 2)
            
            # Preparar historial y detalles
            step_start = time.time()
            fecha_conciliacion = get_mexico_time_naive()
            detalles_dict = []  # Lista de diccionarios para bulk_insert_mappings
            proveedores_encontrados = 0
            
            # Crear detalles y contar coincidencias
            # Usar rfcs_tenant que ya tenemos del JOIN
            for rfc in rfcs_tenant:
                estado = sat_dict.get(rfc, "No encontrado")
                if estado != "No encontrado":
                    proveedores_encontrados += 1
                
                # Preparar diccionario directamente para bulk_insert_mappings
                detalles_dict.append({
                    "rfc": rfc,
                    "estado": estado
                })
            
            proveedores_no_encontrados = total_proveedores - proveedores_encontrados
            porcentaje_exito = (proveedores_encontrados / total_proveedores * 100) if total_proveedores > 0 else 0
            timings['process_matches'] = round((time.time() - step_start) * 1000, 2)
            
            # Guardar en historial 
            step_start = time.time()
            historial = ConciliacionHistorial(
                tenant_id=tenant_id,
                tipo_conciliacion=tipo_conciliacion,
                version_sat=version_sat,
                rfcs_procesados=total_proveedores,
                coincidencias=proveedores_encontrados,
                estado="completado",
                fecha_conciliacion=fecha_conciliacion,
                duracion_ms=0
            )
            
            # Agregar historial para obtener ID
            session.add(historial)
            session.flush()  # Flush para obtener el ID
            
            historial_id = historial.id
            
            # Asignar historial_id a todos los detalles
            for detalle in detalles_dict:
                detalle["conciliacion_id"] = historial_id
            
            timings['create_historial'] = round((time.time() - step_start) * 1000, 2)
            
            # Guardar todos los detalles 
            step_start = time.time()
            if detalles_dict:
                session.bulk_insert_mappings(ConciliacionDetalle, detalles_dict)
                session.flush()
            timings['create_detalles'] = round((time.time() - step_start) * 1000, 2)
            
            # Calcular tiempo total
            total_time = time.time() - start_time
            timings['total'] = round(total_time * 1000, 2)
            
            logger.info(f"Conciliación completada para historial {historial.id} | Timings: {timings}")

            try:
                historial.duracion_ms = int(round(total_time * 1000.0))
            except Exception:
                pass

            return {
                "fecha_conciliacion": fecha_conciliacion.strftime("%Y-%m-%d %H:%M:%S"),
                "tipo_conciliacion": tipo_conciliacion,
                "version_sat": version_sat,
                "rfcs_procesados": total_proveedores,
                "coincidencias": proveedores_encontrados,
                "estado": "completado",
                "total_proveedores": total_proveedores,
                "proveedores_encontrados": proveedores_encontrados,
                "proveedores_no_encontrados": proveedores_no_encontrados,
                "porcentaje_exito": round(porcentaje_exito, 2),
                "historial_id": str(historial.id)
            }
            
        except Exception as e:
            logger.error(f"Error realizando conciliación para tenant {tenant_id}: {e}")
            raise
    
    def realizar_conciliacion_dof_proveedores(self, session: Session, tenant_id: UUID, tipo_conciliacion: str = "DOF + SAT") -> Dict[str, Any]:
        """
        Realiza la conciliación de todos los proveedores del tenant
        PRIORIZA DOF sobre Proveedores (SAT):
        1. Primero busca en DOF (dof_contribuyentes)
        2. Los RFCs no encontrados en DOF se buscan en Proveedores (SAT)
        3. Si existe en DOF, se le da prioridad (no se busca en proveedores)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            tipo_conciliacion: Tipo de conciliación (por defecto "DOF + SAT")
            
        Returns:
            Diccionario con estadísticas de la conciliación
        """
        try:
            start_time = time.time()
            timings = {}
            
            # Obtener solo limite_proveedores del plan 
            step_start = time.time()
            
            # Solo cargar el campo necesario del plan
            tenant = session.query(Tenant).options(
                joinedload(Tenant.plan).load_only(Plan.limite_proveedores)
            ).filter(Tenant.id == tenant_id).first()
            
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} no encontrado")
            
            limite_rfcs = tenant.plan.limite_proveedores if tenant.plan else 0
            timings['get_tenant_and_plan'] = round((time.time() - step_start) * 1000, 2)
            
            # Obtener RFCs del tenant (solo activos, ordenados por fecha - más viejos primero)
            step_start = time.time()
            
            rfcs_tenant = session.query(
                TenantProveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True
            ).order_by(
                TenantProveedor.created_at.asc()
            ).limit(limite_rfcs).all()
            
            # Extraer lista de RFCs
            rfcs_list = [rfc[0] for rfc in rfcs_tenant]
            total_proveedores = len(rfcs_list)
            
            if total_proveedores == 0:
                raise ValueError("No hay proveedores para conciliar")
            
            timings['query_rfcs_tenant'] = round((time.time() - step_start) * 1000, 2)
            
            # PASO 1: Buscar en DOF (PRIORIDAD)
            step_start = time.time()
            
            # Buscar RFCs en DOF
            dof_results = session.query(
                DOFContribuyente.rfc,
                DOFContribuyente.situacion_contribuyente
            ).filter(
                DOFContribuyente.rfc.in_(rfcs_list)
            ).all()
            
            # Crear diccionario de resultados DOF
            dof_dict = {rfc: situacion for rfc, situacion in dof_results}
            rfcs_en_dof = set(dof_dict.keys())
            rfcs_no_en_dof = [rfc for rfc in rfcs_list if rfc not in rfcs_en_dof]
            
            timings['query_dof'] = round((time.time() - step_start) * 1000, 2)
            
            logger.info(f"RFCs encontrados en DOF: {len(rfcs_en_dof)}, RFCs no en DOF: {len(rfcs_no_en_dof)}")
            
            # PASO 2: Buscar en Proveedores (SAT) solo los RFCs que NO están en DOF
            step_start = time.time()
            
            proveedores_dict = {}
            if rfcs_no_en_dof:
                # Buscar solo los RFCs que no están en DOF
                proveedores_results = session.query(
                    Proveedor.rfc,
                    Proveedor.situacion_contribuyente
                ).filter(
                    Proveedor.rfc.in_(rfcs_no_en_dof)
                ).all()
                
                proveedores_dict = {rfc: situacion for rfc, situacion in proveedores_results}
            
            timings['query_proveedores'] = round((time.time() - step_start) * 1000, 2)
            
            # Obtener versión SAT (para el historial)
            step_start = time.time()
            version_sat = self._obtener_version_sat(session)
            timings['get_version_sat'] = round((time.time() - step_start) * 1000, 2)
            
            # Preparar historial y detalles
            step_start = time.time()
            fecha_conciliacion = get_mexico_time_naive()
            detalles_dict = []  # Lista de diccionarios para bulk_insert_mappings
            proveedores_encontrados = 0
            proveedores_en_dof = 0
            proveedores_en_sat = 0
            
            # Crear detalles combinando DOF (prioridad) + Proveedores
            for rfc in rfcs_list:
                estado = None
                fuente = None
                
                # PRIORIDAD 1: Buscar en DOF
                if rfc in dof_dict:
                    estado = dof_dict[rfc]
                    fuente = "DOF"
                    proveedores_en_dof += 1
                    proveedores_encontrados += 1
                # PRIORIDAD 2: Buscar en Proveedores (solo si no está en DOF)
                elif rfc in proveedores_dict:
                    estado = proveedores_dict[rfc]
                    fuente = "SAT"
                    proveedores_en_sat += 1
                    proveedores_encontrados += 1
                else:
                    estado = "No encontrado"
                    fuente = None
                
                # Preparar diccionario directamente para bulk_insert_mappings
                detalles_dict.append({
                    "rfc": rfc,
                    "estado": estado
                })
                
                logger.debug(f"RFC {rfc}: {estado} (fuente: {fuente})")
            
            proveedores_no_encontrados = total_proveedores - proveedores_encontrados
            porcentaje_exito = (proveedores_encontrados / total_proveedores * 100) if total_proveedores > 0 else 0
            timings['process_matches'] = round((time.time() - step_start) * 1000, 2)
            
            # Guardar en historial 
            step_start = time.time()
            historial = ConciliacionHistorial(
                tenant_id=tenant_id,
                tipo_conciliacion=tipo_conciliacion,
                version_sat=version_sat,
                rfcs_procesados=total_proveedores,
                coincidencias=proveedores_encontrados,
                estado="completado",
                fecha_conciliacion=fecha_conciliacion,
                duracion_ms=0
            )
            
            # Agregar historial para obtener ID
            session.add(historial)
            session.flush()  # Flush para obtener el ID
            
            historial_id = historial.id
            
            # Asignar historial_id a todos los detalles
            for detalle in detalles_dict:
                detalle["conciliacion_id"] = historial_id
            
            timings['create_historial'] = round((time.time() - step_start) * 1000, 2)
            
            # Guardar todos los detalles 
            step_start = time.time()
            if detalles_dict:
                session.bulk_insert_mappings(ConciliacionDetalle, detalles_dict)
                session.flush()
            timings['create_detalles'] = round((time.time() - step_start) * 1000, 2)
            
            # Calcular tiempo total
            total_time = time.time() - start_time
            timings['total'] = round(total_time * 1000, 2)
            
            logger.info(f"Conciliación DOF+SAT completada para historial {historial.id} | Timings: {timings}")
            logger.info(f"  - RFCs en DOF: {proveedores_en_dof}")
            logger.info(f"  - RFCs en SAT (no en DOF): {proveedores_en_sat}")
            logger.info(f"  - RFCs no encontrados: {proveedores_no_encontrados}")

            try:
                historial.duracion_ms = int(round(total_time * 1000.0))
            except Exception:
                pass

            return {
                "fecha_conciliacion": fecha_conciliacion.strftime("%Y-%m-%d %H:%M:%S"),
                "tipo_conciliacion": tipo_conciliacion,
                "version_sat": version_sat,
                "rfcs_procesados": total_proveedores,
                "coincidencias": proveedores_encontrados,
                "estado": "completado",
                "total_proveedores": total_proveedores,
                "proveedores_encontrados": proveedores_encontrados,
                "proveedores_no_encontrados": proveedores_no_encontrados,
                "proveedores_en_dof": proveedores_en_dof,
                "proveedores_en_sat": proveedores_en_sat,
                "porcentaje_exito": round(porcentaje_exito, 2),
                "historial_id": str(historial.id)
            }
            
        except Exception as e:
            logger.error(f"Error realizando conciliación DOF+SAT para tenant {tenant_id}: {e}")
            raise
    
    def _obtener_version_sat(self, session: Session) -> str:
        """
        Obtiene la versión del SAT consultando directamente la fecha_lista 
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Versión del SAT en formato string
        """
        try:
            # Consulta directa sin ORM: solo la fecha, sin cargar objeto
            fecha = session.query(Proveedor.fecha_lista).limit(1).scalar()
            
            if fecha:
                return fecha.strftime("%Y-%m-%d")
            else:
                return "No disponible"
                
        except Exception as e:
            logger.warning(f"Error obteniendo versión del SAT: {e}")
            return "No disponible"
    
    def obtener_historial_conciliaciones_paginado(self, session: Session, tenant_id: UUID, pagina: int = 1, por_pagina: int = 10) -> Dict[str, Any]:
        """
        Obtiene el historial de conciliaciones del tenant con paginación 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            pagina: Número de página (empezando en 1)
            por_pagina: Registros por página
            
        Returns:
            Diccionario con historial paginado
        """
        try:
            # Calcular offset
            offset = (pagina - 1) * por_pagina
            
            # Calcular fecha de inicio del mes 
            fecha_actual = get_mexico_time_naive()
            inicio_mes = fecha_actual.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Query 1: Obtener total de registros y métricas del mes en paralelo 
            # Primero el total
            total_registros = session.query(ConciliacionHistorial)\
                .filter(ConciliacionHistorial.tenant_id == tenant_id)\
                .count()
            
            # Query 2: Obtener registros paginados (solo campos necesarios, sin ORM)
            historial_records = session.query(
                ConciliacionHistorial.id,
                ConciliacionHistorial.fecha_conciliacion,
                ConciliacionHistorial.tipo_conciliacion,
                ConciliacionHistorial.version_sat,
                ConciliacionHistorial.rfcs_procesados,
                ConciliacionHistorial.coincidencias,
                ConciliacionHistorial.estado
            ).filter(
                ConciliacionHistorial.tenant_id == tenant_id
            ).order_by(
                ConciliacionHistorial.fecha_conciliacion.desc()
            ).offset(offset).limit(por_pagina).all()
            
            # Formatear historial 
            historial = []
            for row in historial_records:
                historial.append({
                    "id": str(row[0]),
                    "fecha_conciliacion": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else "",
                    "tipo_conciliacion": row[2],
                    "version_sat": row[3] or "No disponible",
                    "rfcs_procesados": row[4],
                    "coincidencias": row[5],
                    "estado": row[6]
                })
            
            # Calcular total de páginas
            total_paginas = (total_registros + por_pagina - 1) // por_pagina
            
            # Query 3: Calcular métricas del mes actual
            metricas_mes = session.query(
                func.count(ConciliacionHistorial.id),
                func.coalesce(func.sum(ConciliacionHistorial.rfcs_procesados), 0),
                func.coalesce(func.avg(ConciliacionHistorial.duracion_ms), 0.0)
            ).filter(
                ConciliacionHistorial.tenant_id == tenant_id,
                ConciliacionHistorial.fecha_conciliacion >= inicio_mes,
                ConciliacionHistorial.duracion_ms > 0
            ).one()
            
            conciliaciones_mes = int(metricas_mes[0]) if metricas_mes[0] else 0
            rfcs_mes = int(metricas_mes[1]) if metricas_mes[1] else 0
            tiempo_promedio_ms = float(round(metricas_mes[2], 2)) if metricas_mes[2] else 0.0
            
            return {
                "historial": historial,
                "total": total_registros,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": total_paginas,
                "conciliaciones_mes": conciliaciones_mes,
                "rfcs_mes": rfcs_mes,
                "tiempo_promedio_ms": tiempo_promedio_ms
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo historial paginado para tenant {tenant_id}: {e}")
            raise

    def eliminar_proveedor(self, session: Session, tenant_id: UUID, rfc: str) -> bool:
        """
        Elimina un proveedor del tenant
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC del proveedor a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            # Verificar que el tenant existe
            tenant = self.tenant_repository.get_by_id(session, tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} no encontrado")
            
            # Eliminar relación
            eliminado = self.tenant_proveedor_repository.delete_by_tenant_and_rfc(session, tenant_id, rfc)
            
            if eliminado:
                logger.info(f"Proveedor {rfc} eliminado del tenant {tenant_id}")
            else:
                logger.warning(f"Proveedor {rfc} no encontrado en tenant {tenant_id}")
            
            return eliminado
            
        except Exception as e:
            logger.error(f"Error eliminando proveedor {rfc} del tenant {tenant_id}: {e}")
            raise
    
    def listar_proveedores_paginado(self, session: Session, tenant_id: UUID, pagina: int = 1, por_pagina: int = 20) -> Dict[str, Any]:
        """
        Lista los proveedores del tenant con paginación
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            pagina: Número de página (empezando en 1)
            por_pagina: Elementos por página
            
        Returns:
            Diccionario con la lista paginada de proveedores
        """
        try:
            # Calcular offset
            offset = (pagina - 1) * por_pagina
            
            # Obtener total de proveedores
            total = session.query(TenantProveedor).filter(
                TenantProveedor.tenant_id == tenant_id
            ).count()
            
            # Obtener proveedores paginados con LEFT JOIN a la tabla de proveedores
            proveedores = session.query(
                TenantProveedor, Proveedor
            ).outerjoin(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id
            ).offset(offset).limit(por_pagina).all()
            
            # Formatear datos
            proveedores_data = []
            for tenant_proveedor, proveedor in proveedores:
                if proveedor:
                    # Proveedor existe en la tabla de proveedores
                    proveedores_data.append({
                        "rfc": proveedor.rfc,
                        "estatus": proveedor.situacion_contribuyente or "No disponible",
                        "fecha_agregado": formatear_fecha_es(tenant_proveedor.created_at)
                    })
                else:
                    # Proveedor no existe en la tabla de proveedores
                    proveedores_data.append({
                        "rfc": tenant_proveedor.rfc,
                        "estatus": "No disponible",
                        "fecha_agregado": formatear_fecha_es(tenant_proveedor.created_at)
                    })
            
            # Calcular total de páginas
            total_paginas = (total + por_pagina - 1) // por_pagina
            
            return {
                "proveedores": proveedores_data,
                "total": total,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": total_paginas
            }
            
        except Exception as e:
            logger.error(f"Error listando proveedores paginados del tenant {tenant_id}: {e}")
            return {
                "proveedores": [],
                "total": 0,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": 0
            }
    
    def get_tenant_stats_within_limit(self, session: Session, tenant_id: UUID, limite_rfcs: int) -> Dict[str, Any]:
        """
        Obtiene estadísticas del tenant: total real de RFCs activos + alertas solo dentro del límite
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            limite_rfcs: Límite de RFCs del plan
            
        Returns:
            Diccionario con estadísticas
        """
        try:
            # Obtener solo los RFCs ACTIVOS del tenant
            todos_proveedores = session.query(
                TenantProveedor, Proveedor
            ).outerjoin(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True  # Solo RFCs activos
            ).order_by(
                TenantProveedor.created_at.asc()  # Ordenar por fecha de agregado (más antiguos primero)
            ).all()
            
            # Total real de RFCs activos añadidos
            total_rfcs_reales = len(todos_proveedores)
            
            # Solo contar alertas de los RFCs activos dentro del límite del plan
            proveedores_dentro_limite = todos_proveedores[:limite_rfcs]
            alertas = 0
            for tenant_proveedor, proveedor in proveedores_dentro_limite:
                if proveedor and proveedor.situacion_contribuyente == "Definitivo":
                    alertas += 1
            
            return {
                "total_rfcs": total_rfcs_reales,  # ← Total real de RFCs activos añadidos
                "alertas": alertas,                # ← Solo alertas dentro del límite
                "proveedores_dentro_limite": proveedores_dentro_limite
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas dentro del límite del tenant {tenant_id}: {e}")
            return {
                "total_rfcs": 0,
                "alertas": 0,
                "proveedores_dentro_limite": []
            }
    
    def obtener_ultima_conciliacion_power_query(self, session: Session, tenant_id: UUID) -> Dict[str, Any]:
        """
        Obtiene la última conciliación en formato para Power Query 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            
        Returns:
            Diccionario con resultado general y subrama de RFCs
        """
        try:
            # Query 1: Obtener última conciliación (solo campos necesarios, sin ORM)
            historial = session.query(
                ConciliacionHistorial.id,
                ConciliacionHistorial.fecha_conciliacion,
                ConciliacionHistorial.tipo_conciliacion,
                ConciliacionHistorial.version_sat
            ).filter(
                ConciliacionHistorial.tenant_id == tenant_id
            ).order_by(
                desc(ConciliacionHistorial.fecha_conciliacion)
            ).first()
            
            if not historial:
                return {}
            
            historial_id, fecha_conciliacion, tipo_conciliacion, version_sat = historial
            
            # Formatear fecha
            fecha_str = fecha_conciliacion.strftime("%Y-%m-%d %H:%M:%S") if fecha_conciliacion else ""
            version_sat = version_sat or "No disponible"
            
            # Query 2: Obtener detalles (solo campos necesarios, sin ORM)
            detalles = session.query(
                ConciliacionDetalle.rfc,
                ConciliacionDetalle.estado
            ).filter(
                ConciliacionDetalle.conciliacion_id == historial_id
            ).all()
            
            # Construir subrama de RFCs 
            rfcs = []
            for rfc, estado in detalles:
                # Calcular resultado de forma 
                if estado == "No encontrado":
                    resultado = "Sin coincidencia"
                elif estado and ("desvirtuado" in estado.lower() or "sentencia" in estado.lower()):
                    resultado = "Regularizado"
                else:
                    resultado = "Coincidencia"
                
                rfcs.append({
                    "rfc": rfc,
                    "estado": estado,
                    "resultado": resultado
                })
            
            # Retornar estructura con resultado general y subrama de RFCs
            return {
                "conciliacion_id": str(historial_id),
                "fecha_conciliacion": fecha_str,
                "tipo_conciliacion": tipo_conciliacion,
                "version_sat": version_sat,
                "rfcs": rfcs
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo última conciliación para Power Query del tenant {tenant_id}: {e}")
            raise
    
    def obtener_detalles_conciliacion(self, session: Session, tenant_id: UUID, historial_id: UUID) -> Dict[str, Any]:
        """
        Obtiene detalles completos de una conciliación 
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant (para validar ownership)
            historial_id: ID del historial de conciliación
            
        Returns:
            Diccionario con historial, detalles y resumen técnico
        """
        try:
            historial = session.query(ConciliacionHistorial).filter(
                ConciliacionHistorial.id == historial_id,
                ConciliacionHistorial.tenant_id == tenant_id
            ).first()
            
            if not historial:
                raise ValueError(f"Conciliación {historial_id} no encontrada para tenant {tenant_id}")
            
            # Obtener todos los detalles
            detalles = session.query(ConciliacionDetalle).filter(
                ConciliacionDetalle.conciliacion_id == historial_id
            ).all()
            
            # Construir lista de RFCs con resultado
            rfcs_list = []
            for detalle in detalles:
                # Calcular resultado según el estado
                if detalle.estado == "No encontrado":
                    resultado = "Sin coincidencia"
                elif "desvirtuado" in detalle.estado.lower() or "sentencia" in detalle.estado.lower():
                    resultado = "Regularizado"
                else:
                    resultado = "Coincidencia"
                
                rfcs_list.append({
                    "rfc": detalle.rfc,
                    "estado": detalle.estado,
                    "resultado": resultado
                })
            
            # Calcular sin coincidencias
            sin_coincidencias = historial.rfcs_procesados - historial.coincidencias
            
            # Construir datos técnicos
            start_time = historial.fecha_conciliacion
            end_time = start_time + timedelta(milliseconds=historial.duracion_ms)
            
            # Mapear trigger_source: "Manual" -> "manual", otros -> "automatic"
            trigger_source = "manual" if historial.tipo_conciliacion == "Manual" else "automatic"
            
            # Formatear fechas en formato ISO 8601 con zona horaria de México
            if start_time:
                if start_time.tzinfo is None:
                 
                    start_time_mexico = start_time.replace(tzinfo=MEXICO_TZ)
                    start_time_str = start_time_mexico.strftime("%Y-%m-%dT%H:%M:%S%z")
                    # Formatear offset como -06:00 en lugar de -0600
                    if len(start_time_str) == 25:
                        start_time_str = start_time_str[:-2] + ":" + start_time_str[-2:]
                else:
                    # Fecha con timezone, convertir a hora de México
                    start_time_mexico = start_time.astimezone(MEXICO_TZ)
                    start_time_str = start_time_mexico.strftime("%Y-%m-%dT%H:%M:%S%z")
                    if len(start_time_str) == 25:
                        start_time_str = start_time_str[:-2] + ":" + start_time_str[-2:]
            else:
                start_time_str = ""
                
            if end_time:
                if end_time.tzinfo is None:
                    # Fecha naive, asumir hora de México y formatear
                    end_time_mexico = end_time.replace(tzinfo=MEXICO_TZ)
                    end_time_str = end_time_mexico.strftime("%Y-%m-%dT%H:%M:%S%z")
                    # Formatear offset como -06:00 en lugar de -0600
                    if len(end_time_str) == 25:
                        end_time_str = end_time_str[:-2] + ":" + end_time_str[-2:]
                else:
                    # Fecha con timezone, convertir a hora de México
                    end_time_mexico = end_time.astimezone(MEXICO_TZ)
                    end_time_str = end_time_mexico.strftime("%Y-%m-%dT%H:%M:%S%z")
                    if len(end_time_str) == 25:
                        end_time_str = end_time_str[:-2] + ":" + end_time_str[-2:]
            else:
                end_time_str = ""
            
            # Obtener sat_version o usar "No disponible"
            sat_version = historial.version_sat if historial.version_sat else "No disponible"
            
            return {
                "rfcs_procesados": historial.rfcs_procesados,
                "coincidencias": historial.coincidencias,
                "sin_coincidencias": sin_coincidencias,
                "duracion_ms": historial.duracion_ms,
                "rfcs": rfcs_list,
                "resumen_tecnico": {
                    "execution_id": str(historial.id),
                    "status": historial.estado,
                    "processed": historial.rfcs_procesados,
                    "matched": historial.coincidencias
                },
                "datos_tecnicos": {
                    "execution_id": str(historial.id),
                    "tenant_id": str(historial.tenant_id),
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "trigger_source": trigger_source,
                    "sat_version": sat_version,
                    "rfc_processed": historial.rfcs_procesados,
                    "matched": historial.coincidencias,
                    "status": historial.estado
                }
            }
            
        except ValueError as e:
            logger.warning(f"Conciliación no encontrada: {e}")
            raise
        except Exception as e:
            logger.error(f"Error obteniendo detalles de conciliación {historial_id}: {e}")
            raise

    def conciliar_rfcs_especificos(self, session: Session, tenant_id: UUID, rfcs: List[str], tipo_conciliacion: str = "Excedentes - Pago") -> UUID:
        """
        Crea una conciliación para una lista específica de RFCs (usado para excedentes pagados)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfcs: Lista de RFCs a conciliar
            tipo_conciliacion: Tipo de conciliación (default: "Excedentes - Pago")
            
        Returns:
            UUID del historial de conciliación creado
        """
        try:
            start_time = time.time()
            
            # Normalizar RFCs
            rfcs_norm = sorted(set(rfc.upper().strip() for rfc in rfcs))
            
            if not rfcs_norm:
                raise ValueError("La lista de RFCs no puede estar vacía")
            
            # Consultar RFCs en SAT
            proveedores_sat = session.query(Proveedor).options(
                load_only(Proveedor.rfc, Proveedor.situacion_contribuyente)
            ).filter(Proveedor.rfc.in_(rfcs_norm)).all()
            
            # Crear diccionario para búsqueda rápida
            sat_dict = {proveedor.rfc: proveedor for proveedor in proveedores_sat}
            coincidencias = len(proveedores_sat)
            
            # Obtener versión SAT consultando cualquier proveedor de la tabla
            version_sat = self._obtener_version_sat(session)
            
            # Crear historial
            fecha_conciliacion = get_mexico_time_naive()
            historial = self.conciliacion_historial_repository.create_historial(
                session=session,
                tenant_id=tenant_id,
                tipo_conciliacion=tipo_conciliacion,
                version_sat=version_sat,
                rfcs_procesados=len(rfcs_norm),
                coincidencias=coincidencias,
                fecha_conciliacion=fecha_conciliacion
            )
            
            # Calcular duración
            total_time = time.time() - start_time
            try:
                historial.duracion_ms = int(round(total_time * 1000.0))
                session.flush()
            except Exception:
                pass
            
            # Crear detalles de conciliación
            detalles_conciliacion = []
            for rfc in rfcs_norm:
                proveedor = sat_dict.get(rfc)
                estado = proveedor.situacion_contribuyente if proveedor else "No encontrado"
                
                detalle = ConciliacionDetalle(
                    conciliacion_id=historial.id,
                    rfc=rfc,
                    estado=estado
                )
                detalles_conciliacion.append(detalle)
            
            # Guardar todos los detalles en una sola operación
            if detalles_conciliacion:
                self.conciliacion_detalle_repository.create_bulk(session, detalles_conciliacion)
            
            logger.info(f"Conciliación de RFCs específicos completada para historial {historial.id} - {len(rfcs_norm)} RFCs, {coincidencias} coincidencias")
            
            return historial.id
            
        except Exception as e:
            logger.error(f"Error conciliando RFCs específicos para tenant {tenant_id}: {e}")
            raise
    
    def realizar_conciliacion_dof_todos_tenants(self, session: Session) -> Dict[str, Any]:
        """
        Ejecuta conciliación DOF+SAT para todos los tenants activos
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Diccionario con resultados de todas las conciliaciones
        """
        try:
            logger.info(" Iniciando conciliación DOF+SAT para todos los tenants")
            
            # Obtener todos los tenants activos
            tenants = self.tenant_repository.get_active_tenants(session)
            total_tenants = len(tenants)
            
            logger.info(f" Total de tenants activos: {total_tenants}")
            
            if total_tenants == 0:
                logger.warning(" No hay tenants activos para procesar")
                return {
                    "total_tenants": 0,
                    "total_procesados": 0,
                    "total_exitosos": 0,
                    "total_fallidos": 0,
                    "resultados": []
                }
            
            resultados = []
            total_exitosos = 0
            total_fallidos = 0
            
            # Procesar cada tenant
            for tenant in tenants:
                try:
                    logger.info(f"🔄 Procesando tenant: {tenant.id} ({tenant.nombre_comercial})")
                    
                    # Ejecutar conciliación DOF+SAT para el tenant
                    resultado = self.realizar_conciliacion_dof_proveedores(
                        session=session,
                        tenant_id=tenant.id,
                        tipo_conciliacion="DOF + SAT"
                    )
                    
                    # Commit para este tenant
                    session.commit()
                    
                    # Enviar correo con reporte PDF a usuarios del tenant
                    try:
                        self._enviar_correo_conciliacion(
                            session=session,
                            tenant=tenant,
                            historial_id=resultado["historial_id"],
                            tipo_conciliacion=resultado["tipo_conciliacion"],
                            fecha_conciliacion=resultado["fecha_conciliacion"],
                            rfcs_procesados=resultado["rfcs_procesados"],
                            coincidencias=resultado["coincidencias"]
                        )
                    except Exception as email_error:
                        # No fallar la conciliación si falla el envío de correo
                        logger.error(f" Error enviando correo para tenant {tenant.id}: {str(email_error)}")
                    
                    # Agregar tenant_id al resultado
                    resultado_item = {
                        "tenant_id": str(tenant.id),
                        "fecha_conciliacion": resultado["fecha_conciliacion"],
                        "tipo_conciliacion": resultado["tipo_conciliacion"],
                        "version_sat": resultado.get("version_sat"),
                        "rfcs_procesados": resultado["rfcs_procesados"],
                        "coincidencias": resultado["coincidencias"],
                        "estado": resultado["estado"],
                        "historial_id": resultado["historial_id"]
                    }
                    
                    resultados.append(resultado_item)
                    total_exitosos += 1
                    
                    logger.success(
                        f"✅ Tenant {tenant.id}: {resultado['rfcs_procesados']} RFCs procesados, "
                        f"{resultado['coincidencias']} coincidencias"
                    )
                    
                except Exception as e:
                    # Rollback para este tenant
                    session.rollback()
                    total_fallidos += 1
                    
                    logger.error(f"❌ Error procesando tenant {tenant.id}: {str(e)}")
                    
                    # Agregar resultado de error
                    resultados.append({
                        "tenant_id": str(tenant.id),
                        "fecha_conciliacion": get_mexico_time_naive().strftime("%Y-%m-%d %H:%M:%S"),
                        "tipo_conciliacion": "DOF + SAT",
                        "version_sat": None,
                        "rfcs_procesados": 0,
                        "coincidencias": 0,
                        "estado": f"error: {str(e)}",
                        "historial_id": None
                    })
            
            logger.success(
                f"✅ Conciliación DOF+SAT completada: "
                f"{total_exitosos} exitosos, {total_fallidos} fallidos de {total_tenants} tenants"
            )
            
            return {
                "total_tenants": total_tenants,
                "total_procesados": len(resultados),
                "total_exitosos": total_exitosos,
                "total_fallidos": total_fallidos,
                "resultados": resultados
            }
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando conciliación DOF+SAT para todos los tenants: {e}")
            raise
    
    def realizar_conciliacion_todos_tenants(self, session: Session) -> Dict[str, Any]:
        """
        Ejecuta conciliación automática para todos los tenants activos
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Diccionario con resultados de todas las conciliaciones
        """
        try:
            logger.info(" Iniciando conciliación automática para todos los tenants")
            
            # Obtener todos los tenants activos
            tenants = self.tenant_repository.get_active_tenants(session)
            total_tenants = len(tenants)
            
            logger.info(f" Total de tenants activos: {total_tenants}")
            
            if total_tenants == 0:
                logger.warning(" No hay tenants activos para procesar")
                return {
                    "total_tenants": 0,
                    "total_procesados": 0,
                    "total_exitosos": 0,
                    "total_fallidos": 0,
                    "resultados": []
                }
            
            resultados = []
            total_exitosos = 0
            total_fallidos = 0
            
            # Procesar cada tenant
            for tenant in tenants:
                try:
                    logger.info(f"🔄 Procesando tenant: {tenant.id} ({tenant.nombre_comercial})")
                    
                    # Ejecutar conciliación automática para el tenant
                    resultado = self.realizar_conciliacion(
                        session=session,
                        tenant_id=tenant.id,
                        tipo_conciliacion="Automatica"
                    )
                    
                    # Commit para este tenant
                    session.commit()
                    
                    # Enviar correo con reporte PDF a usuarios del tenant
                    try:
                        self._enviar_correo_conciliacion(
                            session=session,
                            tenant=tenant,
                            historial_id=resultado["historial_id"],
                            tipo_conciliacion=resultado["tipo_conciliacion"],
                            fecha_conciliacion=resultado["fecha_conciliacion"],
                            rfcs_procesados=resultado["rfcs_procesados"],
                            coincidencias=resultado["coincidencias"]
                        )
                    except Exception as email_error:
                        # No fallar la conciliación si falla el envío de correo
                        logger.error(f" Error enviando correo para tenant {tenant.id}: {str(email_error)}")
                    
                    # Agregar tenant_id al resultado
                    resultado_item = {
                        "tenant_id": str(tenant.id),
                        "fecha_conciliacion": resultado["fecha_conciliacion"],
                        "tipo_conciliacion": resultado["tipo_conciliacion"],
                        "version_sat": resultado.get("version_sat"),
                        "rfcs_procesados": resultado["rfcs_procesados"],
                        "coincidencias": resultado["coincidencias"],
                        "estado": resultado["estado"],
                        "historial_id": resultado["historial_id"]
                    }
                    
                    resultados.append(resultado_item)
                    total_exitosos += 1
                    
                    logger.success(
                        f"✅ Tenant {tenant.id}: {resultado['rfcs_procesados']} RFCs procesados, "
                        f"{resultado['coincidencias']} coincidencias"
                    )
                    
                except Exception as e:
                    # Rollback para este tenant
                    session.rollback()
                    total_fallidos += 1
                    
                    logger.error(f"❌ Error procesando tenant {tenant.id}: {str(e)}")
                    
                    # Agregar resultado de error
                    resultados.append({
                        "tenant_id": str(tenant.id),
                        "fecha_conciliacion": get_mexico_time_naive().strftime("%Y-%m-%d %H:%M:%S"),
                        "tipo_conciliacion": "Automatica",
                        "version_sat": None,
                        "rfcs_procesados": 0,
                        "coincidencias": 0,
                        "estado": f"error: {str(e)}",
                        "historial_id": None
                    })
            
            logger.success(
                f"✅ Conciliación automática completada: "
                f"{total_exitosos} exitosos, {total_fallidos} fallidos de {total_tenants} tenants"
            )
            
            return {
                "total_tenants": total_tenants,
                "total_procesados": len(resultados),
                "total_exitosos": total_exitosos,
                "total_fallidos": total_fallidos,
                "resultados": resultados
            }
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando conciliación automática para todos los tenants: {e}")
            raise
    
    def obtener_dashboard_rfcs(self, session: Session, tenant_id: UUID, pagina: int = 1, por_pagina: int = 20) -> Dict[str, Any]:
        """
        Obtiene el dashboard completo de RFCs del tenant con estadísticas y lista detallada paginada
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            pagina: Número de página (empezando en 1)
            por_pagina: Registros por página
            
        Returns:
            Diccionario con estadísticas y lista paginada de RFCs
        """
        try:
            from app.models.tenant_proveedor import TenantProveedor
            from app.models.proveedor import Proveedor
            from sqlalchemy import func, case
            
            # Calcular estadísticas con queries eficientes (sin traer todos los datos)
            total_rfcs = session.query(func.count(TenantProveedor.rfc)).filter(
                TenantProveedor.tenant_id == tenant_id
            ).scalar() or 0
            
            rfcs_activos = session.query(func.count(TenantProveedor.rfc)).filter(
                TenantProveedor.tenant_id == tenant_id,
                TenantProveedor.activo == True
            ).scalar() or 0
            
            rfcs_inactivos = total_rfcs - rfcs_activos
            
            # RFCs con alerta (Definitivo)
            rfcs_con_alerta = session.query(func.count(TenantProveedor.rfc)).join(
                Proveedor, TenantProveedor.rfc == Proveedor.rfc
            ).filter(
                TenantProveedor.tenant_id == tenant_id,
                Proveedor.situacion_contribuyente == 'Definitivo'
            ).scalar() or 0
            
            # Obtener fecha de última conciliación 
            ultima_conciliacion = self.conciliacion_historial_repository.get_ultima_conciliacion(session, tenant_id)
            fecha_ultima_conciliacion = None
            if ultima_conciliacion and ultima_conciliacion.fecha_conciliacion:
                # Convertir datetime a date
                fecha_ultima_conciliacion = ultima_conciliacion.fecha_conciliacion.date() if isinstance(ultima_conciliacion.fecha_conciliacion, datetime) else ultima_conciliacion.fecha_conciliacion
            
            # Obtener RFCs paginados
            resultado_paginado = self.tenant_proveedor_repository.get_all_rfcs_with_details_paginado(
                session, tenant_id, pagina, por_pagina
            )
            
            return {
                "total_rfcs": total_rfcs,
                "rfcs_activos": rfcs_activos,
                "rfcs_inactivos": rfcs_inactivos,
                "rfcs_con_alerta": rfcs_con_alerta,
                "fecha_ultima_conciliacion": fecha_ultima_conciliacion,
                "rfcs": resultado_paginado["rfcs"],
                "total": resultado_paginado["total"],
                "pagina": resultado_paginado["pagina"],
                "por_pagina": resultado_paginado["por_pagina"],
                "total_paginas": resultado_paginado["total_paginas"]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo dashboard de RFCs del tenant {tenant_id}: {e}")
            return {
                "total_rfcs": 0,
                "rfcs_activos": 0,
                "rfcs_inactivos": 0,
                "rfcs_con_alerta": 0,
                "fecha_ultima_conciliacion": None,
                "rfcs": [],
                "total": 0,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_paginas": 0
            }
    
    def actualizar_estado_operativo_rfc(self, session: Session, tenant_id: UUID, rfc: str, activo: bool) -> Optional[Dict[str, Any]]:
        """
        Actualiza el estado operativo (activo/inactivo) de un RFC
        VERIFICA límite de burst antes de activar
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC a actualizar
            activo: True para activar, False para desactivar
            
        Returns:
            Diccionario con información del RFC actualizado o None si no existe
        """
        try:
            # Obtener el RFC actual
            relation = self.tenant_proveedor_repository.get_by_tenant_and_rfc(session, tenant_id, rfc)
            
            if not relation:
                return None
            
            # Si se intenta ACTIVAR, verificar límite de burst
            if activo and not relation.activo:
                # Obtener el tenant con su plan
                from app.models.tenant import Tenant
                from app.models.plan import Plan
                from sqlalchemy.orm import joinedload, load_only
                
                tenant = session.query(Tenant).options(
                    joinedload(Tenant.plan).load_only(Plan.limite_proveedores)
                ).filter(Tenant.id == tenant_id).first()
                
                if tenant and tenant.plan:
                    limite_rfcs = tenant.plan.limite_proveedores
                    limite_burst = limite_rfcs + int(limite_rfcs * 0.15)
                    
                    # Contar RFCs ACTIVOS actuales
                    total_activos = session.query(TenantProveedor).filter(
                        TenantProveedor.tenant_id == tenant_id,
                        TenantProveedor.activo == True
                    ).count()
                    
                    # Verificar si activar este RFC sobrepasaría el burst
                    if total_activos >= limite_burst:
                        raise ValueError("No se puede activar: sobrepasará el límite de burst permitido")
            
            # Actualizar estado 
            relation.activo = activo
            
            # Obtener nombre del grupo si existe 
            nombre_grupo = None
            if relation.grupo_id:
                from app.models.grupo import Grupo
                grupo = session.query(Grupo.nombre).filter(
                    Grupo.id == relation.grupo_id,
                    Grupo.tenant_id == tenant_id
                ).scalar()
                nombre_grupo = grupo if grupo else None
            
            session.commit()
            session.refresh(relation)
            
            return {
                "rfc": relation.rfc,
                "activo": relation.activo,
                "grupo": nombre_grupo,
                "mensaje": f"RFC {'activado' if activo else 'desactivado'} exitosamente"
            }
            
        except ValueError as ve:
            # Error de validación del límite
            session.rollback()
            logger.warning(f"Validación fallida al activar RFC {rfc}: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error actualizando estado operativo del RFC {rfc}: {e}")
            session.rollback()
            return None
    
    def _enviar_correo_conciliacion(
        self,
        session: Session,
        tenant: Tenant,
        historial_id: str,
        tipo_conciliacion: str,
        fecha_conciliacion: str,
        rfcs_procesados: int,
        coincidencias: int
    ) -> None:
        """
        Envía correo con reporte PDF de conciliación a todos los usuarios activos del tenant
        
        Args:
            session: Sesión de base de datos
            tenant: Objeto Tenant
            historial_id: ID del historial de conciliación
            tipo_conciliacion: Tipo de conciliación
            fecha_conciliacion: Fecha de la conciliación
            rfcs_procesados: Total de RFCs procesados
            coincidencias: Total de coincidencias
        """
        try:
            from uuid import UUID as UUIDType
            
            # Obtener usuarios activos del tenant
            usuario_repo = UsuarioRepository(session)
            usuarios_activos = usuario_repo.get_active_users(tenant.id)
            
            logger.info(f"📧 Buscando usuarios activos para tenant {tenant.nombre_comercial} (ID: {tenant.id})")
            logger.info(f"📧 Usuarios encontrados: {len(usuarios_activos)}")
            
            if not usuarios_activos:
                logger.warning(f"⚠️ No hay usuarios activos para enviar correo al tenant {tenant.nombre_comercial} (ID: {tenant.id})")
                return
            
            # Obtener emails de usuarios activos
            emails_destinatarios = [usuario.email for usuario in usuarios_activos if usuario.email]
            
            logger.info(f" Emails encontrados: {len(emails_destinatarios)}")
            logger.info(f"📧Lista de emails: {emails_destinatarios}")
            
            if not emails_destinatarios:
                logger.warning(f" No hay emails válidos para enviar correo al tenant {tenant.nombre_comercial} (ID: {tenant.id})")
                logger.warning(f" Usuarios encontrados pero sin email: {[f'{u.nombre} {u.apellidos} (ID: {u.id})' for u in usuarios_activos if not u.email]}")
                return
            
            # Generar PDF del reporte
            historial_uuid = UUIDType(historial_id)
            reporte_service = ReporteService()
            datos_reporte = reporte_service.obtener_datos_reporte(session, tenant.id, historial_uuid)
            pdf_buffer = reporte_service.generar_pdf(datos_reporte)
            
            # Enviar correo individualmente a cada destinatario por si algun correo no existe, no se afecte el resto
            email_enviado = email_service.enviar_correo_conciliacion(
                destinatarios=emails_destinatarios,
                tenant_nombre=tenant.nombre_comercial,
                tipo_conciliacion=tipo_conciliacion,
                fecha_conciliacion=fecha_conciliacion,
                rfcs_procesados=rfcs_procesados,
                coincidencias=coincidencias,
                pdf_buffer=pdf_buffer,
                historial_id=historial_id
            )
            
            if not email_enviado:
                logger.warning(f" No se pudo enviar correo a ningún usuario del tenant {tenant.nombre_comercial}")
                
        except Exception as e:
            logger.error(f"Error enviando correo de conciliación para tenant {tenant.id}: {e}")
            raise
    
    def actualizar_grupo_rfc(self, session: Session, tenant_id: UUID, rfc: str, nombre_grupo: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Actualiza el grupo de un RFC (crea el grupo si no existe)
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            rfc: RFC a actualizar
            nombre_grupo: Nombre del grupo (None para eliminar grupo)
            
        Returns:
            Diccionario con información del RFC actualizado o None si no existe
        """
        try:
            from app.repositories.grupo_repository import GrupoRepository
            grupo_repo = GrupoRepository()
            
            # Si se proporciona nombre, buscar o crear el grupo 
            grupo_id = None
            nombre_grupo_final = None
            if nombre_grupo and nombre_grupo.strip():
                grupo = grupo_repo.create_or_get(session, tenant_id, nombre_grupo, commit=False)
                if grupo:
                    grupo_id = grupo.id
                    nombre_grupo_final = grupo.nombre
                else:
                    logger.warning(f"No se pudo crear/obtener grupo: {nombre_grupo}")
                    return None
            
            # Actualizar relación 
            relation = self.tenant_proveedor_repository.update_grupo(session, tenant_id, rfc, grupo_id, commit=False)
            
            if not relation:
                return None
            

            session.commit()
            session.refresh(relation)
            
            return {
                "rfc": relation.rfc,
                "activo": relation.activo,
                "grupo": nombre_grupo_final,
                "grupo_id": str(grupo_id) if grupo_id else None,
                "mensaje": f"Grupo {'asignado' if nombre_grupo else 'eliminado'} exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error actualizando grupo del RFC {rfc}: {e}")
            session.rollback()
            return None