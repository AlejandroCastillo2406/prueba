"""
Servicio de autenticación de usuarios
"""
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from app.models.usuario import Usuario
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.rol import Rol
from app.core.timezone import get_mexico_time_naive
from app.repositories.usuario_repository import UsuarioRepository
from app.dto.auth_dto import (
    RegisterRequest, 
    LoginRequest, 
    LoginResponse, 
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
    CreateUserRequest
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
    SecurityUtils
)
from app.core.config import settings
from app.core.logging import logger


class AuthService:
    """Servicio para gestión de autenticación"""
    
    def __init__(self, db: Session):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
    
    def register_user(self, request: RegisterRequest) -> UserResponse:
        """
        Registra un nuevo usuario
        
        Args:
            request: Datos del registro
            
        Returns:
            UserResponse con datos del usuario creado
            
        Raises:
            ValueError: Si el email ya existe o password es débil
        """
        # Validar que el email no exista
        if self.usuario_repo.email_exists(request.email):
            raise ValueError(f"El email {request.email} ya está registrado")
        
        # Validar fortaleza del password
        is_valid, error_msg = validate_password_strength(request.password)
        if not is_valid:
            raise ValueError(error_msg)
        
        try:
            # Hash del password con bcrypt
            password_hash = hash_password(request.password)
            
            # Crear usuario (sin tenant, sin rol)
            usuario = Usuario(
                tenant_id=None,  
                email=request.email.lower(),
                nombre=request.nombre,
                apellidos=request.apellidos,
                telefono=request.telefono,
                password_hash=password_hash,
                rol_id=None,  
                estado="active",
                email_verificado=False,
                activo=True,
                created_by=None
            )
            
            self.db.add(usuario)
            self.db.commit()
            self.db.refresh(usuario)
            
            logger.info(f"Usuario registrado exitosamente: {usuario.email} (ID: {usuario.id})")
            
            # Construir UserResponse (sin tenant_api_key porque no tiene tenant aún)
            return UserResponse(
                id=usuario.id,
                tenant_api_key=None,
                email=usuario.email,
                nombre=usuario.nombre,
                apellidos=usuario.apellidos,
                telefono=usuario.telefono,
                rol_id=usuario.rol_id,
                estado=usuario.estado,
                email_verificado=usuario.email_verificado,
                ultimo_acceso=usuario.ultimo_acceso,
                created_at=usuario.created_at
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al registrar usuario: {e}")
            raise ValueError(f"Error al crear la cuenta: {str(e)}")
    
    def login(self, request: LoginRequest) -> LoginResponse:
        """
        Autentica un usuario y genera tokens 
        
        Args:
            request: Credenciales de login
            
        Returns:
            LoginResponse con tokens y datos del usuario
            
        Raises:
            ValueError: Si las credenciales son inválidas o usuario bloqueado
        """
        # Query: obtener usuario con tenant api_key
        resultado = self.db.query(
            Usuario.id,
            Usuario.email,
            Usuario.nombre,
            Usuario.apellidos,
            Usuario.telefono,
            Usuario.password_hash,
            Usuario.activo,
            Usuario.estado,
            Usuario.tenant_id,
            Usuario.rol_id,
            Usuario.email_verificado,
            Usuario.ultimo_acceso,
            Usuario.created_at,
            Tenant.api_key
        ).outerjoin(
            Tenant, Usuario.tenant_id == Tenant.id
        ).filter(
            Usuario.email == request.email.lower()
        ).first()
        
        if not resultado:
            raise ValueError("Email o password incorrectos")
        
        # Extraer datos de la tupla
        (user_id, email, nombre, apellidos, telefono, password_hash, activo, estado, 
         tenant_id, rol_id, email_verificado, ultimo_acceso, created_at, tenant_api_key) = resultado
        
        # Verificar que el usuario esté activo (antes de verificar password para fallo rápido)
        if not activo or estado != "active":
            raise ValueError("Usuario bloqueado o inactivo. Contacte al administrador")
        
        # Verificar password 
        if not verify_password(request.password, password_hash):
            raise ValueError("Email o password incorrectos")
        
        # Pre-calcular valores para tokens 
        fecha_acceso = get_mexico_time_naive()
        tenant_id_str = str(tenant_id) if tenant_id else None
        user_id_str = str(user_id)
        
        # Generar tokens 
        token_data = {
            "sub": user_id_str,
            "email": email,
            "tenant_id": tenant_id_str
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": user_id_str})
        
        # Actualizar último acceso
        self.db.query(Usuario).filter(Usuario.id == user_id).update({
            "ultimo_acceso": fecha_acceso
        }, synchronize_session=False)
        
        # Construir UserResponse con api_key del tenant
        user_response = UserResponse(
            id=user_id,
            tenant_api_key=tenant_api_key,
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            telefono=telefono,
            rol_id=rol_id,
            estado=estado,
            email_verificado=email_verificado,
            ultimo_acceso=fecha_acceso,
            created_at=created_at
        )
        
        return LoginResponse(
            user=user_response,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Renueva el access token usando un refresh token válido
        
        Args:
            refresh_token: Refresh token JWT
            
        Returns:
            Nuevo access token
            
        Raises:
            ValueError: Si el refresh token es inválido
        """
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Refresh token inválido")
        
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Refresh token inválido")
        
        # Verificar que el usuario existe y está activo
        usuario = self.usuario_repo.get(uuid.UUID(user_id))
        if not usuario or not usuario.activo or usuario.estado != "active":
            raise ValueError("Usuario no encontrado o bloqueado")
        
        # Generar nuevo access token
        token_data = {
            "sub": str(usuario.id),
            "email": usuario.email,
            "tenant_id": str(usuario.tenant_id) if usuario.tenant_id else None
        }
        
        access_token = create_access_token(token_data)
        
        logger.info(f"Access token renovado para usuario: {usuario.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Se mantiene el mismo refresh token
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    def change_password(self, user_id: uuid.UUID, request: ChangePasswordRequest) -> bool:
        """
        Cambia el password de un usuario
        
        Args:
            user_id: ID del usuario
            request: Datos del cambio de password
            
        Returns:
            True si se cambió exitosamente
            
        Raises:
            ValueError: Si el password actual es incorrecto o el nuevo es débil
        """
        usuario = self.usuario_repo.get(user_id)
        if not usuario:
            raise ValueError("Usuario no encontrado")
        
        # Verificar password actual
        if not verify_password(request.old_password, usuario.password_hash):
            logger.warning(f"Intento de cambio de password con password actual incorrecto: {usuario.email}")
            raise ValueError("Password actual incorrecto")
        
        # Validar fortaleza del nuevo password
        is_valid, error_msg = validate_password_strength(request.new_password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Verificar que el nuevo password sea diferente
        if verify_password(request.new_password, usuario.password_hash):
            raise ValueError("El nuevo password debe ser diferente al actual")
        
        # Actualizar password
        new_password_hash = hash_password(request.new_password)
        self.usuario_repo.update_password(user_id, new_password_hash)
        
        logger.info(f"Password cambiado exitosamente para usuario: {usuario.email}")
        
        return True
    
    def create_user_for_tenant(self, request: CreateUserRequest, tenant_id: uuid.UUID, created_by: uuid.UUID) -> UserResponse:
        """
        Crea un nuevo usuario para un tenant (solo administradores)
        
        Args:
            request: Datos del usuario a crear
            tenant_id: ID del tenant al que se vinculará el usuario
            created_by: ID del usuario administrador que crea el usuario (auditoría)
            
        Returns:
            UserResponse con datos del usuario creado
            
        Raises:
            ValueError: Si el email ya existe, límite de usuarios alcanzado, o rol inválido
        """
        # Validar que el email no exista
        if self.usuario_repo.email_exists(request.email):
            raise ValueError(f"El email {request.email} ya está registrado")
        
        # Validar fortaleza del password
        is_valid, error_msg = validate_password_strength(request.password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Obtener tenant y verificar límite de usuarios del plan 
        from sqlalchemy.orm import joinedload
        tenant = self.db.query(Tenant).options(
            joinedload(Tenant.plan)
        ).filter(Tenant.id == tenant_id).first()
        
        if not tenant:
            raise ValueError("Tenant no encontrado")
        
        if tenant.plan:
            # Contar usuarios actuales del tenant (activos)
            usuarios_count = self.db.query(Usuario).filter(
                Usuario.tenant_id == tenant_id,
                Usuario.activo == True
            ).count()
            
            # Verificar límite de usuarios
            if not tenant.plan.puede_agregar_usuario(usuarios_count):
                limite_usuarios = tenant.plan.limite_usuarios if tenant.plan.limite_usuarios else "ilimitado"
                raise ValueError(
                    f"Límite de usuarios alcanzado. El plan permite {limite_usuarios} usuarios "
                    f"y ya tienes {usuarios_count} usuarios activos."
                )
        
        # Si se proporcionó un rol, verificar que existe
        rol_id = request.rol_id
        if rol_id:
            rol = self.db.query(Rol).filter(Rol.id == rol_id).first()
            if not rol:
                raise ValueError("El rol especificado no existe")
        else:
            # Asignar rol "viewer" por defecto
            rol_viewer = self.db.query(Rol).filter(Rol.nombre == "viewer").first()
            if not rol_viewer:
                raise ValueError("Rol 'viewer' no encontrado. Ejecuta: python crear_roles.py")
            rol_id = rol_viewer.id
        
        try:
            # Hash del password con bcrypt
            password_hash = hash_password(request.password)
            
            # Crear usuario vinculado al tenant con auditoría
            usuario = Usuario(
                tenant_id=tenant_id,
                email=request.email.lower(),
                nombre=request.nombre,
                apellidos=request.apellidos,
                telefono=request.telefono,
                password_hash=password_hash,
                rol_id=rol_id,
                estado="active",
                email_verificado=False,
                activo=True,
                created_by=created_by  # Auditoría: quién lo creó
            )
            
            self.db.add(usuario)
            self.db.commit()
            self.db.refresh(usuario)
            
            logger.info(
                f"Usuario {usuario.email} creado exitosamente para tenant {tenant_id} "
                f"por usuario {created_by} (rol_id: {rol_id})"
            )
            
            # Obtener api_key del tenant
            tenant_api_key = tenant.api_key if tenant else None
            
            # Construir UserResponse con api_key del tenant
            return UserResponse(
                id=usuario.id,
                tenant_api_key=tenant_api_key,
                email=usuario.email,
                nombre=usuario.nombre,
                apellidos=usuario.apellidos,
                telefono=usuario.telefono,
                rol_id=usuario.rol_id,
                estado=usuario.estado,
                email_verificado=usuario.email_verificado,
                ultimo_acceso=usuario.ultimo_acceso,
                created_at=usuario.created_at
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al crear usuario para tenant: {e}")
            raise ValueError(f"Error al crear el usuario: {str(e)}")
    
    def get_current_user(self, token: str) -> Optional[Usuario]:
        """
        Obtiene el usuario actual desde un access token
        
        Args:
            token: JWT access token
            
        Returns:
            Usuario o None si el token es inválido
        """
        payload = decode_token(token)
        
        if not payload or payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        usuario = self.usuario_repo.get(uuid.UUID(user_id))
        
        if not usuario or not usuario.activo or usuario.estado != "active":
            return None
        
        return usuario

