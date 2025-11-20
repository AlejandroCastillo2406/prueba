"""
Rutas para carga de archivos SAT
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.factories.service_factory import service_factory
from app.services.sqs_service import sqs_service

router = APIRouter()


@router.post("/actualizar-sat")
async def actualizar_sat(
    db: Session = Depends(get_db)
):
    """
    Actualiza la lista del SAT desde la fuente oficial.
    
    Si se detecta una nueva versión, después de actualizar la BD,
    se publica un mensaje a SQS para ejecutar conciliaciones automáticas
    para todos los tenants activos.
    """
    try:
        service = service_factory.create_sat_service()
        resultado = service.update_database(db, force=True)
        
        # Verificar si el procesamiento fue exitoso
        if not resultado.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error actualizando lista del SAT"
            )
            
        # Si se detectó una nueva versión, publicar mensaje a SQS
        if resultado.get("nueva_version"):
            fecha_version = resultado.get("fecha_version")
            total_registros = resultado.get("total_registros")
            
            logger.info(f" Nueva versión detectada: {fecha_version}")
            logger.info(" Publicando mensaje a SQS para ejecutar conciliaciones automáticas...")
            
            # Publicar mensaje a SQS
            sqs_success = sqs_service.publish_nueva_version_sat(
                fecha_version=fecha_version,
                total_registros=total_registros
            )
            
            if sqs_success:
                logger.success("✅ Mensaje publicado exitosamente a SQS")
                return {
                    "message": "Lista del SAT actualizada exitosamente",
                    "status": "success",
                    "nueva_version": True,
                    "fecha_version": fecha_version,
                    "sqs_message_sent": True,
                    "total_registros": total_registros
                }
            else:
                # Aunque falle SQS, la actualización de BD fue exitosa
                logger.warning("  Actualización de BD exitosa, pero falló al publicar mensaje a SQS")
                return {
                    "message": "Lista del SAT actualizada exitosamente, pero falló al notificar SQS",
                    "status": "success",
                    "nueva_version": True,
                    "fecha_version": fecha_version,
                    "sqs_message_sent": False,
                    "total_registros": total_registros
                }
        else:
            # No hay nueva versión, solo se verificó
            logger.info(" No se detectó nueva versión del SAT")
            return {
                "message": "Lista del SAT verificada (sin cambios)",
                "status": "success",
                "nueva_version": False,
                "fecha_version": resultado.get("fecha_version"),
                "sqs_message_sent": False
            }
            
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error actualizando SAT: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando SAT: {str(e)}"
        )


@router.get("/estadisticas")
async def obtener_estadisticas_sat(
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas de la lista del SAT
    """
    try:
        service = service_factory.create_sat_service()
        stats = service.get_stats(db)
        
        return {
            "success": True,
            "data": stats,
            "message": "Estadísticas obtenidas exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )
