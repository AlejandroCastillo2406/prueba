"""
Rutas para conciliación
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from loguru import logger
import stripe
from app.models.plan import Plan
from app.models.tenant_proveedor import TenantProveedor
from app.models.orden_pago_excedente import OrdenPagoExcedente
from sqlalchemy import func, and_, exists, select
from sqlalchemy import literal_column

from app.core.database import get_db
from app.core.auth import get_current_tenant, get_current_active_user, verify_internal_api_key
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.dto.conciliacion_dto import (
    ConsultarRFCRequestDTO,
    AgregarProveedorRequestDTO,
    AgregarProveedorResponseDTO,
    AgregarProveedorItemResponseDTO
)
from app.dto.conciliacion_response_dto import ConciliacionResponseDTO
from app.dto.conciliacion_detalle_dto import ConciliacionDetalleResponseDTO
from app.dto.conciliacion_automatica_dto import ConciliacionAutomaticaResponseDTO
from app.core.auth import verify_internal_api_key
from app.dto.orden_pago_dto import (
    ExcedentesDisponiblesResponseDTO,
    CrearOrdenExcedenteRequestDTO,
    CrearOrdenExcedenteResponseDTO,
    OrdenPagoExcedenteResponseDTO
)
from app.dto.rfc_dto import (
    RFCDashboardResponseDTO,
    RFCUpdateResponseDTO,
    ActivarRFCRequestDTO,
    AsignarGrupoRequestDTO,
    GruposListResponseDTO
)
from app.factories.service_factory import service_factory
from app.repositories.orden_pago_repository import OrdenPagoRepository
from app.services.stripe_service import StripeService
from app.services.reporte_service import ReporteService
from app.core.config import settings
from fastapi.responses import StreamingResponse
from uuid import UUID


router = APIRouter()


@router.post("/consultar-rfc")
async def consultar_rfc_en_sat(
    request: ConsultarRFCRequestDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Consulta un RFC en la base de datos del SAT.
    
    Requiere autenticación con API Key en el header X-API-Key.
    
    Devuelve: rfc, nombre_contribuyente, estatus, fecha_archivo_sat
    """
    try:
        # Consulta directa en la base de datos del SAT
        from app.factories.service_factory import service_factory
        proveedor_service = service_factory.create_sat_service()
        proveedor = proveedor_service.get_proveedor_by_rfc(db, request.rfc)
        
        if proveedor:
            return {
                "rfc": request.rfc,
                "nombre_contribuyente": proveedor.razon_social,
                "estatus": proveedor.situacion_contribuyente,
                "fecha_archivo_sat": proveedor.fecha_lista.date() if proveedor.fecha_lista else None
            }
        else:
            return {
                "rfc": request.rfc,
                "nombre_contribuyente": None,
                "estatus": None,
                "fecha_archivo_sat": None
            }
        
    except Exception as e:
        logger.error(f"Error consultando RFC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando RFC: {str(e)}"
        )


@router.post("/agregar-proveedor", response_model=AgregarProveedorResponseDTO)
async def agregar_proveedor(
    request: AgregarProveedorRequestDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Agrega uno o varios proveedores al tenant (manual con JSON).
    
    **Ejemplo de uso:**
    ```json
    {
      "proveedores": [
        {
          "rfc": "ABC123456789",
          "razon_social": "Empresa Ejemplo S.A. de C.V."
        },
        {
          "rfc": "XYZ987654321"
        }
      ]
    }
    ```
    
    **Para subir archivo CSV/Excel**, usar el endpoint `/agregar-proveedor-archivo`
    """
    try:
        # Validar y preparar datos de proveedores
        proveedores_validos = []
        for proveedor in request.proveedores:
            rfc_limpio = str(proveedor.rfc).upper().strip()
            if len(rfc_limpio) not in [12, 13] or not rfc_limpio.isalnum():
                continue
            
            proveedor_data = {
                "rfc": rfc_limpio,
                "razon_social": proveedor.razon_social.strip() if proveedor.razon_social else None
            }
            proveedores_validos.append(proveedor_data)
        
        if not proveedores_validos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos un RFC válido (12 o 13 caracteres alfanuméricos)"
            )
        
        logger.info(f"Agregando {len(proveedores_validos)} proveedor(es) manualmente")
        
        # Obtener límite del plan
        tenant_service = service_factory.create_tenant_service()
        usage_stats = tenant_service.get_tenant_usage(db, current_tenant.id)
        limite_rfcs = usage_stats.get('limite_rfcs', 0)
        
        # Agregar proveedores
        service = service_factory.create_conciliacion_service()
        resultados_batch = service.agregar_proveedores_batch(db, current_tenant.id, proveedores_validos, limite_rfcs)
        
        db.commit()
        
        # Convertir a DTOs
        resultados = []
        for resultado in resultados_batch:
            resultados.append(AgregarProveedorItemResponseDTO(
                rfc=resultado["rfc"],
                proveedor_id=resultado.get("proveedor_id", ""),
                error=resultado.get("error")
            ))
        
        return AgregarProveedorResponseDTO(resultados=resultados)
        
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error agregando proveedores: {str(e)}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error agregando proveedores: {str(e)}"
        )


@router.post("/agregar-proveedor-archivo", response_model=AgregarProveedorResponseDTO)
async def agregar_proveedor_archivo(
    archivo: UploadFile = File(..., description="Archivo CSV o Excel (.csv, .xlsx, .xls)"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Agrega proveedores desde un archivo CSV o Excel.
    
    **Template exacto requerido:**
    - El archivo debe tener exactamente estas columnas: `RFC`, `Razón Social`, `Fecha Inicio`, `Fecha Baja`
    - Si falta alguna columna o hay columnas extras, retorna error "Template inválido"
    
    **Formatos de archivo soportados:**
    - CSV (.csv)
    - Excel (.xlsx, .xls)
    
    **Ejemplo de contenido:**
    ```
    RFC,Razón Social,Fecha Inicio,Fecha Baja
    ABC123456789,EMPRESA EJEMPLO SA,2024-01-15,
    XYZ987654321,COMERCIALIZADORA SC,2023-06-01,2025-12-31
    ```
    
    **Formatos de fecha aceptados:**
    - YYYY-MM-DD (2025-01-15)
    - DD/MM/YYYY (15/01/2025)
    - DD-MM-YYYY (15-01-2025)
    - Dejar vacío si no aplica
    """
    try:
        # Validar extensión
        filename_lower = archivo.filename.lower() if archivo.filename else ""
        if not filename_lower.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de archivo no soportado. Solo se aceptan CSV (.csv) y Excel (.xlsx, .xls)"
            )
        
        # Leer contenido del archivo
        file_content = await archivo.read()
        
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío"
            )
        
        logger.info(f"Procesando archivo {archivo.filename} ({len(file_content)} bytes)")
        
        # Procesar archivo con validación de template
        from app.services.file_processor_service import FileProcessorService
        file_processor = FileProcessorService()
        
        try:
            datos_extraidos, metadatos = file_processor.process_file(file_content, archivo.filename)
        except ValueError as e:
            # Error de template inválido u otro error de validación
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        if not datos_extraidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron RFCs válidos en el archivo"
            )
        
        logger.info(f"Se encontraron {len(datos_extraidos)} RFC(s) válidos en el archivo")
        
        # Obtener límite del plan
        tenant_service = service_factory.create_tenant_service()
        usage_stats = tenant_service.get_tenant_usage(db, current_tenant.id)
        limite_rfcs = usage_stats.get('limite_rfcs', 0)
        
        # Agregar proveedores con datos del archivo
        service = service_factory.create_conciliacion_service()
        resultados_batch = service.agregar_proveedores_batch_con_datos(
            db, 
            current_tenant.id, 
            datos_extraidos, 
            limite_rfcs
        )
        
        db.commit()
        
        # Convertir a DTOs
        resultados = []
        for resultado in resultados_batch:
            resultados.append(AgregarProveedorItemResponseDTO(
                rfc=resultado["rfc"],
                proveedor_id=resultado.get("proveedor_id", ""),
                error=resultado.get("error")
            ))
        
        return AgregarProveedorResponseDTO(resultados=resultados)
        
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando archivo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo: {str(e)}"
        )
