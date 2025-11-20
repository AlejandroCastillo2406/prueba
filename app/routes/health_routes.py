"""
Rutas para health check
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.dto.sat_dto import HealthResponseDTO
from app.core.timezone import get_mexico_time_naive
from app.factories.service_factory import service_factory
from app.core.config import settings


router = APIRouter()


@router.get("/health", response_model=HealthResponseDTO, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    
    Verifica:
    - Estado de la API
    - Conexión a la base de datos
    - Estado de la lista del SAT
    - Última actualización
    """
    # Verificar base de datos
    try:
        service = service_factory.create_sat_service()
        stats = service.get_stats(db)
        db_status = "connected"
        sat_list_status = "updated" if stats.get('total', 0) > 0 else "empty"
        sat_list_last_update = stats.get('ultima_actualizacion')
        sat_list_total = stats.get('total', 0)
    except Exception as e:
        db_status = f"error: {str(e)}"
        sat_list_status = "unknown"
        sat_list_last_update = None
        sat_list_total = 0
    
    return HealthResponseDTO(
        status="healthy",
        timestamp=get_mexico_time_naive(),
        version=settings.APP_VERSION,
        database=db_status,
        sat_list_status=sat_list_status,
        sat_list_last_update=sat_list_last_update,
        sat_list_total_proveedores=sat_list_total
    )
