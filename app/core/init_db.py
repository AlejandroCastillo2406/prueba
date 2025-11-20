"""
Script para inicializar la base de datos
Crea las tablas y opcionalmente carga datos iniciales
"""
from loguru import logger
from app.core.database import init_db, get_db
from app.services.sat_service import sat_service


def initialize_database():
    """Inicializa la base de datos y carga datos iniciales"""
    logger.info("Inicializando base de datos con sistema de cifrado...")
    
    try:
        # Crear tablas
        init_db()
        logger.success("Tablas creadas exitosamente")
        
        # Cargar lista del SAT
        logger.info("Cargando lista del SAT...")
        db = next(get_db())
        
        resultado = sat_service.update_database(db, force=True)
        
        if resultado.get("success"):
            stats = sat_service.get_stats(db)
            logger.success(f"Base de datos inicializada con {stats['total']} proveedores")
            logger.info(f"Definitivos: {stats['definitivos']}")
            logger.info(f"Desvirtuados: {stats['desvirtuados']}")
            logger.info(f"Presuntos: {stats['presuntos']}")
            logger.info(f"Sentencias Favorables: {stats['sentencias_favorables']}")
            if resultado.get("nueva_version"):
                logger.info(f"✅ Nueva versión del SAT detectada: {resultado.get('fecha_version')}")
        else:
            logger.error("Error al cargar lista del SAT")
        
        db.close()
        
        logger.info("Sistema de cifrado AxFiiS inicializado correctamente")
        logger.info("Tenants pueden registrarse en: /api/v1/tenants/")
        logger.info("RFCs pueden agregarse en: /api/v1/rfcs/agregar")
        
    except Exception as e:
        logger.error(f"Error al inicializar base de datos: {e}")
        raise


if __name__ == "__main__":
    initialize_database()