@router.post(
    "/realizar-conciliacion-dof-proveedores",
    response_model=ConciliacionAutomaticaResponseDTO,
    summary="Ejecutar conciliación DOF+SAT para todos los tenants",
    description="Ejecuta conciliación DOF+SAT para todos los tenants activos. Requiere Internal API Key."
)
async def realizar_conciliacion_dof_proveedores(
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    """
    Ejecuta conciliación DOF+SAT para todos los tenants activos.
    PRIORIZA DOF sobre Proveedores (SAT):
    1. Primero busca en DOF (dof_contribuyentes)
    2. Los RFCs no encontrados en DOF se buscan en Proveedores (SAT)
    3. Si existe en DOF, se le da prioridad (no se busca en proveedores)
    
    **Requiere:** Internal API Key en el header `X-Internal-API-Key`
    
    **Retorna:**
    - Total de tenants procesados
    - Total exitosos
    - Total fallidos
    - Lista de resultados por tenant con:
      - tenant_id
      - fecha_conciliacion
      - tipo_conciliacion (DOF + SAT)
      - version_sat
      - rfcs_procesados
      - coincidencias
      - estado
      - historial_id
    """
    try:
        logger.info("🚀 Iniciando conciliación DOF+SAT para todos los tenants")
        
        service = service_factory.create_conciliacion_service()
        resultado = service.realizar_conciliacion_dof_todos_tenants(db)
        
        return ConciliacionAutomaticaResponseDTO(
            total_tenants=resultado["total_tenants"],
            total_procesados=resultado["total_procesados"],
            total_exitosos=resultado["total_exitosos"],
            total_fallidos=resultado["total_fallidos"],
            resultados=resultado["resultados"]
        )
        
    except Exception as e:
        logger.error(f"Error ejecutando conciliación DOF+SAT para todos los tenants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando conciliación DOF+SAT: {str(e)}"
        )


@router.post("/realizar-conciliacion", response_model=ConciliacionResponseDTO)
async def realizar_conciliacion(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Realiza la conciliación de todos los proveedores del tenant.
    
    **Retorna:**
    - Fecha de conciliación
    - Tipo de conciliación (Manual/Automatica)
    - Versión del SAT utilizada
    - RFCs procesados (cantidad total)
    - Coincidencias (número de coincidencias con la BD)
    - Estado (completado)
    """
    try:
        service = service_factory.create_conciliacion_service()
        resultado = service.realizar_conciliacion(db, current_tenant.id, "Manual")
        
        db.commit()
        
        return ConciliacionResponseDTO(
            fecha_conciliacion=resultado["fecha_conciliacion"],
            tipo_conciliacion=resultado["tipo_conciliacion"],
            version_sat=resultado["version_sat"],
            rfcs_procesados=resultado["rfcs_procesados"],
            coincidencias=resultado["coincidencias"],
            estado=resultado["estado"],
            historial_id=resultado["historial_id"]
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error realizando conciliación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error realizando conciliación: {str(e)}"
        )


@router.post(
    "/realizar-conciliacion-automatica-todos",
    response_model=ConciliacionAutomaticaResponseDTO,
    summary="Ejecutar conciliación automática para todos los tenants",
    description="Ejecuta conciliación automática para todos los tenants activos. Requiere Internal API Key."
)
async def realizar_conciliacion_automatica_todos(
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    """
    Ejecuta conciliación automática para todos los tenants activos.
    
    **Requiere:** Internal API Key en el header `X-Internal-API-Key`
    
    **Retorna:**
    - Total de tenants procesados
    - Total exitosos
    - Total fallidos
    - Lista de resultados por tenant con:
      - tenant_id
      - fecha_conciliacion
      - tipo_conciliacion (Automatica)
      - version_sat
      - rfcs_procesados
      - coincidencias
      - estado
      - historial_id
    """
    try:
        logger.info("🚀 Iniciando conciliación automática para todos los tenants")
        
        service = service_factory.create_conciliacion_service()
        resultado = service.realizar_conciliacion_todos_tenants(db)
        
        return ConciliacionAutomaticaResponseDTO(
            total_tenants=resultado["total_tenants"],
            total_procesados=resultado["total_procesados"],
            total_exitosos=resultado["total_exitosos"],
            total_fallidos=resultado["total_fallidos"],
            resultados=resultado["resultados"]
        )
        
    except Exception as e:
        logger.error(f"Error ejecutando conciliación automática para todos los tenants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando conciliación automática: {str(e)}"
        )


@router.get(
    "/conciliacion-detalles/{historial_id}",
    response_model=ConciliacionDetalleResponseDTO,
    summary="Obtener detalles de conciliación (requiere API Key)",
    description="Obtiene los detalles completos de una conciliación específica con todos los RFCs procesados"
)
async def obtener_detalles_conciliacion(
    historial_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene detalles completos de una conciliación.
    
    **Retorna:**
    - Información del historial (fecha, tipo, RFCs procesados, coincidencias, duración)
    - Lista completa de RFCs con sus estados
    - Resumen técnico con execution_id, status, processed y matched
    - Datos técnicos con execution_id, tenant_id, start_time, end_time, trigger_source, sat_version, rfc_processed, matched y status
    

    """
    try:
        # Validar UUID
        try:
            historial_uuid = UUID(historial_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="historial_id debe ser un UUID válido"
            )
        
        service = service_factory.create_conciliacion_service()
        resultado = service.obtener_detalles_conciliacion(db, current_tenant.id, historial_uuid)
        
        return ConciliacionDetalleResponseDTO(**resultado)
        
    except ValueError as e:
        # Conciliación no encontrada o no pertenece al tenant
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error obteniendo detalles de conciliación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo detalles de conciliación: {str(e)}"
        )


@router.get(
    "/conciliacion-detalles/{historial_id}/descargar-pdf",
    summary="Descargar PDF de conciliación (requiere API Key)",
    description="Genera y descarga un PDF con el reporte completo de la conciliación",
    response_class=StreamingResponse
)
async def descargar_pdf_conciliacion(
    historial_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Descarga un PDF con el reporte completo de la conciliación.
    
    **Incluye:**
    - Métricas (RFCs procesados, coincidencias, sin coincidencias, duración)
    - Resultados destacados (RFCs con coincidencias)
    - Resumen técnico
    """
    try:
        # Validar UUID
        try:
            historial_uuid = UUID(historial_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="historial_id debe ser un UUID válido"
            )
        
        # Obtener datos y generar PDF
        reporte_service = ReporteService()
        datos = reporte_service.obtener_datos_reporte(db, current_tenant.id, historial_uuid)
        pdf_buffer = reporte_service.generar_pdf(datos)
        
        # Preparar nombre del archivo
        fecha_str = datos["historial"]["fecha_conciliacion"].strftime("%Y%m%d")
        filename = f"conciliacion_{fecha_str}_{historial_id[:8]}.pdf"
        
        # Usar Response directamente para forzar descarga
        from fastapi import Response
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache"
        }
        
        pdf_content = pdf_buffer.read()
        pdf_buffer.close()
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers=headers
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generando PDF de conciliación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}"
        )


@router.get(
    "/conciliacion-detalles/{historial_id}/descargar-csv",
    summary="Descargar CSV de conciliación (requiere API Key)",
    description="Genera y descarga un CSV con el reporte completo de la conciliación",
    response_class=StreamingResponse
)
async def descargar_csv_conciliacion(
    historial_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Descarga un CSV con el reporte completo de la conciliación.
    
    **Incluye:**
    - Métricas (RFCs procesados, coincidencias, sin coincidencias, duración)
    - Lista completa de RFCs con sus estados y resultados
    - Resumen técnico
    """
    try:
        # Validar UUID
        try:
            historial_uuid = UUID(historial_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="historial_id debe ser un UUID válido"
            )
        
        # Obtener datos y generar CSV
        reporte_service = ReporteService()
        datos = reporte_service.obtener_datos_reporte(db, current_tenant.id, historial_uuid)
        csv_buffer = reporte_service.generar_csv(datos)
        
        # Preparar nombre del archivo
        fecha_str = datos["historial"]["fecha_conciliacion"].strftime("%Y%m%d")
        filename = f"conciliacion_{fecha_str}_{historial_id[:8]}.csv"
        
        # Usar Response directamente para forzar descarga (igual que PDF)
        from fastapi import Response
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/octet-stream",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache"
        }
        
        csv_content = csv_buffer.read()
        csv_buffer.close()
        
        return Response(
            content=csv_content,
            media_type="application/octet-stream",
            headers=headers
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generando CSV de conciliación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando CSV: {str(e)}"
        )


@router.get("/historial")
async def obtener_historial_conciliaciones(
    pagina: int = Query(1, ge=1, description="Número de página"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de conciliaciones del tenant (paginado).
    
    **Retorna:**
    - Lista de conciliaciones realizadas (20 por página)
    - Fecha, tipo, versión SAT, RFCs procesados, coincidencias, estado
    - Información de paginación
    - Métricas del mes actual: conciliaciones_mes, rfcs_mes, tiempo_promedio_ms
    """
    try:
        service = service_factory.create_conciliacion_service()
        resultado = service.obtener_historial_conciliaciones_paginado(
            db, current_tenant.id, pagina, 20  # Fijo a 20 por página
        )
        
        return {
            "historial": resultado["historial"],
            "total": resultado["total"],
            "pagina": resultado["pagina"],
            "por_pagina": resultado["por_pagina"],
            "total_paginas": resultado["total_paginas"],
            "conciliaciones_mes": resultado["conciliaciones_mes"],
            "rfcs_mes": resultado["rfcs_mes"],
            "tiempo_promedio_ms": resultado["tiempo_promedio_ms"]
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de conciliaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo historial: {str(e)}"
        )


@router.get("/ultima-conciliacion")
async def obtener_ultima_conciliacion_power_query(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene la última conciliación en formato para Power Query.
    
    **Formato:**
    - Resultado general con: conciliacion_id, fecha_conciliacion, tipo_conciliacion, version_sat
    - Subrama "rfcs" con array de RFCs: rfc, estado, resultado
    - Compatible con Power Query / Power BI
    
    **Retorna:**
    - Objeto con resultado general y subrama de RFCs
    """
    try:
        service = service_factory.create_conciliacion_service()
        datos = service.obtener_ultima_conciliacion_power_query(db, current_tenant.id)
        
        if not datos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró ninguna conciliación para este tenant"
            )
        
        return datos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo última conciliación para Power Query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo última conciliación: {str(e)}"
        )


@router.delete("/proveedores/{rfc}")
async def eliminar_proveedor(
    rfc: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Elimina un proveedor del tenant por RFC.
    
    **Parámetros:**
    - **rfc**: RFC del proveedor a eliminar (12 o 13 caracteres)
    """
    try:
        # Validar formato de RFC
        rfc = rfc.upper().strip()
        if len(rfc) not in [12, 13]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFC inválido. Debe tener 12 o 13 caracteres"
            )
        
        service = service_factory.create_conciliacion_service()
        eliminado = service.eliminar_proveedor(db, current_tenant.id, rfc)
        
        if not eliminado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proveedor con RFC {rfc} no encontrado"
            )
        
        return {"message": f"Proveedor {rfc} eliminado correctamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando proveedor {rfc}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando proveedor: {str(e)}"
        )


@router.get(
    "/excedentes-disponibles",
    response_model=ExcedentesDisponiblesResponseDTO,
    summary="Listar todos los RFCs excedentes",
    description="Obtiene todos los RFCs excedentes, incluyendo los pagados y no pagados"
)
async def listar_excedentes_disponibles(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Lista todos los RFCs excedentes ACTIVOS, mostrando tanto los pagados como los no pagados.
    
    Los excedentes son los RFCs activos que están fuera del límite del plan.
    Por ejemplo, si el límite es 25, muestra los RFCs activos en las posiciones 26, 27, 28, etc.
    
    **Retorna:**
    - Lista completa de RFCs excedentes activos (pagados y no pagados)
    - Campo 'pagado' indicando el estado de cada RFC
    - Precio unitario por RFC
    - Total si se pagan todos los disponibles
    """
    try:

        # Subconsulta: RFCs pagados
        rfcs_pagados_subq = select(
            func.unnest(OrdenPagoExcedente.rfcs)
        ).filter(
            and_(
                OrdenPagoExcedente.tenant_id == current_tenant.id,
                OrdenPagoExcedente.estado == "pagado"
            )
        ).scalar_subquery()
        
        # Obtener límite del plan directamente del tenant cargado
        limite_rfcs = current_tenant.plan.limite_proveedores if current_tenant.plan else 0
        
        # : Obtener excedentes con información de si están pagados
        
        excedentes_query = db.query(
            TenantProveedor.rfc,
            func.row_number().over(order_by=TenantProveedor.created_at.asc()).label('orden'),
            func.coalesce(
                TenantProveedor.rfc.in_(select(rfcs_pagados_subq).distinct()),
                False
            ).label('pagado')
        ).filter(
            TenantProveedor.tenant_id == current_tenant.id,
            TenantProveedor.activo == True
        ).order_by(
            TenantProveedor.created_at.asc()
        ).offset(limite_rfcs).all()
        
        # Construir respuesta
        excedentes_disponibles = [
            {
                "rfc": rfc,
                "orden": idx,
                "pagado": pagado
            }
            for idx, (rfc, orden, pagado) in enumerate(excedentes_query, start=1)
        ]
        
        return ExcedentesDisponiblesResponseDTO(
            excedentes=excedentes_disponibles
        )
        
    except Exception as e:
        logger.error(f"Error listando excedentes disponibles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo excedentes disponibles: {str(e)}"
        )


@router.post(
    "/crear-orden-excedentes",
    response_model=CrearOrdenExcedenteResponseDTO,
    summary="Crear orden de pago para RFCs excedentes",
    description="Crea una orden de pago en Stripe para conciliar RFCs específicos"
)
async def crear_orden_excedentes(
    request: CrearOrdenExcedenteRequestDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Crea una orden de pago para RFCs excedentes seleccionados.
    
    **Body:**
    - `rfcs`: Lista de RFCs a pagar (mínimo 1)
    
    **Retorna:**
    - ID de la orden
    - URL de checkout de Stripe
    - Información del pago
    """
    try:
        # Validar RFCs
        if not request.rfcs or len(request.rfcs) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe seleccionar al menos un RFC"
            )
        
        # Obtener servicios y repositorios
        tenant_service = service_factory.create_tenant_service()
        conciliacion_service = service_factory.create_conciliacion_service()
        orden_repo = OrdenPagoRepository()
        stripe_service = StripeService()
        
        # Obtener límite del plan
        usage_stats = tenant_service.get_tenant_usage(db, current_tenant.id)
        limite_rfcs = usage_stats.get('limite_rfcs', 0)
        
        # Obtener RFCs excedentes
        proveedores_excedentes = conciliacion_service.tenant_proveedor_repository.get_by_tenant_excedentes(
            db, current_tenant.id, limite_rfcs
        )
        
        rfcs_excedentes_disponibles = [p.rfc for p in proveedores_excedentes]
        
        # Validar que los RFCs solicitados estén en excedentes
        rfcs_solicitados = [rfc.upper().strip() for rfc in request.rfcs]
        rfcs_invalidos = [rfc for rfc in rfcs_solicitados if rfc not in rfcs_excedentes_disponibles]
        
        if rfcs_invalidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Los siguientes RFCs no están en excedentes: {', '.join(rfcs_invalidos)}"
            )
        
        # Verificar que no hayan sido pagados ya
        rfcs_pagados = orden_repo.obtener_rfcs_pagados(db, current_tenant.id)
        rfcs_ya_pagados = [rfc for rfc in rfcs_solicitados if rfc in rfcs_pagados]
        
        if rfcs_ya_pagados:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Los siguientes RFCs ya fueron pagados: {', '.join(rfcs_ya_pagados)}"
            )
        
        # Obtener precio del producto en Stripe
        cantidad_rfcs = len(rfcs_solicitados)
        try:
            precio_obj = stripe.Price.retrieve(settings.STRIPE_PRICE_ID)
            precio_unitario = precio_obj.unit_amount / 100
        except Exception as e:
            logger.warning(f"Error obteniendo precio de Stripe, usando default: {e}")
            precio_unitario = 10.00
        
        monto_total = cantidad_rfcs * precio_unitario
        
        # Crear orden en BD
        orden = orden_repo.crear_orden(
            session=db,
            tenant_id=current_tenant.id,
            rfcs=rfcs_solicitados,
            monto_total=monto_total,
            precio_unitario=precio_unitario
        )
        
        # Crear checkout session en Stripe
        checkout_info = stripe_service.crear_checkout_session(
            orden_id=orden.id,
            cantidad_rfcs=cantidad_rfcs,
            monto_total=monto_total,
            tenant_email=None  # Puedes agregar email del tenant si lo tienes
        )
        
        # Actualizar orden con info de Stripe
        orden_repo.actualizar_stripe_info(
            session=db,
            orden_id=orden.id,
            checkout_session_id=checkout_info['session_id'],
            payment_intent_id=checkout_info.get('payment_intent')
        )
        
        db.commit()
        
        return CrearOrdenExcedenteResponseDTO(
            orden_id=str(orden.id),
            cantidad_rfcs=cantidad_rfcs,
            monto_total=float(monto_total),
            precio_unitario=float(precio_unitario),
            stripe_checkout_url=checkout_info['url'],
            expira_at=orden.expira_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando orden de pago: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando orden de pago: {str(e)}"
        )


@router.get(
    "/orden-excedentes/{orden_id}",
    response_model=OrdenPagoExcedenteResponseDTO,
    summary="Consultar estado de orden de pago",
    description="Obtiene el estado actual de una orden de pago de excedentes"
)
async def consultar_orden_excedentes(
    orden_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Consulta el estado de una orden de pago.
    
    **Path Parameters:**
    - `orden_id`: UUID de la orden
    
    **Retorna:**
    - Estado de la orden
    - RFCs incluidos
    - Estado de conciliación
    """
    try:
        # Validar UUID
        try:
            orden_uuid = UUID(orden_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="orden_id debe ser un UUID válido"
            )
        
        # Obtener orden
        orden_repo = OrdenPagoRepository()
        orden = orden_repo.obtener_por_id(db, orden_uuid, current_tenant.id)
        
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orden {orden_id} no encontrada"
            )
        
        return OrdenPagoExcedenteResponseDTO(
            orden_id=str(orden.id),
            estado=orden.estado,
            rfcs=orden.rfcs,
            cantidad_rfcs=orden.cantidad_rfcs,
            monto_total=float(orden.monto_total),
            precio_unitario=float(orden.precio_unitario),
            conciliado=orden.conciliado,
            conciliacion_id=str(orden.conciliacion_id) if orden.conciliacion_id else None,
            created_at=orden.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            pagado_at=orden.pagado_at.strftime("%Y-%m-%d %H:%M:%S") if orden.pagado_at else None,
            expira_at=orden.expira_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consultando orden: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando orden: {str(e)}"
        )


@router.get(
    "/rfcs/dashboard",
    response_model=RFCDashboardResponseDTO,
    summary="Dashboard de RFCs",
    description="Obtiene estadísticas completas y lista detallada de RFCs del tenant (paginado, 20 por página)"
)
async def obtener_dashboard_rfcs(
    pagina: int = Query(1, ge=1, description="Número de página"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene el dashboard completo de RFCs del tenant (paginado).
    
    **Retorna:**
    - Número total de RFCs
    - Número de RFCs activos
    - Número de RFCs inactivos
    - Número de RFCs con alerta (Definitivo)
    - Fecha de última conciliación (solo fecha: día, mes, año)
    - Lista paginada de RFCs (20 por página) con:
      - RFC
      - Razón social/Nombre contribuyente
      - Estado SAT
      - Estado operativo (activo/inactivo)
      - Grupo
      - Fecha última actualización (solo fecha: día, mes, año)
    - Información de paginación (total, pagina, por_pagina, total_paginas)
    """
    try:
        service = service_factory.create_conciliacion_service()
        resultado = service.obtener_dashboard_rfcs(db, current_tenant.id, pagina, 20)
        
        # Convertir lista de diccionarios a DTOs
        from app.dto.rfc_dto import RFCItemDTO
        rfcs_dto = [
            RFCItemDTO(**rfc_data) for rfc_data in resultado["rfcs"]
        ]
        
        return RFCDashboardResponseDTO(
            total_rfcs=resultado["total_rfcs"],
            rfcs_activos=resultado["rfcs_activos"],
            rfcs_inactivos=resultado["rfcs_inactivos"],
            rfcs_con_alerta=resultado["rfcs_con_alerta"],
            fecha_ultima_conciliacion=resultado["fecha_ultima_conciliacion"],
            rfcs=rfcs_dto,
            total=resultado["total"],
            pagina=resultado["pagina"],
            por_pagina=resultado["por_pagina"],
            total_paginas=resultado["total_paginas"]
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo dashboard de RFCs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo dashboard de RFCs: {str(e)}"
        )


@router.put(
    "/rfcs/{rfc}/estado",
    response_model=RFCUpdateResponseDTO,
    summary="Activar/Desactivar RFC",
    description="Activa o desactiva un RFC del tenant"
)
async def actualizar_estado_rfc(
    rfc: str,
    request: ActivarRFCRequestDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Activa o desactiva un RFC del tenant.
    
    **Parámetros:**
    - rfc: RFC a actualizar
    - activo: True para activar, False para desactivar
    
    **Retorna:**
    - RFC actualizado
    - Estado operativo actualizado
    - Grupo (si existe)
    - Mensaje de confirmación
    """
    try:
        service = service_factory.create_conciliacion_service()
        resultado = service.actualizar_estado_operativo_rfc(
            db, current_tenant.id, rfc, request.activo
        )
        
        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RFC {rfc} no encontrado para este tenant"
            )
        
        return RFCUpdateResponseDTO(
            rfc=resultado["rfc"],
            activo=resultado["activo"],
            grupo=resultado["grupo"],
            mensaje=resultado["mensaje"]
        )
        
    except HTTPException:
        raise
    except ValueError as ve:
        # Error de validación (límite de burst sobrepasado)
        logger.warning(f"Validación fallida al actualizar RFC {rfc}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error actualizando estado del RFC {rfc}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando estado del RFC: {str(e)}"
        )


@router.put(
    "/rfcs/{rfc}/grupo",
    response_model=RFCUpdateResponseDTO,
    summary="Asignar RFC a grupo",
    description="Asigna un RFC a un grupo o elimina su asignación"
)
async def asignar_grupo_rfc(
    rfc: str,
    request: AsignarGrupoRequestDTO,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Asigna un RFC a un grupo o elimina su asignación.
    
    **Parámetros:**
    - rfc: RFC a actualizar
    - grupo: Nombre del grupo (None o cadena vacía para eliminar grupo)
    
    **Retorna:**
    - RFC actualizado
    - Estado operativo
    - Grupo asignado (o None si se eliminó)
    - Mensaje de confirmación
    """
    try:
        service = service_factory.create_conciliacion_service()
        grupo_value = request.grupo.strip() if request.grupo and request.grupo.strip() else None
        resultado = service.actualizar_grupo_rfc(
            db, current_tenant.id, rfc, grupo_value
        )
        
        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RFC {rfc} no encontrado para este tenant"
            )
        
        return RFCUpdateResponseDTO(
            rfc=resultado["rfc"],
            activo=resultado["activo"],
            grupo=resultado["grupo"],
            mensaje=resultado["mensaje"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error asignando grupo al RFC {rfc}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error asignando grupo al RFC: {str(e)}"
        )


@router.get(
    "/grupos",
    response_model=GruposListResponseDTO,
    summary="Listar grupos del tenant",
    description="Obtiene todos los nombres de los grupos creados por el tenant"
)
async def listar_grupos(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Lista todos los nombres de los grupos creados por el tenant.
    
    **Retorna:**
    - Lista de nombres de grupos (solo activos)
    - Total de grupos
    """
    try:
        from app.repositories.grupo_repository import GrupoRepository
        
        grupo_repo = GrupoRepository()
        grupos = grupo_repo.get_by_tenant(db, current_tenant.id)
        
        # Extraer solo los nombres
        nombres_grupos = [grupo.nombre for grupo in grupos]
        
        return GruposListResponseDTO(
            grupos=nombres_grupos,
            total=len(nombres_grupos)
        )
        
    except Exception as e:
        logger.error(f"Error listando grupos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo grupos: {str(e)}"
        )


