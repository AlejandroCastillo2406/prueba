"""
Rutas para operaciones con el DOF (Diario Oficial de la Federación)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime
from loguru import logger
from typing import Optional

from app.core.database import get_db
from app.core.timezone import get_mexico_time_naive
from app.dto.dof_dto import (
    ProcesarDOFRequestDTO,
    ProcesarDOFResponseDTO,
    ErrorDOFDTO
)
from app.services.dof_service import DOFService


router = APIRouter()


@router.post("/procesar", response_model=ProcesarDOFResponseDTO)
async def procesar_dof(
    request: Optional[ProcesarDOFRequestDTO] = Body(None, description="Body opcional. Si no se envía, se usa la fecha actual de CDMX"),
    db: Session = Depends(get_db)
):
    """
    Procesa el Diario Oficial de la Federación para la fecha actual de CDMX,
    extrayendo artículos relacionados con el artículo 69-B del Código Fiscal.
    
    **Endpoint público - No requiere autenticación**
    
    **Uso:**
    - Sin body: Procesa el DOF de la fecha actual de CDMX automáticamente
    - Con fecha opcional: Procesa el DOF de la fecha especificada
    
    **Ejemplos de uso:**
    
    1. Sin parámetros (usa fecha actual de CDMX):
    ```bash
    POST /api/v1/dof/procesar
    ```
    
    2. Con fecha opcional:
    ```json
    {
      "fecha": "2025-10-10"
    }
    ```
    
    3. Con body vacío (también usa fecha actual):
    ```json
    {}
    ```
    
    **Nota:** Si los artículos ya fueron procesados para esa fecha, no se duplican.
    Si todos los artículos ya fueron procesados, el endpoint retorna un mensaje indicándolo.
    """
    try:
        # Obtener fecha: usar la proporcionada o la fecha actual de CDMX
        if request and request.fecha:
            try:
                fecha_procesar = datetime.strptime(request.fecha, "%Y-%m-%d").date()
                logger.info(f"Usando fecha proporcionada: {fecha_procesar}")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Formato de fecha inválido. Use YYYY-MM-DD"
                )
        else:
            # Usar fecha actual de CDMX
            fecha_actual_mexico = get_mexico_time_naive()
            fecha_procesar = fecha_actual_mexico.date()
            logger.info(f"Fecha actual de CDMX: {fecha_procesar}")
            
        
        # Procesar DOF
        service = DOFService()
        resultado = service.procesar_dof_fecha(db, fecha_procesar)
        
        # Convertir errores a DTOs
        errores_dto = [
            ErrorDOFDTO(oficio=error['oficio'], error=error['error'])
            for error in resultado.get('errores', [])
        ]
        
        return ProcesarDOFResponseDTO(
            fecha=resultado['fecha'],
            articulos_encontrados=resultado['articulos_encontrados'],
            articulos_nuevos=resultado['articulos_nuevos'],
            articulos_existentes=resultado['articulos_existentes'],
            articulos_procesados=resultado['articulos_procesados'],
            errores=errores_dto
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando DOF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando DOF: {str(e)}"
        )

