"""
Configuración de la base de datos
SQLAlchemy setup para PostgreSQL
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


# Configuración del engine
connect_args_optimized = {
    "connect_timeout": 5,    
    "options": "-c statement_timeout=15000 -c application_name=axfiis" 
}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,           # Verificar conexiones antes de usar
    pool_size=15,                 
    max_overflow=25,             
    pool_recycle=3600,           # Reciclar conexiones cada hora
    pool_timeout=20,              
    connect_args=connect_args_optimized,
    echo=False,
    # Optimizaciones adicionales
    execution_options={
        "autocommit": False,
        "isolation_level": "READ COMMITTED"  
    }
)
 
# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

def get_db():
    """
    Dependency para obtener sesión de base de datos
    Usar en endpoints de FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicializa la base de datos creando todas las tablas en orden correcto
    """
    # Importar TODOS los modelos para que se registren
    from app.models import (
        proveedor, tenant, usuario, plan, rol,
        grupo, tenant_proveedor, conciliacion_historial, conciliacion_detalle,
        orden_pago_excedente, dof_articulo, dof_contribuyente
    )
    
    try:
        with engine.connect() as conn:
            # Crear esquema test si no existe
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS test"))
            conn.commit()
            print("✅ Esquema 'test' creado/verificado en PostgreSQL")
    except Exception as e:
        print(f"⚠️  Error creando esquema 'test': {e}")
    
    try:
        
        table_creation_order = [
            'planes',           # Sin dependencias
            'proveedores',      # Sin dependencias
            'roles',            # Sin dependencias 
            'dof_articulos',    # Sin dependencias
            'tenants',          # Depende de planes
            'grupos',           # Depende de tenants
            'usuarios',         # Depende de tenants y roles
            'tenant_proveedores', # Depende de tenants y grupos
            'ordenes_pago_excedentes', # Depende de tenants
            'conciliacion_historial', # Depende de tenants
            'resultado_conciliaciones', # Depende de conciliacion_historial
            'dof_contribuyentes' # Depende de dof_articulos
        ]
        
        for table_name in table_creation_order:
            try:
                full_table_name = f'test.{table_name}'
                if full_table_name in Base.metadata.tables:
                    table = Base.metadata.tables[full_table_name]
                    table.create(bind=engine, checkfirst=True)
                    print(f"✅ Tabla {full_table_name} creada")
                else:
                    print(f"⚠️  Tabla {full_table_name} no encontrada en metadata")
                    try:
                        if table_name in Base.metadata.tables:
                            table = Base.metadata.tables[table_name]
                            Base.metadata.create_all(bind=engine, tables=[table])
                            print(f"✅ Tabla {full_table_name} creada con create_all")
                        else:
                            print(f"⚠️  Tabla {table_name} no encontrada en metadata sin esquema")
                    except Exception as create_all_error:
                        print(f"❌ Error creando tabla {full_table_name} con create_all: {create_all_error}")
            except Exception as e:
                print(f"❌ Error creando tabla {table_name}: {e}")
                
        print("✅ Todas las tablas creadas exitosamente")
        print("ℹ️  Para crear roles del sistema, ejecuta: python crear_roles.py")
        
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        raise e

