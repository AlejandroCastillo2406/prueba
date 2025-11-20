"""
Sistema de autenticación por API Key y JWT
"""
from typing import Optional
from fastapi import Header, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.factories.service_factory import service_factory
from app.services.auth_service import AuthService

# Security scheme para JWT
security_bearer = HTTPBearer()


async def get_current_tenant(
    x_api_key: str = Header(..., description="API Key del tenant"),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Obtiene el tenant actual autenticado mediante API Key
    
    Args:
        x_api_key: API Key en el header X-API-Key
        db: Sesión de base de datos
        
    Returns:
        Tenant autenticado
        
    Raises:
        HTTPException: Si la API Key es inválida o el tenant está inactivo
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida. Incluye el header X-API-Key en tu request."
        )
    
    service = service_factory.create_encryption_service()
    tenant = service.get_tenant_by_api_key(db, x_api_key)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o tenant inactivo"
        )
    
    return tenant


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Obtiene el usuario actual autenticado mediante JWT
    
    Args:
        credentials: Credenciales Bearer (JWT token)
        db: Sesión de base de datos
        
    Returns:
        Usuario autenticado
        
    Raises:
        HTTPException: Si el token es inválido o el usuario no existe/está inactivo
    """
    auth_service = AuthService(db)
    
    token = credentials.credentials
    usuario = auth_service.get_current_user(token)
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return usuario


async def get_current_active_user(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    """
    Verifica que el usuario actual esté activo
    
    Args:
        current_user: Usuario autenticado
        
    Returns:
        Usuario activo
        
    Raises:
        HTTPException: Si el usuario está inactivo o bloqueado
    """
    if not current_user.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo o bloqueado"
        )
    
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[Usuario]:
    """
    Obtiene el usuario si está autenticado, o None si no lo está
    Útil para endpoints que funcionan con o sin autenticación
    
    Args:
        credentials: Credenciales Bearer opcionales
        db: Sesión de base de datos
        
    Returns:
        Usuario autenticado o None
    """
    if not credentials:
        return None
    
    auth_service = AuthService(db)
    return auth_service.get_current_user(credentials.credentials)


async def verify_internal_api_key(
    x_internal_api_key: str = Header(..., description="Internal API Key para servicios internos (Lambda)")
) -> bool:
    """
    Verifica la API key interna para servicios internos (Lambda, etc.)
    
    Args:
        x_internal_api_key: Internal API Key en el header X-Internal-API-Key
        
    Returns:
        True si la API key es válida
        
    Raises:
        HTTPException: Si la API key es inválida
    """
    from app.core.config import settings
    
    if not x_internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal API Key requerida. Incluye el header X-Internal-API-Key en tu request."
        )
    
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal API Key inválida"
        )
    
    return True
