"""
Aplicación principal FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import init_db, get_db
from app.core.timezone import get_mexico_time_naive
from app.factories.service_factory import service_factory
from app.routes import health_router, tenant_router, conciliacion_router, sat_loader_router, sat_historico_router
from app.routes.auth_routes import router as auth_router
from app.routes.roles_routes import router as roles_router
from app.routes.plan_routes import router as plan_router
from app.routes.webhook_routes import router as webhook_router
from app.routes.dof_routes import router as dof_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Se ejecuta al iniciar y cerrar el servidor
    """
    # Startup
    logger.info("=" * 80)
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Ambiente: {settings.ENVIRONMENT}")
    logger.info("=" * 80)
    
    # Inicializar base de datos
    try:
        init_db()
        logger.success("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar base de datos: {e}")
    
    # Actualizar lista del SAT
    try:
        logger.info("Verificando lista del SAT...")
        db = next(get_db())
        sat_service = service_factory.create_sat_service()
        resultado = sat_service.update_database(db)
        db.close()
        if resultado.get("success"):
            if resultado.get("nueva_version"):
                logger.info(f"✅ Nueva versión del SAT detectada: {resultado.get('fecha_version')}")
            logger.success("Lista del SAT verificada")
        else:
            logger.warning("No se pudo verificar la lista del SAT")
    except Exception as e:
        logger.error(f"Error al verificar lista del SAT: {e}")
    
    logger.info("Servidor listo para recibir peticiones")    
    yield
    
    # Shutdown
    logger.info("Cerrando aplicación...")
    logger.success("Aplicación cerrada correctamente")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API REST para verificación de proveedores en las listas del SAT (Artículo 69-B). "
        "Permite verificar el estado de proveedores, consultar historial de cambios y "
        "generar recomendaciones basadas en el riesgo fiscal."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para logging de todas las peticiones"""
    start_time = get_mexico_time_naive()
    
    # Log del request
    logger.info(f"→ {request.method} {request.url.path}")
    
    # Procesar request
    try:
        response = await call_next(request)
        
        # Calcular tiempo de procesamiento
        process_time = (get_mexico_time_naive() - start_time).total_seconds()
        
        # Log del response
        logger.info(
            f"← {request.method} {request.url.path} "
            f"[{response.status_code}] ({process_time:.3f}s)"
        )
        
        # Agregar headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        logger.error(f"Error procesando request: {e}")
        raise


# Handler global de excepciones
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejo global de excepciones no capturadas"""
    logger.error(f"Excepción no capturada: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Error interno del servidor",
            "detail": str(exc) if settings.DEBUG else "Ocurrió un error inesperado",
            "timestamp": get_mexico_time_naive().isoformat()
        }
    )


# Incluir routers
app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(
    auth_router,
    prefix="/api/v1",
    tags=["Autenticación"]
)

app.include_router(
    roles_router,
    prefix="/api/v1",
    tags=["Roles"]
)

app.include_router(
    tenant_router,
    prefix="/api/v1/tenants",
    tags=["Tenants"]
)

app.include_router(
    conciliacion_router,
    prefix="/api/v1/conciliacion",
    tags=["Conciliación"]
)

app.include_router(
    sat_loader_router,
    prefix="/api/v1/sat",
    tags=["SAT Loader"]
)

app.include_router(
    sat_historico_router,
    prefix="/api/v1/sat/historico",
    tags=["Lista SAT - Athena"]
)

app.include_router(
    plan_router,
    prefix="/api/v1",
    tags=["Planes"]
)

app.include_router(
    webhook_router,
    prefix="/api/v1/webhooks",
    tags=["Webhooks"]
)

app.include_router(
    dof_router,
    prefix="/api/v1/dof",
    tags=["DOF - Diario Oficial"]
)


# Endpoint raíz
@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint raíz de la API
    Proporciona información básica y enlaces útiles
    """
    return {
        "nombre": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "descripcion": "API de Verificación de Proveedores SAT (Art. 69-B)",
        "documentacion": f"http://{settings.HOST}:{settings.PORT}/docs",
        "health": f"http://{settings.HOST}:{settings.PORT}/api/v1/health", 
        "timestamp": get_mexico_time_naive().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )

