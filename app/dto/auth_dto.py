"""
DTOs para autenticación de usuarios
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class RegisterRequest(BaseModel):
    """Request para registro de nuevo usuario"""
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, description="Password del usuario")
    nombre: str = Field(..., min_length=1, max_length=255, description="Nombre del usuario")
    apellidos: Optional[str] = Field(None, max_length=255, description="Apellidos del usuario")
    telefono: Optional[str] = Field(None, max_length=20, description="Teléfono del usuario")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "MiPassword123!",
                "nombre": "Juan",
                "apellidos": "Pérez López",
                "telefono": "+52 555 1234567"
            }
        }


class LoginRequest(BaseModel):
    """Request para login de usuario"""
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., description="Password del usuario")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "MiPassword123!"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Request para renovar access token"""
    refresh_token: str = Field(..., description="Refresh token válido")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class CreateUserRequest(BaseModel):
    """Request para crear un usuario por administrador del tenant"""
    email: EmailStr = Field(..., description="Email único del usuario")
    password: str = Field(..., min_length=8, description="Password del usuario")
    nombre: str = Field(..., min_length=1, max_length=255, description="Nombre del usuario")
    apellidos: Optional[str] = Field(None, max_length=255, description="Apellidos del usuario")
    telefono: Optional[str] = Field(None, max_length=20, description="Teléfono del usuario")
    rol_id: Optional[uuid.UUID] = Field(None, description="ID del rol a asignar (opcional, por defecto 'viewer')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "empleado@ejemplo.com",
                "password": "MiPassword123!",
                "nombre": "Juan",
                "apellidos": "Pérez López",
                "telefono": "+52 555 1234567",
                "rol_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ChangePasswordRequest(BaseModel):
    """Request para cambiar password"""
    old_password: str = Field(..., description="Password actual")
    new_password: str = Field(..., min_length=8, description="Nuevo password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "MiPasswordViejo123!",
                "new_password": "MiPasswordNuevo456!"
            }
        }


class TokenResponse(BaseModel):
    """Response con tokens de autenticación"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Segundos hasta expiración del access token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class UserResponse(BaseModel):
    """Response con datos del usuario"""
    id: uuid.UUID
    tenant_api_key: Optional[str] = Field(None, description="API Key del tenant")
    email: str
    nombre: str
    apellidos: Optional[str]
    telefono: Optional[str]
    rol_id: Optional[uuid.UUID]
    estado: str
    email_verificado: bool
    ultimo_acceso: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_api_key": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcd",
                "email": "usuario@ejemplo.com",
                "nombre": "Juan",
                "apellidos": "Pérez López",
                "telefono": "+52 555 1234567",
                "rol_id": "770e8400-e29b-41d4-a716-446655440000",
                "estado": "active",
                "email_verificado": True,
                "ultimo_acceso": "2025-10-27T10:30:00",
                "created_at": "2025-10-01T08:00:00"
            }
        }


class LoginResponse(BaseModel):
    """Response completa de login"""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "tenant_api_key": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcd",
                    "email": "usuario@ejemplo.com",
                    "nombre": "Juan",
                    "apellidos": "Pérez López",
                    "rol_id": "770e8400-e29b-41d4-a716-446655440000",
                    "estado": "active",
                    "email_verificado": True
                },
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class TokenPayload(BaseModel):
    """Payload decodificado del JWT token"""
    sub: str = Field(..., description="Subject (user_id)")
    email: str = Field(..., description="Email del usuario")
    tenant_id: str = Field(..., description="ID del tenant")
    type: str = Field(..., description="Tipo de token: access o refresh")
    exp: int = Field(..., description="Timestamp de expiración")
    iat: int = Field(..., description="Timestamp de emisión")

