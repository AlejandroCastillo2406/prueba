"""
Rutas para consultas históricas del SAT usando Athena
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.dto.sat_dto import HistoricoRFCRequestDTO, HistoricoRFCResponseDTO, HistoricoRFCItemDTO
from app.factories.service_factory import service_factory
from app.models.tenant import Tenant

router = APIRouter()


async def verify_api_key(
    x_api_key: str = Header(..., description="API Key del tenant"),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Verifica la API key y retorna el tenant
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida"
        )
    
    encryption_service = service_factory.create_encryption_service()
    tenant = encryption_service.get_tenant_by_api_key(db, x_api_key)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o tenant inactivo"
        )
    
    return tenant


@router.get("/consultar-historico/{rfc}", response_model=HistoricoRFCResponseDTO)
async def obtener_historial_rfc(
    rfc: str,
    current_tenant: Tenant = Depends(verify_api_key)
):
    """
    Consulta el historial de cambios de un RFC en las listas del SAT usando Athena
    
    **Parámetros:**
    - **rfc**: RFC del proveedor a consultar (12 o 13 caracteres)
    
    **Retorna:**
    - Lista de cambios históricos con fechas y situaciones
    - Total de cambios detectados
    - Fecha de última actualización
    """
    try:
        # Validar formato de RFC
        rfc = rfc.upper().strip()
        if len(rfc) not in [12, 13]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFC inválido. Debe tener 12 o 13 caracteres"
            )
        
        # Usar el servicio de Athena para consultar historial
        from app.services.athena_service import AthenaService
        athena_service = AthenaService()
        
        # Consultar historial desde Athena
        historial_data = athena_service.get_historial_rfc(rfc)
        
        if not historial_data:
            return HistoricoRFCResponseDTO(historial=[])
        
        # Formatear respuesta con los campos exactos solicitados
        historial_items = []
        
        for item in historial_data:
            historial_items.append(HistoricoRFCItemDTO(
                rfc=item.get('rfc', rfc),
                nombre_contribuyente=item.get('nombre_contribuyente', 'No disponible'),
                situacion_contribuyente=item.get('situacion_contribuyente', 'No disponible'),
                version=item.get('version', 'No disponible')
            ))
        
        return HistoricoRFCResponseDTO(historial=historial_items)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consultando historial de RFC {rfc}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando historial: {str(e)}"
        )


