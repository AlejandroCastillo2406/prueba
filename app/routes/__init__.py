"""
Rutas/Endpoints de la API
"""
from app.routes.tenant_routes import router as tenant_router
from app.routes.conciliacion_routes import router as conciliacion_router
from app.routes.health_routes import router as health_router
from app.routes.sat_loader_routes import router as sat_loader_router
from app.routes.sat_historico_routes import router as sat_historico_router

__all__ = [
    "tenant_router",
    "conciliacion_router", 
    "health_router",
    "sat_loader_router",
    "sat_historico_router"
]