"""
Utilidades para manejo de zona horaria de México

IMPORTANTE: Los tokens JWT (en app/core/security.py) siguen usando UTC
porque es el estándar internacional y evita problemas de validación.

"""
from datetime import datetime, timezone, timedelta


# Zona horaria de México (CST/CDT - UTC-6)
MEXICO_TZ = timezone(timedelta(hours=-6))

# Meses en español
MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def get_mexico_time() -> datetime:
    """
    Obtiene la hora actual de México (UTC-6)
    
    Returns:
        datetime: Hora actual de México con zona horaria
    """
    return datetime.now(MEXICO_TZ)


def get_mexico_time_naive() -> datetime:
    """
    Obtiene la hora actual de México sin zona horaria (naive datetime)
    Útil para compatibilidad con código existente
    
    Returns:
        datetime: Hora actual de México sin timezone info
    """
    return datetime.now(MEXICO_TZ).replace(tzinfo=None)


def formatear_fecha_es(fecha: datetime) -> str:
    """
    Formatea una fecha en español con el formato: "DD de mes de YYYY"
    
    Args:
        fecha: Fecha a formatear
        
    Returns:
        str: Fecha formateada en español, ej: "28 de octubre de 2025"
    """
    dia = fecha.day
    mes = MESES_ES[fecha.month]
    año = fecha.year
    return f"{dia} de {mes} de {año}"

