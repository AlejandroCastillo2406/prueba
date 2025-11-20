"""
Sistema de logs 
"""
import sys
import logging
from pathlib import Path
from loguru import logger
from app.core.config import settings

# Crear directorio de logs si no existe
log_dir = Path(settings.LOG_FILE).parent
log_dir.mkdir(parents=True, exist_ok=True)

# Constante para número máximo de líneas
MAX_LINES = 100


def file_sink_with_limit(log_file_path: Path):
    """
    Crea un sink personalizado que mantiene solo las últimas N líneas en el archivo
    """
    def sink(message):
        try:
            # Formatear el mensaje manualmente
            record = message.record
            time_str = record['time'].strftime('%Y-%m-%d %H:%M:%S')
            message_str = (
                f"{time_str} | "
                f"{record['level'].name:<8} | "
                f"{record['name']}:{record['function']}:{record['line']} | "
                f"{record['message']}\n"
            )
            
            # Asegurar que termine con newline
            if not message_str.endswith('\n'):
                message_str += '\n'
            
            # Leer líneas existentes si el archivo existe
            if log_file_path.exists():
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # Agregar la nueva línea
            lines.append(message_str)
            
            # Mantener solo las últimas MAX_LINES líneas
            if len(lines) > MAX_LINES:
                lines = lines[-MAX_LINES:]
            
            # Escribir de vuelta al archivo
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            # Si hay error escribiendo al archivo, no fallar silenciosamente
            print(f"Error escribiendo log: {e}", file=sys.stderr)
    
    return sink


def configure_logging():
    """
    Configura el sistema de logging de la aplicación
    Solo mantiene un archivo con las últimas 100 líneas
    """
    # Remover configuración por defecto
    logger.remove()
    
    # Formato para consola
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Formato para archivo
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}\n"
    )
    
    # Logger para consola
    logger.add(
        sys.stdout,
        format=console_format,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # Logger para archivo 
    log_file_path = Path(settings.LOG_FILE)
    
    # Crear sink personalizado
    custom_sink = file_sink_with_limit(log_file_path)
    
    logger.add(
        custom_sink,
        format=file_format,
        level=settings.LOG_LEVEL,
        backtrace=True,
        diagnose=True
    )
    
    # Silenciar logs de SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
    
    logger.info("Sistema de logging configurado correctamente ")


# Configurar al importar
configure_logging()

