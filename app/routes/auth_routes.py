"""
Rutas de autenticación de usuarios
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_active_user
from app.models.usuario import Usuario
from app.services.auth_service import AuthService
from app.dto.auth_dto import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
    CreateUserRequest
)

router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description="Crea una cuenta de usuario nueva. Simple y directo."
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Registra un nuevo usuario en el sistema
    
    - **email**: Email único del usuario
    - **password**: Password (mínimo 8 caracteres, debe incluir mayúsculas, minúsculas, números y caracteres especiales)
    - **nombre**: Nombre del usuario
    - **apellidos**: Apellidos (opcional)
    - **telefono**: Teléfono (opcional)
    
    **Retorna:**
    - Datos del usuario creado
    
    Después del registro, usa `/auth/login` para obtener tus tokens de autenticación.
    """
    try:
        auth_service = AuthService(db)
        return auth_service.register_user(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar usuario: {str(e)}"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Iniciar sesión",
    description="Autentica un usuario y devuelve tokens JWT (access y refresh)"
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Inicia sesión de un usuario
    
    - **email**: Email del usuario
    - **password**: Password del usuario
    
    Retorna:
    - **user**: Datos del usuario autenticado
    - **access_token**: Token JWT para acceder a recursos protegidos (válido 30 minutos)
    - **refresh_token**: Token para renovar el access token (válido 7 días)
    - **token_type**: Tipo de token (bearer)
    - **expires_in**: Segundos hasta expiración del access token
    """
    try:
        auth_service = AuthService(db)
        login_response = auth_service.login(request)
        # Commit explícito al final (más eficiente)
        db.commit()
        return login_response
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar sesión: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
    description="Genera un nuevo access token usando un refresh token válido"
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Renueva el access token
    
    - **refresh_token**: Refresh token válido obtenido en el login
    
    Retorna un nuevo access token. El refresh token se mantiene igual.
    """
    try:
        auth_service = AuthService(db)
        token_response = auth_service.refresh_access_token(request.refresh_token)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al renovar token: {str(e)}"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario actual",
    description="Obtiene los datos del usuario autenticado actualmente"
)
async def get_me(
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Obtiene los datos del usuario actual
    
    Requiere autenticación con Bearer token en el header:
    ```
    Authorization: Bearer {access_token}
    ```
    """
    # Obtener api_key del tenant si existe
    tenant_api_key = None
    if current_user.tenant_id and current_user.tenant:
        tenant_api_key = current_user.tenant.api_key
    
    # Construir UserResponse con api_key del tenant
    return UserResponse(
        id=current_user.id,
        tenant_api_key=tenant_api_key,
        email=current_user.email,
        nombre=current_user.nombre,
        apellidos=current_user.apellidos,
        telefono=current_user.telefono,
        rol_id=current_user.rol_id,
        estado=current_user.estado,
        email_verificado=current_user.email_verificado,
        ultimo_acceso=current_user.ultimo_acceso,
        created_at=current_user.created_at
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Cambiar password",
    description="Permite al usuario cambiar su password"
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cambia el password del usuario actual
    
    - **old_password**: Password actual
    - **new_password**: Nuevo password (debe cumplir políticas de seguridad)
    
    Requiere autenticación con Bearer token.
    """
    try:
        auth_service = AuthService(db)
        auth_service.change_password(current_user.id, request)
        return {
            "message": "Password cambiado exitosamente",
            "success": True
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cambiar password: {str(e)}"
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión",
    description="Invalida el token actual "
)
async def logout(
    current_user: Usuario = Depends(get_current_user)
):
    """
    Cierra la sesión del usuario actual
    
    Nota: En una implementación JWT básica, el cierre de sesión se maneja en el cliente
    eliminando los tokens. Para una invalidación real, se requeriría una blacklist de tokens.
    
    Requiere autenticación con Bearer token.
    """
    return {
        "message": "Sesión cerrada exitosamente",
        "success": True,
        "user_id": str(current_user.id)
    }


@router.post(
    "/create-user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario para el tenant",
    description="Crea un nuevo usuario vinculado directamente al tenant del administrador con auditoría completa"
)
async def create_user(
    request: CreateUserRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo usuario para el tenant del administrador
    
    **Solo administradores y owners pueden crear usuarios.**
    El usuario se crea directamente vinculado al tenant del administrador.
    
    - **email**: Email único del usuario
    - **password**: Password del usuario (mínimo 8 caracteres, debe cumplir políticas de seguridad)
    - **nombre**: Nombre del usuario
    - **apellidos**: Apellidos (opcional)
    - **telefono**: Teléfono (opcional)
    - **rol_id**: ID del rol a asignar (opcional, por defecto 'viewer')
    
    **Validaciones:**
    - El administrador debe tener permisos para crear usuarios (admin/owner)
    - El tenant debe tener capacidad disponible según su plan
    - El email no debe estar en uso
    - Se registra auditoría (quién lo creó, cuándo)
    
    **Retorna:**
    - Datos del usuario creado con información de auditoría
    
    Requiere autenticación con Bearer token.
    """
    try:
        # Verificar que el usuario tenga un tenant
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes tener un tenant para crear usuarios"
            )
        
        # Verificar permisos
        if not current_user.puede_invitar_usuarios():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para crear usuarios. Solo administradores y owners pueden hacerlo."
            )
        
        auth_service = AuthService(db)
        return auth_service.create_user_for_tenant(
            request=request,
            tenant_id=current_user.tenant_id,
            created_by=current_user.id
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear usuario: {str(e)}"
        )

